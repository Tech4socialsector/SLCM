import frappe

def final_check():
    print("Running final check for 'Current Status'...")
    
    # Check DocType fields globally
    print("Checking DocField label='Current Status'...")
    fields = frappe.db.sql("select parent, fieldname, fieldtype from tabDocField where label='Current Status'", as_dict=True)
    for f in fields:
        print(f"MATCH DocField: Parent={f.parent}, Field={f.fieldname}, Type={f.fieldtype}")

    # Check Custom Fields globally
    print("Checking Custom Field label='Current Status'...")
    cfields = frappe.db.sql("select dt, fieldname, fieldtype from `tabCustom Field` where label='Current Status'", as_dict=True)
    for f in cfields:
        print(f"MATCH CustomField: DocType={f.dt}, Field={f.fieldname}, Type={f.fieldtype}")

    # Check Property Setters
    print("Checking Property Setters value='Current Status'...")
    ps = frappe.db.sql("select doc_type, field_name, property, value from `tabProperty Setter` where value='Current Status'", as_dict=True)
    for p in ps:
        print(f"MATCH PropertySetter: DocType={p.doc_type}, Field={p.field_name}, Prop={p.property}")

    # Check Translations
    print("Checking Translations target_name='Current Status'...")
    ts = frappe.db.sql("select source_name, target_name from tabTranslation where target_name='Current Status'", as_dict=True)
    for t in ts:
        print(f"MATCH Translation: {t.source_name} -> {t.target_name}")

    # Check Server Scripts
    print("Checking Server Scripts content...")
    ss = frappe.db.sql("select name, reference_doctype from `tabServer Script` where script like '%Current Status%'", as_dict=True)
    for s in ss:
        print(f"MATCH ServerScript: {s.name} on {s.reference_doctype}")

    # Check Workflow
    print("Checking Workflow state field...")
    wf = frappe.db.sql("select name, document_type, workflow_state_field from tabWorkflow where workflow_state_field='Current Status'", as_dict=True)
    for w in wf:
        print(f"MATCH Workflow: {w.name} on {w.document_type}")

final_check()
