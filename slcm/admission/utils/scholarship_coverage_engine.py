import frappe
from frappe.utils import flt

def calculate_scholarship_amount(application_doc):
    """
    Main entry point for calculating scholarship benefit.
    """
    scheme = frappe.get_doc("Scholarship Scheme", application_doc.scholarship_scheme)
    original_fee = flt(application_doc.original_fee_amount)
    benefit = 0

    # Determine base amount based on "Apply On"
    if scheme.apply_on == "Total Fee":
        base_amount = original_fee
        benefit = calculate_base_benefit(base_amount, scheme)

    elif scheme.apply_on == "Tuition Only":
        base_amount = get_tuition_amount(application_doc)
        benefit = calculate_base_benefit(base_amount, scheme)

    elif scheme.apply_on == "Component-wise":
        benefit = calculate_component_wise(application_doc, scheme)

    else:
        # Default to Total Fee if not specified
        base_amount = original_fee
        benefit = calculate_base_benefit(base_amount, scheme)

    # Cap by scheme maximum amount if applicable (for non-component-wise)
    if scheme.apply_on != "Component-wise" and scheme.max_amount:
        benefit = min(benefit, flt(scheme.max_amount))

    # Prevent over-deduction (total benefit cannot exceed original fee)
    benefit = min(benefit, original_fee)

    return benefit

def calculate_base_benefit(base_amount, scheme):
    """Calculates benefit based on simple coverage type and value."""
    benefit = 0
    if scheme.coverage_type == "Percentage":
        benefit = (flt(base_amount) * flt(scheme.coverage_value)) / 100
    elif scheme.coverage_type == "Fixed":
        benefit = flt(scheme.coverage_value)
    return benefit

def get_tuition_amount(application_doc):
    """Fetches the Tuition component amount from the relevant Fee Structure."""
    # Find active Fee Structure for the program and academic year
    # Assuming Academic Year is available on Applicant or Application
    academic_year = application_doc.get("academic_year")
    if not academic_year:
        academic_year = frappe.db.get_value("Applicant", application_doc.applicant_id, "academic_year")

    fee_structure = frappe.get_all("Fee Structure", 
        filters={
            "program": application_doc.program,
            "academic_year": academic_year,
            "status": "Active"
        },
        limit=1
    )

    if not fee_structure:
        # Fallback to total if no specific structure found
        return flt(application_doc.original_fee_amount)

    fs_doc = frappe.get_doc("Fee Structure", fee_structure[0].name)
    for comp in fs_doc.components:
        # Check by name or link? Usually fee_component logic
        if comp.fee_component == "Tuition" or frappe.db.get_value("Fee Component", comp.fee_component, "is_tuition_fee"):
            return flt(comp.amount)

    return flt(application_doc.original_fee_amount)

def calculate_component_wise(application_doc, scheme):
    """Calculates benefit by applying specific rules to individual fee components."""
    total_benefit = 0
    
    # Get Fee Structure components
    academic_year = application_doc.get("academic_year")
    if not academic_year:
        academic_year = frappe.db.get_value("Applicant", application_doc.applicant_id, "academic_year")

    fee_structure = frappe.get_all("Fee Structure", 
        filters={
            "program": application_doc.program,
            "academic_year": academic_year,
            "status": "Active"
        },
        limit=1
    )

    if not fee_structure:
        return 0

    fs_doc = frappe.get_doc("Fee Structure", fee_structure[0].name)
    components = {c.fee_component: flt(c.amount) for c in fs_doc.components}

    # Apply rules from scheme
    for rule in scheme.get("coverage_rules") or []:
        if not rule.is_applicable:
            continue
            
        comp_amount = components.get(rule.fee_component, 0)
        if comp_amount <= 0:
            continue

        comp_benefit = 0
        if rule.coverage_type == "Percentage":
            comp_benefit = (comp_amount * flt(rule.coverage_value)) / 100
        elif rule.coverage_type == "Fixed":
            comp_benefit = flt(rule.coverage_value)

        # Apply component-level cap
        if rule.maximum_cap:
            comp_benefit = min(comp_benefit, flt(rule.maximum_cap))

        total_benefit += comp_benefit

    return total_benefit
