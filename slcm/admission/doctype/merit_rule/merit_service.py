import frappe
import math
from frappe import _
from frappe.utils import now_datetime
from collections import defaultdict
from slcm.admission.doctype.seat_allocation.seat_allocation import get_applicant_categories, clear_category_cache


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
    if not use_advanced_ranking:
        # Existing logic
        sort_key = lambda x: (
            x.total_score,
            x.hsc_percentage or 0,
            x.entrance_score or 0
        )
        applicant_rows.sort(key=sort_key, reverse=True)
        for i, row in enumerate(applicant_rows):
            row.overall_rank = i + 1
            
        program_groups = defaultdict(list)
        for row in applicant_rows:
            program_groups[row.program].append(row)
        for group in program_groups.values():
            group.sort(key=sort_key, reverse=True)
            for i, row in enumerate(group):
                row.program_rank = i + 1
        return

    # Standard Competition Ranking
    if processing_stage == "Part A Ranking":
        # Sort by Total Score (Calculated via Merit Rule)
        # Tie-break Phase 1: 1. Total Score, 2. HSC Percentage
        sort_key = lambda x: (
            float(x.total_score or 0), 
            float(x.hsc_percentage or 0),
            float(x.entrance_score or 0)
        )
    else:
        # Sort by Total Score (Part A + Part B)
        # Tie-break Phase 2: 1. Total Score, 2. Interview, 3. Part A, 4. HSC, 5. DOB (Older)
        from frappe.utils import get_timestamp
        sort_key = lambda x: (
            float(x.total_score or 0), 
            float(x.interview_score or 0),
            float(x.entrance_score or 0),
            float(x.hsc_percentage or 0),
            -get_timestamp(x.date_of_birth) if x.date_of_birth else 0
        )

    # 1. Overall Rank
    applicant_rows.sort(key=sort_key, reverse=True)
    
    current_rank = 1
    for i, row in enumerate(applicant_rows):
        if i > 0:
            prev_row = applicant_rows[i-1]
            if sort_key(row) != sort_key(prev_row):
                current_rank = i + 1
        row.overall_rank = current_rank

    # 2. Program Rank
    program_groups = defaultdict(list)
    for row in applicant_rows:
        program_groups[row.program].append(row)
    
    for group in program_groups.values():
        group.sort(key=sort_key, reverse=True)
        current_rank = 1
        for i, row in enumerate(group):
            if i > 0:
                prev_row = group[i-1]
                if sort_key(row) != sort_key(prev_row):
                    current_rank = i + 1
            row.program_rank = current_rank

    # 3. Category Rank (Within actual vertical category)
    category_groups = defaultdict(list)
    for row in applicant_rows:
        cat = getattr(row, "actual_category", None) or getattr(row, "vertical_category", None)
        if cat:
            category_groups[cat].append(row)
            
    for group in category_groups.values():
        group.sort(key=sort_key, reverse=True)
        current_rank = 1
        for i, row in enumerate(group):
            if i > 0:
                prev_row = group[i-1]
                if sort_key(row) != sort_key(prev_row):
                    current_rank = i + 1
            row.category_rank = current_rank


