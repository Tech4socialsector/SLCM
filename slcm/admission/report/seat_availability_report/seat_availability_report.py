# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    message = None
    if not data:
        message = _("No data found for the selected filters.")
    else:
        message = _("Category-wise seat capacity, allocated, waitlisted, vacant, and reservation utilization breakdown.")
    
    summary = get_summary(data)
    return columns, data, message, None, summary

def get_summary(data):
    if not data:
        return []
    
    total_seats = sum(row.get("total_seats", 0) for row in data)
    allocated = sum(row.get("allocated", 0) for row in data)
    waitlisted = sum(row.get("waitlisted", 0) for row in data)
    vacant = sum(row.get("vacant_seats", 0) for row in data)
    
    utilization = flt(allocated / total_seats * 100, 2) if total_seats > 0 else 0
    
    return [
        {"label": _("Total Seats"), "value": total_seats, "indicator": "Blue"},
        {"label": _("Total Allocated"), "value": allocated, "indicator": "Green"},
        {"label": _("Total Vacant"), "value": vacant, "indicator": "Red" if vacant > 0 else "Green"},
        {"label": _("Utilization %"), "value": utilization, "indicator": "Blue"}
    ]

def get_columns():
    return [
        {"label": _("Campus"), "fieldname": "campus", "fieldtype": "Link", "options": "Campus", "width": 140},
        {"label": _("Programme"), "fieldname": "program", "fieldtype": "Link", "options": "Programme", "width": 160},
        {"label": _("Category"), "fieldname": "category", "fieldtype": "Data", "width": 110},
        {"label": _("Total Seats"), "fieldname": "total_seats", "fieldtype": "Int", "width": 100},
        {"label": _("Allocated"), "fieldname": "allocated", "fieldtype": "Int", "width": 95},
        {"label": _("Waitlisted"), "fieldname": "waitlisted", "fieldtype": "Int", "width": 95},
        {"label": _("Vacant Seats"), "fieldname": "vacant_seats", "fieldtype": "Int", "width": 115},
        {"label": _("PWD"), "fieldname": "pwd_filled", "fieldtype": "Int", "width": 75},
        {"label": _("Women"), "fieldname": "women_filled", "fieldtype": "Int", "width": 80},
        {"label": _("Karnataka"), "fieldname": "karnataka_filled", "fieldtype": "Int", "width": 95},
        {"label": _("Utilization %"), "fieldname": "util", "fieldtype": "Float", "precision": 2, "width": 110, "is_total": 0}
    ]

