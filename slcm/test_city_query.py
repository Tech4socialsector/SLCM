import frappe
from slcm.admission.web_form.applicant_form.applicant_form import city_query

def execute():
    frappe.form_dict = frappe._dict({
        "filters[state]": "TAMIL NADU",
        "txt": "CH"
    })
    
    result = city_query(txt="CH")
    print("Result:", result)
