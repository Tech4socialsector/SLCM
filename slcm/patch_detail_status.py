import frappe

def execute():
    # Update the status field options in Marks Import Log Detail
    doc = frappe.get_doc('DocType', 'Marks Import Log Detail')
    for field in doc.fields:
        if field.fieldname == 'status':
            field.options = 'Pending\nValid\nMissing Student\nMissing Course\nMissing Course Offering\nDuplicate (Skip)\nSuccess\nFailed'
            break
    doc.save()
    frappe.db.commit()
    print('Patched Marks Import Log Detail status options.')
