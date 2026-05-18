# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from slcm.admission.report.seat_availability_report.seat_availability_report import get_data as get_report_data

@frappe.whitelist()
def get_seat_matrix_data(admission_year=None, admission_cycle=None, campus=None, program=None):
    filters = {
        "admission_year": admission_year,
        "admission_cycle": admission_cycle,
        "campus": campus,
        "program": program
    }
    
    # Use existing report logic to fetch granular data
    raw_data = get_report_data(filters)
    
    # Process for dashboard: Group by Program
    program_summary = {}
    overall = {
        "total_seats": 0,
        "allocated": 0,
        "waitlisted": 0,
        "vacant": 0
    }
    
    for row in raw_data:
        prog = row.get("program")
        if not prog:
            continue
        if prog not in program_summary:
            program_summary[prog] = {
                "program": prog,
                "total_seats": 0,
                "allocated": 0,
                "waitlisted": 0,
                "vacant": 0,
                "categories": []
            }
        
        total_seats = row.get("total_seats", 0)
        allocated = row.get("allocated", 0)
        waitlisted = row.get("waitlisted", 0)
        vacant = row.get("vacant_seats", 0)
        utilization = row.get("util", 0)
        
        program_summary[prog]["total_seats"] += total_seats
        program_summary[prog]["allocated"] += allocated
        program_summary[prog]["waitlisted"] += waitlisted
        program_summary[prog]["vacant"] += vacant
        
        program_summary[prog]["categories"].append({
            "category": row.get("category"),
            "total": total_seats,
            "allocated": allocated,
            "waitlisted": waitlisted,
            "vacant": vacant,
            "utilization": utilization
        })
        
        overall["total_seats"] += total_seats
        overall["allocated"] += allocated
        overall["waitlisted"] += waitlisted
        overall["vacant"] += vacant

    # Sort programs by name
    sorted_programs = sorted(program_summary.values(), key=lambda x: x["program"])
    
    # Calculate overall utilization
    overall["utilization"] = (overall["allocated"] / overall["total_seats"] * 100) if overall["total_seats"] > 0 else 0
    
    return {
        "overall": overall,
        "programs": sorted_programs
    }
