import frappe
from frappe.utils import flt, add_days, today

def run_fee_tests():
    # Setup
    cycle_name = "June To December"
    year_label = "2026-27"
    academic_year_name = "2026-27"
    campus_name = "Bengaluru"
    program_name = "3-Year LL.B. (Hons.)"

    # Ensure Admission Year
    if not frappe.db.exists("Admission Year", year_label):
        frappe.get_doc({
            "doctype": "Admission Year",
            "year": year_label,
            "is_active": 1
        }).insert(ignore_permissions=True)

    # Ensure Academic Year
    if not frappe.db.exists("Academic Year", academic_year_name):
        frappe.get_doc({
            "doctype": "Academic Year",
            "name": academic_year_name,
            "academic_year_name": academic_year_name
        }).insert(ignore_permissions=True, ignore_links=True)

    # Ensure Applicant
    applicant_filters = {"candidate_name": "Test Applicant Fee Logic", "admission_cycle": cycle_name}
    applicant_id = frappe.db.get_value("Applicant", applicant_filters, "name")
    
    if not applicant_id:
        app = frappe.get_doc({
            "doctype": "Applicant",
            "first_name": "Test",
            "last_name": "Applicant",
            "candidate_name": "Test Applicant Fee Logic",
            "admission_cycle": cycle_name,
            "status": "Selected",
            "campus": campus_name,
            "program": program_name
        })
        app.flags.ignore_mandatory = True
        app.insert(ignore_permissions=True, ignore_links=True)
        applicant_id = app.name
    else:
        # Force update status to Selected and ensure program is set
        frappe.db.set_value("Applicant", applicant_id, {
            "status": "Selected",
            "program": program_name
        })
        frappe.db.commit()

    # Ensure Offer Letter
    offer_letter_name = f"OL-{applicant_id}-{program_name}-{campus_name}"
    if not frappe.db.exists("Offer Letter", offer_letter_name):
        ol = frappe.get_doc({
            "doctype": "Offer Letter",
            "applicant": applicant_id,
            "program": program_name,
            "admission_cycle": cycle_name,
            "admission_year": year_label,
            "academic_year": academic_year_name,
            "campus": campus_name,
            "offer_date": today(),
            "status": "Issued"
        })
        ol.flags.ignore_mandatory = True
        ol.insert(ignore_permissions=True, ignore_links=True)
        offer_letter_name = ol.name
    else:
        # Ensure status is Issued for testing
        frappe.db.set_value("Offer Letter", offer_letter_name, "status", "Issued")
        frappe.db.commit()

    # Ensure Scholarship Scheme
    scheme_code = "SCH-T99"
    scheme_name = "Test Scholarship 99"
    if not frappe.db.exists("Scholarship Scheme", {"scheme_code": scheme_code, "admission_cycle": cycle_name}):
        frappe.get_doc({
            "doctype": "Scholarship Scheme",
            "scheme_code": scheme_code,
            "scheme_name": scheme_name,
            "scholarship_name": scheme_name,
            "admission_cycle": cycle_name,
            "scheme_type": "Institutional",
            "status": "Active",
            "coverage_type": "Fixed",
            "coverage_value": 3000, # Match test expectation
            "apply_on": "Total Fee",
            "priority": 1,
            "stage_availability": "Post-Selection",
            "campus": campus_name,
            "program": program_name
        }).insert(ignore_permissions=True, ignore_links=True)
    else:
        # Ensure coverage value is 3000, campus and program
        frappe.db.set_value("Scholarship Scheme", {"scheme_code": scheme_code, "admission_cycle": cycle_name}, {
            "coverage_value": 3000,
            "campus": campus_name,
            "program": program_name
        })
    
    scheme_id = frappe.db.get_value("Scholarship Scheme", {"scheme_code": scheme_code, "admission_cycle": cycle_name}, "name")

    # Prepare Fee Assignment
    afa_filters = {"applicant": applicant_id, "admission_cycle": cycle_name}
    afa_name = frappe.db.get_value("Applicant Fee Assignment", afa_filters, "name")
    if afa_name:
        frappe.delete_doc("Applicant Fee Assignment", afa_name, ignore_permissions=True)
    
    afa = frappe.get_doc({
        "doctype": "Applicant Fee Assignment",
        "applicant": applicant_id,
        "admission_cycle": cycle_name,
        "total_amount": 10000,
        "status": "Draft",
        "offer_letter": offer_letter_name,
        "program": program_name,
        "academic_year": academic_year_name,
        "fee_components": [
            {
                "fee_component": "tution fee",
                "amount": 10000,
                "total_amount": 10000
            }
        ]
    }).insert(ignore_links=True, ignore_permissions=True)

    try:
        print(f"DEBUG: Starting tests for applicant {applicant_id} and cycle {cycle_name}")
        
        # Test 1: Apply Deduction
        sa = frappe.get_doc({
            "doctype": "Scholarship Application",
            "applicant_id": applicant_id,
            "admission_cycle": cycle_name,
            "scholarship_scheme": scheme_id,
            "original_fee_amount": 10000,
            "status": "Submitted",
            "campus": campus_name,
            "program": program_name,
            "family_income": 500000,
            "income_certificate": "/path/to/cert.pdf"
        })
        sa.flags.ignore_mandatory = True
        sa.insert(ignore_permissions=True, ignore_links=True)
        print(f"DEBUG: Created Scholarship Application {sa.name}")

        sa.status = "Approved"
        sa.save(ignore_permissions=True)
        print(f"DEBUG: Approved Scholarship Application")

        afa.reload()
        print(f"DEBUG: AFA scholarship_amount: {afa.scholarship_amount}")
        assert flt(afa.scholarship_amount) == 3000, f"Expected 3000, got {afa.scholarship_amount}"
        assert flt(afa.final_payable_amount) == 7000, f"Expected 7000, got {afa.final_payable_amount}"
        assert afa.scholarship_applied == 1
        
        # Test 2: Revoke Deduction
        sa.status = "Revoked"
        sa.save(ignore_permissions=True)
        print(f"DEBUG: Revoked Scholarship Application")
        
        afa.reload()
        assert flt(afa.scholarship_amount) == 0
        assert flt(afa.final_payable_amount) == 10000
        assert afa.scholarship_applied == 0
        
        print("ALL TESTS PASSED")
    except Exception as e:
        print(f"TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        frappe.db.delete("Scholarship Application", {"applicant_id": applicant_id})
        frappe.db.delete("Applicant Fee Assignment", {"applicant": applicant_id})
        frappe.db.commit()

if __name__ == "__main__":
    run_fee_tests()
