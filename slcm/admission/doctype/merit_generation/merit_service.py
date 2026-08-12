import frappe
import math
from frappe import _
from frappe.utils import now_datetime
from collections import defaultdict
from slcm.admission.doctype.seat_allocation.seat_allocation import get_applicant_categories, clear_category_cache

def _publish_allocation_progress(doc, percent, description, status="In Progress"):
    """
    Safely publishes progress to both the client websocket and Redis cache.
    """
    cycle = getattr(doc, "admission_cycle", None)
    campus = getattr(doc, "campus", None)
    program_level = getattr(doc, "program_level", None) or getattr(doc, "generation_type", None)
    program = getattr(doc, "program", None) or ""

    if not (cycle and campus and program_level):
        return

    # Redis Cache update for polling fallback
    cache_key = f"merit_generation_{cycle}_{campus}_{program_level}_{program}".replace(" ", "_")
    frappe.cache().set_value(cache_key, {
        "percent": percent,
        "status": status,
        "description": _(description),
        "current": int(percent),
        "total": 100
    }, expires_in_sec=300)

def _get_categorized_traits(applicant_id):
    """
    Categorizes applicant traits into Vertical, Horizontal, and Compartmental types.
    Returns: (verticals, horizontals, compartmental)
    """
    all_cats = get_applicant_categories(applicant_id)
    if not all_cats:
        return ([], [], [])
        
    cat_data = frappe.get_all("Admission Category", 
        filters={"name": ["in", all_cats]}, 
        fields=["name", "reservation_type"]
    )
    
    verticals = [c.name for c in cat_data if c.reservation_type == "Vertical"]
    horizontals = [c.name for c in cat_data if c.reservation_type == "Horizontal"]
    compartmental = [c.name for c in cat_data if c.reservation_type == "Compartmentalised Horizontal"]
    
    # Priority: If an applicant has a reserved vertical category, 'General' should be ignored
    if len(verticals) > 1 and "General" in verticals:
        verticals.remove("General")
    
    # Preserve order from all_cats if possible
    order = {name: i for i, name in enumerate(all_cats)}
    verticals.sort(key=lambda x: order.get(x, 99))
    horizontals.sort(key=lambda x: order.get(x, 99))
    compartmental.sort(key=lambda x: order.get(x, 99))
    
    return (verticals, horizontals, compartmental)

def _has_trait(applicant_id, trait_name, is_shortlist=False):
    """Checks if an applicant has a specific trait (exact match)."""
    cats = get_applicant_categories(applicant_id)
    return trait_name in (cats or [])


def calculate_merit_with_rule(applicant, rule):
    """
    Calculates total merit score for an applicant based on the given rule.
    Supports simple fields in Eligibility Result and averaging values from
    ug_degree_details and pg_degree_details child tables.
    """
    total_score = 0
    
    # Pre-fetch merit components for efficiency
    component_map = {}
    component_names = [row.component_type for row in rule.components if row.is_active]
    
    if component_names:
        components = frappe.get_all(
            "Merit Component",
            filters={"name": ["in", component_names]},
            fields=["name", "field_name", "multiplier"]
        )
        component_map = {c.name: c for c in components}

    for row in rule.components:
        if not row.is_active:
            continue

        comp_meta = component_map.get(row.component_type)
        if not comp_meta:
            frappe.logger().warning(f"Merit Component '{row.component_type}' not found.")
            continue

        field_name = comp_meta.field_name
        val = 0

        # Smart mapping for common field names to child tables
        resolved_table = None
        if field_name == "ug_cgpa" or field_name == "ug_degree_details":
            resolved_table = "ug_degree_details"
        elif field_name == "pg_cgpa" or field_name == "pg_degree_details":
            resolved_table = "pg_degree_details"

        if resolved_table:
            child_rows = applicant.get(resolved_table) or []
            if child_rows:
                scores = []
                for r in child_rows:
                    row_val = 0
                    if resolved_table == "ug_degree_details":
                        row_val = r.get("ug_cgpa") or r.get("percentage_cgpa_obtained") or 0
                    else:
                        row_val = r.get("pg_cgpa") or r.get("percentagecgpa_obtained") or 0
                    scores.append(float(row_val))
                
                if scores:
                    val = sum(scores) / len(scores)
        
        # Explicit dot notation fallback: table_field.column_name
        elif "." in field_name:
            table_field, child_field = field_name.split(".", 1)
            child_rows = applicant.get(table_field) or []
            if child_rows:
                scores = [getattr(r, child_field, 0) or 0 for r in child_rows]
                val = sum(scores) / len(scores)
        else:
            # Dynamic attribute lookup for main DocType fields
            val = getattr(applicant, field_name, 0) or 0

        score = val * (comp_meta.multiplier or 1.0)
        total_score += score * (row.weight / 100)

    return total_score


def _rank_applicants(applicant_rows, use_advanced_ranking=False, processing_stage="Part A Ranking"):
    """
    Applies overall and program ranking.
    If use_advanced_ranking=True, applies Standard Competition Ranking (1, 2, 2, 4).
    Final ranking order:
    1. Total Score descending
    2. Part B / Interview Score descending (for Final Allotment Stage)
    """
    def get_stable_key(x):
        """Used for list sorting based purely on merit scores without arbitrary tie-breakers."""
        score = float(getattr(x, "total_score", None) or x.get("total_score") or getattr(x, "entrance_score", None) or x.get("entrance_score") or getattr(x, "nlsat_part_a_score", None) or x.get("nlsat_part_a_score") or 0)
        score = round(score, 3)
        
        if processing_stage == "Part A Ranking":
            return (-score,)
        
        # Final Allotment ranking order:
        # 1. Total Score (Desc)
        # 2. Part B / Interview Score (Desc)
        part_b = float(
            getattr(x, "interview_score", None) or x.get("interview_score") or
            getattr(x, "et_part_b_total_marks_scored", None) or x.get("et_part_b_total_marks_scored") or
            getattr(x, "nlsat_part_b_score", None) or x.get("nlsat_part_b_score") or 0
        )
        part_b = round(part_b, 3)
        
        return (
            -score,
            -part_b
        )


    # Helper to check for same rank (ignores deterministic fallback)
    def is_same_rank(app1, app2):
        score1 = float(getattr(app1, "total_score", None) or app1.get("total_score") or getattr(app1, "entrance_score", None) or app1.get("entrance_score") or getattr(app1, "nlsat_part_a_score", None) or app1.get("nlsat_part_a_score") or 0)
        score2 = float(getattr(app2, "total_score", None) or app2.get("total_score") or getattr(app2, "entrance_score", None) or app2.get("entrance_score") or getattr(app2, "nlsat_part_a_score", None) or app2.get("nlsat_part_a_score") or 0)
        
        score1 = round(score1, 3)
        score2 = round(score2, 3)
        
        if processing_stage == "Part A Ranking":
            return score1 == score2
        
        part_b1 = float(
            getattr(app1, "interview_score", None) or app1.get("interview_score") or
            getattr(app1, "et_part_b_total_marks_scored", None) or app1.get("et_part_b_total_marks_scored") or
            getattr(app1, "nlsat_part_b_score", None) or app1.get("nlsat_part_b_score") or 0
        )
        part_b2 = float(
            getattr(app2, "interview_score", None) or app2.get("interview_score") or
            getattr(app2, "et_part_b_total_marks_scored", None) or app2.get("et_part_b_total_marks_scored") or
            getattr(app2, "nlsat_part_b_score", None) or app2.get("nlsat_part_b_score") or 0
        )
        
        part_b1 = round(part_b1, 3)
        part_b2 = round(part_b2, 3)
        
        return (score1 == score2) and (part_b1 == part_b2)

    # Separate rankable vs rejected candidates.
    # Reject candidate if candidate did NOT appear for Part B (part_b_not_appeared=True)
    # OR scored 0 or negative marks in Part B (part_b_score <= 0).
    rankable_applicants = []
    rejected_applicants = []

    for row in applicant_rows:
        part_b_not_appeared = getattr(row, "part_b_not_appeared", False) or (row.get("part_b_not_appeared") if isinstance(row, dict) else False)
        
        pb_val = getattr(row, "interview_score", None)
        if pb_val is None:
            pb_val = getattr(row, "et_part_b_total_marks_scored", None)
        if pb_val is None:
            pb_val = getattr(row, "nlsat_part_b_score", None)
        if pb_val is None and isinstance(row, dict):
            pb_val = row.get("interview_score") or row.get("et_part_b_total_marks_scored") or row.get("nlsat_part_b_score")
        part_b_score = float(pb_val or 0)
        
        status_val = getattr(row, "status", None) or getattr(row, "selection_status", None) or getattr(row, "shortlist_status", None) or ""
        
        if processing_stage in ["Final Allotment Ranking", "Part B Ranking"] and (part_b_not_appeared or part_b_score <= 0):
            setattr(row, "status", "Rejected")
            if hasattr(row, "shortlist_status"): setattr(row, "shortlist_status", "Rejected")
            if hasattr(row, "selection_status"): setattr(row, "selection_status", "Rejected")
            row.allocation_type = "Not Allocated"
            if hasattr(row, "remarks"):
                if part_b_not_appeared:
                    row.remarks = "Rejected: did not appear for Part B"
                else:
                    row.remarks = "Rejected: Part B marks are 0 or negative"
            rejected_applicants.append(row)
        elif status_val == "Rejected":
            rejected_applicants.append(row)
        else:
            rankable_applicants.append(row)

    # 1. Overall Rank (Only assigned to rankable applicants)
    rankable_applicants.sort(key=get_stable_key)
    
    current_rank = 1
    for i, row in enumerate(rankable_applicants):
        if i > 0:
            if not is_same_rank(row, rankable_applicants[i-1]):
                current_rank = i + 1
        row.overall_rank = current_rank
        if hasattr(row, "shortlist_rank"): row.shortlist_rank = current_rank if processing_stage == "Part A Ranking" else None
        if hasattr(row, "admission_rank"): row.admission_rank = current_rank if processing_stage == "Final Allotment Ranking" else None

    # Clear ranks for rejected applicants
    for row in rejected_applicants:
        row.overall_rank = 0
        row.category_rank = 0
        if hasattr(row, "shortlist_rank"): row.shortlist_rank = None
        if hasattr(row, "admission_rank"): row.admission_rank = None
        if hasattr(row, "part_a_rank"): row.part_a_rank = 0
        if hasattr(row, "part_b_rank"): row.part_b_rank = 0

    # 2. Category Rank (Within actual vertical category)
    category_groups = defaultdict(list)
    for row in rankable_applicants:
        cat = getattr(row, "actual_category", None) or getattr(row, "vertical_category", None) or "General"
        category_groups[cat].append(row)
            
    for group in category_groups.values():
        group.sort(key=get_stable_key)
        current_rank = 1
        for i, row in enumerate(group):
            if i > 0:
                if not is_same_rank(row, group[i-1]):
                    current_rank = i + 1
            row.category_rank = current_rank

    # Re-assemble applicant_rows with rankable candidates first, rejected at the end
    applicant_rows[:] = rankable_applicants + rejected_applicants

    # 3. Part A Rank Calculation (Only calculated during Part A Ranking stage; during Final Allotment stage, Part A rank is preserved from Shortlist)
    if processing_stage == "Part A Ranking":
        def get_part_a_score(x):
            score = float(
                getattr(x, "entrance_score", None) or (x.get("entrance_score") if isinstance(x, dict) else None) or
                getattr(x, "et_part_a_total_marks_scored", None) or (x.get("et_part_a_total_marks_scored") if isinstance(x, dict) else None) or
                getattr(x, "nlsat_part_a_score", None) or (x.get("nlsat_part_a_score") if isinstance(x, dict) else None) or 0
            )
            return round(score, 3)

        def get_part_a_key(x):
            return (-get_part_a_score(x),)

        sorted_by_pa = sorted(applicant_rows, key=get_part_a_key)
        current_pa_rank = 1
        for i, row in enumerate(sorted_by_pa):
            if i > 0:
                if get_part_a_score(row) != get_part_a_score(sorted_by_pa[i-1]):
                    current_pa_rank = i + 1
            setattr(row, "part_a_rank", current_pa_rank)
            if hasattr(row, "shortlist_rank"):
                setattr(row, "shortlist_rank", current_pa_rank)
    else:
        # Final Allotment stage: preserve original Part A rank carried over from Shortlist
        for row in applicant_rows:
            pa_rnk = getattr(row, "part_a_rank", None) or getattr(row, "shortlist_rank", None) or 0
            setattr(row, "part_a_rank", pa_rnk)

    # 4. Part B Rank Calculation
    def get_part_b_score(x):
        score = float(
            getattr(x, "interview_score", None) or (x.get("interview_score") if isinstance(x, dict) else None) or
            getattr(x, "et_part_b_total_marks_scored", None) or (x.get("et_part_b_total_marks_scored") if isinstance(x, dict) else None) or
            getattr(x, "nlsat_part_b_score", None) or (x.get("nlsat_part_b_score") if isinstance(x, dict) else None) or 0
        )
        return round(score, 3)

    def get_part_b_key(x):
        return (-get_part_b_score(x),)


    sorted_by_pb = sorted(applicant_rows, key=get_part_b_key)
    current_pb_rank = 1
    for i, row in enumerate(sorted_by_pb):
        if i > 0:
            if get_part_b_score(row) != get_part_b_score(sorted_by_pb[i-1]):
                current_pb_rank = i + 1
        setattr(row, "part_b_rank", current_pb_rank)

