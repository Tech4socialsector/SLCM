import frappe
from slcm.slcm.report.comprehensive_attendance_report.comprehensive_attendance_report import execute
def test():
    frappe.init(site="slcm.local")
    frappe.connect()
    res = execute(filters={})
    print(res[1])
    return True
