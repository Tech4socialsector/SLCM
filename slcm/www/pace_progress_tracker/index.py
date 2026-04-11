import frappe
from frappe import _

def get_context(context):
    user = frappe.session.user
    if user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect
    
    # Fetch PACE Application
    application = frappe.get_all("PACE Application", 
        filters={"email_address": user}, 
        fields=["name", "status", "programme", "first_name", "last_name", "application_form", "submission_date", "creation"],
        order_by="creation desc",
        limit=1
    )
    
    if not application:
        context.no_application = True
        return context
    
    app = application[0]
    context.app = app
    
    # Programme details
    context.programme = frappe.db.get_value("PACE Programme", app.programme, ["programme_name", "duration", "duration_type"], as_dict=True)
    
    # Verification details
    verification = frappe.get_all("PACE Document Verification",
        filters={"application": app.name},
        fields=["name", "overall_status"],
        limit=1
    )
    
    context.verification = verification[0] if verification else None
    if context.verification:
        context.verification_items = frappe.get_all("PACE Verification Item",
            filters={"parent": context.verification.name},
            fields=["document_name", "fieldname", "file", "status", "remarks", "is_reuploaded"]
        )
    else:
        context.verification_items = []

    # Fee Assignment details
    assignment = frappe.get_all("PACE Applicant Fee Assignment",
        filters={"applicant": app.name, "status": ["!=", "Cancelled"]},
        fields=["name", "status", "total_amount", "final_payable_amount", "currency", "academic_year"],
        limit=1
    )
    
    context.assignment = assignment[0] if assignment else None
    
    # Receipt details
    receipt = frappe.get_all("PACE Receipt",
        filters={"pace_application": app.name},
        fields=["name", "transaction_id", "payment_date"],
        limit=1
    )
    context.receipt = receipt[0] if receipt else None

    # Step status logic
    context.steps = get_step_statuses(app, context.verification, context.assignment)
    
    return context

def get_step_statuses(app, verification, assignment):
    steps = [
        {"id": "submitted", "label": "Submitted", "status": "pending", "date": frappe.utils.format_date(app.creation)},
        {"id": "verified", "label": "Verified", "status": "pending", "date": ""},
        {"id": "fee_payment", "label": "Fee payment", "status": "pending", "date": ""},
        {"id": "offer_letter", "label": "Offer letter", "status": "pending", "date": ""},
        {"id": "enrolled", "label": "Enrolled", "status": "pending", "date": ""}
    ]
    
    # 1. Submitted
    steps[0]["status"] = "completed"
    
    # 2. Verified
    v_status = verification.overall_status if verification else "Pending"
    if v_status == "Verified":
        steps[1]["status"] = "completed"
        steps[1]["date"] = "Verified"
    elif v_status == "Returned for Correction":
        steps[1]["status"] = "active"
        steps[1]["date"] = "Re-upload required"
    elif app.status == "Under Verification":
        steps[1]["status"] = "active"
        steps[1]["date"] = "Processing"
    else:
        steps[1]["status"] = "active"
    
    # 3. Fee Payment
    if steps[1]["status"] == "completed":
        if assignment:
            if assignment.status == "Paid":
                steps[2]["status"] = "completed"
                steps[2]["date"] = "Paid"
            else:
                steps[2]["status"] = "active"
                steps[2]["date"] = "Action required"
        else:
            steps[2]["status"] = "pending"
    
    # 5. Enrolled (Admission)
    if app.status == "Admitted":
        steps[4]["status"] = "completed"
        steps[2]["status"] = "completed" # If admitted, payment must be done (usually)
        steps[1]["status"] = "completed"
    
    return steps
