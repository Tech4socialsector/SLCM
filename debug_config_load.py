import frappe
import traceback
try:
    config = frappe.get_single("Applicant Portal Config")
    print("CONFIG LOADED SUCCESSFULLY")
    print("primary_color:", config.primary_color)
except Exception as e:
    print("CONFIG LOAD FAILED")
    print("Exception:", str(e))
    traceback.print_exc()
