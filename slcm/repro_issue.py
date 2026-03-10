
import frappe
from frappe.desk.form.load import getdoc

def test_getdoc():
    frappe.connect()
    doctype = "Program"
    name = "Bachelor of Science"
    
    # Ensure Program exists
    if not frappe.db.exists(doctype, name):
        frappe.get_doc({
            "doctype": doctype,
            "program_name": name,
            "program_shortcode": "BS",
            "intake_type": "NLSAT"
        }).insert(ignore_permissions=True)
        frappe.db.commit()
        
    print(f"Testing getdoc for {doctype} {name}")
    try:
        doc = getdoc(doctype, name)
        print(f"  SUCCESS")
    except Exception as e:
        print(f"  FAILED: {e}")
        import traceback
        traceback.print_exc()
            
    frappe.destroy()

if __name__ == "__main__":
    test_getdoc()
