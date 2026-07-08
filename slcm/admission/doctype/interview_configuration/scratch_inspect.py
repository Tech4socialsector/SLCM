import frappe

def inspect():
    frappe.init(site="slcm.com", sites_path="/home/bsoft/slcm-bench-v16/sites")
    frappe.connect()
    
    doc = frappe.get_doc("Interview Configuration", "gh")
    doc.status = "Draft"
    doc.save()
    frappe.db.commit()
    
    doc.fetch_applicant_counts()
    
    # Delete any existing list for these program/campus/cycle
    filters = {
        "academic_year": doc.academic_year,
        "campus": doc.campus,
        "admission_cycle": doc.admission_cycle,
        "program": doc.program[0].program
    }
    old_list = frappe.db.get_value("Interview List", filters, "name")
    if old_list:
        frappe.delete_doc("Interview List", old_list, force=True)
        frappe.db.commit()
        
    res = doc.generate_interview_list()
    frappe.db.commit()
    print("Generation result (list name):", res)
    
    # Inspect new list
    new_list = frappe.db.get_value("Interview List", filters, "name")
    if new_list:
        list_doc = frappe.get_doc("Interview List", new_list)
        print("Generated list name:", list_doc.name)
        print("Number of candidates generated:", len(list_doc.interview_applicant))
        for idx, c in enumerate(list_doc.interview_applicant, 1):
            print(f"  {idx}. {c.applicant}")
    else:
        print("No Interview List generated!")
