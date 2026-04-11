import frappe

@frappe.whitelist()
def generate_document_verification(application):
	from frappe import _
	if not frappe.db.exists("PACE Application", application):
		frappe.throw(_("PACE Application {0} not found.").format(application))

	if frappe.db.exists("PACE Document Verification", {"application": application}):
		frappe.throw(_("Verification record already exists for application {0}.").format(application))

	app = frappe.get_doc("PACE Application", application)

	verification = frappe.new_doc("PACE Document Verification")
	verification.application = app.name
	
	# Ensure applicant_name is never empty to avoid DocType validation errors
	applicant_name = app.applicant_name
	if not applicant_name:
		name_parts = [app.get("first_name"), app.get("middle_name"), app.get("last_name")]
		applicant_name = " ".join([p for p in name_parts if p]).strip()
	
	verification.applicant_name = applicant_name or app.name
	verification.overall_status = "Pending"

	meta = frappe.get_meta("PACE Application")

	# Collect all attach field names (excluding student photo)
	attach_fields = [
		field for field in meta.fields
		if field.fieldtype in ["Attach", "Attach Image"]
		and field.fieldname not in ["upload_student_photo", "application_form"]
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
	return verification.name

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

	if "Rejected" in statuses or "Returned for Correction" in statuses:
		doc.overall_status = "Returned for Correction"
		app.status = "Returned for Correction"
		# Convert all Rejected items to Returned for Correction for the applicant to see/fix
		for row in doc.verification_items:
			if row.status == "Rejected":
				row.status = "Returned for Correction"
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

	doc.save(ignore_permissions=True)
	app.save(ignore_permissions=True)

	return {"status": doc.overall_status, "app_status": app.status}
