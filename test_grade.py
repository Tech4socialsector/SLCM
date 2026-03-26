import frappe
frappe.init(site="slcm.test")
frappe.connect()
doc = frappe.get_doc({
    "doctype": "Grading Schema Component",
    "grade": "A<sup>+</sup>",
    "marks_from": 90,
    "marks_to": 100,
    "grade_point": 10,
    "parent": "Dummy",
    "parenttype": "Grading Schema",
    "parentfield": "grades"
})
print("Grade set to:", doc.grade)