def get_data(filters):
    relevant_cycles = []
    if filters.get("admission_year"):
        relevant_cycles = frappe.get_all("Admission Cycle", 
            filters={"admission_year": filters.get("admission_year")}, pluck="name")

    # 1. Fetch relevant Programme Reservation Policies
    prp_filters = {"status": "Active"}
    if filters.get("admission_cycle"):
        prp_filters["admission_cycle"] = filters.get("admission_cycle")
    elif relevant_cycles:
        prp_filters["admission_cycle"] = ["in", relevant_cycles]
    if filters.get("program"):
        prp_filters["program"] = filters.get("program")
    
    # Campus filter for PRP fetch
    if filters.get("campus"):
        prp_filters["campus"] = ["in", [filters.get("campus"), None, ""]]

    raw_policies = frappe.get_all("Programme Reservation Policy", 
        filters=prp_filters, 
        fields=["name", "admission_cycle", "program", "total_seats", "campus", "modified"],
        order_by="modified desc"
    )
    
    # Map policies by (cycle, program, campus) to avoid overwriting different campuses
    # We still prioritize campus-specific policies if a generic one exists
    policies_list = []
    seen_combos = set()
    
    # Sort raw_policies so that campus-specific ones come first (if campus is in filters)
    target_campus = filters.get("campus")
    if target_campus:
        raw_policies.sort(key=lambda x: 0 if x.campus == target_campus else 1)

    for p in raw_policies:
        # If we are filtering by campus, we only care about that campus or generic ones
        # If no campus filter, we want to see all campuses that have mappings
        combo = (p.admission_cycle, p.program, p.campus or "")
        if combo not in seen_combos:
            policies_list.append(p)
            seen_combos.add(combo)
    
    if not policies_list:
        return []

    # 2. Map Campus Intake from Admission Cycle Program
    acp_filters = {}
    if relevant_cycles: acp_filters["parent"] = ["in", relevant_cycles]
    elif filters.get("admission_cycle"): acp_filters["parent"] = filters.get("admission_cycle")
    if filters.get("campus"): acp_filters["campus"] = filters.get("campus")
    if filters.get("program"): acp_filters["program"] = filters.get("program")
    
    acp_records = frappe.get_all("Admission Cycle Program", filters=acp_filters, 
        fields=["parent", "program", "campus", "seats", "reservation_policy"])
    
    # Map mappings by (campus, cycle, program)
    mapping_map = {}
    for r in acp_records:
        mapping_map[(r.campus, r.parent, r.program)] = r

    import math
    final_data = []
    
    for p_summary in policies_list:
        policy = frappe.get_doc("Programme Reservation Policy", p_summary.name)
        program = policy.program
        cycle = policy.admission_cycle
        
        # Find all campuses applicable to this policy
        # If the policy is campus-specific, only that campus. If generic, all mappings that use it.
        target_mappings = []
        if policy.campus:
            m = mapping_map.get((policy.campus, cycle, program))
            if m: target_mappings.append(m)
        else:
            # Generic policy: find all mappings for this cycle/program that don't have their own specific policy
            # OR explicitly link to this one
            for m_key, m_val in mapping_map.items():
                m_campus, m_cycle, m_program = m_key
                if m_cycle == cycle and m_program == program:
                    if not m_val.reservation_policy or m_val.reservation_policy == policy.name:
                        target_mappings.append(m_val)
        
        for mapping in target_mappings:
            campus = mapping.campus
            total_intake = int(mapping.seats or policy.total_seats or 0)
            
            # Use scaled seats if total_intake differs from policy.total_seats
            # or if the user specifically asked for "updated new values"
            is_overridden = (total_intake != policy.total_seats)

            # Determine Vertical Categories
            cat_capacities = {} 
            sum_vertical = 0
            
            # Sort categories so General is last for remainder handling
            sorted_cats = sorted(policy.categories or [], key=lambda x: 1 if (x.category_name or "General") == "General" else 0)
            
            for v in sorted_cats:
                v_name = v.category_name or "General"
                if v_name == "General": continue # handle at end
                
                # If total intake is overridden, prioritize percentage to scale seats
                if is_overridden and v.percentage:
                    v_seats = math.floor(total_intake * (float(v.percentage) / 100.0))
                else:
                    v_seats = int(v.seats or 0) or math.floor(total_intake * (float(v.percentage or 0) / 100.0))
                
                cat_capacities[v_name] = v_seats
                sum_vertical += v_seats
            
            # Remainder goes to General
            remainder = max(0, total_intake - sum_vertical)
            cat_capacities["General"] = remainder

            # Fetch relevant Seat Allocation(s)
            sa_filters = {
                "docstatus": ["<", 2],
                "campus": campus,
                "admission_cycle": cycle,
                "program": program,
                "status": ["in", ["Allocated", "Published"]]
            }
            
            # Aggregate stats across all relevant seat allocations for this combo
            # (In case there are multiple rounds stored in separate docs)
            all_sas = frappe.get_all("Seat Allocation", filters=sa_filters, pluck="name")
            
            stats = {} # { category: { allocated: X, waitlisted: Y, pwd: Z, women: W, karnataka: K } }
            
            if all_sas:
                applicants = frappe.get_all("Seat Selection Applicant", 
                    filters={"parent": ["in", all_sas], "program": program},
                    fields=["applicant_id", "vertical_category", "horizontal_categories", "compartmentalized_category", "selection_status"]
                )
                
                # Use set to avoid double counting if the same applicant is in multiple SA records (shouldn't happen but just in case)
                seen_applicants = set()
                
                for app in applicants:
                    if app.applicant_id in seen_applicants: continue
                    seen_applicants.add(app.applicant_id)
                    
                    v_cat = app.vertical_category or "General"
                    if v_cat not in cat_capacities: v_cat = "General"
                    
                    is_allocated = app.selection_status in ["Selected", "Offer Issued", "Offer Accepted", "Accepted", "Confirmation Fee Paid", "Full Fee Paid"]
                    is_waitlisted = app.selection_status == "Waitlisted"
                    
                    if v_cat not in stats: 
                        stats[v_cat] = {"allocated": 0, "waitlisted": 0, "pwd": 0, "women": 0, "karnataka": 0}
                    
                    if is_allocated:
                        stats[v_cat]["allocated"] += 1
                        
                        # Check Horizontal/Compartmental traits
                        h_cats = (app.horizontal_categories or "").split(",")
                        h_cats = [h.strip() for h in h_cats if h.strip()]
                        
                        if "PWD" in h_cats: stats[v_cat]["pwd"] += 1
                        if "Women" in h_cats or "Female" in h_cats: stats[v_cat]["women"] += 1
                        
                        if app.compartmentalized_category == "Karnataka":
                            stats[v_cat]["karnataka"] += 1
                            
                    elif is_waitlisted:
                        stats[v_cat]["waitlisted"] += 1

            # Build result rows
            for c_name in sorted(cat_capacities.keys()):
                total = cat_capacities[c_name]
                st = stats.get(c_name, {"allocated": 0, "waitlisted": 0, "pwd": 0, "women": 0, "karnataka": 0})
                util = flt(st["allocated"] / total * 100, 2) if total > 0 else 0
                final_data.append({
                    "campus": campus,
                    "program": program,
                    "category": c_name,
                    "total_seats": total,
                    "allocated": st["allocated"],
                    "waitlisted": st["waitlisted"],
                    "vacant_seats": total - st["allocated"],
                    "pwd_filled": st["pwd"],
                    "women_filled": st["women"],
                    "karnataka_filled": st["karnataka"],
                    "util": util
                })

    return final_data
