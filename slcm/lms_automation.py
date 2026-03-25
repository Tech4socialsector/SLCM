import random
import string
import frappe
from frappe.utils.password import update_password

def generate_random_letters(length=12):
    return ''.join(random.choices(string.ascii_letters, k=length))

def handle_payment_paid(doc, method):
    try:
        status = (doc.get("payment_status") or "").strip().lower()
        enrollment_status = (doc.get("enrollment_status") or "").strip().lower()

        if status != "paid" or enrollment_status != "enrolled":
            return

        # Prevent overwriting password and resending notifications on subsequent saves 
        if doc.get("lms_account_created"):
            return

        email = doc.get("email_address")
        student_name = doc.get("candidate_name")

        if not email:
            frappe.throw("Email missing for User creation.")

        email = email.strip()
        
        # User requested password is random 12 letters explicitly
        password = generate_random_letters(12)

        # Idempotent user creation and role assignment
        if frappe.db.exists("User", email):
            user = frappe.get_doc("User", email)
            if "LMS Student" not in frappe.get_roles(user.name):
                user.add_roles("LMS Student")
            
            # User wants every candidate to get a different password randomly
            update_password(user.name, password)
            doc.generated_password_temp = password
        else:
            user = frappe.get_doc({
                "doctype": "User",
                "email": email,
                "first_name": student_name,
                "enabled": 1,
                "send_welcome_email": 0
            })
            user.insert(ignore_permissions=True)
            
            update_password(user.name, password)
            user.add_roles("LMS Student")

            # Store the generated password on the document so the Notification can use it
            doc.generated_password_temp = password

        # Mark as enrolled and LMS account created
        doc.enrollment_status = "Enrolled"
        doc.lms_account_created = 1

    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), title=f"LMS User Creation Failed for {doc.name}")
        frappe.msgprint(f"LMS User Creation Failed: {str(e)}")