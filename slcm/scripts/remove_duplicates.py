
import frappe

def fix_duplicates():
    # 1. Fix Student Group "CRime"
    group_name = "CRime"
    if frappe.db.exists("Student Group", group_name):
        print(f"Fixing Student Group: {group_name}")
        
        # Get all students in the group
        students = frappe.get_all("Student Group Student", 
            filters={"parent": group_name}, 
            fields=["name", "student", "group_roll_number", "idx"],
            order_by="group_roll_number desc" # Keep higher roll number
        )
        
        seen_students = {}
        to_delete = []
        
        for s in students:
            if s.student in seen_students:
                to_delete.append(s.name)
            else:
                seen_students[s.student] = s.name
                
        if to_delete:
            print(f"Deleting {len(to_delete)} duplicate rows from Student Group {group_name}: {to_delete}")
            frappe.db.delete("Student Group Student", {"name": ["in", to_delete]})
            frappe.db.commit()
        else:
            print("No duplicates found in Student Group.")

    # 2. Fix Office Hours Group "Crime"
    oh_group = "Crime"
    if frappe.db.exists("Office Hours Group", oh_group):
        print(f"Fixing Office Hours Group: {oh_group}")
        
        # Need to fetch doc to manipulate child table properly? 
        # Or just delete lines? Deleting lines is safer via SQL/DB for child tables sometimes if we don't want to trigger validations yet.
        # But let's use ORM for safety.
        
        doc = frappe.get_doc("Office Hours Group", oh_group)
        
        seen_students = set()
        new_students = []
        
        # Filter duplicates in the doc list
        for s in doc.students:
            if s.student not in seen_students:
                seen_students.add(s.student)
                new_students.append(s)
            else:
                print(f"Removing duplicate {s.student} from Office Hours Group")
        
        if len(new_students) < len(doc.students):
            doc.students = new_students
            doc.save()
            frappe.db.commit()
            print("Saved Office Hours Group with duplicates removed.")
        else:
            print("No duplicates found in Office Hours Group.")

fix_duplicates()
