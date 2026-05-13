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
    
    # NLSAT Specific: Normalize common category names
    normalized_cats = []
    for c in all_cats:
        if not c: continue
        if "Karnataka" in c: normalized_cats.append("Karnataka")
        elif "Women" in c or "Female" in c: normalized_cats.append("Women")
        elif "PWD" in c or "Disability" in c: normalized_cats.append("PWD")
        else: normalized_cats.append(c)

    verticals = [c.name for c in cat_data if c.reservation_type == "Vertical"]
    horizontals = [c.name for c in cat_data if c.reservation_type == "Horizontal"]
    compartmental = [c.name for c in cat_data if c.reservation_type == "Compartmentalised Horizontal"]
    
    # Also check if any normalized traits should be added to horizontal/compartmental
    if "Karnataka" in normalized_cats and "Karnataka" not in compartmental: compartmental.append("Karnataka")
    if "Women" in normalized_cats and "Women" not in horizontals: horizontals.append("Women")
    if "PWD" in normalized_cats and "PWD" not in horizontals: horizontals.append("PWD")

    # Preserve order from all_cats if possible
    order = {name: i for i, name in enumerate(all_cats)}
    verticals.sort(key=lambda x: order.get(x, 99))
    horizontals.sort(key=lambda x: order.get(x, 99))
    compartmental.sort(key=lambda x: order.get(x, 99))
    
    return (verticals, horizontals, compartmental)

def _has_trait(applicant_id, trait_name):
    """Checks if an applicant has a specific trait (case-insensitive and partial matching)."""
    cats = get_applicant_categories(applicant_id)
    for c in cats:
        if not c: continue
        if trait_name.lower() in c.lower():
            return True
    return False


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

