import json

path = '/home/jenifar/slcm_v16/apps/slcm/slcm/slcm/doctype/exam_schema/exam_schema.json'
with open(path, 'r') as f:
    doc = json.load(f)

fields = doc['fields']
fieldnames = [f['fieldname'] for f in fields]

new_fields = [
    {
        "fieldname": "section_break_makeup",
        "fieldtype": "Section Break",
        "label": "Makeup Composition"
    },
    {
        "fieldname": "makeup_assessment_composition",
        "fieldtype": "Table",
        "label": "Makeup Assessment Composition",
        "options": "Exam Schema Assessment"
    },
    {
        "fieldname": "total_effective_makeup_marks",
        "fieldtype": "Float",
        "label": "Total Effective Makeup Marks",
        "read_only": 1
    },
    {
        "fieldname": "section_break_re_exam",
        "fieldtype": "Section Break",
        "label": "Re-Exam Composition"
    },
    {
        "fieldname": "re_exam_assessment_composition",
        "fieldtype": "Table",
        "label": "Re-Exam Assessment Composition",
        "options": "Exam Schema Assessment"
    },
    {
        "fieldname": "total_effective_re_exam_marks",
        "fieldtype": "Float",
        "label": "Total Effective Re-Exam Marks",
        "read_only": 1
    }
]

# Ensure we don't duplicate existing ones
fields_to_add = [f for f in new_fields if f['fieldname'] not in fieldnames]

# Insert just before section_break_zfjn if possible, otherwise at the end
if 'section_break_zfjn' in fieldnames:
    idx = next((i for i, f in enumerate(fields) if f['fieldname'] == 'section_break_zfjn'), len(fields))
    for f in reversed(fields_to_add):
        fields.insert(idx, f)
else:
    fields.extend(fields_to_add)

doc['field_order'] = [f['fieldname'] for f in fields]

with open(path, 'w') as f:
    json.dump(doc, f, indent=1)

print("exam_schema.json patched with makeup/re-exam tables and totals.")
