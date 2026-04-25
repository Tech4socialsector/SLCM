import frappe
from slcm.pace.assignment_logic import assign_verifier_round_robin

@frappe.whitelist()
def generate_document_verification(application):
	from frappe import _
	if not frappe.db.exists("PACE Application", application):
		frappe.throw(_("PACE Application {0} not found.").format(application))

	existing = frappe.db.exists("PACE Document Verification", {"application": application})
	verification_name = existing

	app = frappe.get_doc("PACE Application", application)

	if not existing:
		verification = frappe.new_doc("PACE Document Verification")
		verification.application = app.name
		
		# Ensure applicant_name is never empty to avoid DocType validation errors
		applicant_name = app.applicant_name
		if not applicant_name:
			name_parts = [app.get("first_name"), app.get("middle_name"), app.get("last_name")]
			applicant_name = " ".join([p for p in name_parts if p]).strip()
		
		verification.applicant_name = applicant_name or app.name
		verification.overall_status = "Pending"
		verification.programme = app.programme

		meta = frappe.get_meta("PACE Application")

		# Define the specific fields to be verified
		verify_fieldnames = [
			"student_signature",
			"ug_degree_certificate",
			"govt_id",
		]

		# Collect only the requested attach fields
		attach_fields = [
			field for field in meta.fields
			if field.fieldname in verify_fieldnames
		]

		if not attach_fields:
			frappe.throw(_("No document fields configured on PACE Application."))

		# Fetch file values directly from DB to avoid cache issues during on_submit
		field_names = [f.fieldname for f in attach_fields] + ["academic_year"]
		db_values = frappe.db.get_value(
			"PACE Application", application, field_names, as_dict=True
		) or {}

		if db_values.get("academic_year"):
			verification.academic_year = db_values.get("academic_year")

		for field in attach_fields:
			file_value = db_values.get(field.fieldname)
			if file_value:
				verification.append("verification_items", {
					"document_name": field.label,
					"fieldname": field.fieldname,
					"file": file_value,
					"status": "Pending"
				})

		if not verification.verification_items:
			frappe.throw(_("No documents found to verify in application {0}.").format(application))

		verification.insert(ignore_permissions=True)
		verification_name = verification.name
	
	# Handle assignment logic for both new and existing records
	# We reload the doc if it was just inserted to ensure we have the object
	doc = frappe.get_doc("PACE Document Verification", verification_name)
	
	if not doc.assigned_verifier:
		assign_verifier_round_robin(doc)
		doc.save(ignore_permissions=True)

	# Handle ToDo and Sharing for the assigned verifier
	assigned_verifier = doc.assigned_verifier
	if assigned_verifier:
		# Check if ToDo already exists for this verifier
		if not frappe.db.exists("ToDo", {
			"reference_type": "PACE Document Verification",
			"reference_name": verification_name,
			"status": "Open",
			"allocated_to": assigned_verifier
		}):
			# Create new ToDo assignment
			frappe.get_doc({
				"doctype": "ToDo",
				"allocated_to": assigned_verifier,
				"reference_type": "PACE Document Verification",
				"reference_name": verification_name,
				"description": _("Assigned for Document Verification"),
				"status": "Open",
				"priority": "Medium"
			}).insert(ignore_permissions=True)

			# Share the record with the verifier silently
			from frappe.share import add as share_add
			share_add("PACE Document Verification", verification_name, assigned_verifier, read=1, notify=0)


	return verification_name

@frappe.whitelist()
def finalize_verification(docname):
	from frappe import _
	doc = frappe.get_doc("PACE Document Verification", docname)

	if doc.overall_status in ["Verified", "Returned for Correction"] and False: # Allow re-finalizing if needed during re-upload?
		# Actually, user's prompt says "Admin clearly sees updated documents. Re-verification is triggered."
		# So finalize needs to be callable again if items are Pending.
		pass

	statuses = [d.status for d in doc.verification_items]

	if "Pending" in statuses:
		frappe.throw(_("All documents must be verified (set to Verified or Rejected) before finalizing."))

	# Remarks validation for rejected items
	for row in doc.verification_items:
		if row.status == "Rejected" and not row.remarks:
			frappe.throw(_("Remarks are required for rejected document: {0}").format(row.document_name))

	app = frappe.get_doc("PACE Application", doc.application)

	if "Rejected" in statuses:
		doc.overall_status = "Rejected"
		app.status = "Rejected"
	elif "Returned for Correction" in statuses:
		doc.overall_status = "Returned for Correction"
		app.status = "Returned for Correction"
	elif all(s == "Verified" for s in statuses):
		doc.overall_status = "Verified"
		app.status = "Verified"
		
		# Create fee assignment based on programme and nationality
		# Only if not already created (check if create_pace_fee_assignment is idempotent or has checks)
		from slcm.pace.utils import create_pace_fee_assignment
		create_pace_fee_assignment(app.name)

	# Update verification metadata and clear re-upload flags
	doc.has_reuploaded_items = 0
	for row in doc.verification_items:
		if row.status == "Verified":
			row.is_reuploaded = 0
		
		row.verified_by = frappe.session.user
		row.verified_on = frappe.utils.now_datetime()

	doc.verified_by = frappe.session.user
	doc.verified_on = frappe.utils.now_datetime()

	# Set flag to ensure on_update sends the email even if status didn't change
	doc.flags.force_notification = True
	doc.save(ignore_permissions=True)
	app.save(ignore_permissions=True)

	return {"status": doc.overall_status, "app_status": app.status}
