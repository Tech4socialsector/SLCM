# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {
            "label": _("Campus"),
            "fieldname": "campus",
            "fieldtype": "Link",
            "options": "Campus",
            "width": 150
        },
        {
            "label": _("Program"),
            "fieldname": "program",
            "fieldtype": "Link",
            "options": "Program",
            "width": 150
        },
        {
            "label": _("Category"),
            "fieldname": "category",
            "fieldtype": "Data",
            "width": 180
        },
        {
            "label": _("Total Seats"),
            "fieldname": "total_seats",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "label": _("Allocated"),
            "fieldname": "allocated",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "label": _("Waitlisted"),
            "fieldname": "waitlisted",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "label": _("Vacant Seats"),
            "fieldname": "vacant_seats",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "label": _("PWD Filled"),
            "fieldname": "pwd_filled",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "label": _("Women Filled"),
            "fieldname": "women_filled",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "label": _("Karnataka Filled"),
            "fieldname": "karnataka_filled",
            "fieldtype": "Int",
            "width": 130
        },
        {
            "label": _("Utilization %"),
            "fieldname": "utilization_percent",
            "fieldtype": "Percent",
            "width": 120
        }
    ]

def get_data(filters):
    relevant_cycles = []
    if filters.get("admission_year"):
        relevant_cycles = frappe.get_all("Admission Cycle", 
            filters={"admission_year": filters.get("admission_year")}, pluck="name")

    # 1. Fetch relevant Program Reservation Policies
    prp_filters = {"status": "Active"}
    if filters.get("admission_cycle"):
        prp_filters["admission_cycle"] = filters.get("admission_cycle")
    elif relevant_cycles:
        prp_filters["admission_cycle"] = ["in", relevant_cycles]
    if filters.get("program"):
        prp_filters["program"] = filters.get("program")
    if filters.get("campus"):
        prp_filters["campus"] = ["in", [filters.get("campus"), None, ""]]

    raw_policies = frappe.get_all("Program Reservation Policy", 
        filters=prp_filters, 
        fields=["name", "admission_cycle", "program", "total_seats", "campus", "modified"],
        order_by="modified desc"
    )
    
    # Priority: Campus-specific > Generic
    policies_map = {}
    for p in raw_policies:
        key = (p.admission_cycle, p.program)
        if key not in policies_map or (p.campus == filters.get("campus")):
            policies_map[key] = p
    
    policies = list(policies_map.values())
    if not policies:
        return []

    # 2. Map Campus Intake from Admission Cycle Program
    acp_filters = {}
    if relevant_cycles: acp_filters["parent"] = ["in", relevant_cycles]
    elif filters.get("admission_cycle"): acp_filters["parent"] = filters.get("admission_cycle")
    if filters.get("campus"): acp_filters["campus"] = filters.get("campus")
    if filters.get("program"): acp_filters["program"] = filters.get("program")
    
    acp_records = frappe.get_all("Admission Cycle Program", filters=acp_filters, fields=["parent", "program", "campus", "seats", "reservation_policy"])
    policy_campus_map = {}
    for r in acp_records:
        pol_key = r.reservation_policy or (r.parent, r.program)
        m_key = (r.campus, r.parent, r.program)
        policy_campus_map.setdefault(pol_key, {})[m_key] = r

    import math
    final_data = []
    processed_keys = set() 
    
    for p_summary in policies:
        policy = frappe.get_doc("Program Reservation Policy", p_summary.name)
        mappings_dict = policy_campus_map.get(policy.name) or policy_campus_map.get((policy.admission_cycle, policy.program)) or {}
        mappings = list(mappings_dict.values())
        
        if not mappings: continue

        for mapping in mappings:
            campus = mapping.campus
            program = policy.program
            
            # Safeguard
            entry_key = (campus, program, policy.admission_cycle)
            if entry_key in processed_keys: continue
            processed_keys.add(entry_key)
            
            total_intake = int(mapping.seats or policy.total_seats or 0)

            # Determine Vertical Categories
            cat_capacities = {} 
            sum_vertical = 0
            for v in (policy.categories or []):
                v_name = v.category_name or "General"
                v_seats = int(v.seats or 0) or math.floor(total_intake * (float(v.percentage or 0) / 100.0))
                cat_capacities[v_name] = v_seats
                sum_vertical += v_seats
            
            remainder = max(0, total_intake - sum_vertical)
            if remainder > 0 or "General" not in cat_capacities:
                cat_capacities["General"] = cat_capacities.get("General", 0) + remainder

            # Fetch relevant Seat Allocation
            sa_filters = {
                "docstatus": ["<", 2],
                "campus": campus,
                "admission_cycle": policy.admission_cycle,
                "status": ["in", ["Allocated", "Published"]]
            }
            if mapping.program: sa_filters["program"] = mapping.program
            
            latest_sa = frappe.db.get_value("Seat Allocation", sa_filters, "name", order_by="modified desc")
            
            stats = {} # { category: { allocated: X, waitlisted: Y, pwd: Z, women: W, karnataka: K } }
            
            if latest_sa:
                applicants = frappe.get_all("Seat Selection Applicant", 
                    filters={"parent": latest_sa, "program": program},
                    fields=["applicant_id", "vertical_category", "horizontal_categories", "compartmentalized_category", "selection_status"]
                )
                
                for app in applicants:
                    v_cat = app.vertical_category or "General"
                    if v_cat not in cat_capacities: v_cat = "General"
                    
                    is_allocated = app.selection_status in ["Selected", "Offer Issued", "Offer Accepted", "Accepted", "Fee Paid"]
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

            for c_name in sorted(cat_capacities.keys()):
                total = cat_capacities[c_name]
                st = stats.get(c_name, {"allocated": 0, "waitlisted": 0, "pwd": 0, "women": 0, "karnataka": 0})
                util = (st["allocated"] / total * 100) if total > 0 else 0
                final_data.append(frappe._dict({
                    "campus": campus, "program": program, "category": c_name,
                    "total_seats": total, "allocated": st["allocated"], "waitlisted": st["waitlisted"],
                    "vacant_seats": max(0, total - st["allocated"]),
                    "pwd_filled": st["pwd"],
                    "women_filled": st["women"],
                    "karnataka_filled": st["karnataka"],
                    "utilization_percent": util
                }))

    return final_data


    return final_data
