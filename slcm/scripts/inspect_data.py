
import frappe

def inspect():
    # Find a student with an approved condonation
    condonations = frappe.get_all("Student Attendance Condonation", 
        filters={"final_status": "Approved", "docstatus": 1},
        fields=["name", "student", "course_offering", "number_of_hours", "number_of_sessions"]
    )
    
    if not condonations:
        print("No approved condonations found.")
        return

    print(f"Found {len(condonations)} approved condonations.")
    
    for cond in condonations[:5]:
        print(f"\nChecking Condonation: {cond.name}")
        print(f"Student: {cond.student}, Course: {cond.course_offering}")
        print(f"Hours: {cond.number_of_hours}, Sessions: {cond.number_of_sessions}")
        
        summary = frappe.get_value("Attendance Summary", 
            {"student": cond.student, "course_offering": cond.course_offering},
            ["name", "total_classes", "attended_classes", "attendance_percentage", "condonation_list"],
            as_dict=True
        )
        
        if summary:
            print(f"Summary Found: {summary.name}")
            print(f"Total Classes: {summary.total_classes}")
            print(f"Attended Classes: {summary.attended_classes}")
            print(f"Percentage: {summary.attendance_percentage}")
            
            # Check if condonation is potentially added
            # We can't know for sure without recalculating, but we can check if the list is populated
            
            # Fetch the child table rows
            summary_doc = frappe.get_doc("Attendance Summary", summary.name)
            print("Condonation List in Summary:")
            found_in_list = False
            for row in summary_doc.condonation_list:
                print(f" - App: {row.condonation_application}, Hours: {row.number_of_hours}, Status: {row.final_status}")
                if row.condonation_application == cond.name:
                    found_in_list = True
            
            if not found_in_list:
                print(">>> WARNING: Condonation NOT found in summary list!")
            else:
                print("Condonation found in summary list.")
                
            # Perform a test calculation
            from slcm.slcm.utils.attendance_calculator import calculate_student_attendance
            print("Recalculating...")
            new_summary = calculate_student_attendance(cond.student, cond.course_offering)
            print(f"New Attended: {new_summary['attended_classes']}")
            print(f"New Percentage: {new_summary['attendance_percentage']}")
            
            if new_summary['attended_classes'] != summary.attended_classes:
                print(f">>> MISMATCH: Old Attended {summary.attended_classes} vs New {new_summary['attended_classes']}")
        else:
            print(">>> WARNING: No Attendance Summary found!")

inspect()
