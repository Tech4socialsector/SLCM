import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field

def install():
    if not frappe.db.exists('DocType', 'Marks Import Log'):
        doc = frappe.get_doc({
            'doctype': 'DocType',
            'name': 'Marks Import Log',
            'module': 'SLCM',
            'custom': 0,
            'autoname': 'hash',
            'permissions': [{'role': 'slcm_Registrar', 'read': 1, 'write': 1, 'create': 1, 'delete': 1, 'submit': 0, 'cancel': 0, 'amend': 0}],
            'fields': [
                {'fieldname': 'import_file', 'label': 'Import File', 'fieldtype': 'Attach', 'reqd': 1},
                {'fieldname': 'imported_by', 'label': 'Imported By', 'fieldtype': 'Link', 'options': 'User', 'read_only': 1, 'default': frappe.session.user if frappe.session and hasattr(frappe.session, 'user') else 'Administrator'},
                {'fieldname': 'import_date', 'label': 'Import Date', 'fieldtype': 'Datetime', 'read_only': 1, 'default': 'Now'},
                {'fieldname': 'status', 'label': 'Status', 'fieldtype': 'Select', 'options': 'Queued\nIn Progress\nCompleted\nCompleted with Errors\nFailed'},
                {'fieldname': 'total_rows', 'label': 'Total Rows', 'fieldtype': 'Int', 'read_only': 1},
                {'fieldname': 'success_count', 'label': 'Success Count', 'fieldtype': 'Int', 'read_only': 1},
                {'fieldname': 'failed_count', 'label': 'Failed Count', 'fieldtype': 'Int', 'read_only': 1},
                {'fieldname': 'skipped_count', 'label': 'Skipped Count', 'fieldtype': 'Int', 'read_only': 1},
                {'fieldname': 'missing_offerings_count', 'label': 'Missing Offerings Count', 'fieldtype': 'Int', 'read_only': 1},
                {'fieldname': 'error_summary', 'label': 'Error Summary', 'fieldtype': 'Small Text', 'read_only': 1},
                {'fieldname': 'remarks', 'label': 'Remarks', 'fieldtype': 'Small Text'}
            ]
        })
        doc.insert(ignore_permissions=True)
        print('Marks Import Log Doctype created.')
    
    if not frappe.db.exists('DocType', 'Marks Import Log Detail'):
        doc = frappe.get_doc({
            'doctype': 'DocType',
            'name': 'Marks Import Log Detail',
            'module': 'SLCM',
            'custom': 0,
            'autoname': 'hash',
            'permissions': [{'role': 'slcm_Registrar', 'read': 1, 'write': 1, 'create': 1, 'delete': 1, 'submit': 0, 'cancel': 0, 'amend': 0}],
            'fields': [
                {'fieldname': 'import_log', 'label': 'Import Log', 'fieldtype': 'Link', 'options': 'Marks Import Log', 'reqd': 1, 'in_list_view': 1},
                {'fieldname': 'row_number', 'label': 'Row Number', 'fieldtype': 'Int'},
                {'fieldname': 'registration_id', 'label': 'Registration ID', 'fieldtype': 'Data'},
                {'fieldname': 'course_code', 'label': 'Course Code', 'fieldtype': 'Data'},
                {'fieldname': 'term_name', 'label': 'Term Name', 'fieldtype': 'Data'},
                {'fieldname': 'status', 'label': 'Status', 'fieldtype': 'Select', 'options': 'Success\nFailed\nSkipped\nMissing Course Offering', 'in_list_view': 1},
                {'fieldname': 'student_course_marks', 'label': 'Student Course Marks', 'fieldtype': 'Link', 'options': 'Student Course Marks'},
                {'fieldname': 'error_reason', 'label': 'Error Reason', 'fieldtype': 'Small Text'},
                {'fieldname': 'raw_row_json', 'label': 'Raw Row JSON', 'fieldtype': 'Long Text'}
            ]
        })
        doc.insert(ignore_permissions=True)
        print('Marks Import Log Detail Doctype created.')
    
    frappe.db.commit()
