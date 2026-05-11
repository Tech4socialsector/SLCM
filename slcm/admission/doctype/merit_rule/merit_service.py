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
    horizontals = [c.name for c in cat_data if c.reservation_type == "Horizontal" or "women" in c.name.lower() or "pwd" in c.name.lower()]
    compartmental = [c.name for c in cat_data if c.reservation_type == "Compartmental" or "karnataka" in c.name.lower()]
    
    # Remove duplicates if name-based matching picked up something already in a category
    horizontals = [h for h in horizontals if h not in verticals]
    compartmental = [c for c in compartmental if c not in verticals and c not in horizontals]
    
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
        if processing_stage == "Part A Ranking":
            return (
                -(float(x.total_score or 0)),
                getattr(x, "name", "") or getattr(x, "applicant_id", "")
            )
        
        # Final Allotment tie-breakers (Descending for scores, Ascending for DOB and Name)
        return (
            -(float(x.total_score or 0)),
            -(float(getattr(x, "interview_score", 0) or getattr(x, "nlsat_part_b_score", 0) or 0)),
            -(float(getattr(x, "entrance_score", 0) or getattr(x, "nlsat_part_a_score", 0) or 0)),
            -(float(getattr(x, "hsc_percentage", 0) or 0)),
            get_timestamp(x.date_of_birth) if getattr(x, "date_of_birth", None) else 9999999999,
            getattr(x, "name", "") or getattr(x, "applicant_id", "")
        )

    # Helper to check for same rank (ignores deterministic fallback)
    def is_same_rank(app1, app2):
        if processing_stage == "Part A Ranking":
            return float(app1.total_score or 0) == float(app2.total_score or 0)
        
        k1 = (float(app1.total_score or 0), 
              float(getattr(app1, "interview_score", 0) or getattr(app1, "nlsat_part_b_score", 0) or 0),
              float(getattr(app1, "entrance_score", 0) or getattr(app1, "nlsat_part_a_score", 0) or 0),
              float(getattr(app1, "hsc_percentage", 0) or 0),
              get_timestamp(app1.date_of_birth) if getattr(app1, "date_of_birth", None) else 0)
        
        k2 = (float(app2.total_score or 0), 
              float(getattr(app2, "interview_score", 0) or getattr(app2, "nlsat_part_b_score", 0) or 0),
              float(getattr(app2, "entrance_score", 0) or getattr(app2, "nlsat_part_a_score", 0) or 0),
              float(getattr(app2, "hsc_percentage", 0) or 0),
              get_timestamp(app2.date_of_birth) if getattr(app2, "date_of_birth", None) else 0)
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

    # 3. Compartment Rank (Karnataka Students)
    compartmentalized_groups = defaultdict(list)
    for row in applicant_rows:
        # Check if they have the Karnataka trait
        is_karnataka = "karnataka" in (getattr(row, "compartmentalized_category", "") or "").lower()
        if not is_karnataka:
            # Check trait logic if field not set yet
            from slcm.admission.doctype.seat_allocation.seat_allocation import get_applicant_categories
            is_karnataka = any("karnataka" in c.lower() for c in get_applicant_categories(row.applicant_id))
            
        if is_karnataka:
            cat = getattr(row, "actual_category", None) or "General"
            key = f"{cat}_Karnataka"
            compartmentalized_groups[key].append(row)

    for group in compartmentalized_groups.values():
        group.sort(key=get_stable_key)
        current_rank = 1
        for i, row in enumerate(group):
            if i > 0:
                if not is_same_rank(row, group[i-1]):
                    current_rank = i + 1
            
            if hasattr(row, "compartmentalized_rank"):
                row.compartmentalized_rank = current_rank


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
        else:
            # If program is not provided, ensure we don't match a program-specific list
            # by checking if program field is empty (or just matching level-wise as before)
            # Actually, the user probably wants to match the level-wise one.
            pass

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
            # To do this, we must clear the old document
            if existing_doc.docstatus == 1:
                existing_doc.cancel()
                frappe.delete_doc("Merit List", existing_doc.name, ignore_permissions=True, force=True)
                frappe.db.commit()
            elif existing_doc.docstatus == 0:
                frappe.delete_doc("Merit List", existing_doc.name, ignore_permissions=True, force=True)
                frappe.db.commit()

    merit_rule_filters = {
        "admission_cycle": cycle,
        "campus": campus,
        "program_level": program_level,
        "is_active": 1
    }
    
    # Try program-specific mapping first
    merit_rule_name = None
    if program:
        rule_filters = merit_rule_filters.copy()
        rule_filters["program"] = program
        merit_rule_name = frappe.db.get_value("Merit Rule Mapping", rule_filters, "merit_rule")

    # Fallback to level-wise mapping
    if not merit_rule_name:
        merit_rule_name = frappe.db.get_value("Merit Rule Mapping", merit_rule_filters, "merit_rule")

    if not merit_rule_name:
        prog_msg = f" for Program '{program}'" if program else ""
        frappe.throw(
            f"No active Merit Rule Mapping found{prog_msg} for Program Level '{program_level}', "
            f"Campus '{campus}' and Admission Cycle '{cycle}'.",
            title="Missing Merit Rule Mapping"
        )

    rule = frappe.get_doc("Merit Rule", merit_rule_name)

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
            
        applicant_names = frappe.get_all(
            "Shortlisting Merit Candidate", 
            filters={"parent": sp_name, "shortlist_status": "Shortlisted"}, 
            pluck="applicant_id"
        )
    else:
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
        # Publish real progress to the frontend
        frappe.publish_progress(
            (i + 1) * 100 / total_applicants, 
            title=_("Generating Merit List"), 
            description=_("Processing applicant {0} of {1}").format(i + 1, total_applicants)
        )
        
        app = frappe.get_doc("Eligibility Result", name)
        
        # Filter zero/negative scores for entrance-based stages
        is_advanced = frappe.db.get_value("Program Reservation Policy", {"program": app.program, "admission_cycle": cycle}, "enable_advanced_shortlisting")
        if is_advanced and processing_stage == "Part A Ranking" and (app.get("entrance_test_score") or 0) <= 0:
            continue

        # Score Calculation: Part A only for shortlisting, Part A + B for final allotment
        part_a = float(app.get("entrance_test_score") or 0)
        part_b = float(app.get("interview_score") or 0)
        
        if processing_stage == "Part A Ranking":
            total_score = part_a
        else:
            total_score = part_a + part_b

        status = "Selected" # Selection is handled by advanced allocation logic later

        # Get categorized traits
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
            "actual_category": primary_cat
        })

    if not merit.merit_applicants:
        frappe.throw(
            f"No applicants could be processed for Program Level '{program_level}'.",
            title="Empty Merit List"
        )

    merit.total_applicants = len(merit.merit_applicants)

    # Detect if advanced logic is needed (check first applicant's program PRP)
    first_app_prog = merit.merit_applicants[0].program
    use_advanced = frappe.db.get_value("Program Reservation Policy", {"program": first_app_prog, "admission_cycle": cycle}, "enable_advanced_shortlisting")

    _rank_applicants(merit.merit_applicants, use_advanced_ranking=use_advanced, processing_stage=processing_stage)
    
    # Calculate Percentiles if using advanced ranking
    if use_advanced:
        all_scores = [float(row.entrance_score or 0) for row in merit.merit_applicants]
        total_count = len(all_scores)
        if total_count > 0:
            for row in merit.merit_applicants:
                score = float(row.entrance_score or 0)
                le_count = len([s for s in all_scores if s <= score])
                percentile = (le_count / total_count) * 100
                row.percentile_score = percentile
                # Sync back to Eligibility Result
                frappe.db.set_value("Eligibility Result", row.applicant_id, "percentile_score", percentile)

    # Sort child table rows by overall_rank so they appear in order in the UI
    merit.merit_applicants.sort(key=lambda x: x.overall_rank)
    for i, row in enumerate(merit.merit_applicants):
        row.idx = i + 1
        
    if save:
        merit.insert()

    if save:
        # Log merit calculation for each applicant
        from slcm.admission.doctype.admission_audit_log.audit_service import log_merit_action
        for row in merit.merit_applicants:
            log_merit_action(
                merit_list=merit.name,
                admission_cycle=merit.admission_cycle,
                applicant=row.applicant_id,
                program=row.program,
                action_type="Merit Calculated",
                remarks=f"Calculated via Merit Rule: {merit_rule_name}. Total Score: {row.total_score:.3f}"
            )

        # merit.submit() removed as per request to keep it editable/non-submittable
        frappe.db.commit()
    return merit


