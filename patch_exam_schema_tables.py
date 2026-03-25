import json

path = '/home/jenifar/slcm_v16/apps/slcm/slcm/slcm/doctype/exam_schema/exam_schema.json'
with open(path, 'r') as f:
    doc = json.load(f)

fields = doc['fields']
fieldnames = [f['fieldname'] for f in fields]

new_fields = [
    {
        "fieldname": "internal_assessment_composition",
        "fieldtype": "Table",
        "label": "Internal Assessment Composition",
        "options": "Exam Schema Assessment"
    },
    {
        "fieldname": "total_effective_internal_marks",
        "fieldtype": "Float",
        "label": "Total Effective Internal Marks",
        "read_only": 1
    },
    {
        "fieldname": "section_break_external",
        "fieldtype": "Section Break",
        "label": "External Composition"
    },
    {
        "fieldname": "external_assessment_composition",
        "fieldtype": "Table",
        "label": "External Assessment Composition",
        "options": "Exam Schema Assessment"
    },
    {
        "fieldname": "total_effective_external_marks",
        "fieldtype": "Float",
        "label": "Total Effective External Marks",
        "read_only": 1
    }
]

# Ensure we don't duplicate existing ones
fields_to_add = [f for f in new_fields if f['fieldname'] not in fieldnames]

# Insert at the end
fields.extend(fields_to_add)

doc['field_order'] = [f['fieldname'] for f in fields]

with open(path, 'w') as f:
    json.dump(doc, f, indent=1)

print("exam_schema.json patched with internal/external tables and totals.")
