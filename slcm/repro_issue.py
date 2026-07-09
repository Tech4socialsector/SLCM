import frappe
import json

def reproduce_issue():
    doctype = "Programme"
    name = "Ph.D. in Interdisciplinary Legal Studies"
    print(f"Loading {doctype} {name}...")
    try:
        doc = frappe.get_doc(doctype, name)
        print("Successfully loaded document")
        # print(json.dumps(doc.as_dict(), indent=4, default=str))
    except Exception as e:
        print(f"Failed to load document: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    frappe.connect()
    reproduce_issue()
    frappe.destroy()
