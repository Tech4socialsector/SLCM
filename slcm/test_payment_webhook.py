import frappe
from slcm.slcm.doctype.foundations_for_a_legal_education.foundations_for_a_legal_education import verify_payment

def run():
    # 1. Create a dummy Doc
    doc = frappe.get_doc({
        "doctype": "Foundations for a Legal Education",
        "candidate_name": "Test Webhook User",
        "email_address": "test_webhook@example.com",
        "candidate_contact_number": "1234567890",
        "where_did_you_hear_about_the_fle_programme": "Social Media",
        "payment_status": "Unpaid"
    })
    doc.insert(ignore_permissions=True)
    doc_name = doc.name
    
    print(f"Created Doc: {doc_name}")
    
    # 2. Simulate verify_payment (we will mock the signature part by directly calling save)
    # Since we can't easily mock the Razorpay signature verification without a real API key,
    # we'll just replicate what verify_payment does AFTER verification:
    try:
        payment_doc = frappe.get_doc("Foundations for a Legal Education", doc_name)
        payment_doc.payment_status = "Paid"
        payment_doc.enrollment_status = "Enrolled"
        payment_doc.payment_instructions = "Payment successful. Reference ID: pay_mock123"
        print("Saving document to trigger hooks...")
        payment_doc.save(ignore_permissions=True)
        
        # 3. Verify User Creation
        email = "test_webhook@example.com"
        if frappe.db.exists("User", email):
            user = frappe.get_doc("User", email)
            roles = frappe.get_roles(user.name)
            print(f"SUCCESS: User created with roles: {roles}")
        else:
            print("FAILURE: User was NOT created!")
            
    except Exception as e:
        print("Error during save:", str(e))
        print(frappe.get_traceback())