def generate_merit_for_level(cycle, campus, program_level, program=None, processing_stage="Part A Ranking", save=True):
    """
    Generates a Merit List for a specific Program Level or Program.
    """
    if save:
        # Check if a Merit List already exists
        existing_filters = {
            "admission_cycle": cycle,
            "campus": campus,
            "program_level": program_level,
            "merit_processing_stage": processing_stage
        }
        if program:
            existing_filters["program"] = program

        existing = frappe.db.get_value(
            "Merit List",
            existing_filters,
            ["name", "docstatus"],
            as_dict=True
        )
        if existing:
            existing_doc = frappe.get_doc("Merit List", existing.get("name"))

            # If already published, do not allow automatic re-generation via this service
            if existing_doc.status == "Published":
                return existing_doc

            # If status is "Generated" or "Draft", soft-archive it as 'Superseded' to preserve audit trail
            if existing_doc.docstatus == 1:
                existing_doc.cancel()
            existing_doc.db_set("status", "Superseded")
            frappe.db.commit()


    # Fetch applicants names
    if processing_stage == "Final Allotment Ranking":
        sp_filters = {
            "admission_cycle": cycle,
            "campus": campus,
            "program_level": program_level,
            "status": ["!=", "Superseded"]
        }
        if program:
            sp_filters["program"] = program

        sp_name = frappe.db.get_value("Shortlisting Merit List", sp_filters, "name", order_by="creation desc")
        if not sp_name:
            prog_err = f" for {program}" if program else f" for {program_level}"
            frappe.throw(f"No Shortlisting Merit List found{prog_err}. Please generate the shortlist first.")
            
        shortlist_data = frappe.get_all(
            "Shortlisting Merit Candidate", 
            filters={
                "parent": sp_name, 
                "parentfield": "shortlist_applicants",
                "shortlist_status": "Shortlisted"
            }, 
            fields=[
                "applicant_id", "shortlist_category", "vertical_category", 
                "allocation_type", "compartmentalized_category", "horizontal_categories",
                "shortlist_rank"
            ]
        )
        applicant_names = [d.applicant_id for d in shortlist_data]
        shortlist_cat_map = {d.applicant_id: d for d in shortlist_data}
    else:
        shortlist_cat_map = {}
        query_args = {
            "cycle": cycle,
            "campus": campus,
            "program_level": program_level
        }
        program_cond = ""
        if program:
            program_cond = " AND etsa.program = %(program)s "
            query_args["program"] = program

        applicant_records = frappe.db.sql(f"""
            SELECT etsa.applicant
            FROM `tabEntrance Test Seat Allocation` etsa
            LEFT JOIN `tabProgramme` p ON etsa.program = p.name
            WHERE etsa.admission_cycle = %(cycle)s
              AND etsa.campus = %(campus)s
              AND (etsa.program_level = %(program_level)s OR p.level_of_study = %(program_level)s)
              AND etsa.entrance_test_status = 'Attended'
              AND etsa.result_status = 'Pass'
              {program_cond}
        """, query_args, as_dict=True)

        applicant_names = [r.applicant for r in applicant_records]
    

    # Build Merit List
    merit = frappe.new_doc("Merit List")
    merit.admission_cycle = cycle
    merit.campus = campus
    merit.program_level = program_level
    merit.program = program
    merit.merit_processing_stage = processing_stage
    merit.generated_on = now_datetime()
    merit.status = "Generated"

    cache_key = f"merit_generation_{cycle}_{campus}_{program_level}_{program or ''}".replace(" ", "_")
    frappe.cache().delete_value(cache_key)
    frappe.cache().set_value(cache_key, {
        "current": 0,
        "total": len(applicant_names),
        "percent": 0,
        "description": "Starting merit generation...",
        "status": "In Progress"
    }, expires_in_sec=300)

    total_applicants = len(applicant_names)

    # Bulk pre-fetch Entrance Test Seat Allocation, Applicant, child tables, and category traits
    # to eliminate N+1 database queries inside the processing loop.
    etsa_records = frappe.get_all(
        "Entrance Test Seat Allocation",
        filters={"name": ["in", applicant_names]},
        fields=[
            "name", "applicant", "candidate_name", "program", "program_level",
            "part_a_total_marks_scored", "part_b_total_marks_scored",
            "shortlisted_status", "percentile", "gender"
        ]
    ) if applicant_names else []
    etsa_map = {r.name: r for r in etsa_records}

    applicant_records = frappe.get_all(
        "Applicant",
        filters={"name": ["in", applicant_names]},
        fields=["name", "hsc_percentage", "date_of_birth"]
    ) if applicant_names else []
    applicant_map = {r.name: r for r in applicant_records}

    # Pre-fill category cache for _get_categorized_traits
    from slcm.admission.doctype.seat_allocation.seat_allocation import _CATEGORY_CACHE
    if applicant_names:
        cat_rows = frappe.get_all(
            "Applicant Category",
            filters={"parent": ["in", applicant_names], "parenttype": "Entrance Test Seat Allocation"},
            fields=["parent", "category"]
        )
        cat_map = defaultdict(list)
        for r in cat_rows:
            if r.category:
                cat_map[r.parent].append(r.category)

        vertical_set = {"SC", "ST", "OBC-NCL", "EWS"}
        for name in applicant_names:
            etsa_rec = etsa_map.get(name) or {}
            raw_cats = cat_map.get(name, [])
            gender = etsa_rec.get("gender")
            if gender == "Female" and "Women" not in raw_cats:
                raw_cats.append("Women")

            normalized = []
            for c in raw_cats:
                if not c: continue
                c_str = str(c).strip()
                if "Karnataka" in c_str: normalized.append("Karnataka")
                elif "Women" in c_str or "Female" in c_str: normalized.append("Women")
                elif "PWD" in c_str or "Person with Disability" in c_str: normalized.append("PWD")
                elif "OBC" in c_str or "BC" in c_str: normalized.append("OBC-NCL")
                elif "EWS" in c_str: normalized.append("EWS")
                elif "ST" in c_str: normalized.append("ST")
                elif "SC" in c_str: normalized.append("SC")
                else: normalized.append(c_str)

            final_categories = list(set(normalized))
            if not any(v in final_categories for v in vertical_set):
                final_categories.append("General")

            _CATEGORY_CACHE[name] = final_categories

    for i, name in enumerate(applicant_names):
        percent = (i + 1) * 80.0 / total_applicants
        description = _("Processing applicant {0} of {1}").format(i + 1, total_applicants)
        frappe.cache().set_value(cache_key, {
            "current": i + 1,
            "total": total_applicants,
            "percent": percent,
            "description": description,
            "status": "In Progress"
        }, expires_in_sec=300)
        # Fetch Entrance Test Seat Allocation and Applicant documents (via pre-fetched maps)
        etsa_doc = etsa_map.get(name) or frappe._dict({"name": name, "applicant": name})
        applicant_doc = applicant_map.get(name) or {}

        ug_avg = 0
        pg_avg = 0

        # Build local dictionary mimicking Eligibility Result properties
        # part_b_not_appeared: True when candidate was shortlisted for Part A but never appeared
        # for Part B (shortlisted_status on ETSA is not 'Shortlisted').
        # Candidates who appeared and scored 0 are NOT flagged as not_appeared.
        etsa_part_b_shortlisted = (etsa_doc.get("shortlisted_status") or "") == "Shortlisted"
        app = frappe._dict({
            "applicant_id": etsa_doc.get("applicant") or name,
            "candidate_name": etsa_doc.get("candidate_name") or "Unknown",
            "program": etsa_doc.get("program"),
            "program_level": etsa_doc.get("program_level"),
            "hsc_percentage": applicant_doc.get("hsc_percentage") or 0,
            "et_part_a_total_marks_scored": etsa_doc.get("part_a_total_marks_scored") or 0,
            "et_part_b_total_marks_scored": etsa_doc.get("part_b_total_marks_scored") or 0,
            "ug_cgpa": ug_avg,
            "pg_cgpa": pg_avg,
            "date_of_birth": applicant_doc.get("date_of_birth"),
            "percentile_score": etsa_doc.get("percentile") or 0,
            "part_b_not_appeared": processing_stage != "Part A Ranking" and not etsa_part_b_shortlisted
        })
        
        # Advanced shortlisting logic (skip candidates with 0 or negative scores in Part A)
        if processing_stage == "Part A Ranking" and (app.get("et_part_a_total_marks_scored") or 0) <= 0:
            continue

        part_a = float(app.get("et_part_a_total_marks_scored") or 0)
        part_b = float(app.get("et_part_b_total_marks_scored") or 0)
        
        if processing_stage == "Part A Ranking":
            total_score = part_a
            status = "Selected"
        else:
            total_score = part_a + part_b
            # Reject if candidate did not appear for Part B OR scored 0 or negative marks in Part B
            status = "Rejected" if (app.get("part_b_not_appeared") or part_b <= 0) else "Selected"

        verticals, horizontals, compartmental = _get_categorized_traits(app.applicant_id)
        primary_cat = verticals[0] if verticals else "General"

        merit.append("merit_applicants", {
            "applicant_id": app.applicant_id,
            "candidate_name": app.candidate_name,
            "program": app.program,
            "program_level": app.program_level,
            "hsc_percentage": app.get("hsc_percentage") or 0,
            "entrance_score": app.get("et_part_a_total_marks_scored") or 0,
            "interview_score": app.get("et_part_b_total_marks_scored") or 0,
            "ug_cgpa": app.get("ug_cgpa") or 0,
            "pg_cgpa": app.get("pg_cgpa") or 0,
            "date_of_birth": app.get("date_of_birth"),
            "total_score": total_score,
            "status": status,
            "overall_rank": 0,
            "part_a_rank": shortlist_cat_map.get(app.applicant_id, {}).get("shortlist_rank") or 0,
            "part_b_rank": 0,
            "program_rank": 0,
            "category_rank": 0,
            "actual_category": primary_cat,
            "shortlist_category": shortlist_cat_map.get(app.applicant_id, {}).get("shortlist_category"),
            "vertical_category": shortlist_cat_map.get(app.applicant_id, {}).get("vertical_category"),
            "allocation_type": shortlist_cat_map.get(app.applicant_id, {}).get("allocation_type"),
            "compartmentalized_category": shortlist_cat_map.get(app.applicant_id, {}).get("compartmentalized_category"),
            "compartment_category": shortlist_cat_map.get(app.applicant_id, {}).get("compartment_category"),
            "horizontal_compartmentalized": shortlist_cat_map.get(app.applicant_id, {}).get("horizontal_compartmentalized"),
            "horizontal_categories": shortlist_cat_map.get(app.applicant_id, {}).get("horizontal_categories"),
            "percentile_score": app.get("percentile_score") or 0
        })

    if not merit.merit_applicants:
        frappe.throw(
            f"No applicants could be processed for Program Level '{program_level}'.",
            title="Empty Merit List"
        )

    merit.total_applicants = len(merit.merit_applicants)

    first_app_prog = merit.merit_applicants[0].program
    # Always use advanced ranking/allocation logic
    _rank_applicants(merit.merit_applicants, use_advanced_ranking=True, processing_stage=processing_stage)
    
    # Calculate and persist percentiles for each program group separately.
    grouped_by_program = {}
    for row in merit.merit_applicants:
        grouped_by_program.setdefault(row.program, []).append(row)

    is_shortlist_stage = (processing_stage == "Part A Ranking")
    for _prog_applicants in grouped_by_program.values():
        _calculate_and_sync_percentiles(_prog_applicants, is_shortlist=is_shortlist_stage)

    merit.merit_applicants.sort(key=lambda x: (1 if (x.overall_rank or 0) == 0 else 0, x.overall_rank or 999999))
    for i, row in enumerate(merit.merit_applicants):
        row.idx = i + 1
        
    _populate_category_lists(merit)
        
    if True:
        if processing_stage == "Final Allotment Ranking":
            # Simple population for Final Merit (Shows everyone in their category tabs as Selected)
            _populate_category_lists(merit)
        else:
            # Shortlisting stage still needs advanced logic for multiplier targets
            execute_advanced_allocation_logic(merit, is_shortlist_allocation=True)
            _populate_category_lists(merit)

    merit.total_applicants = len(merit.merit_applicants)
    merit.total_selected = len([a for a in merit.merit_applicants if a.status == "Selected" or getattr(a, "allocation_type", "") in ("Open", "Reserved")])
    merit.total_rejected = len([a for a in merit.merit_applicants if a.status == "Rejected"])

    if save:
        merit.insert()
        frappe.db.commit()
        _publish_allocation_progress(merit, 100, "Merit List Generated Successfully", status="Completed")
    else:
        _publish_allocation_progress(merit, 80, "Shortlisting candidates...", status="In Progress")
    return merit


def _apply_percentile_cutoffs(doc):
    """
    Applies NLSAT minimum percentile eligibility from Programme Reservation Policy.
    """
    policy_name = frappe.db.get_value("Programme Reservation Policy", {
        "admission_cycle": doc.admission_cycle,
        "program": doc.program
    }, "name")
    
    if not policy_name:
        return
        
    policy = frappe.get_doc("Programme Reservation Policy", policy_name)
    
    vertical_targets = {}
    for v in policy.categories:
        vertical_targets[v.category_name or "General"] = {"min_percentile": v.min_percentile}
        
    horizontal_targets = {}
    for h in policy.horizontal_reservations:
        horizontal_targets[h.category_name] = {"min_percentile": h.min_percentile}
    
    for row in doc.merit_applicants:
        if _check_percentile_eligibility(row, vertical_targets, horizontal_targets):
            row.status = "Selected"
        else:
            row.status = "Rejected"
            row.remarks = f"Below minimum percentile threshold"