# ---------------------------------------------------------
# ADVANCED SEAT ALLOCATION LOGIC (NLSIU PROCESS)
# ---------------------------------------------------------

def execute_advanced_allocation_logic(doc, is_shortlist_allocation=False):
    """
    Generic advanced allocation logic. Configurable via Program Reservation Policy.
    Handles Shortlisting Merit List (Phase 1) and Final Admission (Phase 2).
    """
    clear_category_cache()
    
    # Group applicants by program
    child_table = "shortlist_applicants" if is_shortlist_allocation else "selection_applicant"
    applicants_list = getattr(doc, child_table)
    
    grouped_by_program = {}
    for row in applicants_list:
        grouped_by_program.setdefault(row.program, []).append(row)
        # Ensure total_score is available for sorting if not present (Shortlisting Merit Candidate case)
        if not hasattr(row, "total_score") and hasattr(row, "nlsat_part_a_score"):
            row.total_score = row.nlsat_part_a_score
            
    # Perform ranking before allocation to ensure overall_rank, category_rank etc. are set
    processing_stage = "Part A Ranking" if is_shortlist_allocation else "Final Allotment Ranking"
    _rank_applicants(
        applicants_list, 
        use_advanced_ranking=True, 
        processing_stage=processing_stage
    )

    total_selected = 0
    total_rejected = 0
    
    all_allocated = []
    all_processed = []

    for program, applicants in grouped_by_program.items():
        # If the parent document has a program specified, skip others
        if getattr(doc, "program", None) and program != doc.program:
            continue

        policy_name = frappe.db.get_value("Program Reservation Policy", {
            "admission_cycle": doc.admission_cycle,
            "program": program
        }, "name")
        
        if not policy_name:
            continue
            
        policy = frappe.get_doc("Program Reservation Policy", policy_name)
        if not policy.enable_advanced_shortlisting:
            continue

        is_shortlist_phase = is_shortlist_allocation or (doc.admission_phase == "Shortlisting Merit List")
        open_merit_cat = policy.open_merit_category or "General"
        multiplier = policy.get("shortlisting_multiplier") or 1.0
        
        # 1. Setup Seat Targets
        vertical_targets = {}
        for v in policy.categories:
            target = v.shortlisting_target if is_shortlist_phase else v.seats
            if is_shortlist_phase and not target:
                target = int((v.seats or 0) * multiplier)

            vertical_targets[v.category_name] = {
                "total": target or 0,
                "filled": 0,
                "waitlist_total": v.waitlist_seats if not is_shortlist_phase else 0,
                "waitlist_filled": 0,
                "priority": v.priority,
                "min_percentile": v.min_percentile
            }

        compartmental_targets = {}
        for c in policy.compartmental_reservations:
            target = c.shortlisting_target if is_shortlist_phase else c.seats
            if is_shortlist_phase and not target:
                target = int((c.seats or 0) * multiplier)

            # If vertical_category is specified, only apply to that category.
            # Otherwise, apply to all vertical categories.
            v_cats = [c.vertical_category] if c.vertical_category else [v.category_name for v in policy.categories]
            
            for v_cat in v_cats:
                if v_cat not in compartmental_targets: compartmental_targets[v_cat] = {}
                compartmental_targets[v_cat][c.category_name] = {
                    "total": target or 0,
                    "filled": 0,
                    "waitlist_total": c.waitlist_seats if not is_shortlist_phase else 0,
                    "waitlist_filled": 0,
                    "priority": c.priority,
                    "min_percentile": c.min_percentile
                }

        horizontal_targets = {}
        for h in policy.horizontal_reservations:
            target = h.shortlisting_target if is_shortlist_phase else h.seats
            if is_shortlist_phase and not target:
                target = int((h.seats or 0) * multiplier)

            horizontal_targets[h.category_name] = {
                "total": target or 0,
                "filled": 0,
                "waitlist_total": h.waitlist_seats if not is_shortlist_phase else 0,
                "waitlist_filled": 0,
                "priority": h.priority,
                "min_percentile": h.min_percentile
            }

        # Identification for generic displacement protection
        all_horizontal_names = list(horizontal_targets.keys())
        for v_cats in compartmental_targets.values():
            all_horizontal_names.extend(list(v_cats.keys()))

        # 2. Sort Applicants
        if is_shortlist_phase:
            applicants.sort(key=lambda x: (-(x.nlsat_part_a_score or 0), -(x.total_score or 0)))
        else:
            applicants.sort(key=lambda x: (-(x.total_score or 0), -(getattr(x, "nlsat_part_b_score", 0) or 0)))

        unallocated = applicants[:]
        allocated_list = []

        # ---------------------------------------------------------
        # PHASE 1: Open Merit
        # ---------------------------------------------------------
        open_merit_info = vertical_targets.get(open_merit_cat)
        if open_merit_info:
            for app in unallocated[:]:
                if open_merit_info["filled"] < open_merit_info["total"]:
                    # Percentile Check (If score is present)
                    threshold = _get_candidate_min_percentile(app.applicant_id, open_merit_cat, vertical_targets, compartmental_targets, horizontal_targets)
                    if (app.get("percentile_score") or 0) < (threshold or 0):
                        continue
                            
                    _assign_seat_to_applicant(app, open_merit_cat, "Open", allocated_list, unallocated, open_merit_info, is_shortlist_allocation)
        
        # ---------------------------------------------------------
        # PHASE 2: Compartmental Rebalancing in Open Merit
        # ---------------------------------------------------------
        if open_merit_cat in compartmental_targets:
            _rebalance_compartmental_quota(
                open_merit_cat, compartmental_targets[open_merit_cat], allocated_list, unallocated, 
                vertical_targets[open_merit_cat], is_shortlist_phase, policy, is_shortlist_allocation
            )

        # ---------------------------------------------------------
        # PHASE 3: Vertical Reserved Categories
        # ---------------------------------------------------------
        reserved_categories = sorted([c for c in vertical_targets.keys() if c != open_merit_cat], 
                                     key=lambda c: vertical_targets[c]["priority"] or 999)
        
        for v_cat in reserved_categories:
            v_info = vertical_targets[v_cat]
            for app in unallocated[:]:
                if v_info["filled"] < v_info["total"]:
                    app_cats = get_applicant_categories(app.applicant_id)
                    if v_cat in app_cats:
                        # Percentile Check (If score is present)
                        threshold = _get_candidate_min_percentile(app.applicant_id, v_cat, vertical_targets, compartmental_targets, horizontal_targets)
                        if (app.get("percentile_score") or 0) < (threshold or 0):
                            continue
                        
                        _assign_seat_to_applicant(app, v_cat, "Reserved", allocated_list, unallocated, v_info, is_shortlist_allocation)

        # ---------------------------------------------------------
        # PHASE 4: Compartmental Rebalancing in Reserved Categories
        # ---------------------------------------------------------
        for v_cat in reserved_categories:
            if v_cat in compartmental_targets:
                _rebalance_compartmental_quota(
                    v_cat, compartmental_targets[v_cat], allocated_list, unallocated, 
                    vertical_targets[v_cat], is_shortlist_phase, policy, is_shortlist_allocation
                )

        # ---------------------------------------------------------
        # PHASE 5: Horizontal Overall Quotas
        # ---------------------------------------------------------
        horizontal_categories = sorted(horizontal_targets.keys(), key=lambda c: horizontal_targets[c]["priority"] or 999)
        
        for h_cat in horizontal_categories:
            h_info = horizontal_targets[h_cat]
            current_coverage = [a for a in allocated_list if h_cat in get_applicant_categories(a.applicant_id)]
            deficit = h_info["total"] - len(current_coverage)
            
            if deficit > 0:
                potential_candidates = [u for u in unallocated if h_cat in get_applicant_categories(u.applicant_id)]
                
                for in_cand in potential_candidates:
                    if deficit <= 0: break
                    
                    if not is_shortlist_phase:
                        threshold = h_info["min_percentile"]
                        if (in_cand.get("percentile_score") or 0) < (threshold or 0):
                            continue

                    app_categories = get_applicant_categories(in_cand.applicant_id)
                    v_cat_belong = next((v for v in reserved_categories + [open_merit_cat] if v in app_categories), None)
                    
                    if not v_cat_belong: continue
                    
                    # Identify candidates to displace (prioritize non-compartmental)
                    eligible_out = [a for a in allocated_list if a.vertical_category == v_cat_belong and h_cat not in get_applicant_categories(a.applicant_id)]
                    if eligible_out:
                        # Prioritize displacing non-compartmentalized candidates
                        compartmental_names = list(compartmental_targets.get(v_cat_belong, {}).keys())
                        eligible_out.sort(key=lambda x: (any(c in compartmental_names for c in get_applicant_categories(x.applicant_id)), x.total_score or 0))
                        
                        _execute_candidate_displacement(in_cand, eligible_out[0], allocated_list, unallocated, is_shortlist_allocation)
                        deficit -= 1
                        
                        if v_cat_belong == open_merit_cat:
                            _apply_merit_migration_protection(eligible_out[0], open_merit_cat, all_horizontal_names, allocated_list, unallocated, is_shortlist_allocation)

        # ---------------------------------------------------------
        # PHASE 5: Waitlist Allocation (Final Allotment Only)
        # ---------------------------------------------------------
        if not is_shortlist_phase:
            for v_cat in vertical_targets.keys():
                v_info = vertical_targets[v_cat]
                for app in unallocated[:]:
                    if v_info["waitlist_filled"] < v_info["waitlist_total"]:
                        app_cats = get_applicant_categories(app.applicant_id)
                        if v_cat == open_merit_cat or v_cat in app_cats:
                            threshold = _get_candidate_min_percentile(app.applicant_id, v_cat, vertical_targets, compartmental_targets, horizontal_targets)
                            if (app.get("percentile_score") or 0) < (threshold or 0):
                                continue
                            
                            _assign_seat_to_applicant(app, v_cat, "Waitlist", allocated_list, unallocated, v_info, is_shortlist_allocation, is_waitlist=True)

        total_selected += len([a for a in allocated_list if getattr(a, "selection_status", "") != "Waitlisted" and getattr(a, "shortlist_status", "") != "Waitlisted"])
        all_allocated.extend(allocated_list)
        all_processed.extend(applicants)

        # ---------------------------------------------------------
        # FINAL PASS: Recalculate ranks after all displacements
        # ---------------------------------------------------------
        _rank_applicants(
            all_processed, 
            use_advanced_ranking=True, 
            processing_stage=processing_stage
        )

        # Ensure lists are sorted by overall rank for display
        all_allocated.sort(key=lambda x: x.overall_rank)
        all_processed.sort(key=lambda x: x.overall_rank)
        
        # ---------------------------------------------------------
        # FINAL PASS: Build display strings and categories
        # ---------------------------------------------------------
        for app in allocated_list:
            # Get categorized traits
            v_traits, h_traits, c_traits = _get_categorized_traits(app.applicant_id)
            
            # 1. Update Actual Category (preserve original vertical category)
            if v_traits:
                app.actual_category = v_traits[0]
            elif not getattr(app, "actual_category", None):
                app.actual_category = "General"
                
            # 2. Capture horizontal traits (multi-value support)
            if hasattr(app, "horizontal_categories"):
                app.horizontal_categories = ", ".join(sorted(h_traits)) if h_traits else "Open"
            
            # 3. Capture compartmental traits (Karnataka)
            if hasattr(app, "compartmentalized_category"):
                app.compartmentalized_category = c_traits[0] if c_traits else "Open"
            
            # 4. Build combined display string: Vertical + Compartmental + Horizontal
            display_field = "shortlist_category" if is_shortlist_allocation else "allocated_category"
            if hasattr(app, display_field):
                parts = [app.vertical_category]
                if getattr(app, "compartmentalized_category", None) and app.compartmentalized_category != "Open":
                    parts.append(app.compartmentalized_category)
                if getattr(app, "horizontal_categories", None) and app.horizontal_categories != "Open":
                    h_list = [h.strip() for h in app.horizontal_categories.split(",") if h.strip()]
                    parts.extend(h_list)
                
                setattr(app, display_field, " + ".join(parts))

        for u in unallocated:
            status_field = "shortlist_status" if is_shortlist_allocation else "selection_status"
            setattr(u, status_field, "Rejected")
            
            # Fill basic info for audit
            v_traits, h_traits, c_traits = _get_categorized_traits(u.applicant_id)
            u.actual_category = v_traits[0] if v_traits else "General"
            u.vertical_category = u.actual_category
            u.allocation_type = "Not Allocated"
            if hasattr(u, "horizontal_categories"): u.horizontal_categories = "Open"
            if hasattr(u, "compartmentalized_category"): u.compartmentalized_category = "Open"
            
            total_rejected += 1

        doc.total_selected = total_selected
    doc.total_rejected = total_rejected

    # Ensure ranks are mapped for the child tables
    for app in all_processed:
        if is_shortlist_allocation:
            app.shortlist_rank = app.overall_rank
        else:
            app.admission_rank = app.overall_rank
            # For final allotment, also capture Part A rank if available from previous phase
            if not getattr(app, "shortlist_rank", None):
                # (Optional: fetch from Shortlisting Merit List if needed, 
                # but usually it's already in Eligibility Result if synced)
                pass

    # ---------------------------------------------------------
    # POPULATE CATEGORY-SPECIFIC TABLES
    # ---------------------------------------------------------
    if is_shortlist_allocation:
        # 1. Master Rank List (Everyone processed)
        doc.set("shortlist_applicants", [])
        # Sort by overall_rank (calculated in _rank_applicants)
        all_processed.sort(key=lambda x: x.overall_rank or 999999)
        for app in all_processed:
            doc.append("shortlist_applicants", _copy_applicant_data(app))

        # 2. Category-specific Lists (Prevention of duplicates)
        category_tables = {
            "General": "general_list",
            "SC": "sc_list",
            "ST": "st_list",
            "OBC": "obc_list",
            "OBC-NCL": "obc_list",
            "EWS": "ews_list",
            "Karnataka": "karnataka_list",
            "Women": "women_list",
            "PWD": "pwd_list"
        }
        for t in category_tables.values(): doc.set(t, [])

        for app in all_allocated:
            row_data = _copy_applicant_data(app)
            v_cat = app.vertical_category
            v_traits, h_traits, c_traits = _get_categorized_traits(app.applicant_id)
            
            # Set of tables already added to for this candidate (prevents duplicates)
            added_to = set()

            # Map vertical bucket (General/SC/ST/etc)
            v_table = _get_table_by_name(v_cat, category_tables)
            if v_table:
                doc.append(v_table, row_data)
                added_to.add(v_table)
            
            # ALSO map original vertical trait (fixes OBC list for candidates in General)
            for trait in v_traits:
                vt_table = _get_table_by_name(trait, category_tables)
                if vt_table and vt_table not in added_to:
                    doc.append(vt_table, row_data)
                    added_to.add(vt_table)
            
            # Map compartmental traits (Karnataka)
            for trait in c_traits:
                c_table = _get_table_by_name(trait, category_tables)
                if c_table and c_table not in added_to:
                    doc.append(c_table, row_data)
                    added_to.add(c_table)

            # Map horizontal traits (Women/PWD)
            for trait in h_traits:
                h_table = _get_table_by_name(trait, category_tables)
                if h_table and h_table not in added_to:
                    doc.append(h_table, row_data)
                    added_to.add(h_table)

    return True