def generate_merit_for_level(cycle, campus, program_level, processing_stage="Part A Ranking", save=True):
    """
    Generates a Merit List for a specific Program Level.
    """
    if save:
        # Check if a Merit List already exists
        existing = frappe.db.get_value(
            "Merit List",
            {
                "admission_cycle": cycle,
                "campus": campus,
                "program_level": program_level,
                "merit_processing_stage": processing_stage
            },
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

    merit_rule_name = frappe.db.get_value(
        "Merit Rule Mapping",
        {
            "admission_cycle": cycle,
            "campus": campus,
            "program_level": program_level,
            "is_active": 1
        },
        "merit_rule"
    )
    if not merit_rule_name:
        frappe.throw(
            f"No active Merit Rule Mapping found for Program Level '{program_level}', "
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
        sp_name = frappe.db.get_value("Shortlisting Process", sp_filters, "name", order_by="creation desc")
        if not sp_name:
            frappe.throw(f"No Shortlisting Process found for {program_level}. Please generate the shortlist first.")
            
        applicant_names = frappe.get_all(
            "Shortlisting Applicant", 
            filters={"parent": sp_name, "shortlist_status": "Shortlisted"}, 
            pluck="applicant_id"
        )
    else:
        applicant_names = frappe.get_all(
            "Eligibility Result",
            filters={
                "admission_cycle": cycle,
                "campus": campus,
                "program_level": program_level
            },
            pluck="name"
        )
    
    if not applicant_names:
        frappe.throw(
            f"No eligible applicants found for Program Level '{program_level}' in this stage.",
            title="No Applicants Found"
        )

    # Build Merit List
    merit = frappe.new_doc("Merit List")
    merit.admission_cycle = cycle
    merit.campus = campus
    merit.program_level = program_level
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

        total_score = calculate_merit_with_rule(app, rule)

        status = "Selected" if total_score >= rule.minimum_marks else "Rejected"

        # Get primary vertical category name
        app_cats = get_applicant_categories(app.applicant_id)
        primary_cat = app_cats[0] if app_cats else "General"

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
    Handles Shortlisting (Phase 1) and Final Admission (Phase 2).
    """
    clear_category_cache()
    
    # Group applicants by program
    child_table = "shortlist_applicants" if is_shortlist_allocation else "selection_applicant"
    applicants_list = getattr(doc, child_table)
    
    grouped_by_program = {}
    for row in applicants_list:
        grouped_by_program.setdefault(row.program, []).append(row)
        # Ensure total_score is available for sorting if not present (Shortlisting Applicant case)
        if not hasattr(row, "total_score") and hasattr(row, "nlsat_part_a_score"):
            row.total_score = row.nlsat_part_a_score

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

        is_shortlist_phase = is_shortlist_allocation or (doc.admission_phase == "Shortlisting")
        open_merit_cat = policy.open_merit_category or "General"
        multiplier = policy.get("shortlisting_multiplier") or 1.0
        
        # 1. Setup Seat Targets
        vertical_targets = {}
        for v in policy.categories:
            target = v.shortlisting_target if is_shortlist_phase else v.seats
            if is_shortlist_phase and not target:
                target = (v.seats or 0) * multiplier

            vertical_targets[v.category_name] = {
                "total": target or 0,
                "filled": 0,
                "priority": v.priority,
                "min_percentile": v.min_percentile
            }

        compartmental_targets = {}
        for c in policy.compartmental_reservations:
            target = c.shortlisting_target if is_shortlist_phase else c.seats
            if is_shortlist_phase and not target:
                target = (c.seats or 0) * multiplier

            v_cat = c.vertical_category
            if v_cat not in compartmental_targets: compartmental_targets[v_cat] = {}
            compartmental_targets[v_cat][c.category_name] = {
                "total": target or 0,
                "filled": 0,
                "priority": c.priority,
                "min_percentile": c.min_percentile
            }

        horizontal_targets = {}
        for h in policy.horizontal_reservations:
            target = h.shortlisting_target if is_shortlist_phase else h.seats
            if is_shortlist_phase and not target:
                target = (h.seats or 0) * multiplier

            horizontal_targets[h.category_name] = {
                "total": target or 0,
                "filled": 0,
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
                            _apply_merit_migration_protection(in_cand, open_merit_cat, all_horizontal_names, allocated_list, unallocated, is_shortlist_allocation)

        total_selected += len(allocated_list)
        
        # ---------------------------------------------------------
        # FINAL PASS: Build display strings and horizontal traits
        # ---------------------------------------------------------
        cat_types = {c.name: c.reservation_type for c in frappe.get_all("Admission Category", fields=["name", "reservation_type"])}
        
        for app in allocated_list:
            # 1. Capture horizontal traits
            traits = [c for c in get_applicant_categories(app.applicant_id) if cat_types.get(c) == "Horizontal"]
            if traits and hasattr(app, "horizontal_categories"):
                app.horizontal_categories = ", ".join(sorted(traits))
            
            # 2. Build combined display string: Vertical + Compartmental + Horizontal
            display_field = "shortlist_category" if is_shortlist_allocation else "allocated_category"
            if hasattr(app, display_field):
                parts = [app.vertical_category]
                
                c_cat = getattr(app, "compartment_category", None)
                if c_cat:
                    parts.append(c_cat)
                
                h_cats_str = getattr(app, "horizontal_categories", None)
                if h_cats_str:
                    h_cats = [h.strip() for h in h_cats_str.split(",") if h.strip()]
                    parts.extend(h_cats)
                
                setattr(app, display_field, " + ".join(parts))

        for u in unallocated:
            status_field = "shortlist_status" if is_shortlist_allocation else "selection_status"
            setattr(u, status_field, "Rejected")
            total_rejected += 1

    doc.total_selected = total_selected
    doc.total_rejected = total_rejected
    return True

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

def _assign_seat_to_applicant(app, vertical_cat, alloc_type, allocated_list, unallocated, v_info, is_shortlist_allocation=False):
    status_field = "shortlist_status" if is_shortlist_allocation else "selection_status"
    status_value = "Shortlisted" if is_shortlist_allocation else "Selected"
    setattr(app, status_field, status_value)
    app.vertical_category = vertical_cat
    app.allocation_type = alloc_type
    
    if hasattr(app, "allocated_category"):
        app.allocated_category = vertical_cat
    if hasattr(app, "shortlist_category"):
        app.shortlist_category = vertical_cat
        
    v_info["filled"] += 1
    allocated_list.append(app)
    unallocated.remove(app)

def _rebalance_compartmental_quota(v_cat, c_targets, allocated_list, unallocated, v_info, is_shortlist, policy, is_shortlist_allocation=False):
    for c_cat, c_info in c_targets.items():
        current_coverage = [a for a in allocated_list if a.vertical_category == v_cat and c_cat in get_applicant_categories(a.applicant_id)]
        deficit = c_info["total"] - len(current_coverage)
        
        if deficit > 0:
            potential_candidates = [u for u in unallocated if c_cat in get_applicant_categories(u.applicant_id) and v_cat in get_applicant_categories(u.applicant_id)]
            
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
                    if hasattr(in_cand, "compartment_category"):
                        in_cand.compartment_category = c_cat
                    deficit -= 1
                    
                    if v_cat == (policy.open_merit_category or "General"):
                        all_horizontal_names = [c.category_name for c in policy.compartmental_reservations] + [c.category_name for c in policy.horizontal_reservations]
                        _apply_merit_migration_protection(in_cand, v_cat, all_horizontal_names, allocated_list, unallocated, is_shortlist_allocation)

def _execute_candidate_displacement(in_cand, out_cand, allocated_list, unallocated, is_shortlist_allocation=False):
    v_cat = out_cand.vertical_category
    a_type = out_cand.allocation_type
    
    status_field = "shortlist_status" if is_shortlist_allocation else "selection_status"
    selected_status = "Shortlisted" if is_shortlist_allocation else "Selected"
    
    setattr(out_cand, status_field, "Rejected")
    out_cand.vertical_category = ""
    out_cand.allocation_type = ""
    if hasattr(out_cand, "compartment_category"):
        out_cand.compartment_category = ""
    if hasattr(out_cand, "horizontal_categories"):
        out_cand.horizontal_categories = ""
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
        lowest_reserved = reserved_allocated[-1]
        if (app.total_score or 0) > (lowest_reserved.total_score or 0):
             _execute_candidate_displacement(app, lowest_reserved, allocated_list, unallocated, is_shortlist_allocation)