def _populate_category_lists(doc):
    """
    Populates category-specific tables in Merit List/Shortlisting Merit List for UI display.
    Uses the results of the advanced allocation logic (allocated_category, vertical_category).
    """
    if not hasattr(doc, "general_list"):
        return
        
    # Clear existing
    list_fields = ["general_list", "sc_list", "st_list", "obc_list", "ews_list", "karnataka_list", "women_list", "pwd_list"]
    if hasattr(doc, "meta") and doc.meta:
        for f in doc.meta.get("fields") or []:
            if f.fieldtype == "Table" and f.fieldname.endswith("_list") and f.fieldname not in list_fields:
                list_fields.append(f.fieldname)
    for field in list_fields:
        if hasattr(doc, field):
            doc.set(field, [])
            
    policy = None
    multiplier = 1.0
    if getattr(doc, "program", None) and getattr(doc, "admission_cycle", None):
        policy_name = frappe.db.get_value("Programme Reservation Policy", {
            "admission_cycle": doc.admission_cycle,
            "program": doc.program
        }, "name")
        if policy_name:
            policy = frappe.get_doc("Programme Reservation Policy", policy_name)
            mult_val = policy.get("shortlisting_multiplier")
            multiplier = 1.0 if mult_val is None else float(mult_val)

    comp_cat = "Karnataka"
    if policy and policy.compartmental_reservations:
        for comp in policy.compartmental_reservations:
            comp_cat = comp.category_name or "Karnataka"
            break

    app_list = []
    if hasattr(doc, "shortlist_applicants"):
        app_list = doc.shortlist_applicants
    elif hasattr(doc, "merit_applicants"):
        app_list = doc.merit_applicants
    elif hasattr(doc, "selection_applicant"):
        app_list = doc.selection_applicant

    # Sort by rank to ensure we pick the top candidates for tabs
    sorted_applicants = sorted(
        app_list,
        key=lambda x: (
            getattr(x, "shortlist_rank", None)
            or getattr(x, "overall_rank", None)
            or getattr(x, "selection_rank", None)
            or getattr(x, "rank", None)
            or 9999
        )
    )

    for row in sorted_applicants:
        status_field = "status"
        if hasattr(doc, "shortlist_applicants"):
            status_field = "shortlist_status"
        elif hasattr(doc, "selection_applicant"):
            status_field = "selection_status"


        if getattr(row, status_field, "") == "Rejected":
            continue

        # Prepare data for append (exclude idx and name to allow creating NEW rows in separate child tables)
        row_data = row.as_dict()
        for field in ["idx", "name", "parent", "parentfield", "parenttype"]:
            if field in row_data:
                del row_data[field]

        # 1. Use allocation results for categorization
        v_cat = getattr(row, "vertical_category", "")
        alloc_type = getattr(row, "allocation_type", "")
        disp_cat = getattr(row, "allocated_category", "") or getattr(row, "shortlist_category", "")
        
        # 2. Populate General List (Open Merit)
        if v_cat == "General" or alloc_type == "Open":
            if hasattr(doc, "general_list"):
                doc.append("general_list", row_data)
            
        # 3. Vertical Lists (only if allocated to that vertical specifically)
        target_field = None
        if v_cat and v_cat != "General":
            norm_v_cat = v_cat.lower().replace("-ncl", "").replace("-", "_")
            target_field = f"{norm_v_cat}_list"
        
        if target_field and hasattr(doc, target_field):
            doc.append(target_field, row_data)
            
        # 4. Special Lists (Horizontal/Compartmental) - Use _has_trait for partial matching (e.g. Karnataka Students)
        is_shortlist = hasattr(doc, "shortlist_applicants")
        if _has_trait(row.applicant_id, comp_cat, is_shortlist) and hasattr(doc, "karnataka_list"):
            doc.append("karnataka_list", row_data)
        if _has_trait(row.applicant_id, "Women", is_shortlist) and hasattr(doc, "women_list"):
            doc.append("women_list", row_data)
        if _has_trait(row.applicant_id, "PWD", is_shortlist) and hasattr(doc, "pwd_list"):
            doc.append("pwd_list", row_data)

    # Populate Category Summary with rich policy targets
    if hasattr(doc, "category_summary"):
        doc.set("category_summary", [])
        
        # Try to fetch the policy to get rich targets
        policy = None
        multiplier = 1.0
        is_shortlist = hasattr(doc, "shortlist_applicants")
        if getattr(doc, "program", None) and getattr(doc, "admission_cycle", None):
            policy_name = frappe.db.get_value("Programme Reservation Policy", {
                "admission_cycle": doc.admission_cycle,
                "program": doc.program
            }, "name")
            if policy_name:
                policy = frappe.get_doc("Programme Reservation Policy", policy_name)
                if is_shortlist:
                    mult_val = policy.get("shortlisting_multiplier")
                    multiplier = 1.0 if mult_val is None else float(mult_val)
                else:
                    multiplier = 1.0
        
        # Build map from vertical, compartmental, and horizontal categories to seats & required targets
        category_mapping = {}
        ordered_cats = []
        
        if policy:
            total_eligible_summary = len(sorted_applicants)
            # 1. Main vertical categories
            for v in policy.categories:
                v_cat_name = v.category_name or "General"
                if is_shortlist and multiplier == 0:
                    req_seats = total_eligible_summary
                else:
                    req_seats = v.get("shortlisting_target")
                    if not req_seats:
                        req_seats = int((v.seats or 0) * multiplier)
                category_mapping[v_cat_name] = {
                    "seats": v.seats or 0,
                    "required": req_seats or 0
                }
                if v_cat_name not in ordered_cats:
                    ordered_cats.append(v_cat_name)
            
            # 2. Compartmental
            for comp in policy.compartmental_reservations:
                comp_cat = comp.category_name or "Karnataka"
                percentage = comp.percentage or 0.0
                for v_cat in list(category_mapping.keys()):
                    # Avoid compounding on already compartmentalized categories
                    if any(c.category_name in v_cat for c in policy.compartmental_reservations):
                        continue
                    v_info = category_mapping[v_cat]
                    seats = int((v_info["seats"] * percentage) / 100.0)
                    req = total_eligible_summary if (is_shortlist and multiplier == 0) else int(seats * multiplier)
                    comp_name = f"{comp_cat} {v_cat}"
                    category_mapping[comp_name] = {
                        "seats": seats,
                        "required": req
                    }
                    if comp_name not in ordered_cats:
                        ordered_cats.append(comp_name)
            
            # 3. Horizontal
            for h in policy.horizontal_reservations:
                h_name = h.category_name
                if is_shortlist and multiplier == 0:
                    req_seats = total_eligible_summary
                else:
                    req_seats = h.get("shortlisting_target")
                    if not req_seats:
                        req_seats = int((h.seats or 0) * multiplier)
                category_mapping[h_name] = {
                    "seats": h.seats or 0,
                    "required": req_seats or 0
                }
                if h_name not in ordered_cats:
                    ordered_cats.append(h_name)
        else:
            # Dynamic fallback to database config if policy is missing
            db_cats = frappe.get_all("Admission Category", fields=["name", "reservation_type"])
            verticals = [c.name for c in db_cats if c.reservation_type == "Vertical"]
            compartmentals = [c.name for c in db_cats if c.reservation_type == "Compartmentalised Horizontal"]
            horizontals = [c.name for c in db_cats if c.reservation_type == "Horizontal"]
            
            for v in verticals:
                category_mapping[v] = {"seats": 0, "required": 0}
                ordered_cats.append(v)
            for comp in compartmentals:
                for v in verticals:
                    comp_name = f"{comp} {v}"
                    category_mapping[comp_name] = {"seats": 0, "required": 0}
                    ordered_cats.append(comp_name)
            for h in horizontals:
                category_mapping[h] = {"seats": 0, "required": 0}
                ordered_cats.append(h)
                
        is_shortlist = hasattr(doc, "shortlist_applicants")
        counts = {}
        valid_active = ["Selected", "Offer Issued", "Offer Accepted", "Accepted", "Fee Paid", "Payment Completed", "Enrolled", "Seat Selected", "Confirmation Fee Paid", "Full Fee Paid", "Shortlisted"]
        
        # Resolve dynamic categorisation tallies from DB masters
        db_cats_all = frappe.get_all("Admission Category", fields=["name", "reservation_type"])
        comp_types = [c.name for c in db_cats_all if c.reservation_type == "Compartmentalised Horizontal"]
        horiz_types = [c.name for c in db_cats_all if c.reservation_type == "Horizontal"]
        
        for cat in ordered_cats:
            is_comp = False
            for comp_name in comp_types:
                if cat.startswith(f"{comp_name} ") or cat.startswith(f"{comp_name}("):
                    v_name = cat[len(comp_name):].strip("() ")
                    if v_name == "Common":
                        counts[cat] = len([x for x in sorted_applicants if getattr(x, status_field, "") in valid_active and _has_trait(x.applicant_id, comp_name, is_shortlist)])
                    else:
                        counts[cat] = len([x for x in sorted_applicants if getattr(x, status_field, "") in valid_active and (getattr(x, "vertical_category", "") or getattr(x, "actual_category", "")) == v_name and _has_trait(x.applicant_id, comp_name, is_shortlist)])
                    is_comp = True
                    break
            if not is_comp:
                if cat in horiz_types:
                    counts[cat] = len([x for x in sorted_applicants if getattr(x, status_field, "") in valid_active and _has_trait(x.applicant_id, cat, is_shortlist)])
                else:
                    counts[cat] = len([x for x in sorted_applicants if getattr(x, status_field, "") in valid_active and getattr(x, "vertical_category", "") == cat])
        
        for cat in ordered_cats:
            info = category_mapping.get(cat, {"seats": 0, "required": 0})
            req_val = info["required"]
            act_val = counts.get(cat, 0)
            doc.append("category_summary", {
                "category": cat,
                "seats": info["seats"],
                "multiplier": multiplier,
                "required_to_shortlist": req_val,
                "actually_shortlisted": act_val,
                "vacant_seats": max(0, req_val - act_val)
            })



