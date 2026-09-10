import frappe
def check_log():
    details = frappe.get_all('Marks Import Log Detail', filters={'import_log': 'rr0cumqubg'}, fields=['row_number', 'status', 'error_reason'])
    print("DETAILS:", details)
