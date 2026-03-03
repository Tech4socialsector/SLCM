import frappe
from slcm.admission.doctype.merit_rule.merit_service import generate_merit_for_level

def verify():
    # Use existing data to avoid link validation issues
    cycle = "QC-Test-Cycle"
    campus = "CAMP-0002"
    program_level = "UG"

    # Create a temporary Merit Rule
    rule_name = "SIMULATED-VERIFY-RULE"
    if frappe.db.exists("Merit Rule", rule_name):
        frappe.delete_doc("Merit Rule", rule_name)
    
    rule = frappe.get_doc({
        "doctype": "Merit Rule",
        "rule_name": rule_name,
        "admission_cycle": cycle,
        "program_level": program_level,
        "minimum_marks": 60,
        "version": 1,
        "is_active": 1,
        "approval_authority": "VC",
        "effective_from": "2026-01-01",
        "components": [
            {
                "component_type": "HSC Percentage",
                "weight": 100,
                "is_active": 1
            }
        ]
    }).insert(ignore_permissions=True)

    # Mocking applicants for the test runner skip
    # Since generate_merit_for_level fetch from DB, we need some Eligibility Result records
    # Let's create two temporary ones
    app1_id = "VERIFY-APP-1"
    app2_id = "VERIFY-APP-2"

    for aid in [app1_id, app2_id]:
        if frappe.db.exists("Eligibility Result", aid):
            frappe.delete_doc("Eligibility Result", aid)

    frappe.get_doc({
        "doctype": "Eligibility Result",
        "applicant_id": app1_id,
        "candidate_name": "Applicant High",
        "program": "Test", # Assuming 'Test' might fail, let's find a real program if needed or ignore link if possible
        "program_level": program_level,
        "hsc_percentage": 70,
        "admission_cycle": cycle,
        "campus": campus,
        "result_status": "Qualified"
    }).insert(ignore_permissions=True)

    frappe.get_doc({
        "doctype": "Eligibility Result",
        "applicant_id": app2_id,
        "candidate_name": "Applicant Low",
        "program": "Test",
        "program_level": program_level,
        "hsc_percentage": 50,
        "admission_cycle": cycle,
        "campus": campus,
        "result_status": "Qualified"
    }).insert(ignore_permissions=True)

    # Need a mapping for generate_merit_for_level to find the rule
    # We'll temporarily deactivate others if any
    frappe.db.sql("update `tabMerit Rule Mapping` set is_active=0 where admission_cycle=%s and campus=%s and program_level=%s", (cycle, campus, program_level))
    
    mapping = frappe.get_doc({
        "doctype": "Merit Rule Mapping",
        "admission_cycle": cycle,
        "campus": campus,
        "program_level": program_level,
        "merit_rule": rule.name,
        "priority": 999,
        "is_active": 1
    }).insert(ignore_permissions=True)

    try:
        # Run Generation
        merit_list = generate_merit_for_level(cycle, campus, program_level)

        # Check results
        applicants = [d.applicant_id for d in merit_list.merit_applicants]
        print(f"Applicants in Merit List: {applicants}")
        
        # V1 should be in, V2 should not
        high_present = any(app1_id in a for a in applicants)
        low_present = any(app2_id in a for a in applicants)

        print(f"High Score Present: {high_present}")
        print(f"Low Score Present: {low_present}")

        if high_present and not low_present:
            print("Verification Successful!")
        else:
            print("Verification Failed!")
            if not high_present: print("Error: High score applicant missing.")
            if low_present: print("Error: Low score applicant included.")

    finally:
        frappe.db.rollback()
        print("Cleanup (Rollback) successful.")

if __name__ == "__main__":
    verify()
