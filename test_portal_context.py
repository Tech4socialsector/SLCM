import frappe
from slcm.www.my_applications import get_context as my_apps_context
from slcm.www.admission.program_detail import get_context as prog_detail_context

frappe.init(site="slcm.com")
frappe.connect()

# Mock context
context = frappe._dict()

print("Testing my-applications...")
try:
    my_apps_context(context)
except frappe.Redirect:
    print("Redirected (Guest)")
except Exception as e:
    print(f"Error (my-apps): {e}")

print("Testing program-detail...")
frappe.form_dict.name = 'ba-llb-hons'
try:
    prog_detail_context(context)
except Exception as e:
    print(f"Error (prog-detail): {e}")

print("\nRecent Portal Debug Logs:")
logs = frappe.get_all("Error Log",
    filters={"method": "Portal Debug"},
    fields=["error", "creation"],
    order_by="creation desc",
    limit=20)
for l in logs:
    print(f"{l.creation}: {l.error[:300]}")
    print("---")
