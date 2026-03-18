import frappe
from frappe import _

def get_context(context):
    offer_name = frappe.form_dict.get('offer')
    
    # Default value for offer to avoid jinja error
    context.offer = {"name": "", "program": "", "campus": ""}
    
    if not offer_name:
        return context
        
    # Fetch offer data
    offers = frappe.get_all("Offer Letter", 
        filters={"name": offer_name}, 
        fields=["name", "applicant", "program", "campus"],
        limit=1
    )
    
    if offers:
        offer_data = offers[0]
        context.offer = offer_data
        
        # Pre-fill applicant details
        context.applicant_name = frappe.db.get_value("Applicant", offer_data.applicant, "candidate_name")
        
        # Get cancellation reason types
        meta = frappe.get_meta("Admission Cancellation")
        reason_field = meta.get_field("cancellation_reason_type")
        context.cancellation_reasons = reason_field.options.split("\n") if reason_field else []
        
        # Find associated fee invoice through Applicant Fee Assignment
        fee_invoice = frappe.db.get_value("Applicant Fee Assignment", 
            {"offer_letter": offer_data.name, "status": ["!=", "Cancelled"]}, 
            "fee_invoice"
        )
        
        # Find associated fee payment
        payments = []
        if fee_invoice:
            payments = frappe.get_all("Fee Payment", 
                filters={"fee_invoice": fee_invoice, "status": "Submitted"},
                fields=["name", "amount", "reference_number"],
                limit=1
            )
        context.payment = payments[0] if payments else None
    
    # Get Portal Config for colors
    context.portal_config = frappe.get_single("Applicant Portal Config")
    
    context.no_cache = 1
    return context