def _get_table_by_name(category_name, table_map):
    if not category_name: return None
    name = category_name.lower()
    for key, table_field in table_map.items():
        if key.lower() in name:
            return table_field
    return None

def _copy_applicant_data(app):
    """Creates a dict for child table row from applicant object/dict."""
    fields = [
        "applicant_id", "candidate_name", "program", "nlsat_part_a_score",
        "shortlist_rank", "category_rank", "actual_category", "date_of_birth",
        "vertical_category", "compartmentalized_category", "horizontal_categories",
        "allocation_type", "shortlist_category", "shortlist_status",
        "nlsat_part_b_score", "total_score", "selection_status", "overall_rank",
        "admission_rank", "allocated_category"
    ]
    data = {}
    for f in fields:
        data[f] = getattr(app, f, None)
    return data

def _get_candidate_min_percentile(applicant_id, vertical_cat, vertical_targets, compartmental_targets, horizontal_targets):
    """
    Finds the minimum percentile for a candidate based on their traits and assigned vertical.
    If multiple traits apply, usually the most lenient (lowest) threshold applies as per rules.
    """
    app_cats = get_applicant_categories(applicant_id)
    thresholds = []
    
    # 1. From assigned vertical
    if vertical_cat in vertical_targets:
        thresholds.append(vertical_targets[vertical_cat].get("min_percentile") or 0)
        
    # 2. From candidate's other traits (Horizontal/Compartmental)
    for cat in app_cats:
        # Check horizontal targets
        if cat in horizontal_targets:
            thresholds.append(horizontal_targets[cat].get("min_percentile") or 0)
        # Check compartmental targets
        for v_dict in compartmental_targets.values():
            if cat in v_dict:
                thresholds.append(v_dict[cat].get("min_percentile") or 0)
                
    # Filter out 0s. 
    # Note: If multiple apply, we use the candidate's natural category threshold 
    # to determine their overall eligibility for the admission process.
    thresholds = [t for t in thresholds if t > 0]
    return min(thresholds) if thresholds else 0