def execute_advanced_allocation_logic(doc, is_shortlist_allocation=False, ignore_seat_limits=False):
    """
    NLSAT specific seat allocation logic based on document rules.
    Phases:
    1. Vertical Allocation (General, then Reserved)
    2. Karnataka Sub-quota Adjustments (with recursive displacement)
    3. Horizontal Reservation (PWD, then Women)
    """
    if is_shortlist_allocation:
        return execute_part_a_shortlisting(doc)
        
    clear_category_cache()
    karnataka_vacancies = {}
    
    child_table = None
    status_field = "status"
    if hasattr(doc, "shortlist_applicants"):
        child_table = "shortlist_applicants"
        status_field = "shortlist_status"
    elif hasattr(doc, "selection_applicant"):
        child_table = "selection_applicant"
        status_field = "selection_status"
    elif hasattr(doc, "merit_applicants"):
        child_table = "merit_applicants"
        status_field = "status"
        
    if not child_table:
        return False

    applicants_list = getattr(doc, child_table)
    
    # Reset all statuses before re-running the logic to ensure a clean slate
    for row in applicants_list:
        setattr(row, status_field, "Selected" if not is_shortlist_allocation else "Shortlisted")
        row.vertical_category = ""
        row.allocation_type = "Open"
        if hasattr(row, "remarks"):
            row.remarks = ""
    
    _publish_allocation_progress(doc, 82, "Ranking Applicants & Percentiles...")

    # Initial Rank
    processing_stage = "Part A Ranking" if is_shortlist_allocation else "Final Allotment Ranking"
    _rank_applicants(applicants_list, use_advanced_ranking=True, processing_stage=processing_stage)

    grouped_by_program = {}
    for row in applicants_list:
        grouped_by_program.setdefault(row.program, []).append(row)

    # Calculate and persist percentiles for each program group separately.
    # This must happen before the percentile eligibility filter below.
    if getattr(doc, "doctype", "") != "Seat Allocation":
        for _prog_applicants in grouped_by_program.values():
            _calculate_and_sync_percentiles(_prog_applicants, is_shortlist=is_shortlist_allocation)

    for program, applicants in grouped_by_program.items():
        policy_name = frappe.db.get_value("Programme Reservation Policy", {
            "admission_cycle": doc.admission_cycle,
            "program": program
        }, "name")

        if not policy_name:
            frappe.throw(
                f"No Programme Reservation Policy found for Program '{program}' in Admission Cycle '{doc.admission_cycle}'. "
                f"Please create and configure a Programme Reservation Policy for this program first.",
                title="Missing Reservation Policy"
            )
        policy = frappe.get_doc("Programme Reservation Policy", policy_name)

        mult_val = policy.get("shortlisting_multiplier")
        multiplier = 1.0 if mult_val is None else float(mult_val)
        is_shortlist_phase = is_shortlist_allocation or getattr(doc, "merit_processing_stage", "") == "Part A Ranking"
        total_eligible_count = len(applicants)
        
        # 1. Setup Targets from Policy
        vertical_targets = {}
        for v in policy.categories:
            v_cat_name = v.category_name or "General"
            
            if is_shortlist_phase and multiplier == 0:
                seats = total_eligible_count
            else:
                seats = v.get("shortlisting_target") if is_shortlist_phase else v.seats
                if is_shortlist_phase and not seats:
                    seats = int((v.seats or 0) * multiplier)
                elif not is_shortlist_phase:
                    seats = v.seats or 0
            
            vertical_targets[v_cat_name] = {
                "seats": seats or 0,
                "original_seats": v.seats or 0,
                "filled": 0,
                "waitlist_seats": v.waitlist_seats or 0,
                "waitlist_filled": 0,
                "compartmentalized_category": v.compartmentalized_category,
                "compartmentalized_waitlist_seats": v.compartmentalized_waitlist_seats or 0,
                "compartmentalized_waitlist_filled": 0,
                "min_percentile": v.min_percentile,
                "priority": v.priority or 0
            }

        compartmental_targets = {}
        for comp in policy.compartmental_reservations:
            comp_cat = comp.category_name
            percentage = comp.percentage or 25.0
            
            for v_cat, v_info in vertical_targets.items():
                target_key = (comp_cat, v_cat)
                comp_seats = int((v_info["original_seats"] * percentage) / 100.0)
                comp_target_seats = total_eligible_count if (is_shortlist_phase and multiplier == 0) else (int(comp_seats * multiplier) if is_shortlist_phase else comp_seats)
                compartmental_targets[target_key] = {
                    "category": comp_cat,
                    "seats": comp_target_seats,
                    "original_seats": comp_seats,
                    "filled": 0
                }

        horizontal_targets = {}
        for h in policy.horizontal_reservations:
            if is_shortlist_phase and multiplier == 0:
                seats = total_eligible_count
            else:
                seats = h.shortlisting_target if is_shortlist_phase else h.seats
                if is_shortlist_phase and not seats:
                    seats = int((h.seats or 0) * multiplier)
            horizontal_targets[h.category_name] = {
                "name": h.category_name,
                "seats": seats or 0,
                "original_seats": h.seats or 0,
                "filled": 0,
                "min_percentile": h.min_percentile,
                "priority": h.priority or 99
            }

        # 2. Filter by Part B appearance & score (0 or minus marks are rejected in final allocation).
        eligible_applicants = []
        for app in applicants:
            part_b_not_appeared = getattr(app, "part_b_not_appeared", False) or (app.get("part_b_not_appeared") if isinstance(app, dict) else False)
            
            pb_val = getattr(app, "interview_score", None)
            if pb_val is None:
                pb_val = getattr(app, "et_part_b_total_marks_scored", None)
            if pb_val is None:
                pb_val = getattr(app, "nlsat_part_b_score", None)
            if pb_val is None and isinstance(app, dict):
                pb_val = app.get("interview_score") or app.get("et_part_b_total_marks_scored") or app.get("nlsat_part_b_score")
            part_b_score = float(pb_val or 0)

            apply_pct_shortlisting = bool(getattr(policy, "apply_percentile_cutoff_for_shortlisting", 0)) if policy else False

            if not is_shortlist_phase and (part_b_not_appeared or part_b_score <= 0):
                setattr(app, status_field, "Rejected")
                app.allocation_type = "Not Allocated"
                if part_b_not_appeared:
                    app.remarks = "Rejected: did not appear for Part B"
                else:
                    app.remarks = "Rejected: Part B marks are 0 or negative"
            elif is_shortlist_phase and not apply_pct_shortlisting:
                eligible_applicants.append(app)
            elif _check_percentile_eligibility(app, vertical_targets, horizontal_targets):
                eligible_applicants.append(app)
            else:
                setattr(app, status_field, "Rejected")
                app.allocation_type = "Not Allocated"
                app.remarks = "Did not meet minimum percentile threshold"

        unallocated = eligible_applicants[:]
        allocated_list = []

        # --- PHASE 1: INITIAL VERTICAL ALLOTMENT ---
        _publish_allocation_progress(doc, 85, "Applying vertical allocations (General and reserved quotas)...")

        # Requirement: General first, then reserved.
        ordered_cats = ["General"] + sorted([c for c in vertical_targets.keys() if c != "General"], 
                                          key=lambda x: vertical_targets[x]["priority"])
        
        for v_cat in ordered_cats:
            v_info = vertical_targets[v_cat]
            for app in unallocated[:]:
                # Use the already-stored actual_category field on the row (set during merit generation).
                # This avoids a live DB re-fetch (via _get_categorized_traits) which can return a
                # different value due to normalization differences, causing valid candidates to be skipped.
                actual_v = (
                    getattr(app, "actual_category", None)
                    or (getattr(app, "vertical_category", None))
                    or "General"
                )
                # Fallback to live DB lookup only if stored field is blank
                if not actual_v or actual_v.strip() == "":
                    v_traits, __, __ = _get_categorized_traits(app.applicant_id)
                    actual_v = v_traits[0] if v_traits else "General"

                # Rule: Top merit get General seats regardless of their category (Merit Migration)
                can_take_seat = (v_cat == "General") or (actual_v == v_cat)
                
                if can_take_seat and v_info["filled"] < v_info["seats"]:
                    alloc_type = "Open" if v_cat == "General" else "Reserved"
                    _assign_seat_to_applicant(app, v_cat, alloc_type, allocated_list, unallocated, v_info, status_field)

        # --- PHASE 2: COMPARTMENTAL SUB-QUOTA ADJUSTMENT ---
        _publish_allocation_progress(doc, 90, "Applying compartmental sub-quota adjustments (Karnataka sub-quotas)...")




        # Requirement: Displace lowest AI in the pool with next highest student from compartmental category.
        for comp_row in policy.compartmental_reservations:
            comp_cat = comp_row.category_name
            for v_cat in ordered_cats:
                v_info = vertical_targets[v_cat]
                target_info = compartmental_targets.get((comp_cat, v_cat))
                if not target_info or target_info["seats"] <= 0: continue
                
                # Count current coverage in this pool
                comp_in_v = [a for a in allocated_list if a.vertical_category == v_cat and _has_trait(a.applicant_id, comp_cat)]
                deficit = target_info["seats"] - len(comp_in_v)
                
                if deficit > 0:
                    if v_cat == "General":
                        # For General Karnataka sub-quota, candidates can come from unallocated OR
                        # from reserved categories in allocated_list (Merit Migration from Reserved to Open Karnataka)
                        potential_unallocated = [u for u in unallocated if _has_trait(u.applicant_id, comp_cat) and _check_percentile_eligibility(u, vertical_targets, horizontal_targets)]
                        potential_allocated_reserved = [a for a in allocated_list if a.vertical_category != "General" and _has_trait(a.applicant_id, comp_cat) and _check_percentile_eligibility(a, vertical_targets, horizontal_targets)]
                        potential_in = potential_unallocated + potential_allocated_reserved
                        potential_in.sort(key=lambda x: (x.overall_rank or 999999))
                    else:
                        potential_in = [u for u in unallocated if _has_trait(u.applicant_id, comp_cat) and _check_percentile_eligibility(u, vertical_targets, horizontal_targets)]
                        potential_in = [u for u in potential_in if v_cat in get_applicant_categories(u.applicant_id)]
                        potential_in.sort(key=lambda x: (x.overall_rank or 999999))
                    
                    for in_cand in potential_in:
                        if deficit <= 0: break
                        
                        eligible_out = [a for a in allocated_list if a.vertical_category == v_cat and not _has_trait(a.applicant_id, comp_cat)]
                        if eligible_out:
                            # Sort by lowest merit rank for displacement (highest rank number)
                            eligible_out.sort(key=lambda x: -(x.overall_rank or 999999))
                            out_cand = eligible_out[0]
                            
                            # If in_cand is already in this vertical category, skip
                            if getattr(in_cand, "vertical_category", None) == v_cat:
                                continue

                            # If in_cand was in a reserved category, free up that reserved seat
                            prev_v = getattr(in_cand, "vertical_category", None)
                            if prev_v and prev_v in vertical_targets:
                                vertical_targets[prev_v]["filled"] -= 1
                                if in_cand in allocated_list:
                                    allocated_list.remove(in_cand)

                            # Recursive Displacement: Save out_cand in their reserved category if possible
                            disp_reason = f"Displaced from {v_cat} category to accommodate {comp_cat} sub-quota candidate {in_cand.candidate_name or in_cand.applicant_id} ({in_cand.applicant_id})"
                            _execute_recursive_displacement(out_cand, allocated_list, unallocated, vertical_targets, status_field, karnataka_vacancies, reason=disp_reason)
                            in_cand.remarks = f"Allocated seat under {comp_cat} {v_cat} Sub-quota displacing {out_cand.candidate_name or out_cand.applicant_id} ({out_cand.applicant_id})"
                            _assign_seat_to_applicant(in_cand, v_cat, "Open" if v_cat == "General" else "Reserved", allocated_list, unallocated, v_info, status_field)
                            deficit -= 1

                    # Recalculate deficit after attempting to fill with available Karnataka candidates
                    comp_in_v = [a for a in allocated_list if a.vertical_category == v_cat and _has_trait(a.applicant_id, comp_cat)]
                    remaining_deficit = target_info["seats"] - len(comp_in_v)
                    revert_unfilled = getattr(policy, "revert_unfilled_compartmental_seats", False)
                    if remaining_deficit > 0 and not revert_unfilled and not (is_shortlist_phase and multiplier == 0):
                        # Identify All-India candidates in this category that are currently allocated
                        eligible_out = [a for a in allocated_list if a.vertical_category == v_cat and not _has_trait(a.applicant_id, comp_cat)]
                        max_ai_allowed = v_info["seats"] - target_info["seats"]
                        excess_ai = len(eligible_out) - max_ai_allowed
                        if excess_ai > 0 and eligible_out:
                            eligible_out.sort(key=lambda x: -(x.overall_rank or 999999))
                            # We need to displace excess_ai of them so these seats remain vacant
                            to_displace = eligible_out[:excess_ai]
                            for out_cand in to_displace:
                                disp_reason = f"Displaced from {v_cat} category as All-India quota limit was reached for unfilled {comp_cat} seats"
                                _execute_recursive_displacement(out_cand, allocated_list, unallocated, vertical_targets, status_field, karnataka_vacancies, reason=disp_reason)
                        
                        # Store the vacancy count
                        karnataka_vacancies[v_cat] = remaining_deficit

        # --- PHASE 3: HORIZONTAL RESERVATION (e.g., PWD & Women) ---
        _publish_allocation_progress(doc, 93, "Applying horizontal reservations (Women & PWD quotas)...")

        ordered_h_cats = sorted(horizontal_targets.values(), key=lambda x: x["priority"])
        for h_info in ordered_h_cats:
            h_cat = h_info["name"]
            if h_info["seats"] <= 0: continue
            
            h_count = len([a for a in allocated_list if _has_trait(a.applicant_id, h_cat)])
            deficit = h_info["seats"] - h_count
            
            if deficit > 0:
                potential = [u for u in unallocated if _has_trait(u.applicant_id, h_cat)]
                potential.sort(key=lambda x: (x.overall_rank or 999999))
                for in_cand in potential:
                    if deficit <= 0: break
                    
                    v_traits, _, _ = _get_categorized_traits(in_cand.applicant_id)
                    v_belong = v_traits[0] if v_traits else "General"
                    
                    # Try to displace lowest candidate in the same vertical category who doesn't have this horizontal trait
                    # and isn't satisfying a compartmental sub-quota
                    eligible_out = [a for a in allocated_list if a.vertical_category == v_belong 
                                    and not any(_has_trait(a.applicant_id, c.category_name) for c in policy.compartmental_reservations)
                                    and not _has_trait(a.applicant_id, h_cat)]
                    
                    if eligible_out:
                        eligible_out.sort(key=lambda x: -(x.overall_rank or 999999))
                        out_cand = eligible_out[0]
                        
                        disp_reason = f"Displaced from {v_belong} category to accommodate {h_cat} horizontal reservation candidate {in_cand.candidate_name or in_cand.applicant_id} ({in_cand.applicant_id})"
                        _execute_recursive_displacement(out_cand, allocated_list, unallocated, vertical_targets, status_field, karnataka_vacancies, reason=disp_reason)
                        in_cand.remarks = f"Allocated seat under {h_cat} Horizontal Reservation displacing {out_cand.candidate_name or out_cand.applicant_id} ({out_cand.applicant_id})"
                        _assign_seat_to_applicant(in_cand, v_belong, "Open" if v_belong == "General" else "Reserved", allocated_list, unallocated, vertical_targets[v_belong], status_field)
                        deficit -= 1

        # --- PHASE 3.25: MULTI-TRAIT SUB-QUOTA RECONCILIATION ---
        # If Phase 3 introduced horizontal candidates with compartmental traits (e.g. PWD + Karnataka),
        # the category may now have more compartmental candidates than its target quota.
        # Reconcile so that excess compartmental candidates (who do not have other protected horizontal traits)
        # are released back to unallocated, making room for top unallocated vertical merit candidates.
        for comp_row in policy.compartmental_reservations:
            comp_cat = comp_row.category_name
            for v_cat in ordered_cats:
                v_info = vertical_targets[v_cat]
                target_info = compartmental_targets.get((comp_cat, v_cat))
                if not target_info or target_info["seats"] <= 0:
                    continue

                comp_in_v = [a for a in allocated_list if a.vertical_category == v_cat and _has_trait(a.applicant_id, comp_cat)]
                excess = len(comp_in_v) - target_info["seats"]
                if excess > 0:
                    # Candidates eligible to be released: those who have comp_cat trait,
                    # but DO NOT satisfy any other mandatory horizontal reservation (like PWD)
                    # and are the lowest ranked in merit
                    releasable = [
                        a for a in comp_in_v
                        if not any(
                            _has_trait(a.applicant_id, h.category_name)
                            for h in policy.horizontal_reservations
                            if h.category_name != "Women"
                        )
                    ]
                    # Further verify they are not essential for Women quota if Women quota would fall below target
                    releasable_safe = []
                    for cand in releasable:
                        is_safe = True
                        for h in policy.horizontal_reservations:
                            if _has_trait(cand.applicant_id, h.category_name):
                                cur_h_count = len([a for a in allocated_list if _has_trait(a.applicant_id, h.category_name)])
                                if cur_h_count <= horizontal_targets[h.category_name]["seats"]:
                                    is_safe = False
                                    break
                        if is_safe:
                            releasable_safe.append(cand)

                    if releasable_safe:
                        # Sort by lowest merit (highest rank number)
                        releasable_safe.sort(key=lambda x: -(x.overall_rank or 999999))
                        to_release = releasable_safe[:excess]
                        for rel_cand in to_release:
                            disp_reason = f"Displaced from {v_cat} as {comp_cat} sub-quota was fulfilled by higher/dual-trait candidate"
                            _execute_recursive_displacement(rel_cand, allocated_list, unallocated, vertical_targets, status_field, karnataka_vacancies, reason=disp_reason)

        # --- PHASE 3.5: VERTICAL BACKFILL ---
        _publish_allocation_progress(doc, 96, "Applying vertical backfills for vacant seats...")

        # Requirement: If displacements in Phase 2 or 3 created vacancies in vertical quotas,
        # fill them now from the remaining unallocated pool.
        for v_cat in ordered_cats:
            v_info = vertical_targets[v_cat]
            kv_count = karnataka_vacancies.get(v_cat, 0)
            while v_info["filled"] < (v_info["seats"] - kv_count):
                # Find best merit unallocated candidates who belong to this vertical category
                potential = []
                for u in unallocated:
                    u_verticals, _, _ = _get_categorized_traits(u.applicant_id)
                    u_primary = u_verticals[0] if u_verticals else "General"
                    if v_cat == "General" or u_primary == v_cat:
                        potential.append(u)
                
                if not potential:
                    break
                
                # Sort by rank (lowest rank number is highest merit)
                potential.sort(key=lambda x: (x.overall_rank or 999999))
                in_cand = potential[0]
                
                in_cand.remarks = f"Allocated seat under {v_cat} Vertical Backfill based on Final Rank #{in_cand.overall_rank or ''}"
                _assign_seat_to_applicant(in_cand, v_cat, "Open" if v_cat == "General" else "Reserved", allocated_list, unallocated, v_info, status_field)

        # --- PHASE 3.6: TIE-BREAKER FOR SEAT ALLOCATION ---
        # If candidates have the same overall_rank in the final rank as the last allocated candidate 
        # in a category, they must be assigned/allocated to that category/seat.
        if not is_shortlist_phase:
            tie_candidates_to_assign = []
            for v_cat in ordered_cats:
                v_info = vertical_targets[v_cat]
                v_allocated = [x for x in allocated_list if x.vertical_category == v_cat]
                if not v_allocated:
                    continue
                ranks_in_v = [getattr(x, "overall_rank", None) or (x.get("overall_rank") if isinstance(x, dict) else None) for x in v_allocated]
                ranks_in_v = [r for r in ranks_in_v if r is not None]
                if not ranks_in_v:
                    continue
                max_rank = max(ranks_in_v)
                
                # Check for unallocated candidates with the exact same overall_rank at cutoff
                for u in unallocated:
                    u_rank = getattr(u, "overall_rank", None) or (u.get("overall_rank") if isinstance(u, dict) else None)
                    if u_rank is not None and u_rank == max_rank:
                        actual_v = (
                            getattr(u, "actual_category", None)
                            or getattr(u, "vertical_category", None)
                            or "General"
                        )
                        if not actual_v or actual_v.strip() == "":
                            v_traits, __, __ = _get_categorized_traits(u.applicant_id)
                            actual_v = v_traits[0] if v_traits else "General"
                            
                        if v_cat == "General" or actual_v == v_cat:
                            # Only allocate tie candidate if seat quota has space OR candidate fulfills an unfulfilled sub-quota
                            has_unfilled_subquota = False
                            for comp_row in policy.compartmental_reservations:
                                comp_cat = comp_row.category_name
                                target_info = compartmental_targets.get((comp_cat, v_cat))
                                if target_info and target_info["seats"] > 0:
                                    comp_in_v = [a for a in allocated_list if a.vertical_category == v_cat and _has_trait(a.applicant_id, comp_cat)]
                                    if len(comp_in_v) < target_info["seats"] and _has_trait(u.applicant_id, comp_cat):
                                        has_unfilled_subquota = True
                                        break
                            
                            if v_info["filled"] < v_info["seats"] or has_unfilled_subquota:
                                tie_candidates_to_assign.append((u, v_cat))

            for tie_cand, v_cat in tie_candidates_to_assign:
                if tie_cand in unallocated:
                    alloc_type = "Open" if v_cat == "General" else "Reserved"
                    tie_cand.remarks = f"Allocated seat under {v_cat} Category due to Final Cutoff Score Tie (Total Score: {getattr(tie_cand, 'total_score', '')}, Final Rank #{getattr(tie_cand, 'overall_rank', '')})"
                    _assign_seat_to_applicant(
                        tie_cand, 
                        v_cat, 
                        alloc_type, 
                        allocated_list, 
                        unallocated, 
                        vertical_targets[v_cat], 
                        status_field
                    )

        # Explicitly Reject remaining before Waitlist Phase (unless shortlisting with multiplier = 0)
        for u in unallocated:
            if is_shortlist_phase and multiplier == 0:
                setattr(u, status_field, "Shortlisted")
                u.allocation_type = "Open"
                u.vertical_category = getattr(u, "actual_category", "General") or "General"
                display_field = "allocated_category" if hasattr(u, "allocated_category") else "shortlist_category"
                setattr(u, display_field, u.vertical_category)
            else:
                setattr(u, status_field, "Rejected")
                u.allocation_type = "Not Allocated"
                if not getattr(u, "remarks", None):
                    u.remarks = f"Not allocated: Exceeded {getattr(u, 'actual_category', 'General') or 'General'} category seat capacity / cutoff rank (Final Rank #{getattr(u, 'overall_rank', '') or ''})"
                u.vertical_category = ""

        # --- PHASE 4: WAITLIST ALLOCATION ---
        _publish_allocation_progress(doc, 98, "Generating waitlist and final summaries...")

        if not is_shortlist_phase:
            for v_cat in ordered_cats:
                v_info = vertical_targets[v_cat]
                w_limit = v_info.get("waitlist_seats", 0)
                w_comp_limit = v_info.get("compartmentalized_waitlist_seats", 0)
                comp_cat = v_info.get("compartmentalized_category")
                
                if w_limit <= 0 and w_comp_limit <= 0: continue
                
                # Find remaining unallocated who are eligible for this category
                potential_w = [u for u in unallocated if getattr(u, status_field) == "Rejected"]
                if v_cat != "General":
                    potential_w = [u for u in potential_w if v_cat in get_applicant_categories(u.applicant_id)]
                
                # Merit sort
                potential_w.sort(key=lambda x: (-(float(getattr(x, "total_score", 0) or 0)), (x.overall_rank or 999999)))
                
                for w_cand in potential_w:
                    is_comp = False
                    if comp_cat and _has_trait(w_cand.applicant_id, comp_cat):
                        is_comp = True
                        
                    assigned = False
                    if is_comp and v_info.get("compartmentalized_waitlist_filled", 0) < w_comp_limit:
                        assigned = True
                        v_info["compartmentalized_waitlist_filled"] = v_info.get("compartmentalized_waitlist_filled", 0) + 1
                        w_cand.remarks = f"Waitlisted under {comp_cat} {v_cat} Sub-quota based on merit ranking (Waitlist Rank #{v_info['compartmentalized_waitlist_filled']})"
                    elif v_info.get("waitlist_filled", 0) < w_limit:
                        assigned = True
                        v_info["waitlist_filled"] = v_info.get("waitlist_filled", 0) + 1
                        w_cand.remarks = f"Waitlisted under {v_cat} Category based on merit ranking (Waitlist Rank #{v_info['waitlist_filled']})"
                        
                    if assigned:
                        # Use _assign_seat_to_applicant to handle categorization strings
                        _assign_seat_to_applicant(w_cand, v_cat, w_cand.allocation_type, [], [], {"filled": 0}, status_field)
                        # Reset the status back to Waitlisted since _assign sets it to Selected/Shortlisted
                        setattr(w_cand, status_field, "Waitlisted")

        # --- POPULATE SUMMARY ---
        if hasattr(doc, "category_summary"):
            doc.set("category_summary", [])
            summary_table = "category_summary"
            
            db_cats_all = frappe.get_all("Admission Category", fields=["name", "reservation_type"])
            comp_types = [c.name for c in db_cats_all if c.reservation_type == "Compartmentalised Horizontal"]
            horiz_types = [c.name for c in db_cats_all if c.reservation_type == "Horizontal"]
            rejection_statuses = ["Rejected", "Offer Declined", "Offer Expired", "Withdrawn"]

            def get_rejected_count(cat):
                is_comp = False
                for comp_name in comp_types:
                    if cat.startswith(f"{comp_name} ") or cat.startswith(f"{comp_name}("):
                        v_name = cat[len(comp_name):].strip("() ")
                        if v_name == "Common":
                            return len([x for x in applicants_list if getattr(x, status_field, "") in rejection_statuses and _has_trait(x.applicant_id, comp_name, is_shortlist_allocation)])
                        else:
                            return len([x for x in applicants_list if getattr(x, status_field, "") in rejection_statuses and (getattr(x, "vertical_category", "") or getattr(x, "actual_category", "")) == v_name and _has_trait(x.applicant_id, comp_name, is_shortlist_allocation)])
                if cat in horiz_types:
                    return len([x for x in applicants_list if getattr(x, status_field, "") in rejection_statuses and _has_trait(x.applicant_id, cat, is_shortlist_allocation)])
                else:
                    return len([x for x in applicants_list if getattr(x, status_field, "") in rejection_statuses and (getattr(x, "actual_category", "") == cat or getattr(x, "vertical_category", "") == cat)])

            def append_sum(cat, orig, req, filled, w_filled=0, w_req=0):
                row = {
                    "category": cat,
                    "seats": orig,
                    "multiplier": multiplier if is_shortlist_phase else 1.0,
                }
                # Support both Shortlisting and Final Allotment summary formats
                if hasattr(doc, "shortlist_applicants"):
                    row["required_to_shortlist"] = req
                    row["actually_shortlisted"] = filled
                    row["vacant_seats"] = max(0, req - filled)
                else:
                    row["required"] = req
                    row["actually_allocated"] = filled
                    row["total_seats"] = orig
                    row["allocated_seats"] = filled
                    row["vacant_seats"] = max(0, req - filled)
                    row["waitlist_required"] = w_req
                    row["actually_waitlisted"] = w_filled
                    row["actually_rejected"] = get_rejected_count(cat)
                doc.append(summary_table, row)

            # 1. Main Vertical Categories
            for v_cat in ordered_cats:
                v_info = vertical_targets[v_cat]
                append_sum(v_cat, v_info.get("original_seats", 0), v_info["seats"], v_info["filled"], 
                           v_info.get("waitlist_filled", 0) + v_info.get("compartmentalized_waitlist_filled", 0), 
                           v_info.get("waitlist_seats", 0) + v_info.get("compartmentalized_waitlist_seats", 0))
                
            # 2. Horizontal (PWD, Women, etc.)
            for h_info in ordered_h_cats:
                h_cat = h_info["name"]
                h_filled = len([a for a in allocated_list if _has_trait(a.applicant_id, h_cat)])
                append_sum(h_cat, h_info.get("original_seats", 0), h_info["seats"], h_filled)
            
            # 3. Compartmental Breakdown
            for (comp_cat, v_cat), target in compartmental_targets.items():
                if target["original_seats"] > 0:
                    filled_in_v = len([a for a in allocated_list if a.vertical_category == v_cat and _has_trait(a.applicant_id, comp_cat)])
                    append_sum(f"{comp_cat} ({v_cat})", target["original_seats"], target["seats"], filled_in_v)
            
            # 4. Compartmental (Common)
            for comp_row in policy.compartmental_reservations:
                comp_cat = comp_row.category_name
                total_orig = sum(t["original_seats"] for (cc, vc), t in compartmental_targets.items() if cc == comp_cat)
                total_req = sum(t["seats"] for (cc, vc), t in compartmental_targets.items() if cc == comp_cat)
                total_filled = len([a for a in allocated_list if _has_trait(a.applicant_id, comp_cat)])
                if total_req > 0:
                    append_sum(f"{comp_cat} (Common)", total_orig, total_req, total_filled)


    _publish_allocation_progress(doc, 100, "Finalized!", status="Completed")

    return True

