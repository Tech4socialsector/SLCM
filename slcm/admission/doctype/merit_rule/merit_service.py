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
            fields=["applicant_id", "shortlist_category"]
        )
        applicant_names = [d.applicant_id for d in shortlist_data]
        shortlist_cat_map = {d.applicant_id: d.shortlist_category for d in shortlist_data}
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
    
    if not applicant_names:
        prog_err = f" for Program '{program}'" if program else f" for Program Level '{program_level}'"
        frappe.throw(
            f"No eligible applicants found{prog_err} in this stage.",
            title="No Applicants Found"
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
        
        is_advanced = frappe.db.get_value("Program Reservation Policy", {"program": app.program, "admission_cycle": cycle}, "enable_advanced_shortlisting")
        if is_advanced and processing_stage == "Part A Ranking" and (app.get("entrance_test_score") or 0) <= 0:
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
            "shortlist_category": shortlist_cat_map.get(app.applicant_id),
            "percentile_score": app.get("percentile_score") or 0
        })

    if not merit.merit_applicants:
        frappe.throw(
            f"No applicants could be processed for Program Level '{program_level}'.",
            title="Empty Merit List"
        )

    merit.total_applicants = len(merit.merit_applicants)

    first_app_prog = merit.merit_applicants[0].program
    use_advanced = frappe.db.get_value("Program Reservation Policy", {"program": first_app_prog, "admission_cycle": cycle}, "enable_advanced_shortlisting")

    _rank_applicants(merit.merit_applicants, use_advanced_ranking=use_advanced, processing_stage=processing_stage)
    
    # Remove incorrect dynamic percentile calculation

    merit.merit_applicants.sort(key=lambda x: x.overall_rank)
    for i, row in enumerate(merit.merit_applicants):
        row.idx = i + 1
        
    _populate_category_lists(merit)
        
    if use_advanced:
        if processing_stage == "Final Allotment Ranking":
            _apply_percentile_cutoffs(merit)
        else:
            execute_advanced_allocation_logic(merit, is_shortlist_allocation=(processing_stage == "Part A Ranking"))

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
    """
    if not hasattr(doc, "general_list"):
        return
        
    # Clear existing
    list_fields = ["general_list", "sc_list", "st_list", "obc_list", "ews_list", "karnataka_list", "women_list", "pwd_list"]
    for field in list_fields:
        if hasattr(doc, field):
            doc.set(field, [])
            
    for row in doc.merit_applicants:
        # All candidates who pass percentile are in the General List (Open Merit)
        if row.status == "Selected":
            doc.append("general_list", row.as_dict())
            
        v_traits, h_traits, c_traits = _get_categorized_traits(row.applicant_id)
        
        # Vertical Lists
        if v_traits:
            v_cat = v_traits[0]
            target_field = {
                "SC": "sc_list",
                "ST": "st_list",
                "OBC-NCL": "obc_list",
                "EWS": "ews_list"
            }.get(v_cat)
            
            if target_field and hasattr(doc, target_field):
                doc.append(target_field, row.as_dict())
            
        # Horizontal/Karnataka Lists
        if any("Karnataka" in t for t in c_traits) and hasattr(doc, "karnataka_list"):
            doc.append("karnataka_list", row.as_dict())
            
        if "Women" in h_traits and hasattr(doc, "women_list"):
            doc.append("women_list", row.as_dict())
            
        if "PWD" in h_traits and hasattr(doc, "pwd_list"):
            doc.append("pwd_list", row.as_dict())

    # Populate Summary
    if hasattr(doc, "category_summary"):
        doc.set("category_summary", [])
        # Simple summary for Final Rank List phase
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
    
    # Sort for initial rank
    processing_stage = "Part A Ranking" if is_shortlist_allocation else "Final Allotment Ranking"
    _rank_applicants(applicants_list, use_advanced_ranking=True, processing_stage=processing_stage)

    grouped_by_program = {}
    for row in applicants_list:
        if getattr(row, status_field, "") == "Rejected":
            continue
        grouped_by_program.setdefault(row.program, []).append(row)

    total_selected = 0
    total_rejected = 0

    for program, applicants in grouped_by_program.items():
        policy_name = frappe.db.get_value("Program Reservation Policy", {
            "admission_cycle": doc.admission_cycle,
            "program": program
        }, "name")
        
        if not policy_name:
            continue
            
        policy = frappe.get_doc("Program Reservation Policy", policy_name)
        if not policy.enable_advanced_shortlisting:
            continue

        # Setup targets
        multiplier = policy.get("shortlisting_multiplier") or 1.0
        is_shortlist_phase = is_shortlist_allocation or (getattr(doc, "doctype", "") == "Shortlisting Merit List")
        
        vertical_targets = {}
        for v in policy.categories:
            seats = v.shortlisting_target if is_shortlist_phase else v.seats
            if is_shortlist_phase and not seats:
                seats = int((v.seats or 0) * multiplier)
            
            vertical_targets[v.category_name] = {
                "seats": seats or 0,
                "filled": 0,
                "waitlist_seats": v.waitlist_seats or 0 if not is_shortlist_phase else 0,
                "waitlist_filled": 0,
                "min_percentile": v.min_percentile,
                "priority": v.priority or 0
            }

        ka_targets = {}
        common_ka_row = next((c for c in policy.compartmental_reservations if c.category_name == "Karnataka"), None)
        
        if common_ka_row:
            # Condition: Each vertical category must contain a percentage (e.g., 25%) of Karnataka students
            ka_percentage = common_ka_row.percentage or 25.0
            
            for v_cat, v_info in vertical_targets.items():
                v_seats = v_info["seats"]
                # Calculate target seats for this vertical
                ka_v_seats = int((v_seats * ka_percentage) / 100.0)
                
                ka_targets[v_cat] = {
                    "seats": ka_v_seats,
                    "filled": 0
                }
            
            # Also keep a "Common" target for the total summary
            total_ka_seats = common_ka_row.shortlisting_target if is_shortlist_phase else common_ka_row.seats
            if is_shortlist_phase and not total_ka_seats:
                total_ka_seats = int((common_ka_row.seats or 0) * multiplier)
            
            ka_targets["Common"] = {
                "seats": total_ka_seats or sum(t["seats"] for t in ka_targets.values()),
                "filled": 0
            }

        horizontal_targets = {}
        for h in policy.horizontal_reservations:
            seats = h.shortlisting_target if is_shortlist_phase else h.seats
            if is_shortlist_phase and not seats:
                seats = int((h.seats or 0) * multiplier)
            
            horizontal_targets[h.category_name] = {
                "seats": seats or 0,
                "filled": 0
            }

        # Sorting: Rank list is already sorted by _rank_applicants
        unallocated = applicants[:]
        allocated_list = []
        displaced_reserved = [] # Candidates displaced from General who are SC/ST/OBC/EWS

        # PHASE A: General Category
        gen_cat = "General"
        gen_info = vertical_targets.get(gen_cat)
        if gen_info:
            gen_seats = gen_info["seats"]
            # 1. Initial pick
            for app in unallocated[:]:
                if ignore_seat_limits or len([a for a in allocated_list if a.vertical_category == gen_cat]) < gen_seats:
                    _assign_seat_to_applicant(app, gen_cat, "Open", allocated_list, unallocated, gen_info, status_field)
            
            # 2. Karnataka Adjustment
            # 2. Karnataka Adjustment for General
            ka_v_target = ka_targets.get(gen_cat, {}).get("seats", 0)
            if ka_v_target > 0:
                ka_in_gen = [a for a in allocated_list if a.vertical_category == gen_cat and "Karnataka" in get_applicant_categories(a.applicant_id)]
                deficit = ka_v_target - len(ka_in_gen)
                if deficit > 0:
                    # Candidates from unallocated who are Karnataka (any vertical trait)
                    potential_ka = [u for u in unallocated if "Karnataka" in get_applicant_categories(u.applicant_id)]
                    for in_cand in potential_ka:
                        if deficit <= 0: break
                        # Displace lowest ranked All India candidate in General
                        eligible_out = [a for a in allocated_list if a.vertical_category == gen_cat and "Karnataka" not in get_applicant_categories(a.applicant_id)]
                        if eligible_out:
                            eligible_out.sort(key=lambda x: (float(getattr(x, "total_score", 0) or getattr(x, "nlsat_part_a_score", 0) or getattr(x, "entrance_score", 0) or 0)))
                            out_cand = eligible_out[0]
                            _execute_candidate_displacement(in_cand, out_cand, allocated_list, unallocated, status_field)
                            in_cand.vertical_category = gen_cat
                            in_cand.allocation_type = "Open"
                            
                            # If displaced belongs to reserved, it will be picked up in Phase B
                            deficit -= 1

        # PHASE B: Vertically Reserved Categories
        reserved_cats = [c for c in vertical_targets.keys() if c != gen_cat]
        reserved_cats.sort(key=lambda x: vertical_targets[x]["priority"])

        for v_cat in reserved_cats:
            v_info = vertical_targets[v_cat]
            # 1. Seat displaced first
            for app in displaced_reserved[:]:
                v_traits, _, _ = _get_categorized_traits(app.applicant_id)
                if v_traits and v_traits[0] == v_cat:
                    if ignore_seat_limits or v_info["filled"] < v_info["seats"]:
                        _assign_seat_to_applicant(app, v_cat, "Reserved", allocated_list, unallocated, v_info, status_field)
                        displaced_reserved.remove(app)
            
            # 2. Fill remaining from rank list
            for app in unallocated[:]:
                v_traits, _, _ = _get_categorized_traits(app.applicant_id)
                if v_traits and v_traits[0] == v_cat:
                    if ignore_seat_limits or v_info["filled"] < v_info["seats"]:
                        _assign_seat_to_applicant(app, v_cat, "Reserved", allocated_list, unallocated, v_info, status_field)
            
            # 3. Karnataka Adjustment for this reserved category
            ka_v_target = ka_targets.get(v_cat, {}).get("seats", 0)
            if ka_v_target > 0:
                ka_in_v = [a for a in allocated_list if a.vertical_category == v_cat and "Karnataka" in get_applicant_categories(a.applicant_id)]
                deficit = ka_v_target - len(ka_in_v)
                if deficit > 0:
                    # Must belong to that vertical + Karnataka
                    potential_ka = [u for u in unallocated if "Karnataka" in get_applicant_categories(u.applicant_id) and v_cat in get_applicant_categories(u.applicant_id)]
                    for in_cand in potential_ka:
                        if deficit <= 0: break
                        eligible_out = [a for a in allocated_list if a.vertical_category == v_cat and "Karnataka" not in get_applicant_categories(a.applicant_id)]
                        if eligible_out:
                            eligible_out.sort(key=lambda x: (float(getattr(x, "total_score", 0) or getattr(x, "nlsat_part_a_score", 0) or getattr(x, "entrance_score", 0) or 0)))
                            _execute_candidate_displacement(in_cand, eligible_out[0], allocated_list, unallocated, status_field)
                            in_cand.vertical_category = v_cat
                            in_cand.allocation_type = "Reserved"
                            deficit -= 1

        # PHASE C: Horizontally Reserved (Women and PWD) - Global
        # "The following horizontal reservations shall be applied across categories: 36 Women, 6 PWD"
        h_order = ["PWD", "Women"] # Typically PWD first
        for h_cat in h_order:
            h_info = horizontal_targets.get(h_cat)
            if not h_info: continue
            
            h_count = len([a for a in allocated_list if h_cat in get_applicant_categories(a.applicant_id)])
            deficit = h_info["seats"] - h_count
            
            if deficit > 0:
                potential = [u for u in unallocated if h_cat in get_applicant_categories(u.applicant_id)]
                for in_cand in potential:
                    if deficit <= 0: break
                    
                    # Displace lowest All India in their relevant category
                    # We need to find which category this candidate belongs to
                    v_traits, _, _ = _get_categorized_traits(in_cand.applicant_id)
                    v_belong = v_traits[0] if v_traits else gen_cat
                    
                    # Prioritize displacing All India (AI) candidates first
                    ai_candidates = [a for a in allocated_list if a.vertical_category == v_belong 
                                    and "Karnataka" not in get_applicant_categories(a.applicant_id)
                                    and not any(h in get_applicant_categories(a.applicant_id) for h in ["Women", "PWD"])]
                    
                    eligible_out = []
                    if ai_candidates:
                        eligible_out = ai_candidates
                    else:
                        # Fallback: Displace Karnataka candidate if no AI candidate is available in this vertical
                        eligible_out = [a for a in allocated_list if a.vertical_category == v_belong 
                                        and not any(h in get_applicant_categories(a.applicant_id) for h in ["Women", "PWD"])]
                    
                    if eligible_out:
                        # Displacement: lowest ranked goes out, highest potential in
                        eligible_out.sort(key=lambda x: (float(getattr(x, "total_score", 0) or getattr(x, "nlsat_part_a_score", 0) or getattr(x, "entrance_score", 0) or 0)))
                        _execute_candidate_displacement(in_cand, eligible_out[0], allocated_list, unallocated, status_field)
                        in_cand.vertical_category = v_belong
                        in_cand.allocation_type = "Open" if v_belong == gen_cat else "Reserved"
                        deficit -= 1

        # Sort unallocated by merit for waitlist phase
        unallocated.sort(key=lambda x: (-(float(getattr(x, "total_score", 0) or getattr(x, "nlsat_part_a_score", 0) or getattr(x, "entrance_score", 0) or 0)), -(getattr(x, "interview_score", 0) or getattr(x, "nlsat_part_b_score", 0) or 0)))

        # PHASE D: Waitlist
        if not is_shortlist_phase and not ignore_seat_limits:
            for v_cat in vertical_targets.keys():
                v_info = vertical_targets[v_cat]
                w_seats = v_info["waitlist_seats"]
                for app in unallocated[:]:
                    if v_info["waitlist_filled"] < w_seats:
                        v_traits, _, _ = _get_categorized_traits(app.applicant_id)
                        app_v = v_traits[0] if v_traits else gen_cat
                        if app_v == v_cat:
                            _assign_seat_to_applicant(app, v_cat, "Waitlist", allocated_list, unallocated, v_info, status_field, is_waitlist=True)

        # Re-set display categories
        for app in allocated_list:
            v_traits, h_traits, c_traits = _get_categorized_traits(app.applicant_id)
            parts = [app.vertical_category]

            # Populate individual fields for UI visibility
            if hasattr(app, "compartmentalized_category"):
                app.compartmentalized_category = c_traits[0] if c_traits else ""
            if hasattr(app, "horizontal_categories"):
                app.horizontal_categories = ", ".join(h_traits)
            
            if c_traits: parts.extend(c_traits)
            if h_traits: parts.extend(h_traits)
            
            display_field = "allocated_category" if hasattr(app, "allocated_category") else "shortlist_category"
            setattr(app, display_field, " + ".join(parts))

        if not ignore_seat_limits:
            for u in unallocated:
                setattr(u, status_field, "Rejected")
                u.allocation_type = "Not Allocated"
                if not getattr(u, "remarks", ""):
                    u.remarks = "Rank beyond available seat capacity and waitlist limit"

        # PHASE E: Populate category-specific tables for UI display (Shortlisting only)
        if getattr(doc, "doctype", "") == "Shortlisting Merit List" and hasattr(doc, "category_summary"):
            table_map = {
                "General": "general_list",
                "SC": "sc_list",
                "ST": "st_list",
                "OBC": "obc_list",
                "EWS": "ews_list",
                "Karnataka": "karnataka_list",
                "Women": "women_list",
                "PWD": "pwd_list"
            }
            
            doc.set("category_summary", [])
            
            # 1. Vertical Summary
            for v_cat, v_info in vertical_targets.items():
                actual_seats = v_info["seats"] / multiplier if multiplier else 0
                doc.append("category_summary", {
                    "category": v_cat,
                    "seats": int(actual_seats),
                    "multiplier": multiplier,
                    "required_to_shortlist": v_info["seats"],
                    "actually_shortlisted": len([a for a in allocated_list if a.vertical_category == v_cat])
                })
                
            # 2. Horizontal/Sub-quota Summary
            # Combine horizontal and common targets for the summary
            all_sub_targets = horizontal_targets.copy()
            for k, v in ka_targets.items():
                all_sub_targets[f"Karnataka ({k})"] = v

            for cat, h_info in all_sub_targets.items():
                if not cat: continue
                actual_seats = h_info["seats"] / multiplier if multiplier else 0
                # Fix: Actually shortlisted should only count candidates belonging to THIS specific category
                if cat == "Karnataka (Common)":
                    actually_shortlisted = len([a for a in allocated_list if "Karnataka" in get_applicant_categories(a.applicant_id)])
                elif "Karnataka (" in cat:
                    # Extract vertical category from "Karnataka (SC)"
                    v_cat = cat.split("(")[1].split(")")[0]
                    actually_shortlisted = len([a for a in allocated_list if "Karnataka" in get_applicant_categories(a.applicant_id) and a.vertical_category == v_cat])
                else:
                    actually_shortlisted = len([a for a in allocated_list if cat in get_applicant_categories(a.applicant_id)])

                doc.append("category_summary", {
                    "category": cat,
                    "seats": int(actual_seats),
                    "multiplier": multiplier,
                    "required_to_shortlist": h_info["seats"],
                    "actually_shortlisted": actually_shortlisted
                })

            for app in allocated_list:
                # 1. Primary Vertical
                v_table = _get_table_by_name(app.vertical_category, table_map)
                if v_table and hasattr(doc, v_table):
                    doc.append(v_table, _copy_applicant_data(app))
                
                # 2. Sub-quotas (Karnataka, Women, PWD)
                app_cats = get_applicant_categories(app.applicant_id)
                # Match against table_map keys case-insensitively
                for cat in app_cats:
                    if not cat: continue
                    found_key = next((k for k in ["Karnataka", "Women", "PWD"] if k.lower() == cat.lower()), None)
                    if found_key:
                        s_table = table_map.get(found_key)
                        if s_table and hasattr(doc, s_table):
                             doc.append(s_table, _copy_applicant_data(app))

    return True


def _get_table_by_name(category_name, table_map):
    if not category_name: return None
    name = category_name.lower()
    for key, table_field in table_map.items():
        if key.lower() in name: return table_field
    return None


def _copy_applicant_data(app):
    fields = [
        "applicant_id", "candidate_name", "program", "nlsat_part_a_score",
        "shortlist_rank", "category_rank", "actual_category", "date_of_birth",
        "vertical_category", "compartmentalized_category", "horizontal_categories",
        "allocation_type", "shortlist_category", "shortlist_status",
        "nlsat_part_b_score", "total_score", "selection_status", "overall_rank",
        "admission_rank", "allocated_category"
    ]
    return {f: getattr(app, f, None) for f in fields}


def _get_candidate_min_percentile(applicant_id, vertical_cat, vertical_targets, compartmental_targets, horizontal_targets):
    app_cats = get_applicant_categories(applicant_id)
    thresholds = []
    if vertical_cat in vertical_targets: thresholds.append(vertical_targets[vertical_cat].get("min_percentile") or 0)
    for cat in app_cats:
        if cat in horizontal_targets: thresholds.append(horizontal_targets[cat].get("min_percentile") or 0)
        for v_dict in compartmental_targets.values():
            if cat in v_dict: thresholds.append(v_dict[cat].get("min_percentile") or 0)
    thresholds = [t for t in thresholds if t > 0]
    return min(thresholds) if thresholds else 0


def _assign_seat_to_applicant(app, vertical_cat, alloc_type, allocated_list, unallocated, v_info, status_field, is_waitlist=False):
    if is_waitlist: status_value = "Waitlisted"
    else:
        if status_field == "shortlist_status": status_value = "Shortlisted"
        elif status_field == "selection_status": status_value = "Selected"
        else: status_value = "Selected"
        
    setattr(app, status_field, status_value)
    app.vertical_category = vertical_cat
    app.allocation_type = alloc_type
    if hasattr(app, "allocated_category"): app.allocated_category = vertical_cat
    if hasattr(app, "shortlist_category"): app.shortlist_category = vertical_cat
    if is_waitlist: v_info["waitlist_filled"] += 1
    else: v_info["filled"] += 1
    allocated_list.append(app)
    unallocated.remove(app)


def _rebalance_compartmental_quota(v_cat, c_targets, allocated_list, unallocated, v_info, is_shortlist, policy, status_field):
    for c_cat, c_info in c_targets.items():
        current_coverage = [a for a in allocated_list if a.vertical_category == v_cat and c_cat in get_applicant_categories(a.applicant_id)]
        deficit = c_info["total"] - len(current_coverage)
        if deficit > 0:
            open_merit_cat = policy.open_merit_category or "General"
            potential_candidates = [u for u in unallocated if c_cat in get_applicant_categories(u.applicant_id) and (v_cat == open_merit_cat or v_cat in get_applicant_categories(u.applicant_id))]
            for in_cand in potential_candidates:
                if deficit <= 0: break
                if not is_shortlist:
                    threshold = c_info["min_percentile"]
                    if (in_cand.get("percentile_score") or 0) < (threshold or 0): continue
                eligible_out = [a for a in allocated_list if a.vertical_category == v_cat and c_cat not in get_applicant_categories(a.applicant_id)]
                if eligible_out:
                    eligible_out.sort(key=lambda x: (False, float(getattr(x, "total_score", 0) or getattr(x, "nlsat_part_a_score", 0) or getattr(x, "entrance_score", 0) or 0)))
                    _execute_candidate_displacement(in_cand, eligible_out[0], allocated_list, unallocated, status_field)
                    if hasattr(in_cand, "compartmentalized_category"): in_cand.compartmentalized_category = c_cat
                    deficit -= 1
                    if v_cat == (policy.open_merit_category or "General"):
                        all_horizontal_names = [c.category_name for c in policy.compartmental_reservations] + [c.category_name for c in policy.horizontal_reservations]
                        _apply_merit_migration_protection(eligible_out[0], v_cat, all_horizontal_names, allocated_list, unallocated, status_field)


def _execute_candidate_displacement(in_cand, out_cand, allocated_list, unallocated, status_field):
    v_cat = out_cand.vertical_category
    a_type = out_cand.allocation_type
    setattr(out_cand, status_field, "Rejected")
    out_cand.vertical_category = ""
    out_cand.allocation_type = "Not Allocated"
    if hasattr(out_cand, "compartmentalized_category"): out_cand.compartmentalized_category = ""
    if hasattr(out_cand, "horizontal_categories"): out_cand.horizontal_categories = ""
    if hasattr(out_cand, "allocated_category"): out_cand.allocated_category = ""
    if hasattr(out_cand, "shortlist_category"): out_cand.shortlist_category = ""
    allocated_list.remove(out_cand)
    unallocated.append(out_cand)
    selected_status = "Shortlisted" if status_field == "shortlist_status" else "Selected"
    setattr(in_cand, status_field, selected_status)
    in_cand.vertical_category = v_cat
    in_cand.allocation_type = a_type
    if hasattr(in_cand, "allocated_category"): in_cand.allocated_category = v_cat
    if hasattr(in_cand, "shortlist_category"): in_cand.shortlist_category = v_cat
    allocated_list.append(in_cand)
    unallocated.remove(in_cand)
    allocated_list.sort(key=lambda x: (-(float(getattr(x, "total_score", 0) or getattr(x, "nlsat_part_a_score", 0) or getattr(x, "entrance_score", 0) or 0)), -(getattr(x, "nlsat_part_b_score", 0) or 0)))


def _apply_merit_migration_protection(app, open_merit_cat, all_horizontal_names, allocated_list, unallocated, status_field):
    all_cats = get_applicant_categories(app.applicant_id)
    cat_data = frappe.get_all("Admission Category", filters={"name": ["in", all_cats]}, fields=["name", "reservation_type"])
    reserved_vs = [c.name for c in cat_data if c.reservation_type == "Vertical" and c.name != open_merit_cat]
    if not reserved_vs: return
    target_v_cat = reserved_vs[0]
    reserved_allocated = [a for a in allocated_list if a.vertical_category == target_v_cat]
    if reserved_allocated:
        reserved_allocated.sort(key=lambda x: (float(getattr(x, "total_score", 0) or getattr(x, "nlsat_part_a_score", 0) or getattr(x, "entrance_score", 0) or 0), float(getattr(x, "interview_score", 0) or getattr(x, "nlsat_part_b_score", 0) or 0)))
        lowest_reserved = reserved_allocated[0]
        
        score_app = float(getattr(app, "total_score", 0) or getattr(app, "nlsat_part_a_score", 0) or getattr(app, "entrance_score", 0) or 0)
        score_lowest = float(getattr(lowest_reserved, "total_score", 0) or getattr(lowest_reserved, "nlsat_part_a_score", 0) or getattr(lowest_reserved, "entrance_score", 0) or 0)

        if score_app > score_lowest:
             _execute_candidate_displacement(app, lowest_reserved, allocated_list, unallocated, status_field)
