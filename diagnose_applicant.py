import frappe
import os

def diagnose():
    sites_path = "/home/joy-sathish/frappe/slcm/sites"
    os.chdir(sites_path)
    frappe.init(site="slcm.com", sites_path=sites_path)
    frappe.connect()

    print("=== Applicant Meta ===")
    meta = frappe.get_meta("Applicant")
    email_fields = [f.fieldname for f in meta.fields if "email" in f.fieldname.lower()]
    print("Email-related fields:", email_fields)
    
    # Check if 'user' or 'user_id' exists
    user_fields = [f.fieldname for f in meta.fields if "user" in f.fieldname.lower()]
    print("User-related fields:", user_fields)

    print("\n=== Sample Applicant Records ===")
    samples = frappe.get_all("Applicant", fields=["name", "owner", "creation"] + email_fields, limit=3)
    for s in samples:
        print(s)

    if samples:
        print("\n=== Detailed Sample (first one) ===")
        doc = frappe.get_doc("Applicant", samples[0].name)
        for f in doc.meta.fields:
            val = doc.get(f.fieldname)
            if val:
                print(f"  {f.fieldname}: {val}")
        print(f"  owner: {doc.owner}")

    frappe.destroy()

if __name__ == "__main__":
    diagnose()
