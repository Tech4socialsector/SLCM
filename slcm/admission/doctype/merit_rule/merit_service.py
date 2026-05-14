import frappe
import math
from frappe import _
from frappe.utils import now_datetime
from collections import defaultdict
from slcm.admission.doctype.seat_allocation.seat_allocation import get_applicant_categories, clear_category_cache

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
    
    # Preserve order from all_cats if possible
    order = {name: i for i, name in enumerate(all_cats)}
    verticals.sort(key=lambda x: order.get(x, 99))
    horizontals.sort(key=lambda x: order.get(x, 99))
    compartmental.sort(key=lambda x: order.get(x, 99))
    
    return (verticals, horizontals, compartmental)

def _has_trait(applicant_id, trait_name):
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
    If processing_stage="Final Allotment Ranking", tie-break on Interview Score (interview_score).
    """
    # 1. Prepare Keys for Sorting and Ranking
    from frappe.utils import get_timestamp
    
    def get_stable_key(x):
        """Used for actual list sorting (adds deterministic fallback)."""
        score = float(getattr(x, "total_score", 0) or getattr(x, "nlsat_part_a_score", 0) or getattr(x, "entrance_score", 0) or 0)
        
        if processing_stage == "Part A Ranking":
            return (
                -score,
                getattr(x, "name", "") or getattr(x, "applicant_id", "")
            )
        
        # Final Allotment tie-breakers (Descending for scores, Descending for DOB/Age)
        # 1. Total Score (Desc)
        # 2. Part B Score (Desc)
        # 3. Date of Birth (Ascending for older)
        dob = x.get("date_of_birth") or "9999-12-31"
        interview_score = float(getattr(x, "interview_score", 0) or getattr(x, "nlsat_part_b_score", 0) or 0)
        
        return (
            -score,
            -interview_score,
            getattr(x, "name", "") or getattr(x, "applicant_id", "")
        )

    # Helper to check for same rank (ignores deterministic fallback)
    def is_same_rank(app1, app2):
        score1 = float(getattr(app1, "total_score", 0) or getattr(app1, "nlsat_part_a_score", 0) or getattr(app1, "entrance_score", 0) or 0)
        score2 = float(getattr(app2, "total_score", 0) or getattr(app2, "nlsat_part_a_score", 0) or getattr(app2, "entrance_score", 0) or 0)
        
        if processing_stage == "Part A Ranking":
            return score1 == score2
        
        int_score1 = float(getattr(app1, "interview_score", 0) or getattr(app1, "nlsat_part_b_score", 0) or 0)
        int_score2 = float(getattr(app2, "interview_score", 0) or getattr(app2, "nlsat_part_b_score", 0) or 0)
        
        k1 = (score1, int_score1)
        k2 = (score2, int_score2)
        return k1 == k2

    # 1. Overall Rank
    applicant_rows.sort(key=get_stable_key)
    
    current_rank = 1
    for i, row in enumerate(applicant_rows):
        if i > 0:
            if not is_same_rank(row, applicant_rows[i-1]):
                current_rank = i + 1
        row.overall_rank = current_rank
        # Sync shortlist/admission rank to overall rank (since it's already program-specific)
        if hasattr(row, "shortlist_rank"): row.shortlist_rank = current_rank
        if hasattr(row, "admission_rank"): row.admission_rank = current_rank

    # 2. Category Rank (Within actual vertical category)
    category_groups = defaultdict(list)
    for row in applicant_rows:
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

            # If status is "Generated" or "Draft", we allow re-generation
            if existing_doc.docstatus == 1:
                existing_doc.cancel()
                frappe.delete_doc("Merit List", existing_doc.name, ignore_permissions=True, force=True)
                frappe.db.commit()
            elif existing_doc.docstatus == 0:
                frappe.delete_doc("Merit List", existing_doc.name, ignore_permissions=True, force=True)
                frappe.db.commit()


    # Fetch applicants names
    if processing_stage == "Final Allotment Ranking":
        sp_filters = {
            "admission_cycle": cycle,
            "campus": campus,
            "program_level": program_level
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
                "allocation_type", "compartmentalized_category", "horizontal_categories"
            ]
        )
        applicant_names = [d.applicant_id for d in shortlist_data]
        shortlist_cat_map = {d.applicant_id: d for d in shortlist_data}
    else:
        shortlist_cat_map = {}
        er_filters = {
            "admission_cycle": cycle,
            "campus": campus,
            "program_level": program_level
        }
        if program:
            er_filters["program"] = program

        applicant_names = frappe.get_all(
            "Eligibility Result",
            filters=er_filters,
            pluck="name"
        )
    

    # Build Merit List
    merit = frappe.new_doc("Merit List")
    merit.admission_cycle = cycle
    merit.campus = campus
    merit.program_level = program_level
    merit.program = program
    merit.merit_processing_stage = processing_stage
    merit.generated_on = now_datetime()
    merit.status = "Generated"

    total_applicants = len(applicant_names)
    for i, name in enumerate(applicant_names):
        frappe.publish_progress(
            (i + 1) * 100 / total_applicants, 
            title=_("Generating Merit List"), 
            description=_("Processing applicant {0} of {1}").format(i + 1, total_applicants)
        )
        
        app = frappe.get_doc("Eligibility Result", name)
        
        # Advanced shortlisting logic (skip candidates with 0 or negative scores in Part A)
        if processing_stage == "Part A Ranking" and (app.get("entrance_test_score") or 0) <= 0:
            continue

        part_a = float(app.get("entrance_test_score") or 0)
        part_b = float(app.get("interview_score") or 0)
        
        if processing_stage == "Part A Ranking":
            total_score = part_a
        else:
            total_score = part_a + part_b

        status = "Selected" 

        verticals, horizontals, compartmental = _get_categorized_traits(app.applicant_id)
        primary_cat = verticals[0] if verticals else "General"

        merit.append("merit_applicants", {
            "applicant_id": app.applicant_id,
            "candidate_name": app.candidate_name,
            "program": app.program,
            "program_level": app.program_level,
            "hsc_percentage": app.get("hsc_percentage") or 0,
            "entrance_score": app.get("entrance_test_score") or 0,
            "interview_score": app.get("interview_score") or 0,
            "ug_cgpa": app.get("ug_cgpa") or 0,
            "pg_cgpa": app.get("pg_cgpa") or 0,
            "date_of_birth": app.get("date_of_birth"),
            "total_score": total_score,
            "status": status,
            "overall_rank": 0,
            "program_rank": 0,
            "category_rank": 0,
            "actual_category": primary_cat,
            "shortlist_category": shortlist_cat_map.get(app.applicant_id, {}).get("shortlist_category"),
            "vertical_category": shortlist_cat_map.get(app.applicant_id, {}).get("vertical_category"),
            "allocation_type": shortlist_cat_map.get(app.applicant_id, {}).get("allocation_type"),
            "compartmentalized_category": shortlist_cat_map.get(app.applicant_id, {}).get("compartmentalized_category"),
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
    
    # Note: percentile calculation is handled inside execute_advanced_allocation_logic per program group

    merit.merit_applicants.sort(key=lambda x: x.overall_rank)
    for i, row in enumerate(merit.merit_applicants):
        row.idx = i + 1
        
    _populate_category_lists(merit)
        
    if True:
        if processing_stage == "Final Allotment Ranking":
            _apply_percentile_cutoffs(merit)
            # Simple population for Final Merit (Shows everyone in their category tabs)
            _populate_category_lists(merit)
        else:
            # Shortlisting stage still needs advanced logic for multiplier targets
            execute_advanced_allocation_logic(merit, is_shortlist_allocation=True)
            _populate_category_lists(merit)

    if save:
        merit.insert()

        frappe.db.commit()
    return merit


def _apply_percentile_cutoffs(doc):
    """
    Applies NLSAT minimum percentile eligibility from Program Reservation Policy.
    """
    policy_name = frappe.db.get_value("Program Reservation Policy", {
        "admission_cycle": doc.admission_cycle,
        "program": doc.program
    }, "name")
    
    if not policy_name:
        return
        
    policy = frappe.get_doc("Program Reservation Policy", policy_name)
    
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
    for field in list_fields:
        if hasattr(doc, field):
            doc.set(field, [])
            
    app_list = []
    if hasattr(doc, "shortlist_applicants"):
        app_list = doc.shortlist_applicants
    elif hasattr(doc, "merit_applicants"):
        app_list = doc.merit_applicants
    elif hasattr(doc, "selection_applicant"):
        app_list = doc.selection_applicant

    # Sort by rank to ensure we pick the top candidates for tabs
    sorted_applicants = sorted(app_list, key=lambda x: x.overall_rank or 9999)

    for row in sorted_applicants:
        status_field = "status"
        if hasattr(row, "shortlist_status"):
            status_field = "shortlist_status"
        elif hasattr(row, "selection_status"):
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
        if v_cat == "SC": target_field = "sc_list"
        elif v_cat == "ST": target_field = "st_list"
        elif v_cat == "OBC-NCL": target_field = "obc_list"
        elif v_cat == "EWS": target_field = "ews_list"
        
        if target_field and hasattr(doc, target_field):
            doc.append(target_field, row_data)
            
        # 4. Special Lists (Horizontal/Compartmental) - Use _has_trait for partial matching (e.g. Karnataka Students)
        if _has_trait(row.applicant_id, "Karnataka") and hasattr(doc, "karnataka_list"):
            doc.append("karnataka_list", row_data)
        if _has_trait(row.applicant_id, "Women") and hasattr(doc, "women_list"):
            doc.append("women_list", row_data)
        if _has_trait(row.applicant_id, "PWD") and hasattr(doc, "pwd_list"):
            doc.append("pwd_list", row_data)

    # Populate Summary only if it doesn't already have rich data
    if hasattr(doc, "category_summary"):
        has_rich_data = any(row.get("seats") for row in doc.get("category_summary") or [])
        if not has_rich_data:
            doc.set("category_summary", [])
            counts = {
                "General": len(doc.get("general_list") or []),
                "SC": len(doc.get("sc_list") or []),
                "ST": len(doc.get("st_list") or []),
                "OBC-NCL": len(doc.get("obc_list") or []),
                "EWS": len(doc.get("ews_list") or []),
                "Karnataka": len(doc.get("karnataka_list") or []),
                "Women": len(doc.get("women_list") or []),
                "PWD": len(doc.get("pwd_list") or [])
            }
            for cat, count in counts.items():
                doc.append("category_summary", {
                    "category": cat,
                    "actually_shortlisted": count
                })



def execute_advanced_allocation_logic(doc, is_shortlist_allocation=False, ignore_seat_limits=False):
    """
    NLSAT specific seat allocation logic based on document rules.
    Phases:
    1. Vertical Allocation (General, then Reserved)
    2. Karnataka Sub-quota Adjustments (with recursive displacement)
    3. Horizontal Reservation (PWD, then Women)
    """
    clear_category_cache()
    
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
    
    # Initial Rank
    processing_stage = "Part A Ranking" if is_shortlist_allocation else "Final Allotment Ranking"
    _rank_applicants(applicants_list, use_advanced_ranking=True, processing_stage=processing_stage)

    grouped_by_program = {}
    for row in applicants_list:
        grouped_by_program.setdefault(row.program, []).append(row)

    # Calculate and persist percentiles for each program group separately.
    # This must happen before the percentile eligibility filter below.
    for _prog_applicants in grouped_by_program.values():
        _calculate_and_sync_percentiles(_prog_applicants, is_shortlist=is_shortlist_allocation)

    for program, applicants in grouped_by_program.items():
        policy_name = frappe.db.get_value("Program Reservation Policy", {
            "admission_cycle": doc.admission_cycle,
            "program": program
        }, "name")
        
        if not policy_name: continue
        policy = frappe.get_doc("Program Reservation Policy", policy_name)

        multiplier = policy.get("shortlisting_multiplier") or 1.0
        is_shortlist_phase = is_shortlist_allocation or getattr(doc, "merit_processing_stage", "") == "Part A Ranking"
        
        # 1. Setup Targets from Policy
        vertical_targets = {}
        for v in policy.categories:
            v_cat_name = v.category_name or "General"
            
            seats = v.shortlisting_target if is_shortlist_phase else v.seats
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
                "min_percentile": v.min_percentile,
                "priority": v.priority or 0
            }

        compartmental_targets = {}
        for comp in policy.compartmental_reservations:
            comp_cat = comp.category_name
            percentage = comp.percentage or 25.0
            
            for v_cat, v_info in vertical_targets.items():
                target_key = (comp_cat, v_cat)
                compartmental_targets[target_key] = {
                    "category": comp_cat,
                    "seats": int((v_info["seats"] * percentage) / 100.0),
                    "original_seats": int((v_info["original_seats"] * percentage) / 100.0),
                    "filled": 0
                }

        horizontal_targets = {}
        for h in policy.horizontal_reservations:
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

        # 2. Filter by Percentile Eligibility (Requirement I.6)
        eligible_applicants = []
        for app in applicants:
            if _check_percentile_eligibility(app, vertical_targets, horizontal_targets):
                eligible_applicants.append(app)
            else:
                setattr(app, status_field, "Rejected")
                app.allocation_type = "Not Allocated"
                app.remarks = "Did not meet minimum percentile threshold"

        unallocated = eligible_applicants[:]
        allocated_list = []

        # --- PHASE 1: INITIAL VERTICAL ALLOTMENT ---
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
                    potential_in = [u for u in unallocated if _has_trait(u.applicant_id, comp_cat)]
                    # Filter potential by category if not General
                    if v_cat != "General":
                        potential_in = [u for u in potential_in if v_cat in get_applicant_categories(u.applicant_id)]
                    
                    for in_cand in potential_in:
                        if deficit <= 0: break
                        
                        eligible_out = [a for a in allocated_list if a.vertical_category == v_cat and not _has_trait(a.applicant_id, comp_cat)]
                        if eligible_out:
                            # Sort by lowest merit rank for displacement (highest rank number)
                            eligible_out.sort(key=lambda x: -(x.overall_rank or 999999))
                            out_cand = eligible_out[0]
                            
                            # Recursive Displacement: Save out_cand in their reserved category if possible
                            _execute_recursive_displacement(out_cand, allocated_list, unallocated, vertical_targets, status_field)
                            _assign_seat_to_applicant(in_cand, v_cat, "Open" if v_cat == "General" else "Reserved", allocated_list, unallocated, v_info, status_field)
                            deficit -= 1

        # --- PHASE 3: HORIZONTAL RESERVATION (e.g., PWD & Women) ---
        ordered_h_cats = sorted(horizontal_targets.values(), key=lambda x: x["priority"])
        for h_info in ordered_h_cats:
            h_cat = h_info["name"]
            if h_info["seats"] <= 0: continue
            
            h_count = len([a for a in allocated_list if _has_trait(a.applicant_id, h_cat)])
            deficit = h_info["seats"] - h_count
            
            if deficit > 0:
                potential = [u for u in unallocated if _has_trait(u.applicant_id, h_cat)]
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
                        
                        _execute_recursive_displacement(out_cand, allocated_list, unallocated, vertical_targets, status_field)
                        _assign_seat_to_applicant(in_cand, v_belong, "Open" if v_belong == "General" else "Reserved", allocated_list, unallocated, vertical_targets[v_belong], status_field)
                        deficit -= 1

        # Final check: Document does not mention backfilling vertical categories (OBC/SC/ST/EWS)
        # during shortlisting if there is a shortfall of candidates. 
        # Only Karnataka, PWD, and Women have explicit shortfall instructions.
        total_backfilled = 0

        # Explicitly Reject remaining before Waitlist Phase
        for u in unallocated:
            setattr(u, status_field, "Rejected")
            u.allocation_type = "Not Allocated"
            u.remarks = "Not enough merit to secure a seat"
            u.vertical_category = ""

        # --- PHASE 4: WAITLIST ALLOCATION ---
        if not is_shortlist_phase:
            for v_cat in ordered_cats:
                v_info = vertical_targets[v_cat]
                w_limit = v_info.get("waitlist_seats", 0)
                if w_limit <= 0: continue
                
                # Find remaining unallocated who are eligible for this category
                potential_w = [u for u in unallocated if getattr(u, status_field) == "Rejected"]
                if v_cat != "General":
                    potential_w = [u for u in potential_w if v_cat in get_applicant_categories(u.applicant_id)]
                
                # Merit sort
                potential_w.sort(key=lambda x: (-(float(getattr(x, "total_score", 0) or 0)), (x.overall_rank or 999999)))
                
                for w_cand in potential_w:
                    if v_info["waitlist_filled"] < w_limit:
                        # Use _assign_seat_to_applicant to handle categorization strings
                        _assign_seat_to_applicant(w_cand, v_cat, w_cand.allocation_type, [], [], {"filled": 0}, status_field)
                        # Reset the status back to Waitlisted since _assign sets it to Selected/Shortlisted
                        setattr(w_cand, status_field, "Waitlisted")
                        v_info["waitlist_filled"] += 1

        # --- POPULATE SUMMARY ---
        if hasattr(doc, "category_summary"):
            doc.set("category_summary", [])
            summary_table = "category_summary"
            
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
                else:
                    row["required"] = req
                    row["actually_allocated"] = filled
                    row["total_seats"] = orig
                    row["allocated_seats"] = filled
                    row["vacant_seats"] = max(0, req - filled)
                    row["waitlist_required"] = w_req
                    row["actually_waitlisted"] = w_filled
                doc.append(summary_table, row)

            # 1. Main Vertical Categories
            for v_cat in ordered_cats:
                v_info = vertical_targets[v_cat]
                append_sum(v_cat, v_info.get("original_seats", 0), v_info["seats"], v_info["filled"], v_info.get("waitlist_filled", 0), v_info.get("waitlist_seats", 0))
                
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


    return True

def _check_percentile_eligibility(app, vertical_targets, horizontal_targets=None):
    """
    Checks if an applicant meets the minimum percentile threshold for their ACTUAL category.
    Targets are dynamically derived from the Program Reservation Policy.
    """
    v_traits, _, _ = _get_categorized_traits(app.applicant_id)
    primary_cat = v_traits[0] if v_traits else "General"
    
    thresholds = []
    
    # 1. Base Vertical Threshold
    if primary_cat in vertical_targets:
        thresholds.append(float(vertical_targets[primary_cat].get("min_percentile") or 0))
    
    # 2. Horizontal Overrides (e.g., PWD)
    if horizontal_targets:
        for h_cat, h_info in horizontal_targets.items():
            if _has_trait(app.applicant_id, h_cat):
                thresholds.append(float(h_info.get("min_percentile") or 0))
    
    # Rule: If multiple thresholds apply (e.g. SC + PWD), the most lenient (minimum) applies
    threshold = min(thresholds) if thresholds else 0
        
    percentile = float(getattr(app, "percentile_score", 0) or 0)
    if not percentile and getattr(app, "applicant_id", None):
        er_percentile = frappe.db.get_value("Eligibility Result", {"applicant_id": app.applicant_id}, "percentile_score")
        if er_percentile is not None:
            percentile = float(er_percentile)
            
    return percentile >= threshold

def _execute_recursive_displacement(out_cand, allocated_list, unallocated, vertical_targets, status_field):
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
    
    # 2. Fall-back to Reserved Category if they were in General
    # Only fall back if they were displaced from a DIFFERENT category (e.g., General -> SC).
    if actual_v_cat != "General" and actual_v_cat != prev_v:
        v_info = vertical_targets.get(actual_v_cat)
        if v_info:
            if v_info["filled"] < v_info["seats"]:
                _assign_seat_to_applicant(out_cand, actual_v_cat, "Reserved", allocated_list, unallocated, v_info, status_field)
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
                        # Attempt to recursively displace the candidate we just pushed out, 
                        # in case they have somewhere else to go (though usually they don't if they were in their own category)
                        _execute_recursive_displacement(lowest_cand, allocated_list, unallocated, vertical_targets, status_field)

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
    if hasattr(app, "compartmentalized_category"):
        app.compartmentalized_category = c_traits[0] if c_traits else ""
    
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
    # For shortlisting rows the field is nlsat_part_a_score;
    # for Final Merit List rows it is total_score.
    # Fall back gracefully: use whichever is populated.
    def _get_score(app):
        if is_shortlist:
            return float(getattr(app, "nlsat_part_a_score", 0) or 0)
        val = float(getattr(app, "total_score", 0) or 0)
        if val == 0:
            # fallback for rows that only carry nlsat_part_a_score
            val = float(getattr(app, "nlsat_part_a_score", 0) or 0)
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
        count_le = bisect.bisect_right(all_scores, score)  # # scores <= this score
        percentile = round((count_le / total_count) * 100, 4)
        app.percentile_score = percentile

        if getattr(app, "applicant_id", None):
            updates.append((app.applicant_id, percentile))

    # 4. Bulk update Eligibility Result.
    # Eligibility Result is named by applicant_id (autoname = field:applicant_id),
    # so we can use it directly as the primary key.
    for applicant_id, percentile in updates:
        if frappe.db.exists("Eligibility Result", applicant_id):
            frappe.db.set_value("Eligibility Result", applicant_id, "percentile_score", percentile, update_modified=False)

    frappe.db.commit()