def debug_check_merit(name):
    doc = frappe.get_doc("Shortlisting Merit List", name)
    print(f"Checking Merit List: {name}")
    print(f"Status: {doc.status}")
    
    # 1. Check summary
    print("\n--- Summary ---")
    for row in doc.category_summary:
        print(f"Category: {row.category}, Required: {row.required_to_shortlist}, Actually: {row.actually_shortlisted}")
    
    # 2. Check Ranking Ties
    print("\n--- Ranking Ties (First 10) ---")
    apps = doc.shortlist_applicants[:10]
    for app in apps:
        print(f"Rank: {app.shortlist_rank}, Score: {app.nlsat_part_a_score}, Name: {app.candidate_name}")
    
    # 3. Check for <= 0 scores
    zero_scores = [a for a in doc.shortlist_applicants if (a.nlsat_part_a_score or 0) <= 0]
    print(f"\nCandidates with <= 0 scores: {len(zero_scores)}")
    
    # 4. Check Horizontal Quotas (PWD/Women)
    pwd_count = len(doc.pwd_list)
    women_count = len(doc.women_list)
    print(f"\nPWD List Count: {pwd_count}")
    print(f"Women List Count: {women_count}")

    # 5. Check if PWD displacement happened
    pwd_app = next((a for a in doc.shortlist_applicants if a.applicant_id == "APP-2026-00017"), None)
    if pwd_app:
        print(f"\nPWD Applicant APP-2026-00017: {pwd_app.shortlist_status}, Category: {pwd_app.shortlist_category}")
    else:
        print("\nPWD Applicant APP-2026-00017 NOT FOUND in shortlist_applicants")


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
    
    # Remove incorrect dynamic percentile calculation

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

    if save:
        merit.insert()
        from slcm.admission.doctype.admission_audit_log.audit_service import log_merit_action
        for row in merit.merit_applicants:
            log_merit_action(
                merit_list=merit.name,
                admission_cycle=merit.admission_cycle,
                applicant=row.applicant_id,
                program=row.program,
                action_type="Merit Calculated",
                remarks=f"Total Score: {float(getattr(row, 'total_score', 0) or getattr(row, 'nlsat_part_a_score', 0) or getattr(row, 'entrance_score', 0) or 0):.3f} (Part A: {row.get('entrance_score') or row.get('nlsat_part_a_score') or 0}, Part B: {row.get('interview_score') or row.get('nlsat_part_b_score') or 0})"
            )
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
    thresholds = {v.category_name: float(v.min_percentile or 0) for v in policy.categories}
    
    for row in doc.merit_applicants:
        percentile = float(row.percentile_score or 0)
        # We use the candidate's actual vertical category to find the threshold
        v_traits, _, _ = _get_categorized_traits(row.applicant_id)
        primary_cat = v_traits[0] if v_traits else "General"
        
        threshold = thresholds.get(primary_cat, 0)
        
        if percentile < threshold:
            row.status = "Rejected"
            row.remarks = f"Below minimum percentile threshold for {primary_cat} ({threshold}%)"
        else:
            row.status = "Selected"


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
            
    # Sort by rank to ensure we pick the top candidates for tabs
    sorted_applicants = sorted(doc.merit_applicants, key=lambda x: x.overall_rank or 9999)

    for row in sorted_applicants:
        if getattr(row, "status", "") == "Rejected":
            continue

        # Prepare data for append (exclude idx to allow continuous numbering in the child table)
        row_data = row.as_dict()
        if "idx" in row_data:
            del row_data["idx"]

        # 1. Use allocation results for categorization
        v_cat = getattr(row, "vertical_category", "")
        alloc_type = getattr(row, "allocation_type", "")
        disp_cat = getattr(row, "allocated_category", "") or getattr(row, "shortlist_category", "")
        
        # 2. Populate General List (Open Merit)
        if v_cat == "General" or alloc_type == "Open":
            if hasattr(doc, "general_list"):
                doc.append("general_list", row_data)
            
        # 3. Vertical Lists (only if allocated to that vertical specifically, or belongs to it)
        # NLSAT Rule: If an SC candidate is in Open, they also appear in General list.
        # But for the SC tab, usually we show everyone in that category.
        v_traits, _, _ = _get_categorized_traits(row.applicant_id)
        actual_v = v_traits[0] if v_traits else "General"
        
        target_field = None
        if actual_v == "SC": target_field = "sc_list"
        elif actual_v == "ST": target_field = "st_list"
        elif actual_v == "OBC-NCL": target_field = "obc_list"
        elif actual_v == "EWS": target_field = "ews_list"
        
        if target_field and hasattr(doc, target_field):
            doc.append(target_field, row_data)
            
        # 4. Special Lists (Horizontal/Compartmental)
        app_cats = get_applicant_categories(row.applicant_id)
        if "Karnataka" in app_cats and hasattr(doc, "karnataka_list"):
            doc.append("karnataka_list", row_data)
        if "Women" in app_cats and hasattr(doc, "women_list"):
            doc.append("women_list", row_data)
        if "PWD" in app_cats and hasattr(doc, "pwd_list"):
            doc.append("pwd_list", row_data)

    # Populate Summary
    if hasattr(doc, "category_summary"):
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
    
    # Initial Rank
    processing_stage = "Part A Ranking" if is_shortlist_allocation else "Final Allotment Ranking"
    _rank_applicants(applicants_list, use_advanced_ranking=True, processing_stage=processing_stage)

    grouped_by_program = {}
    for row in applicants_list:
        # Ignore already rejected candidates if they were explicitly rejected (e.g. by a previous manual step)
        if getattr(row, status_field, "") == "Rejected" and not ignore_seat_limits:
            continue
        grouped_by_program.setdefault(row.program, []).append(row)

    for program, applicants in grouped_by_program.items():
        policy_name = frappe.db.get_value("Program Reservation Policy", {
            "admission_cycle": doc.admission_cycle,
            "program": program
        }, "name")
        
        if not policy_name: continue
        policy = frappe.get_doc("Program Reservation Policy", policy_name)
        # Always run advanced logic for Seat Allocation; for Merit List check the flag
        if getattr(doc, "doctype", "") != "Seat Allocation" and not policy.enable_advanced_shortlisting: 
            continue

        multiplier = policy.get("shortlisting_multiplier") or 1.0
        is_shortlist_phase = is_shortlist_allocation or (getattr(doc, "doctype", "") == "Shortlisting Merit List")
        
        # 1. Setup Targets from Policy
        vertical_targets = {}
        for v in policy.categories:
            v_cat_name = v.category_name or "General"
            
            seats = v.shortlisting_target if is_shortlist_phase else v.seats
            if is_shortlist_phase and not seats:
                seats = int((v.seats or 0) * multiplier)
            else:
                seats = v.seats or 0
            
            vertical_targets[v_cat_name] = {
                "seats": seats or 0,
                "original_seats": v.seats or 0,
                "waitlist_seats": v.waitlist_seats or 0,
                "waitlist_filled": 0,
                "filled": 0,
                "min_percentile": v.min_percentile,
                "priority": v.priority or 0
            }

        ka_targets = {}
        ka_percentage = 25.0 # Default NLSAT requirement
        common_ka_row = next((c for c in policy.compartmental_reservations if c.category_name == "Karnataka"), None)
        if common_ka_row:
            ka_percentage = common_ka_row.percentage or 25.0
            
        for v_cat, v_info in vertical_targets.items():
            ka_targets[v_cat] = {
                "seats": int((v_info["seats"] * ka_percentage) / 100.0),
                "original_seats": int((v_info["original_seats"] * ka_percentage) / 100.0),
                "filled": 0
            }

        horizontal_targets = {}
        for h in policy.horizontal_reservations:
            seats = h.shortlisting_target if is_shortlist_phase else h.seats
            if is_shortlist_phase and not seats:
                seats = int((h.seats or 0) * multiplier)
            horizontal_targets[h.category_name] = {
                "seats": seats or 0,
                "original_seats": h.seats or 0,
                "filled": 0
            }

        # 2. Filter by Percentile Eligibility (Requirement I.6)
        eligible_applicants = []
        for app in applicants:
            if _check_percentile_eligibility(app, vertical_targets):
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
                v_traits, _, _ = _get_categorized_traits(app.applicant_id)
                actual_v = v_traits[0] if v_traits else "General"
                
                # Rule: Top merit get General seats regardless of their category (Merit Migration)
                can_take_seat = (v_cat == "General") or (actual_v == v_cat)
                
                if can_take_seat and v_info["filled"] < v_info["seats"]:
                    alloc_type = "Open" if v_cat == "General" else "Reserved"
                    _assign_seat_to_applicant(app, v_cat, alloc_type, allocated_list, unallocated, v_info, status_field)

        # --- PHASE 2: KARNATAKA SUB-QUOTA ADJUSTMENT ---
        # Requirement: Displace lowest AI in the pool with next highest Karnataka student.
        for v_cat in ordered_cats:
            v_info = vertical_targets[v_cat]
            ka_info = ka_targets.get(v_cat)
            if not ka_info or ka_info["seats"] <= 0: continue
            
            # Count current Karnataka coverage in this pool
            ka_in_v = [a for a in allocated_list if a.vertical_category == v_cat and _has_trait(a.applicant_id, "Karnataka")]
            deficit = ka_info["seats"] - len(ka_in_v)
            
            if deficit > 0:
                potential_ka = [u for u in unallocated if _has_trait(u.applicant_id, "Karnataka")]
                # Filter potential Karnataka by category if not General
                if v_cat != "General":
                    potential_ka = [u for u in potential_ka if v_cat in get_applicant_categories(u.applicant_id)]
                
                for in_cand in potential_ka:
                    if deficit <= 0: break
                    
                    eligible_out = [a for a in allocated_list if a.vertical_category == v_cat and not _has_trait(a.applicant_id, "Karnataka")]
                    if eligible_out:
                        # Sort by lowest merit rank for displacement (highest rank number)
                        eligible_out.sort(key=lambda x: -(x.overall_rank or 999999))
                        out_cand = eligible_out[0]
                        
                        # Recursive Displacement: Save out_cand in their reserved category if possible
                        _execute_recursive_displacement(out_cand, allocated_list, unallocated, vertical_targets, status_field)
                        _assign_seat_to_applicant(in_cand, v_cat, "Open" if v_cat == "General" else "Reserved", allocated_list, unallocated, v_info, status_field)
                        deficit -= 1

        # --- PHASE 3: HORIZONTAL RESERVATION (PWD & Women) ---
        h_order = ["PWD", "Women"]
        for h_cat in h_order:
            h_info = horizontal_targets.get(h_cat)
            if not h_info or h_info["seats"] <= 0: continue
            
            h_count = len([a for a in allocated_list if _has_trait(a.applicant_id, h_cat)])
            deficit = h_info["seats"] - h_count
            
            if deficit > 0:
                potential = [u for u in unallocated if _has_trait(u.applicant_id, h_cat)]
                for in_cand in potential:
                    if deficit <= 0: break
                    
                    v_traits, _, _ = _get_categorized_traits(in_cand.applicant_id)
                    v_belong = v_traits[0] if v_traits else "General"
                    
                    # Try to displace lowest AI candidate in the same vertical category
                    eligible_out = [a for a in allocated_list if a.vertical_category == v_belong 
                                    and not _has_trait(a.applicant_id, "Karnataka")
                                    and not _has_trait(a.applicant_id, h_cat)]
                    
                    if eligible_out:
                        eligible_out.sort(key=lambda x: -(x.overall_rank or 999999))
                        out_cand = eligible_out[0]
                        
                        _execute_recursive_displacement(out_cand, allocated_list, unallocated, vertical_targets, status_field)
                        _assign_seat_to_applicant(in_cand, v_belong, "Open" if v_belong == "General" else "Reserved", allocated_list, unallocated, vertical_targets[v_belong], status_field)
                        deficit -= 1

        # --- PHASE 4: WAITLIST ALLOCATION ---
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
                    setattr(w_cand, status_field, "Waitlisted")
                    w_cand.allocation_type = "Reserved" if v_cat != "General" else "Open"
                    w_cand.vertical_category = v_cat
                    w_cand.remarks = f"Waitlisted under {v_cat} quota"
                    
                    # Sync combined category string
                    _assign_seat_to_applicant(w_cand, v_cat, w_cand.allocation_type, [], [], {"filled": 0}, status_field)
                    # Reset the status back to Waitlisted since _assign sets it to Selected/Shortlisted
                    setattr(w_cand, status_field, "Waitlisted")
                    
                    v_info["waitlist_filled"] += 1

    # --- POPULATE SUMMARY ---
    if hasattr(doc, "category_summary"):
        doc.set("category_summary", [])
        
        # 1. Main Vertical Categories
        for v_cat in ordered_cats:
            v_info = vertical_targets[v_cat]
            doc.append("category_summary", {
                "category": v_cat,
                "seats": v_info.get("original_seats", 0),
                "multiplier": multiplier,
                "required": v_info["seats"],
                "actually_allocated": v_info["filled"],
                # Backward compatibility for old UI
                "total_seats": v_info.get("original_seats", 0),
                "allocated_seats": v_info["filled"],
                "vacant_seats": max(0, v_info["seats"] - v_info["filled"])
            })
            
        # 2. Horizontal (PWD, Women)
        for h_cat in ["PWD", "Women"]:
            h_info = horizontal_targets.get(h_cat)
            if h_info:
                h_filled = len([a for a in allocated_list if _has_trait(a.applicant_id, h_cat)])
                doc.append("category_summary", {
                    "category": h_cat,
                    "seats": h_info.get("original_seats", 0),
                    "multiplier": multiplier,
                    "required": h_info["seats"],
                    "actually_allocated": h_filled,
                    # Backward compatibility
                    "total_seats": h_info.get("original_seats", 0),
                    "allocated_seats": h_filled,
                    "vacant_seats": max(0, h_info["seats"] - h_filled)
                })
        
        # 3. Karnataka Breakdown
        for v_cat in ordered_cats:
            ka_info = ka_targets.get(v_cat)
            if ka_info:
                # Count Karnataka students in THIS vertical pool
                ka_in_v = len([a for a in allocated_list if a.vertical_category == v_cat and _has_trait(a.applicant_id, "Karnataka")])
                doc.append("category_summary", {
                    "category": f"Karnataka ({v_cat})",
                    "seats": ka_info.get("original_seats", 0),
                    "multiplier": multiplier,
                    "required": ka_info["seats"],
                    "actually_allocated": ka_in_v,
                    # Backward compatibility
                    "total_seats": ka_info.get("original_seats", 0),
                    "allocated_seats": ka_in_v,
                    "vacant_seats": max(0, ka_info["seats"] - ka_in_v)
                })
        
        # 4. Karnataka (Common)
        ka_total_orig = sum(k.get("original_seats", 0) for k in ka_targets.values())
        ka_total_req = sum(k.get("seats", 0) for k in ka_targets.values())
        ka_total_filled = len([a for a in allocated_list if _has_trait(a.applicant_id, "Karnataka")])
        if ka_total_req > 0:
            doc.append("category_summary", {
                "category": "Karnataka (Common)",
                "seats": ka_total_orig,
                "multiplier": multiplier,
                "required": ka_total_req,
                "actually_allocated": ka_total_filled,
                # Backward compatibility
                "total_seats": ka_total_orig,
                "allocated_seats": ka_total_filled,
                "vacant_seats": max(0, ka_total_req - ka_total_filled)
            })

    return True

