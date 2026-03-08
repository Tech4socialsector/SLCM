import frappe
import os

def seed_detail_data():
    sites_path = "/home/joy-sathish/frappe/slcm/sites"
    os.chdir(sites_path)
    frappe.init(site="slcm.com", sites_path=sites_path)
    frappe.connect()

    try:
        doc = frappe.get_doc("Applicant Portal Config")
        
        doc.support_name = "Admissions Office"
        doc.support_role = "Admissions Coordinator"
        doc.support_email = "admissions@nlsiu.ac.in"
        
        # Check if stage_next_steps exists in meta
        if any(f.fieldname == "stage_next_steps" for f in doc.meta.fields):
            # Clear existing next steps to avoid duplicates if re-run
            doc.set("stage_next_steps", [])
            
            steps = [
                {"stage_name": "Application",   "step_text": "Complete all required fields and submit your form."},
                {"stage_name": "Entrance Test", "step_text": "Download your admit card and check test details."},
                {"stage_name": "Interview",     "step_text": "Check your interview slot and confirm attendance."},
                {"stage_name": "Merit List",    "step_text": "Monitor the merit list for your rank and category."},
                {"stage_name": "Offer",         "step_text": "Review your offer letter and pay the acceptance fee."},
            ]
            
            for s in steps:
                doc.append("stage_next_steps", s)
        else:
            print("Warning: stage_next_steps field not found in meta.")
            
        doc.save()
        frappe.db.commit()
        print("✅ Detail support and next steps seeded in Applicant Portal Config")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

    frappe.destroy()

if __name__ == "__main__":
    seed_detail_data()
