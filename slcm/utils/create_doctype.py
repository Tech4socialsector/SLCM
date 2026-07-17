import frappe

def create_available_seats_doctype():
    if frappe.db.exists("DocType", "Available Exam Center Seats"):
        print("DocType already exists")
        return
        
    doc = frappe.get_doc({
        "doctype": "DocType",
        "name": "Available Exam Center Seats",
        "module": "Admission",
        "custom": 0,
        "is_submittable": 0,
        "fields": [
            {"fieldname": "entrance_test_provider", "label": "Entrance Test Provider", "fieldtype": "Link", "options": "Entrance Test Provider", "in_list_view": 1, "reqd": 1},
            {"fieldname": "center_name", "label": "Centre Name", "fieldtype": "Data", "read_only": 1},
            {"fieldname": "room_code", "label": "Room Code", "fieldtype": "Data", "read_only": 1},
            {"fieldname": "room_name", "label": "Room Name", "fieldtype": "Data", "read_only": 1},
            {"fieldname": "building", "label": "Building", "fieldtype": "Data", "read_only": 1},
            {"fieldname": "floor", "label": "Floor", "fieldtype": "Data", "read_only": 1},
            {"fieldname": "seat_number", "label": "Seat Number", "fieldtype": "Data", "in_list_view": 1, "reqd": 1},
            {"fieldname": "status", "label": "Status", "fieldtype": "Select", "options": "Available\nOccupied", "default": "Available", "in_list_view": 1},
            {"fieldname": "section_break_applicant", "fieldtype": "Section Break", "label": "Applicant Details (Vacated By)"},
            {"fieldname": "vacated_by_applicant", "label": "Vacated By Applicant", "fieldtype": "Link", "options": "Applicant"},
            {"fieldname": "vacated_by_name", "label": "Vacated By Name", "fieldtype": "Data"},
            {"fieldname": "section_break_new", "fieldtype": "Section Break", "label": "New Assignment"},
            {"fieldname": "assigned_to_applicant", "label": "Assigned To Applicant", "fieldtype": "Link", "options": "Applicant"},
            {"fieldname": "assigned_to_name", "label": "Assigned To Name", "fieldtype": "Data"}
        ],
        "permissions": [
            {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
            {"role": "Entrance Test Admin", "read": 1, "write": 1, "create": 1, "delete": 1}
        ],
        "naming_rule": "Expression",
        "autoname": "format:AECS-{####}"
    })
    doc.insert(ignore_permissions=True)
    print("Created DocType: Available Exam Center Seats")
