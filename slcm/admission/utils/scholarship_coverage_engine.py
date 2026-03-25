import frappe
from frappe.utils import flt

def calculate_scholarship_amount(application_doc):
    """
    Main entry point for calculating scholarship benefit.
    """
    scheme = frappe.get_doc("Scholarship Scheme", application_doc.scholarship_scheme)
    original_fee = flt(application_doc.original_fee_amount)
    benefit = 0

    # Determine calculation mode
    # Case 1: Component-wise rules (Either by coverage_type OR by apply_on)
    if scheme.coverage_type == "Component-wise" or scheme.apply_on == "Component-wise":
        benefit = calculate_component_wise(application_doc, scheme)

    # Case 2: Simple calculation on a specific base
    else:
        if scheme.apply_on == "Tuition Only":
            base_amount = get_tuition_amount(application_doc)
        else:
            # Default to Total Fee
            base_amount = original_fee
            
        benefit = calculate_base_benefit(base_amount, scheme)

    # Cap by scheme maximum amount if applicable (for non-component-wise or overall cap)
    if scheme.max_amount and flt(scheme.max_amount) > 0:
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

def resolve_fee_structure(application_doc):
    """
    Finds the active Fee Structure for the given application.
    Logic mirrors OfferService.get_active_config and FeeService.
    """
    program = application_doc.program
    campus = application_doc.campus
    cycle = application_doc.admission_cycle
    
    # Try to find academic year from Applicant if not on application
    academic_year = application_doc.get("academic_year")
    if not academic_year:
        academic_year = frappe.db.get_value("Applicant", application_doc.applicant_id, "academic_year")
    
    # Also try mapping from Admission Cycle -> Admission Year -> Academic Year (via settings or name match)
    if not academic_year:
        admission_year = frappe.db.get_value("Admission Cycle", cycle, "admission_year")
        if admission_year:
            # Simple assumption: Admission Year name matches Academic Year name
            if frappe.db.exists("Academic Year", admission_year):
                academic_year = admission_year
    
    # Last fallback: Admission Settings
    if not academic_year:
        academic_year = frappe.db.get_single_value("Admission Settings", "current_academic_year")

    if not academic_year:
        return None

    # Find active Fee Structure
    fee_structure = frappe.get_all("Fee Structure", 
        filters={
            "program": program,
            "academic_year": academic_year,
            "status": "Active"
        },
        limit=1
    )

    if not fee_structure:
        return None

    return frappe.get_doc("Fee Structure", fee_structure[0].name)

def get_tuition_amount(application_doc):
    """Fetches the Tuition component amount from the relevant Fee Structure."""
    fs_doc = resolve_fee_structure(application_doc)
    if not fs_doc:
        return flt(application_doc.original_fee_amount)

    for comp in fs_doc.components:
        # Check by name or flag
        is_tuition = False
        if comp.fee_component == "Tuition":
            is_tuition = True
        else:
            # Check if the fee component record has the tuition flag
            is_tuition = frappe.db.get_value("Fee Component", comp.fee_component, "is_tuition_fee")

        if is_tuition:
            return flt(comp.amount)

    return flt(application_doc.original_fee_amount)

def calculate_component_wise(application_doc, scheme):
    """Calculates benefit by applying specific rules to individual fee components."""
    total_benefit = 0
    
    fs_doc = resolve_fee_structure(application_doc)
    if not fs_doc:
        return 0

    # Build component lookup: {component_name/id: amount}
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
        if rule.maximum_cap and flt(rule.maximum_cap) > 0:
            comp_benefit = min(comp_benefit, flt(rule.maximum_cap))

        total_benefit += comp_benefit

    return total_benefit
