import frappe

def cleanup_duplicates():
    # Find all students with duplicate summaries for the same course offering
    # We group by student, course_offering
    duplicates = frappe.db.sql("""
        SELECT student, course_offering, COUNT(*) as count
        FROM `tabAttendance Summary`
        WHERE docstatus < 2
        GROUP BY student, course_offering
        HAVING count > 1
    """, as_dict=True)

    print(f"Found {len(duplicates)} pairs with duplicates.")

    for d in duplicates:
        student = d.student
        offering = d.course_offering
        
        # Get all summaries for this pair, ordered by modified desc
        summaries = frappe.get_all("Attendance Summary", 
            filters={"student": student, "course_offering": offering, "docstatus": ["<", 2]},
            fields=["name", "modified"],
            order_by="modified desc"
        )
        
        # Keep the first one (most recently modified), delete the rest
        if len(summaries) > 1:
            to_keep = summaries[0]
            to_delete = summaries[1:]
            
            print(f"Keeping {to_keep.name} for {student} - {offering}")
            for s in to_delete:
                print(f"Deleting duplicate {s.name}")
                frappe.delete_doc("Attendance Summary", s.name, force=1)
                
    frappe.db.commit()
    print("Cleanup complete.")

cleanup_duplicates()
