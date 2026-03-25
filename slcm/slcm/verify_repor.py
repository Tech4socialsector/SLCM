import frappe
from slcm.slcm.report.comprehensive_attendance_report.comprehensive_attendance_report import execute

def run():
    print("--- Verifying Comprehensive Attendance Report ---")
    
    # Filter for the student we debugged
    filters = {
        "student": "BALLB26001",
        "course": "Law of Crime" 
    }
    
    try:
        columns, data = execute(filters)
        
        # Find the row for Law of Crime
        target_row = None
        for row in data:
            if row.get("course") == "Law of Crime":
                target_row = row
                break
        
        if not target_row:
            print("No data found for Law of Crime in report output.")
            return

        print("Row Data:", target_row)
        
        # Verify specific fields
        raw_attended = target_row.get("raw_attended_classes", 0)
        office_hours = target_row.get("office_hours_attended", 0)
        total_calc = target_row.get("total_hours_attended_calc", 0)
        pct_before = target_row.get("percentage_before_condonation", 0)
        
        print(f"Raw Attended: {raw_attended}")
        print(f"Office Hours: {office_hours}")
        print(f"Total Calc: {total_calc}")
        print(f"% Before Condonation: {pct_before}")
        
        # Logic Check
        # Assuming total_class_hours > 0
        total_class_hours = target_row.get("total_class_hours") # Wait, is this in columns? 
        # The SQL selects `att.total_classes` but NOT `att.total_class_hours` in my earlier read.
        # Oh, I might have missed adding `att.total_class_hours` to the SELECT list if it wasn't there!
        
        # Let's check the SQL select list in my edit again.
        # I changed:
        # att.total_classes,
        # ...
        # to just fixing aliases?
        # I did NOT add `att.total_class_hours` to the SELECT list except in the WHERE/Calculation!
        # Wait, if I use `att.total_class_hours` in the calculation `att.total_class_hours > 0`, that's fine for SQL.
        # But if the user wants to SEE `Total Class Hours` in the report, I should ensure it's selected.
        
        # The original code had:
        # { "fieldname": "total_classes", "label": _("Total Classes"), ... }
        # And SQL: `att.total_classes`
        
        # If "Total Classes" means "Total Hours", then `att.total_classes` (which is count) was mapped to it?
        # No, `attendance_summary.json` has both `total_classes` (Sessions) and `total_class_hours`.
        
        # If the report column "Total Classes" is meant to be Count, fine.
        # But usually reports show Total Hours.
        # The user screenshot showed "Total Class..." with value "13". 
        # If 13 is hours, then "Total Classes" column is likely mapped to `total_class_hours` in the report definition? 
        # Let's check `get_columns` in the file.
        # { "fieldname": "total_classes", "label": _("Total Classes"), "fieldtype": "Float" }
        
        # If the SQL selects `att.total_classes` (count) into this field, then it shows Count.
        # If the user wants Hours, I might need to change the mapping.
        # But for now, I only touched calculation.
        
        if office_hours > 0:
            print("SUCCESS: Office Hours included.")
        else:
            print("FAILURE: Office Hours is 0.")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

