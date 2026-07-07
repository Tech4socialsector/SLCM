import frappe
from frappe.utils import now_datetime, flt

def run_application_tests():
    # Setup data
    cycle = frappe.get_all("Admission Cycle", limit=1)
    if not cycle:
        print("No Admission Cycle found")
        return
    cycle_name = cycle[0].name
    
    scheme_name = f"SS-{cycle_name}-ATS"
    if frappe.db.exists("Scholarship Scheme", scheme_name):
        frappe.delete_doc("Scholarship Scheme", scheme_name)
    
    # Create mapping
    program = frappe.get_all("Program", limit=1)
    program_name = program[0].name if program else "Test Program"
    campus = frappe.get_all("Campus", limit=1)
    campus_name = campus[0].name if campus else "Test Campus"
    category_name = "General"

    s = frappe.get_doc({
        "doctype": "Scholarship Scheme",
        "scheme_name": "App Test",
        "scheme_code": "ATS",
        "admission_cycle": cycle_name,
        "scheme_type": "Merit",
        "coverage_type": "Percentage",
        "coverage_value": 50,
        "max_amount": 5000,
        "status": "Active",
        "is_active": 1,
        "priority": 1,
        "campus": campus_name,
        "program": program_name,
        "category": category_name,
        "min_merit_score": 80.0
    })
    s.insert(ignore_permissions=True)
    frappe.db.commit()
    scheme_name = s.name

    # Create Applicant
    applicant = frappe.get_doc({
        "doctype": "Applicant",
        "candidate_name": "Test Applicant",
        "email": "test@example.com",
        "mobile_number": "+91-9876543210",
        "gender": "Male",
        "date_of_birth": "2000-01-01",
        "admission_cycle": cycle_name,
        "academic_year": frappe.db.get_value("Admission Cycle", cycle_name, "academic_year") or "2026-27",
        "status": "Submitted",
        "program": program_name,
        "campus": campus_name,
        "admission_category": category_name
    })
    applicant.flags.ignore_mandatory = True
    applicant.insert(ignore_permissions=True)
    frappe.db.commit()
    applicant_name = applicant.name

    print("--- Test 1: Benefit Calculation (Percentage) ---")
    app1 = frappe.get_doc({
        "doctype": "Scholarship Application",
        "applicant_id": applicant_name,
        "applicant_name": applicant_name, # In DocType it's also a link
        "scholarship_scheme": scheme_name,
        "admission_cycle": cycle_name,
        "program": program_name,
        "campus": campus_name,
        "family_income": 500000,
        "income_certificate": "/path/to/cert.pdf",
        "original_fee_amount": 10000,
        "status": "Submitted"
    })
    app1.validate()
    print(f"Calculated Benefit: {app1.calculated_benefit}")
    print(f"Final Fee: {app1.final_fee_amount}")
    if flt(app1.calculated_benefit) == 5000:
        print("SUCCESS: Benefit correct")
    else:
        print(f"FAIL: Expected 5000, got {app1.calculated_benefit}")

    print("--- Test 2: Duplicate Prevention ---")
    app1.insert(ignore_permissions=True)
    frappe.db.commit()
    
    app2 = frappe.get_doc({
        "doctype": "Scholarship Application",
        "applicant_id": applicant_name,
        "scholarship_scheme": scheme_name,
        "admission_cycle": cycle_name,
        "program": program_name,
        "campus": campus_name,
        "family_income": 500000,
        "income_certificate": "/path/to/cert.pdf",
        "status": "Submitted"
    })
    try:
        app2.validate()
        print("FAIL: Duplicate application bypass")
    except Exception as e:
        print(f"SUCCESS: Caught duplicate: {e}")

    # Cleanup
    frappe.db.rollback()
    print("Verification Completed")

if __name__ == "__main__":
    run_application_tests()
