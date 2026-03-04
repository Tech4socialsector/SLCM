import json

path = '/home/jenifar/slcm_v16/apps/slcm/slcm/slcm/doctype/exam_schema_assessment/exam_schema_assessment.json'
with open(path, 'r') as f:
    doc = json.load(f)

fields = doc['fields']
fieldnames = [f['fieldname'] for f in fields]

new_fields = [
    {
        "fieldname": "section_break_substitution",
        "fieldtype": "Section Break",
        "label": "Substitution Settings"
    },
    {
        "fieldname": "substitution_type",
        "fieldtype": "Select",
        "label": "Substitution Type",
        "options": "\nAssessment\nComponent"
    },
    {
        "fieldname": "substitute_assessment",
        "fieldtype": "Link",
        "label": "Substitute For Assessment",
        "options": "Exam Assessment",
        "depends_on": "eval:doc.substitution_type=='Assessment'"
    },
    {
        "fieldname": "substitute_component",
        "fieldtype": "Select",
        "label": "Substitute For Component",
        "options": "\nInternal\nExternal",
        "depends_on": "eval:doc.substitution_type=='Component'"
    },
    {
        "fieldname": "column_break_sub",
        "fieldtype": "Column Break"
    },
    {
        "fieldname": "substitute_weightage",
        "fieldtype": "Percent",
        "label": "Weightage (%)",
        "depends_on": "eval:doc.substitution_type"
    },
    {
        "fieldname": "substitute_effective_marks",
        "fieldtype": "Float",
        "label": "Effective Marks",
        "read_only": 1,
        "depends_on": "eval:doc.substitution_type"
    },
    {
        "fieldname": "substitute_assessment_effective_marks",
        "fieldtype": "Float",
        "label": "Substitute Assessment Effective Marks",
        "read_only": 1,
        "depends_on": "eval:doc.substitution_type"
    }
]

# Ensure we don't duplicate existing ones
fields_to_add = [f for f in new_fields if f['fieldname'] not in fieldnames]

# Insert at the end
fields.extend(fields_to_add)

doc['field_order'] = [f['fieldname'] for f in fields]

with open(path, 'w') as f:
    json.dump(doc, f, indent=1)

print("exam_schema_assessment.json patched with substitution fields.")
