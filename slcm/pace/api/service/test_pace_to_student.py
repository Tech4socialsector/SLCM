import frappe
from slcm.pace.api.service.pace_to_student import convert_pace_to_student

def test_conversion():
    try:
        res = convert_pace_to_student('PACE-2026 - 2027-00177')
        print(f"Result: {res}")
        frappe.db.commit()
    except Exception as e:
        print(f"Error: {e}")
        print(frappe.get_traceback())

if __name__ == "__main__":
    test_conversion()
