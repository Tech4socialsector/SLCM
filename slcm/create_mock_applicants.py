import frappe

def run():
    source_app = frappe.get_doc("Applicant", "APP-2026-01267")
    
    count = 0
    for i in range(1, 11):
        try:
            new_app = frappe.copy_doc(source_app)
            
            # Make unique fields
            new_app.candidate_name = f"{source_app.candidate_name} Mock {i}"
            
            original_email = source_app.email or "test@example.com"
            email_parts = original_email.split("@")
            if len(email_parts) == 2:
                new_app.email = f"{email_parts[0]}_mock{i}@{email_parts[1]}"
            else:
                new_app.email = f"mock{i}@example.com"
                
            new_app.status = "Submitted"
            new_app.application_fee_status = "Pending"
            
            # Reset timeline tracking fields
            new_app.last_draft_reminder_sent = None
            new_app.last_fee_reminder_sent = None
            new_app.rejected_reason = None
            
            new_app.insert(ignore_permissions=True)
            count += 1
        except Exception as e:
            print(f"Failed to create Mock {i}: {str(e)}")
            frappe.log_error(frappe.get_traceback(), "Mock Applicant Creation Failed")
            
    frappe.db.commit()
    print(f"Successfully created {count} mock applicant records in Submitted stage.")