def _assign_seat_to_applicant(app, vertical_cat, alloc_type, allocated_list, unallocated, v_info, is_shortlist_allocation=False, is_waitlist=False):
    status_field = "shortlist_status" if is_shortlist_allocation else "selection_status"
    
    if is_waitlist:
        status_value = "Waitlisted"
    else:
        status_value = "Shortlisted" if is_shortlist_allocation else "Selected"
        
    setattr(app, status_field, status_value)
    app.vertical_category = vertical_cat
    app.allocation_type = alloc_type
    
    if hasattr(app, "allocated_category"):
        app.allocated_category = vertical_cat
    if hasattr(app, "shortlist_category"):
        app.shortlist_category = vertical_cat
        
    if is_waitlist:
        v_info["waitlist_filled"] += 1
    else:
        v_info["filled"] += 1
        
    allocated_list.append(app)
    unallocated.remove(app)

def _rebalance_compartmental_quota(v_cat, c_targets, allocated_list, unallocated, v_info, is_shortlist, policy, is_shortlist_allocation=False):
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
                    if (in_cand.get("percentile_score") or 0) < (threshold or 0):
                        continue

                eligible_out = [a for a in allocated_list if a.vertical_category == v_cat and c_cat not in get_applicant_categories(a.applicant_id)]
                if eligible_out:
                    # Sort to displace lowest rank non-compartmentalized first
                    eligible_out.sort(key=lambda x: (False, x.total_score or 0)) # Generic: anyone without the trait is same
                    _execute_candidate_displacement(in_cand, eligible_out[0], allocated_list, unallocated, is_shortlist_allocation)
                    if hasattr(in_cand, "compartmentalized_category"):
                        in_cand.compartmentalized_category = c_cat
                    deficit -= 1
                    
                    if v_cat == (policy.open_merit_category or "General"):
                        all_horizontal_names = [c.category_name for c in policy.compartmental_reservations] + [c.category_name for c in policy.horizontal_reservations]
                        _apply_merit_migration_protection(eligible_out[0], v_cat, all_horizontal_names, allocated_list, unallocated, is_shortlist_allocation)

