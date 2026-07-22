import frappe

def run():
    doc = frappe.get_doc("DocType", "Bulk Email")
    
    # check if field already exists
    if not any(f.fieldname == "server_response" for f in doc.fields):
        # find index of status field to insert after it
        idx = 0
        for i, f in enumerate(doc.fields):
            if f.fieldname == "status":
                idx = i + 1
                break
        
        doc.insert_after(doc.fields[idx-1], {
            "fieldname": "server_response",
            "fieldtype": "Code",
            "label": "Server Response",
            "read_only": 1
        })
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        print("Added server_response field to Bulk Email")
    else:
        print("server_response field already exists")
