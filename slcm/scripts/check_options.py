import frappe

def check_options():
    try:
        fle_doc = frappe.get_doc("DocType", "Foundations for a Legal Education")
        for f in fle_doc.fields:
            if f.fieldname == "payment_status":
                print(f"FLE Payment Status options:\n{repr(f.options)}")
        
        log_doc = frappe.get_doc("DocType", "FLE Payment Log")
        for f in log_doc.fields:
            if f.fieldname == "payment_status":
                print(f"Log Payment Status options:\n{repr(f.options)}")
    except Exception as e:
        print(e)
check_options()
