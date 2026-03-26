import json
import os

filepath = "/home/jenifar/slcm_v16/apps/slcm/slcm/slcm/doctype/foundations_for_a_legal_education/foundations_for_a_legal_education.json"
with open(filepath, 'r') as f:
    data = json.load(f)

for field in data.get('fields', []):
    if field.get('fieldname') == 'payment_status':
        field['options'] = "Unpaid\nPayment Initiated\nAuthorized\nCaptured\nPaid\nPayment Failed\nFailed\nRefunded\nPending\nCancelled"
        break

with open(filepath, 'w') as f:
    json.dump(data, f, indent=1)
print("Updated payment_status options successfully.")
