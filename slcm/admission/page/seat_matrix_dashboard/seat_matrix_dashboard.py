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
        prog = row.program
        if prog not in program_summary:
            program_summary[prog] = {
                "program": prog,
                "total_seats": 0,
                "allocated": 0,
                "waitlisted": 0,
                "vacant": 0,
                "categories": []
            }
        
        program_summary[prog]["total_seats"] += row.total_seats
        program_summary[prog]["allocated"] += row.allocated
        program_summary[prog]["waitlisted"] += row.waitlisted
        program_summary[prog]["vacant"] += row.vacant_seats
        
        program_summary[prog]["categories"].append({
            "category": row.category,
            "total": row.total_seats,
            "allocated": row.allocated,
            "waitlisted": row.waitlisted,
            "vacant": row.vacant_seats,
            "utilization": row.utilization_percent
        })
        
        overall["total_seats"] += row.total_seats
        overall["allocated"] += row.allocated
        overall["waitlisted"] += row.waitlisted
        overall["vacant"] += row.vacant_seats

    # Sort programs by name
    sorted_programs = sorted(program_summary.values(), key=lambda x: x["program"])
    
    # Calculate overall utilization
    overall["utilization"] = (overall["allocated"] / overall["total_seats"] * 100) if overall["total_seats"] > 0 else 0
    
    return {
        "overall": overall,
        "programs": sorted_programs
    }
