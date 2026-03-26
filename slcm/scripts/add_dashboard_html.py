import frappe

def add_html_field():
    doc = frappe.get_doc("DocType", "Examination Plan")
    if not any(f.fieldname == "dashboard_html" for f in doc.fields):
        doc.append("fields", {
            "fieldname": "dashboard_html",
            "fieldtype": "HTML",
            "label": "Dashboard Data",
            "insert_after": "examination_name",
            "in_list_view": 0
        })
        
        # Move it to the top
        fields = doc.fields
        dashboard_field = fields.pop(-1)
        fields.insert(0, dashboard_field)
        for i, f in enumerate(fields):
            f.idx = i + 1
            
        doc.save()
        frappe.db.commit()
        print("dashboard_html field added successfully.")
    else:
        print("dashboard_html field already exists.")

if __name__ == "__main__":
    add_html_field()