def _execute_candidate_displacement(in_cand, out_cand, allocated_list, unallocated, is_shortlist_allocation=False):
    v_cat = out_cand.vertical_category
    a_type = out_cand.allocation_type
    
    status_field = "shortlist_status" if is_shortlist_allocation else "selection_status"
    selected_status = "Shortlisted" if is_shortlist_allocation else "Selected"
    
    setattr(out_cand, status_field, "Rejected")
    out_cand.vertical_category = "Open"
    out_cand.allocation_type = "Not Allocated"
    if hasattr(out_cand, "compartmentalized_category"):
        out_cand.compartmentalized_category = "Open"
    if hasattr(out_cand, "horizontal_categories"):
        out_cand.horizontal_categories = "Open"
    if hasattr(out_cand, "allocated_category"):
        out_cand.allocated_category = ""
    if hasattr(out_cand, "shortlist_category"):
        out_cand.shortlist_category = ""
        
    allocated_list.remove(out_cand)
    unallocated.append(out_cand)
    
    setattr(in_cand, status_field, selected_status)
    in_cand.vertical_category = v_cat
    in_cand.allocation_type = a_type
    # Note: compartment and horizontal are set by the caller or in final pass
    if hasattr(in_cand, "allocated_category"):
        in_cand.allocated_category = v_cat
    if hasattr(in_cand, "shortlist_category"):
        in_cand.shortlist_category = v_cat
        
    allocated_list.append(in_cand)
    unallocated.remove(in_cand)
    
    # Resort allocated list to maintain rank order
    allocated_list.sort(key=lambda x: (-(x.total_score or 0), -(getattr(x, "nlsat_part_b_score", 0) or 0)))

def _apply_merit_migration_protection(app, open_merit_cat, all_horizontal_names, allocated_list, unallocated, is_shortlist_allocation=False):
    """
    Ensures that reserved candidates displaced from the Open list are migrated to their reserved vertical category.
    """
    app_cats = get_applicant_categories(app.applicant_id)
    reserved_vs = [c for c in app_cats if c not in all_horizontal_names and c != open_merit_cat]
    
    if not reserved_vs: return
    
    target_v_cat = reserved_vs[0]
    reserved_allocated = [a for a in allocated_list if a.vertical_category == target_v_cat]
    
    if reserved_allocated:
        # Sort to find the actual lowest rank candidate in this reserved vertical
        reserved_allocated.sort(key=lambda x: (
            float(x.total_score or 0), 
            float(getattr(x, "interview_score", 0) or getattr(x, "nlsat_part_b_score", 0) or 0)
        ))
        lowest_reserved = reserved_allocated[0]
        if (app.total_score or 0) > (lowest_reserved.total_score or 0):
             _execute_candidate_displacement(app, lowest_reserved, allocated_list, unallocated, is_shortlist_allocation)
