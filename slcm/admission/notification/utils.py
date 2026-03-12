import frappe

def set_payment_request_receiver(doc, method=None):
    """
    Sets the notification_receiver attribute on Payment Request 
    so that the Notification engine can use it.
    """
    if doc.reference_doctype == "Offer Letter":
        applicant = frappe.db.get_value("Offer Letter", doc.reference_name, "applicant")
        if applicant:
            applicant_email = frappe.db.get_value("Applicant", applicant, "email")
            if applicant_email:
                user_name = frappe.db.get_value("User", {"email": applicant_email}, "name")
                if user_name:
                    doc.notification_receiver = user_name
        return
    if doc.reference_doctype == "Applicant":
        applicant = doc.reference_name
        if applicant:
            applicant_email = frappe.db.get_value("Applicant", applicant, "email")
            if applicant_email:
                user_name = frappe.db.get_value("User", {"email": applicant_email}, "name")
                if user_name:
                    # We set it on the object. 
                    # If the field doesn't exist in the DB, Frappe still carries it in the doc object
                    # during the transaction/event.
                    doc.notification_receiver = user_name