def _check_percentile_eligibility(app, vertical_targets, horizontal_targets=None):
    """
    Checks if an applicant meets the minimum percentile threshold for their ACTUAL category.
    Targets are dynamically derived from the Programme Reservation Policy.
    """
    v_traits, _, _ = _get_categorized_traits(app.applicant_id)
    primary_cat = v_traits[0] if v_traits else "General"
    
    thresholds = []
    
    # 1. Base Vertical Threshold
    if primary_cat in vertical_targets:
        v_min = vertical_targets[primary_cat].get("min_percentile")
        if v_min is not None and v_min != "":
            val = float(v_min)
            if val > 0:
                thresholds.append(val)
    
    # 2. Horizontal Overrides (e.g., PWD)
    # Only consider horizontal cutoff if min_percentile is explicitly configured AND > 0
    # (or if h_cat is PWD, apply PWD cutoff if non-zero)
    if horizontal_targets:
        for h_cat, h_info in horizontal_targets.items():
            if _has_trait(app.applicant_id, h_cat):
                h_min = h_info.get("min_percentile")
                if h_min is not None and h_min != "":
                    val = float(h_min)
                    if val > 0:
                        thresholds.append(val)
                elif h_cat == "PWD":
                    thresholds.append(40.0)
    
    # Rule: If multiple thresholds apply (e.g. General 75% + PWD 40%), the most lenient (minimum) applies
    threshold = min(thresholds) if thresholds else 0
        
    percentile = float(getattr(app, "percentile_score", 0) or 0)
    if not percentile and getattr(app, "applicant_id", None):
        er_percentile = frappe.db.get_value("Entrance Test Seat Allocation", {"applicant": app.applicant_id}, "percentile")
        if er_percentile is not None:
            percentile = float(er_percentile)
            
    return percentile >= threshold