def _check_percentile_eligibility(app, vertical_targets):
    """
    Checks if an applicant meets the minimum percentile threshold for their ACTUAL category.
    """
    v_traits, _, _ = _get_categorized_traits(app.applicant_id)
    primary_cat = v_traits[0] if v_traits else "General"
    
    threshold = 0
    if primary_cat in vertical_targets:
        threshold = float(vertical_targets[primary_cat].get("min_percentile") or 0)
        
    percentile = float(getattr(app, "percentile_score", 0) or 0)
    return percentile >= threshold

def _execute_recursive_displacement(out_cand, allocated_list, unallocated, vertical_targets, status_field):
    """
    Displaces a candidate from their current seat.
    If they belong to a reserved category, attempts to re-allocate them to that category pool.
    """
    v_traits, _, _ = _get_categorized_traits(out_cand.applicant_id)
    actual_v_cat = v_traits[0] if v_traits else "General"
    
    # 1. Basic displacement - Decrement current category count if possible
    prev_v = getattr(out_cand, "vertical_category", "")
    if prev_v and prev_v in vertical_targets:
        vertical_targets[prev_v]["filled"] -= 1

    allocated_list.remove(out_cand)
    unallocated.append(out_cand)
    setattr(out_cand, status_field, "Rejected")
    out_cand.allocation_type = "Not Allocated"
    out_cand.vertical_category = ""
    
    # 2. Fall-back to Reserved Category if they were in General
    if actual_v_cat != "General":
        v_info = vertical_targets.get(actual_v_cat)
        if v_info:
            if v_info["filled"] < v_info["seats"]:
                _assign_seat_to_applicant(out_cand, actual_v_cat, "Reserved", allocated_list, unallocated, v_info, status_field)
            else:
                # Pool full, try to displace lowest AI in THEIR category
                ai_in_v = [a for a in allocated_list if a.vertical_category == actual_v_cat 
                           and not _has_trait(a.applicant_id, "Karnataka")]
                if ai_in_v:
                    ai_in_v.sort(key=lambda x: -(x.overall_rank or 999999))
                    lowest_ai = ai_in_v[0]
                    if (out_cand.overall_rank or 999999) < (lowest_ai.overall_rank or 999999):
                        _execute_candidate_displacement(out_cand, lowest_ai, allocated_list, unallocated, status_field)

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
    allocated_list.remove(out_cand)
    unallocated.append(out_cand)
    
    _assign_seat_to_applicant(in_cand, v_cat, a_type, allocated_list, unallocated, {"filled": 0}, status_field)
    # The {"filled": 0} is a dummy as _assign_seat_to_applicant increments it, but we are just swapping.
    # We should actually pass the correct v_info but for a swap it doesn't change the total filled count.
    # To be safe, we'll sort the final list later.
    allocated_list.sort(key=lambda x: (-(float(getattr(x, "total_score", 0) or 0)), (x.overall_rank or 999999)))
