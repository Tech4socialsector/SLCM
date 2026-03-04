import frappe
from slcm.admission.doctype.merit_rule.merit_service import generate_merit_for_level

def verify():
    # Setup dummy data
    cycle = "Verify Cycle 3"
    campus = "Verify Campus 3"
    program_level = "UG"

    # Cleanup existing if any
    frappe.db.delete("Merit Rule", {"rule_name": "Verify Rule 3"})
    frappe.db.delete("Merit Rule Mapping", {"admission_cycle": cycle})
    frappe.db.delete("Eligibility Result", {"admission_cycle": cycle})
    frappe.db.delete("Merit List", {"admission_cycle": cycle})

    # Create Rule
    rule = frappe.get_doc({
        "doctype": "Merit Rule",
        "rule_name": "Verify Rule 3",
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

    # Create Mapping
    frappe.get_doc({
        "doctype": "Merit Rule Mapping",
        "admission_cycle": cycle,
        "campus": campus,
        "program_level": program_level,
        "merit_rule": rule.name,
        "priority": 1,
        "is_active": 1
    }).insert(ignore_permissions=True)

    # Create applicants
    # App 1: Score 70 (Qualified)
    frappe.get_doc({
        "doctype": "Eligibility Result",
        "applicant_id": "V3-APP-001",
        "candidate_name": "Verify One",
        "program": "Test Program",
        "program_level": program_level,
        "hsc_percentage": 70,
        "admission_cycle": cycle,
        "campus": campus,
        "result_status": "Qualified"
    }).insert(ignore_permissions=True)

    # App 2: Score 50 (Qualified but below min marks)
    frappe.get_doc({
        "doctype": "Eligibility Result",
        "applicant_id": "V3-APP-002",
        "candidate_name": "Verify Two",
        "program": "Test Program",
        "program_level": program_level,
        "hsc_percentage": 50,
        "admission_cycle": cycle,
        "campus": campus,
        "result_status": "Qualified"
    }).insert(ignore_permissions=True)

    # Run Generation
    merit_list = generate_merit_for_level(cycle, campus, program_level)

    # Check results
    applicants = [d.applicant_id for d in merit_list.merit_applicants]
    print(f"Applicants in Merit List: {applicants}")
    
    assert "V3-APP-001" in applicants, "V3-APP-001 should be in the list"
    assert "V3-APP-002" not in applicants, "V3-APP-002 should NOT be in the list"
    assert len(merit_list.merit_applicants) == 1, f"Expected 1 applicant, found {len(merit_list.merit_applicants)}"
    
    print("Verification Successful!")
    frappe.db.rollback()
