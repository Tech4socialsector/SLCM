import json
import os

def patch_grading_schema():
    path = '/home/jenifar/slcm_v16/apps/slcm/slcm/slcm/doctype/grading_schema/grading_schema.json'
    with open(path, 'r') as f:
        doc = json.load(f)

    fields = doc['fields']
    fieldnames = [f['fieldname'] for f in fields]
    
    # 1. rename grading_schema_name label to "Schema Code"
    # 2. Add `schema_name` (Label: Name) after `grading_schema_name`
    # 3. Add `description` (Small Text) after `schema_name`
    # 4. Rename section_break_grades to "Grade Schema Global Settings"
    # 5. Rename grades to "Regular/Makeup Exam Composition"

    for f in fields:
        if f['fieldname'] == 'grading_schema_name':
            f['label'] = 'Schema Code'
        elif f['fieldname'] == 'section_break_grades':
            f['label'] = 'Grade Schema Global Settings'
        elif f['fieldname'] == 'grades':
            f['label'] = 'Regular/Makeup Exam Composition'
            f['description'] = ''

    if 'schema_name' not in fieldnames:
        idx = next((i for i, f in enumerate(fields) if f['fieldname'] == 'grading_schema_name'), 0)
        fields.insert(idx + 1, {
            "fieldname": "schema_name",
            "fieldtype": "Data",
            "label": "Name",
            "in_list_view": 1
        })
        fieldnames.insert(idx + 1, 'schema_name')

    if 'description' not in fieldnames:
        idx = next((i for i, f in enumerate(fields) if f['fieldname'] == 'schema_name'), 1)
        fields.insert(idx + 1, {
            "fieldname": "description",
            "fieldtype": "Small Text",
            "label": "Description"
        })
        fieldnames.insert(idx + 1, 'description')
        
    doc['field_order'] = [f['fieldname'] for f in fields]
    
    with open(path, 'w') as f:
        json.dump(doc, f, indent=1)

def patch_grading_schema_component():
    path = '/home/jenifar/slcm_v16/apps/slcm/slcm/slcm/doctype/grading_schema_component/grading_schema_component.json'
    with open(path, 'r') as f:
        doc = json.load(f)

    fields = doc['fields']
    fieldnames = [f['fieldname'] for f in fields]

    if 'qualitative_meaning' not in fieldnames:
        idx = next((i for i, f in enumerate(fields) if f['fieldname'] == 'grade'), 0)
        fields.insert(idx + 1, {
            "fieldname": "qualitative_meaning",
            "fieldtype": "Data",
            "label": "Qualitative Meaning",
            "in_list_view": 1
        })
        fieldnames.insert(idx + 1, 'qualitative_meaning')

    doc['field_order'] = [f['fieldname'] for f in fields]
    
    with open(path, 'w') as f:
        json.dump(doc, f, indent=1)

if __name__ == "__main__":
    patch_grading_schema()
    patch_grading_schema_component()
    print("Patched Grading Schema schemas successfully.")
