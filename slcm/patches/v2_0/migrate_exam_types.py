import frappe

def execute():
	# 1. Create Exam Type Config records for CLAT, NLSAT, PACE
	exam_types = ['CLAT', 'NLSAT', 'PACE']
	for et in exam_types:
		if not frappe.db.exists('Exam Type Config', et):
			doc = frappe.get_doc({
				'doctype': 'Exam Type Config',
				'exam_name': et,
				'exam_code': et,
				'exam_category': 'National',
				'score_import_method': 'CSV Upload'
			})
			doc.insert(ignore_permissions=True)
			
			# Add default score field for Rank if needed
			doc.append('score_fields', {
				'field_name': 'rank',
				'label': 'Rank',
				'field_type': 'Int'
			})
			doc.save(ignore_permissions=True)

	# 2. Map existing Admission Cycle workflow_type to exam_type
	if frappe.db.has_column('Admission Cycle', 'exam_type') and frappe.db.has_column('Admission Cycle', 'workflow_type'):
		frappe.db.sql("""
			UPDATE `tabAdmission Cycle` 
			SET exam_type = workflow_type 
			WHERE (exam_type IS NULL OR exam_type = '') 
			AND workflow_type IN ('CLAT', 'NLSAT', 'PACE')
		""")