def _execute_recursive_displacement(out_cand, allocated_list, unallocated, vertical_targets, status_field, karnataka_vacancies=None, reason=None):
    """
    Displaces a candidate from their current seat.
    If they belong to a reserved category, attempts to re-allocate them to that category pool.
    """
    v_traits, __, __ = _get_categorized_traits(out_cand.applicant_id)
    actual_v_cat = v_traits[0] if v_traits else "General"
    
    # 1. Basic displacement - Decrement current category count if possible
    prev_v = getattr(out_cand, "vertical_category", "")
    if prev_v and prev_v in vertical_targets:
        vertical_targets[prev_v]["filled"] -= 1

    if out_cand in allocated_list:
        allocated_list.remove(out_cand)
    unallocated.append(out_cand)
    setattr(out_cand, status_field, "Rejected")
    out_cand.allocation_type = "Not Allocated"
    out_cand.vertical_category = ""
    
    if reason:
        out_cand.remarks = reason
    elif not getattr(out_cand, "remarks", None):
        out_cand.remarks = f"Displaced from {prev_v or 'allocated seat'} due to quota adjustment"

    # 2. Fall-back to Reserved Category if they were in General
    # Only fall back if they were displaced from a DIFFERENT category (e.g., General -> SC).
    if actual_v_cat != "General" and actual_v_cat != prev_v:
        v_info = vertical_targets.get(actual_v_cat)
        if v_info:
            kv_count = (karnataka_vacancies or {}).get(actual_v_cat, 0)
            if v_info["filled"] < (v_info["seats"] - kv_count):
                _assign_seat_to_applicant(out_cand, actual_v_cat, "Reserved", allocated_list, unallocated, v_info, status_field)
                out_cand.remarks = f"Re-allocated to {actual_v_cat} reserved seat after displacement from General category"
            else:
                # Pool full, try to displace lowest in THEIR category
                candidates_in_v = [a for a in allocated_list if a.vertical_category == actual_v_cat]
                if candidates_in_v:
                    candidates_in_v.sort(key=lambda x: -(x.overall_rank or 999999))
                    
                    # Preference: Displace candidates with no special traits (AI) to protect quotas
                    def has_any_special_trait(app_id):
                        v, h, c = _get_categorized_traits(app_id)
                        return bool(h or c)

                    ai_in_v = [a for a in candidates_in_v if not has_any_special_trait(a.applicant_id)]
                    
                    lowest_cand = ai_in_v[0] if ai_in_v else candidates_in_v[0]
                    
                    if (out_cand.overall_rank or 999999) < (lowest_cand.overall_rank or 999999):
                        _execute_candidate_displacement(out_cand, lowest_cand, allocated_list, unallocated, status_field)
                        out_cand.remarks = f"Re-allocated to {actual_v_cat} reserved seat after displacement from General category"
                        disp_reason = f"Displaced from {actual_v_cat} reserved category by higher merit candidate ({out_cand.candidate_name or out_cand.applicant_id}) returning from General list"
                        _execute_recursive_displacement(lowest_cand, allocated_list, unallocated, vertical_targets, status_field, karnataka_vacancies, reason=disp_reason)

def _assign_seat_to_applicant(app, vertical_cat, alloc_type, allocated_list, unallocated, v_info, status_field):
    status_value = "Selected"
    if status_field == "shortlist_status": status_value = "Shortlisted"
    
    setattr(app, status_field, status_value)
    app.vertical_category = vertical_cat
    app.allocation_type = alloc_type
    
    # Synchronization of category strings for UI (e.g. SC+Women)
    v_traits, h_traits, c_traits = _get_categorized_traits(app.applicant_id)
    
    # Also populate separate fields for the before_save hook in Seat Allocation
    if hasattr(app, "horizontal_categories"):
        app.horizontal_categories = ", ".join(h_traits) if h_traits else ""
    
    # Robust mapping for compartmentalized traits (supporting multiple field names)
    c_val = c_traits[0] if c_traits else ""
    if hasattr(app, "compartmentalized_category"):
        app.compartmentalized_category = c_val
    if hasattr(app, "compartment_category"):
        app.compartment_category = c_val
    if hasattr(app, "horizontal_compartmentalized"):
        app.horizontal_compartmentalized = c_val
    
    # We want the Allocated Vertical Category first, then any other traits
    parts = [vertical_cat]
    
    # Add other traits but avoid duplicates (case-insensitive)
    existing = [vertical_cat.lower()]
    for trait in (c_traits + h_traits):
        if not trait: continue
        if trait.lower() not in existing:
            parts.append(trait)
            existing.append(trait.lower())
    
    display_field = "allocated_category" if hasattr(app, "allocated_category") else "shortlist_category"
    setattr(app, display_field, " + ".join(parts))

    # Populating default selection remarks if no specific displacement/tie remark already exists
    if not getattr(app, "remarks", None):
        rank_val = getattr(app, "overall_rank", None) or getattr(app, "shortlist_rank", None) or ""
        score_val = getattr(app, "total_score", None) or getattr(app, "nlsat_part_a_score", None) or ""
        act_cat = getattr(app, "actual_category", None) or "General"
        score_str = f" (Score: {score_val})" if score_val else ""
        if vertical_cat == "General":
            if act_cat != "General":
                app.remarks = f"Allocated seat under General (Open Merit) via Merit Migration from {act_cat} based on Final Rank #{rank_val}{score_str}"
            else:
                app.remarks = f"Allocated seat under General (Open Merit) based on Final Rank #{rank_val}{score_str}"
        else:
            cat_rank = getattr(app, "category_rank", None) or ""
            cat_rank_str = f" Category Rank #{cat_rank}," if cat_rank else ""
            app.remarks = f"Allocated seat under {vertical_cat} Reserved Quota based on{cat_rank_str} Final Rank #{rank_val}{score_str}"
    
    v_info["filled"] += 1
    allocated_list.append(app)
    if app in unallocated:
        unallocated.remove(app)

def _execute_candidate_displacement(in_cand, out_cand, allocated_list, unallocated, status_field):
    """Simple displacement logic for Karnataka/Horizontal swaps."""
    v_cat = out_cand.vertical_category
    a_type = out_cand.allocation_type
    
    setattr(out_cand, status_field, "Rejected")
    out_cand.allocation_type = "Not Allocated"
    out_cand.vertical_category = ""
    if out_cand in allocated_list:
        allocated_list.remove(out_cand)
    unallocated.append(out_cand)
    
    _assign_seat_to_applicant(in_cand, v_cat, a_type, allocated_list, unallocated, {"filled": 0}, status_field)
    # The {"filled": 0} is a dummy as _assign_seat_to_applicant increments it, but we are just swapping.
    # We should actually pass the correct v_info but for a swap it doesn't change the total filled count.
    # To be safe, we'll sort the final list later.
    allocated_list.sort(key=lambda x: (-(float(getattr(x, "total_score", 0) or 0)), (x.overall_rank or 999999)))

def _calculate_and_sync_percentiles(applicants, is_shortlist=False):
    """
    Calculates percentiles based on the current pool of applicants and 
    updates the Eligibility Result records in the database.

    Formula: (# candidates with score <= this candidate's score) / (total candidates) * 100

    Score field used:
    - Shortlisting stage:  nlsat_part_a_score  (Part A)
    - Final stage:         total_score          (Part A + Part B)
    """
    import bisect

    if not applicants:
        return

    # 1. Determine the score field based on processing stage
    def _get_score(app):
        def _val(obj, key):
            if isinstance(obj, dict):
                return obj.get(key)
            return getattr(obj, key, None)

        if is_shortlist:
            v = _val(app, "nlsat_part_a_score")
            if v is None or v == "":
                v = _val(app, "entrance_score")
            if v is None or v == "":
                v = _val(app, "total_score")
            return float(v or 0)
        val = float(_val(app, "total_score") or 0)
        if val == 0:
            val = float(_val(app, "nlsat_part_a_score") or _val(app, "entrance_score") or 0)
        return val

    # 2. Collect and sort all scores
    all_scores = sorted([_get_score(a) for a in applicants])
    total_count = len(all_scores)

    if total_count == 0:
        return

    # 3. Calculate cumulative percentiles and persist
    updates = []  # (applicant_id, percentile)
    for app in applicants:
        score = _get_score(app)
        count_le = bisect.bisect_left(all_scores, score)  # # scores < this score
        percentile = round((count_le / total_count) * 100, 4)
        if isinstance(app, dict):
            app["percentile_score"] = percentile
            app_id = app.get("applicant_id")
        else:
            app.percentile_score = percentile
            app_id = getattr(app, "applicant_id", None)

        if app_id:
            updates.append((app_id, percentile))

    # 4. Bulk update Entrance Test Seat Allocation.
    if getattr(frappe, "db", None) and hasattr(frappe.db, "exists"):
        for applicant_id, percentile in updates:
            if frappe.db.exists("Entrance Test Seat Allocation", applicant_id):
                frappe.db.set_value("Entrance Test Seat Allocation", applicant_id, "percentile", percentile, update_modified=False)

        if hasattr(frappe.db, "commit"):
            frappe.db.commit()


def execute_part_a_shortlisting(doc):
    """
    Executes Part A shortlisting based on user's exact specification.
    """
    clear_category_cache()

    child_table = None
    status_field = "status"
    if hasattr(doc, "shortlist_applicants"):
        child_table = "shortlist_applicants"
        status_field = "shortlist_status"
    elif hasattr(doc, "merit_applicants"):
        child_table = "merit_applicants"
    if not child_table:
        return False

    applicants = getattr(doc, child_table)

    # 1. Reset all fields on all rows first (Regeneration cleanup)
    for row in applicants:
        row.shortlist_rank = 0
        row.category_rank = 0
        row.vertical_category = ""
        row.allocation_type = "Not Allocated"
        row.compartmentalized_category = ""
        row.horizontal_categories = ""
        row.shortlist_category = ""
        if hasattr(row, "remarks"):
            row.remarks = ""
        setattr(row, status_field, "Draft")

    _rank_applicants(applicants, use_advanced_ranking=True, processing_stage="Part A Ranking")
    policy = None
    multiplier = 1.0
    if getattr(doc, "program", None) and getattr(doc, "admission_cycle", None):
        policy_name = frappe.db.get_value("Programme Reservation Policy", {
            "admission_cycle": doc.admission_cycle,
            "program": doc.program
        }, "name")
        if not policy_name:
            frappe.throw(
                f"No Programme Reservation Policy found for Program '{doc.program}' in Admission Cycle '{doc.admission_cycle}'. "
                f"Please create and configure a Programme Reservation Policy for this program first.",
                title="Missing Reservation Policy"
            )
        policy = frappe.get_doc("Programme Reservation Policy", policy_name)
        mult_val = policy.get("shortlisting_multiplier")
        multiplier = 1.0 if mult_val is None else float(mult_val)

    # Determine dynamic compartmental category name
    comp_cat = "Karnataka"
    if policy and policy.compartmental_reservations:
        for comp in policy.compartmental_reservations:
            comp_cat = comp.category_name or "Karnataka"
            break
    comp_key = comp_cat.lower()

    # Determine vertical categories dynamically
    vertical_cats = ["General", "SC", "ST", "OBC-NCL", "EWS"]
    if policy:
        vertical_cats = []
        for v in policy.categories:
            v_name = v.category_name or "General"
            if v_name not in vertical_cats:
                vertical_cats.append(v_name)
        if "General" not in vertical_cats:
            vertical_cats.append("General")

    # 2. Filter & prepare eligible candidates pool
    eligible_applicants = []
    for row in applicants:
        # Fetch Entrance Test Seat Allocation (or use row attributes if mock/test)
        try:
            etsa_doc = frappe.get_doc("Entrance Test Seat Allocation", row.applicant_id)
            part_a_score = etsa_doc.part_a_total_marks_scored
            et_status = etsa_doc.entrance_test_status
            result_status = etsa_doc.result_status
        except Exception:
            etsa_doc = None
            part_a_score = None
            et_status = "Attended"
            result_status = "Pass"

        if part_a_score is None:
            part_a_score = getattr(row, "nlsat_part_a_score", None) or getattr(row, "entrance_score", None) or getattr(row, "total_score", None) or 0
        
        if (et_status or "Attended") == "Attended" and (result_status or "Pass") == "Pass" and part_a_score > 0:
            # Sync scores to row
            row.nlsat_part_a_score = part_a_score
            if hasattr(row, "total_score"):
                row.total_score = part_a_score
            
            cats = get_applicant_categories(row.applicant_id)
            
            # Map vertical category dynamically
            matched_v = "General"
            for v_cat_name in vertical_cats:
                if v_cat_name != "General" and v_cat_name in cats:
                    matched_v = v_cat_name
                    break
            row.actual_category = matched_v
            
            # Map traits for shortlist processing
            row.is_karnataka = (comp_cat in cats)
            row.is_pwd = ("PWD" in cats)
            row.is_female = ("Women" in cats)
            
            eligible_applicants.append(row)

    # 3. Sort overall candidates by Part A score desc
    def get_part_a_stable_key(x):
        score = float(getattr(x, "nlsat_part_a_score", 0) or 0)
        return (-score,)

    eligible_applicants.sort(key=get_part_a_stable_key)


    # 4. Assign overall rank using standard competition ranking
    current_rank = 1
    for i, row in enumerate(eligible_applicants):
        if i > 0:
            if row.nlsat_part_a_score != eligible_applicants[i-1].nlsat_part_a_score:
                current_rank = i + 1
        row.shortlist_rank = current_rank
        if hasattr(row, "overall_rank"):
            row.overall_rank = current_rank

    # 4b. Calculate and sync Part A percentile scores for eligible applicants
    grouped_by_prog = {}
    for row in eligible_applicants:
        p_key = getattr(row, "program", None) or getattr(doc, "program", None) or "Default"
        grouped_by_prog.setdefault(p_key, []).append(row)

    for _prog_applicants in grouped_by_prog.values():
        _calculate_and_sync_percentiles(_prog_applicants, is_shortlist=True)

    # 4c. Filter by minimum percentile eligibility threshold from Programme Reservation Policy (if enabled)
    apply_pct_shortlisting = bool(getattr(policy, "apply_percentile_cutoff_for_shortlisting", 0)) if policy else False
    if policy and apply_pct_shortlisting:
        vertical_targets_pct = {}
        horizontal_targets_pct = {}
        for v in policy.categories:
            v_cat_name = v.category_name or "General"
            vertical_targets_pct[v_cat_name] = {"min_percentile": v.min_percentile}
        for h in policy.horizontal_reservations:
            horizontal_targets_pct[h.category_name] = {"min_percentile": h.min_percentile}

        percentile_eligible = []
        for app in eligible_applicants:
            if _check_percentile_eligibility(app, vertical_targets_pct, horizontal_targets_pct):
                percentile_eligible.append(app)
            else:
                setattr(app, status_field, "Rejected")
                app.allocation_type = "Not Allocated"
                if hasattr(app, "remarks"):
                    app.remarks = "Did not meet minimum percentile threshold"
        eligible_applicants = percentile_eligible

    targets = {
        "PWD": 30,
        "Women": 180
    }
    defaults_fallback = {
        "General": {"total": 245, "karnataka": 60, comp_key: 60},
        "SC": {"total": 90, "karnataka": 20, comp_key: 20},
        "ST": {"total": 45, "karnataka": 10, comp_key: 10},
        "OBC-NCL": {"total": 160, "karnataka": 40, comp_key: 40},
        "EWS": {"total": 60, "karnataka": 15, comp_key: 15},
    }
    for v_cat_name in vertical_cats:
        if v_cat_name in defaults_fallback:
            targets[v_cat_name] = defaults_fallback[v_cat_name].copy()
        else:
            targets[v_cat_name] = {"total": 0, "karnataka": 0, comp_key: 0}

    if policy:
        total_eligible_count = len(eligible_applicants)
        # 1. Main vertical categories
        for v in policy.categories:
            v_cat_name = v.category_name or "General"
            if multiplier == 0:
                req_seats = total_eligible_count
            else:
                req_seats = v.get("shortlisting_target")
                if not req_seats:
                    req_seats = int((v.seats or 0) * multiplier)
            if v_cat_name not in targets:
                targets[v_cat_name] = {}
            targets[v_cat_name]["total"] = req_seats

        # 2. Compartmental (sub-quotas inside each vertical category)
        comp_percentage = 25.0
        for comp in policy.compartmental_reservations:
            if comp.category_name == comp_cat:
                comp_percentage = comp.percentage or 25.0
                break

        policy_seats = {v.category_name or "General": v.seats or 0 for v in policy.categories}
        for cat in vertical_cats:
            v_seats = policy_seats.get(cat, 0)
            comp_seats = int((v_seats * comp_percentage) / 100.0)
            if multiplier == 0:
                targets[cat][comp_key] = total_eligible_count
            else:
                targets[cat][comp_key] = int(comp_seats * multiplier)

        # 3. Horizontal reservations (Women, PWD)
        for h in policy.horizontal_reservations:
            h_name = h.category_name
            if not h_name: continue
            if multiplier == 0:
                req_seats = total_eligible_count
            else:
                req_seats = h.get("shortlisting_target")
                if not req_seats:
                    req_seats = int((h.seats or 0) * multiplier)
            targets[h_name] = req_seats

    # 5. General shortlist (Select top candidates)
    general_shortlist = eligible_applicants[:targets["General"]["total"]]

    # 6. Compartmental fill for General
    all_karnataka_available = len([x for x in eligible_applicants if x.is_karnataka])
    kar_req_gen = targets["General"].get(comp_key, 0)
    gen_deficit = max(0, kar_req_gen - all_karnataka_available)

    karnataka_count = len([x for x in general_shortlist if x.is_karnataka])
    if karnataka_count < kar_req_gen:
        remaining_karnataka = [x for x in eligible_applicants[targets["General"]["total"]:] if x.is_karnataka]
        to_add = remaining_karnataka[:kar_req_gen - karnataka_count]
        for kar_cand in to_add:
            # Find and displace the lowest ranked non-Karnataka candidate in general_shortlist
            for idx in range(len(general_shortlist) - 1, -1, -1):
                if not general_shortlist[idx].is_karnataka:
                    displaced_cand = general_shortlist.pop(idx)
                    displaced_cand.remarks = f"Displaced from General shortlist to accommodate Karnataka sub-quota candidate {kar_cand.candidate_name or kar_cand.applicant_id} ({kar_cand.applicant_id})"
                    kar_cand.remarks = f"Shortlisted under {comp_cat} General Sub-quota displacing {displaced_cand.candidate_name or displaced_cand.applicant_id} ({displaced_cand.applicant_id})"
                    general_shortlist.append(kar_cand)
                    break

    # Ensure All-India candidates do not exceed their quota, leaving unfilled Karnataka seats vacant
    if multiplier != 0:
        max_ai_allowed = targets["General"]["total"] - kar_req_gen
        ai_in_shortlist = [x for x in general_shortlist if not x.is_karnataka]
        excess_ai = len(ai_in_shortlist) - max_ai_allowed
        if excess_ai > 0:
            removed_count = 0
            for idx in range(len(general_shortlist) - 1, -1, -1):
                if not general_shortlist[idx].is_karnataka:
                    displaced_cand = general_shortlist.pop(idx)
                    displaced_cand.remarks = "Displaced from General shortlist as All-India quota limit was reached for unfilled Karnataka seats"
                    removed_count += 1
                    if removed_count == excess_ai:
                        break

    targets["General"]["total"] = len(general_shortlist)

    # 7. Reserved category shortlisting
    reserved_rules = []
    for v_cat_name in vertical_cats:
        if v_cat_name != "General":
            reserved_rules.append({
                "cat": v_cat_name,
                "total": targets[v_cat_name]["total"],
                "karnataka": targets[v_cat_name].get(comp_key, 0)
            })

    shortlists = {
        "General": general_shortlist
    }

    for rule in reserved_rules:
        cat = rule["cat"]
        total_req = rule["total"]
        kar_req = rule["karnataka"]
        
        # Pool strictly belonging to this vertical category, excluding general_shortlist
        pool = [x for x in eligible_applicants if x.actual_category == cat and x not in general_shortlist]
        
        # Calculate available Karnataka candidates strictly in this category's pool
        all_karnataka_available = len([x for x in pool if x.is_karnataka])
        deficit = max(0, kar_req - all_karnataka_available)

        # Initial candidates up to total required
        cat_shortlist = pool[:total_req]
        
        # Karnataka compartmentalized sub-quota check inside this category shortlist
        karnataka_count = len([x for x in cat_shortlist if x.is_karnataka])
        if karnataka_count < kar_req:
            remaining_karnataka = [x for x in pool[total_req:] if x.is_karnataka]
            to_add = remaining_karnataka[:kar_req - karnataka_count]
            for kar_cand in to_add:
                # Find and displace the lowest ranked non-Karnataka candidate in cat_shortlist
                for idx in range(len(cat_shortlist) - 1, -1, -1):
                    if not cat_shortlist[idx].is_karnataka:
                        displaced_cand = cat_shortlist.pop(idx)
                        displaced_cand.remarks = f"Displaced from {cat} shortlist to accommodate Karnataka sub-quota candidate {kar_cand.candidate_name or kar_cand.applicant_id} ({kar_cand.applicant_id})"
                        kar_cand.remarks = f"Shortlisted under {comp_cat} {cat} Sub-quota displacing {displaced_cand.candidate_name or displaced_cand.applicant_id} ({displaced_cand.applicant_id})"
                        cat_shortlist.append(kar_cand)
                        break

        # Ensure All-India candidates do not exceed their quota, leaving unfilled Karnataka seats vacant
        max_ai_allowed = total_req - kar_req
        ai_in_shortlist = [x for x in cat_shortlist if not x.is_karnataka]
        excess_ai = len(ai_in_shortlist) - max_ai_allowed
        if excess_ai > 0:
            removed_count = 0
            for idx in range(len(cat_shortlist) - 1, -1, -1):
                if not cat_shortlist[idx].is_karnataka:
                    displaced_cand = cat_shortlist.pop(idx)
                    displaced_cand.remarks = f"Displaced from {cat} shortlist as All-India quota limit was reached for unfilled Karnataka seats"
                    removed_count += 1
                    if removed_count == excess_ai:
                        break

        targets[cat]["total"] = len(cat_shortlist)
        shortlists[cat] = cat_shortlist

    # --- 7b. Apply PWD Horizontal Reservation First ---
    def get_all_selected():
        res = []
        for s_list in shortlists.values():
            res.extend(s_list)
        return res

    all_selected = get_all_selected()
    selected_set = {x.applicant_id for x in all_selected}
    pwd_count = sum(1 for x in all_selected if x.is_pwd)
    
    women_count = None
    
    def accommodate_displaced_candidate(displaced_cand, shortlist_name):
        if displaced_cand.applicant_id in selected_set:
            selected_set.remove(displaced_cand.applicant_id)
            
        if shortlist_name == "General":
            v_cat = displaced_cand.actual_category
            if v_cat != "General":
                target_list = shortlists[v_cat]
                target_total = targets[v_cat]["total"]
                
                if len(target_list) < target_total:
                    target_list.append(displaced_cand)
                    displaced_cand.remarks = f"Shortlisted in {v_cat} reserved pool after displacement from General shortlist"
                    selected_set.add(displaced_cand.applicant_id)
                else:
                    displaceable = [
                        (idx, x) for idx, x in enumerate(target_list)
                        if not x.is_pwd and not (women_count is not None and x.is_female)
                    ]
                    if displaceable:
                        # Prefer to displace non-Karnataka candidates if the incoming displaced candidate is not Karnataka
                        if not displaced_cand.is_karnataka:
                            non_kar = [p for p in displaceable if not p[1].is_karnataka]
                            if non_kar:
                                displaceable = non_kar
                        lowest_idx, lowest_in_r = max(displaceable, key=lambda pair: (pair[1].shortlist_rank or 999999))
                        if (displaced_cand.shortlist_rank or 0) < (lowest_in_r.shortlist_rank or 999999):
                            target_list.pop(lowest_idx)
                            lowest_in_r.remarks = f"Displaced from {v_cat} shortlist by higher merit candidate ({displaced_cand.candidate_name or displaced_cand.applicant_id}) returning from General list"
                            target_list.append(displaced_cand)
                            displaced_cand.remarks = f"Shortlisted in {v_cat} reserved pool after displacement from General shortlist"
                            selected_set.remove(lowest_in_r.applicant_id)
                            selected_set.add(displaced_cand.applicant_id)
    
    if pwd_count < targets["PWD"]:
        remaining_pwd = [x for x in eligible_applicants if x.is_pwd and x.applicant_id not in selected_set]
        pwd_to_add = remaining_pwd[:targets["PWD"] - pwd_count]
        
        for pwd_cand in pwd_to_add:
            cat = pwd_cand.actual_category
            shortlist = shortlists[cat]
            
            displaced = False
            # 1. Try to find lowest-ranked non-PWD in same compartment (Karnataka vs All-India)
            same_compartment = [
                (idx, x) for idx, x in enumerate(shortlist)
                if not x.is_pwd and x.is_karnataka == pwd_cand.is_karnataka
            ]
            if same_compartment:
                lowest_idx, lowest_cand = max(same_compartment, key=lambda pair: (pair[1].shortlist_rank or 999999))
                shortlist.pop(lowest_idx)
                lowest_cand.remarks = f"Displaced from {cat} shortlist to accommodate PWD horizontal reservation candidate {pwd_cand.candidate_name or pwd_cand.applicant_id} ({pwd_cand.applicant_id})"
                pwd_cand.remarks = f"Shortlisted under PWD Horizontal Reservation displacing {lowest_cand.candidate_name or lowest_cand.applicant_id} ({lowest_cand.applicant_id})"
                shortlist.append(pwd_cand)
                accommodate_displaced_candidate(lowest_cand, cat)
                selected_set.add(pwd_cand.applicant_id)
                displaced = True
            
            # 2. Try to find lowest-ranked non-PWD in same vertical category
            if not displaced:
                same_cat = [
                    (idx, x) for idx, x in enumerate(shortlist)
                    if not x.is_pwd
                ]
                if same_cat:
                    lowest_idx, lowest_cand = max(same_cat, key=lambda pair: (pair[1].shortlist_rank or 999999))
                    shortlist.pop(lowest_idx)
                    lowest_cand.remarks = f"Displaced from {cat} shortlist to accommodate PWD horizontal reservation candidate {pwd_cand.candidate_name or pwd_cand.applicant_id} ({pwd_cand.applicant_id})"
                    pwd_cand.remarks = f"Shortlisted under PWD Horizontal Reservation displacing {lowest_cand.candidate_name or lowest_cand.applicant_id} ({lowest_cand.applicant_id})"
                    shortlist.append(pwd_cand)
                    accommodate_displaced_candidate(lowest_cand, cat)
                    selected_set.add(pwd_cand.applicant_id)
                    displaced = True
                    
            if not displaced:
                # Append directly if no displacement possible
                shortlist.append(pwd_cand)
                selected_set.add(pwd_cand.applicant_id)

    # --- 7c. Apply Women Horizontal Reservation Second ---
    def get_pwd_total():
        all_sel = get_all_selected()
        return sum(1 for x in all_sel if x.is_pwd)

    all_selected = get_all_selected()
    selected_set = {x.applicant_id for x in all_selected}
    women_count = sum(1 for x in all_selected if x.is_female)
    
    if women_count < targets["Women"]:
        remaining_female = [x for x in eligible_applicants if x.is_female and x.applicant_id not in selected_set]
        female_to_add = remaining_female[:targets["Women"] - women_count]
        
        for female_cand in female_to_add:
            cat = female_cand.actual_category
            shortlist = shortlists[cat]
            
            displaced = False
            
            # Preference 1: Male, Non-PWD, Same Compartment
            cands_1 = [
                (idx, x) for idx, x in enumerate(shortlist)
                if not x.is_female and not x.is_pwd and x.is_karnataka == female_cand.is_karnataka
            ]
            if cands_1:
                lowest_idx, lowest_cand = max(cands_1, key=lambda pair: (pair[1].shortlist_rank or 999999))
                shortlist.pop(lowest_idx)
                lowest_cand.remarks = f"Displaced from {cat} shortlist to accommodate Women horizontal reservation candidate {female_cand.candidate_name or female_cand.applicant_id} ({female_cand.applicant_id})"
                female_cand.remarks = f"Shortlisted under Women Horizontal Reservation displacing {lowest_cand.candidate_name or lowest_cand.applicant_id} ({lowest_cand.applicant_id})"
                shortlist.append(female_cand)
                accommodate_displaced_candidate(lowest_cand, cat)
                selected_set.add(female_cand.applicant_id)
                displaced = True
                
            # Preference 2: Male, Non-PWD, Any Compartment
            if not displaced:
                cands_2 = [
                    (idx, x) for idx, x in enumerate(shortlist)
                    if not x.is_female and not x.is_pwd
                ]
                if cands_2:
                    lowest_idx, lowest_cand = max(cands_2, key=lambda pair: (pair[1].shortlist_rank or 999999))
                    shortlist.pop(lowest_idx)
                    lowest_cand.remarks = f"Displaced from {cat} shortlist to accommodate Women horizontal reservation candidate {female_cand.candidate_name or female_cand.applicant_id} ({female_cand.applicant_id})"
                    female_cand.remarks = f"Shortlisted under Women Horizontal Reservation displacing {lowest_cand.candidate_name or lowest_cand.applicant_id} ({lowest_cand.applicant_id})"
                    shortlist.append(female_cand)
                    accommodate_displaced_candidate(lowest_cand, cat)
                    selected_set.add(female_cand.applicant_id)
                    displaced = True
                    
            # Preference 3: Male, PWD, Same Compartment (Protect PWD >= targets["PWD"])
            if not displaced:
                cands_3 = [
                    (idx, x) for idx, x in enumerate(shortlist)
                    if not x.is_female and x.is_pwd and x.is_karnataka == female_cand.is_karnataka
                ]
                if cands_3 and get_pwd_total() - 1 >= targets["PWD"]:
                    lowest_idx, lowest_cand = max(cands_3, key=lambda pair: (pair[1].shortlist_rank or 999999))
                    shortlist.pop(lowest_idx)
                    shortlist.append(female_cand)
                    accommodate_displaced_candidate(lowest_cand, cat)
                    selected_set.add(female_cand.applicant_id)
                    displaced = True
                    
            # Preference 4: Male, PWD, Any Compartment (Protect PWD >= targets["PWD"])
            if not displaced:
                cands_4 = [
                    (idx, x) for idx, x in enumerate(shortlist)
                    if not x.is_female and x.is_pwd
                ]
                if cands_4 and get_pwd_total() - 1 >= targets["PWD"]:
                    lowest_idx, lowest_cand = max(cands_4, key=lambda pair: (pair[1].shortlist_rank or 999999))
                    shortlist.pop(lowest_idx)
                    shortlist.append(female_cand)
                    accommodate_displaced_candidate(lowest_cand, cat)
                    selected_set.add(female_cand.applicant_id)
                    displaced = True
                    
            if not displaced:
                # Append directly if no displacement possible
                shortlist.append(female_cand)
                selected_set.add(female_cand.applicant_id)

    # Helper function to assign a shortlisted candidate
    def assign_candidate(candidate_row, vertical_cat, alloc_type):
        candidate_row.vertical_category = vertical_cat
        candidate_row.allocation_type = alloc_type
        setattr(candidate_row, status_field, "Shortlisted" if status_field == "shortlist_status" else "Selected")
        
        # Build horizontal/compartmentalized categories
        h_traits = []
        if candidate_row.is_female:
            h_traits.append("Women")
        if candidate_row.is_pwd:
            h_traits.append("PWD")
        candidate_row.horizontal_categories = ", ".join(h_traits)
        
        if candidate_row.is_karnataka:
            candidate_row.compartmentalized_category = comp_cat
        else:
            candidate_row.compartmentalized_category = ""
            
        # Build display category
        parts = [vertical_cat]
        if candidate_row.is_karnataka:
            parts.append(comp_cat)
        if candidate_row.is_female:
            parts.append("Women")
        if candidate_row.is_pwd:
            parts.append("PWD")
            
        display_field = "allocated_category" if hasattr(candidate_row, "allocated_category") else "shortlist_category"
        setattr(candidate_row, display_field, " + ".join(parts))

        # Default remarks if not already populated by a specific displacement or tie event
        if not getattr(candidate_row, "remarks", None):
            rank_val = getattr(candidate_row, "shortlist_rank", None) or getattr(candidate_row, "overall_rank", None) or ""
            score_val = getattr(candidate_row, "nlsat_part_a_score", None) or getattr(candidate_row, "total_score", None) or ""
            act_cat = getattr(candidate_row, "actual_category", None) or "General"
            score_str = f" (Score: {score_val})" if score_val else ""
            if vertical_cat == "General":
                if act_cat != "General":
                    candidate_row.remarks = f"Shortlisted under General (Open Merit) via Merit Migration from {act_cat} based on Part A Rank #{rank_val}{score_str}"
                else:
                    candidate_row.remarks = f"Shortlisted under General (Open Merit) based on Part A Rank #{rank_val}{score_str}"
            else:
                cat_rank = getattr(candidate_row, "category_rank", None) or ""
                cat_rank_str = f" Category Rank #{cat_rank}," if cat_rank else ""
                candidate_row.remarks = f"Shortlisted under {vertical_cat} Reserved Quota based on{cat_rank_str} Part A Rank #{rank_val}{score_str}"

    # --- 7c.5 Add Tie Candidates (Option A) ---
    for cat_name in list(shortlists.keys()):
        s_list = shortlists[cat_name]
        if not s_list:
            continue
        lowest_score = min(float(getattr(x, "nlsat_part_a_score", 0) or 0) for x in s_list)
        current_selected_ids = {x.applicant_id for x in get_all_selected()}
        
        tie_candidates = []
        for cand in eligible_applicants:
            if cand.applicant_id in current_selected_ids:
                continue
            cand_score = float(getattr(cand, "nlsat_part_a_score", 0) or 0)
            if abs(cand_score - lowest_score) < 0.0001:
                if cat_name == "General" or cand.actual_category == cat_name:
                    tie_candidates.append(cand)
                    
        for tie_cand in tie_candidates:
            tie_cand.remarks = f"Shortlisted under {cat_name} List due to Cutoff Score Tie (Score: {getattr(tie_cand, 'nlsat_part_a_score', '')}, Part A Rank #{getattr(tie_cand, 'shortlist_rank', '')})"
            s_list.append(tie_cand)

    # --- 7d. Assignment & Sanitization Pass ---
    all_final_selected = get_all_selected()
    final_selected_set = {x.applicant_id for x in all_final_selected}
    
    # Assign properties to all selected candidates
    for cat_name, s_list in shortlists.items():
        alloc_type = "Open" if cat_name == "General" else "Reserved"
        for row in s_list:
            assign_candidate(row, cat_name, alloc_type)
            
    # Mark candidates not selected as Rejected / Not Allocated
    for row in applicants:
        if row.applicant_id not in final_selected_set:
            if multiplier == 0 and hasattr(row, "nlsat_part_a_score") and float(row.nlsat_part_a_score or 0) > 0:
                assign_candidate(row, getattr(row, "actual_category", "General") or "General", "Open")
                continue
            row.vertical_category = ""
            row.allocation_type = "Not Allocated"
            setattr(row, status_field, "Rejected")
            if hasattr(row, "remarks") and not row.remarks:
                rank_val = getattr(row, "shortlist_rank", None) or getattr(row, "overall_rank", None) or ""
                score_val = getattr(row, "nlsat_part_a_score", None) or getattr(row, "total_score", None) or ""
                act_cat = getattr(row, "actual_category", None) or "General"
                row.remarks = f"Not shortlisted: Exceeded {act_cat} category quota cutoff (Part A Rank #{rank_val}, Score: {score_val})"
            row.compartmentalized_category = ""
            row.horizontal_categories = ""
            display_field = "allocated_category" if hasattr(row, "allocated_category") else "shortlist_category"
            setattr(row, display_field, "")

    # 8. Assign Category Rank for all eligible applicants
    from collections import defaultdict
    category_pools = defaultdict(list)
    for row in eligible_applicants:
        category_pools[row.actual_category].append(row)
        
    for cat, cat_list in category_pools.items():
        cat_list.sort(key=get_part_a_stable_key)
        current_cat_rank = 1
        for i, row in enumerate(cat_list):
            if i > 0:
                if row.nlsat_part_a_score != cat_list[i-1].nlsat_part_a_score:
                    current_cat_rank = i + 1
            row.category_rank = current_cat_rank

    # 9. Perform Validation & Logs
    # 9. Perform Validation & Logs
    total_selected = len([x for x in applicants if getattr(x, status_field) in ["Shortlisted", "Selected"]])
    pwd_selected = len([x for x in applicants if getattr(x, status_field) in ["Shortlisted", "Selected"] and x.is_pwd])
    women_selected = len([x for x in applicants if getattr(x, status_field) in ["Shortlisted", "Selected"] and x.is_female])

    actual_ews_count = 0
    for row in applicants:
        cats = get_applicant_categories(row.applicant_id)
        if "EWS" in cats:
            actual_ews_count += 1

    logs = [
        f"Validation Logs after shortlisting generation:",
        f"- Total selected count: {total_selected}"
    ]
    for v_cat_name in vertical_cats:
        v_sel = len([x for x in applicants if getattr(x, status_field) in ["Shortlisted", "Selected"] and x.vertical_category == v_cat_name])
        v_comp = len([x for x in applicants if getattr(x, status_field) in ["Shortlisted", "Selected"] and x.vertical_category == v_cat_name and x.is_karnataka])
        logs.append(f"- {v_cat_name} selected count: {v_sel} ({comp_cat}: {v_comp})")

    logs.append(f"- PWD selected count: {pwd_selected}")
    logs.append(f"- Women selected count: {women_selected}")
    logs.append(f"- Actual EWS candidate count in Applicants: {actual_ews_count}")

    validation_log = "\n".join(logs)
    frappe.logger().info(validation_log)
    # frappe.msgprint(validation_log, title="Validation Log")
 
    # 1. throw error if Any EWS selected candidate does not have EWS category
    for row in applicants:
        if getattr(row, status_field) in ["Shortlisted", "Selected"] and row.vertical_category == "EWS":
            cats = get_applicant_categories(row.applicant_id)
            if "EWS" not in cats:
                frappe.throw(f"Validation failed: Selected EWS candidate {row.applicant_id} is not EWS in Entrance Test Seat Allocation.")

    # 2. throw error if Any selected candidate has Part A Marks <= 0
    for row in applicants:
        if getattr(row, status_field) in ["Shortlisted", "Selected"]:
            etsa_doc = frappe.get_doc("Entrance Test Seat Allocation", row.applicant_id)
            if (etsa_doc.part_a_total_marks_scored or 0) <= 0:
                frappe.throw(f"Validation failed: Selected candidate {row.applicant_id} has Part A Marks <= 0.")

    # 3. throw error if Any selected candidate has Entrance Test Status != Attended
    for row in applicants:
        if getattr(row, status_field) in ["Shortlisted", "Selected"]:
            etsa_doc = frappe.get_doc("Entrance Test Seat Allocation", row.applicant_id)
            if etsa_doc.entrance_test_status != "Attended":
                frappe.throw(f"Validation failed: Selected candidate {row.applicant_id} has Entrance Test Status != Attended.")

    # 4. throw error if Any selected candidate has Status / Result != Pass
    for row in applicants:
        if getattr(row, status_field) in ["Shortlisted", "Selected"]:
            etsa_doc = frappe.get_doc("Entrance Test Seat Allocation", row.applicant_id)
            if etsa_doc.result_status != "Pass":
                frappe.throw(f"Validation failed: Selected candidate {row.applicant_id} has Status / Result != Pass.")

    # 5. throw error if Any Not Allocated candidate has Shortlisted Category filled
    for row in applicants:
        if getattr(row, status_field) not in ["Shortlisted", "Selected"]:
            display_field = "allocated_category" if hasattr(row, "allocated_category") else "shortlist_category"
            if getattr(row, display_field, ""):
                frappe.throw(f"Validation failed: Not Allocated candidate {row.applicant_id} has Shortlisted Category filled: '{getattr(row, display_field)}'.")

    # 6. throw error if Duplicate selected candidate exists
    seen = set()
    for row in applicants:
        if getattr(row, status_field) in ["Shortlisted", "Selected"]:
            if row.applicant_id in seen:
                frappe.throw(f"Validation failed: Duplicate selected candidate: {row.applicant_id}.")
            seen.add(row.applicant_id)

    # 7. General selected count must be General total from targets
    gen_selected = len([x for x in applicants if getattr(x, status_field) in ["Shortlisted", "Selected"] and x.vertical_category == "General"])
    sc_selected = len([x for x in applicants if getattr(x, status_field) in ["Shortlisted", "Selected"] and x.vertical_category == "SC"])
    st_selected = len([x for x in applicants if getattr(x, status_field) in ["Shortlisted", "Selected"] and x.vertical_category == "ST"])
    obc_selected = len([x for x in applicants if getattr(x, status_field) in ["Shortlisted", "Selected"] and x.vertical_category == "OBC-NCL"])
    ews_selected = len([x for x in applicants if getattr(x, status_field) in ["Shortlisted", "Selected"] and x.vertical_category == "EWS"])

    expected_gen_selected = len(general_shortlist)
    if gen_selected != expected_gen_selected:
        frappe.throw(f"Validation failed: General selected count is {gen_selected}, expected {expected_gen_selected}.")
        
    # 8. Reserved categories selected count must match their shortlist lengths
    for v_cat_name in vertical_cats:
        if v_cat_name == "General": continue
        v_selected = len([x for x in applicants if getattr(x, status_field) in ["Shortlisted", "Selected"] and x.vertical_category == v_cat_name])
        expected_v_selected = len(shortlists.get(v_cat_name, []))
        if v_selected != expected_v_selected:
            frappe.throw(f"Validation failed: {v_cat_name} selected count is {v_selected}, expected {expected_v_selected}.")

    # 12. PWD selected count must be PWD target (or pool size if pool is smaller)
    total_pwd_available = len([x for x in eligible_applicants if x.is_pwd])
    expected_pwd = min(targets["PWD"], total_pwd_available)
    if pwd_selected < expected_pwd:
        frappe.throw(f"Validation failed: PWD selected count is {pwd_selected}, expected {expected_pwd}.")

    # 13. Women selected count must be Women target (or pool size if pool is smaller)
    total_women_available = len([x for x in eligible_applicants if x.is_female])
    expected_women = min(targets["Women"], total_women_available)
    if women_selected < expected_women:
        frappe.throw(f"Validation failed: Women selected count is {women_selected}, expected {expected_women}.")

    return True
