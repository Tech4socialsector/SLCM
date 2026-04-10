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
	verification.applicant_name = app.applicant_name or f"{app.get('first_name', '')} {app.get('last_name', '')}".strip() or app.name
	verification.overall_status = "Pending"

	meta = frappe.get_meta("PACE Application")

	# Collect all attach field names (excluding student photo)
	attach_fields = [
		field for field in meta.fields
		if field.fieldtype in ["Attach", "Attach Image"]
		and field.fieldname != "upload_student_photo"
	]

	if not attach_fields:
		frappe.throw(_("No document fields configured on PACE Application."))

	# Fetch file values directly from DB to avoid cache issues during on_submit
	field_names = [f.fieldname for f in attach_fields]
	db_values = frappe.db.get_value(
		"PACE Application", application, field_names, as_dict=True
	) or {}

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

	if doc.overall_status in ["Verified", "Returned for Correction"]:
		frappe.throw(_("Verification has already been finalized."))

	statuses = [d.status for d in doc.verification_items]

	if "Pending" in statuses:
		frappe.throw(_("All documents must be finalized (Verified, Rejected, or Returned for Correction) before finalizing."))

	app = frappe.get_doc("PACE Application", doc.application)

	if set(["Rejected", "Returned for Correction"]).intersection(statuses):
		doc.overall_status = "Returned for Correction"
		app.status = "Under Verification"
	elif all(s == "Verified" for s in statuses):
		doc.overall_status = "Verified"
		app.status = "Verified"
		# Create fee assignment based on programme and nationality
		from slcm.pace.utils import create_pace_fee_assignment
		create_pace_fee_assignment(app.name)
	else:
		frappe.throw(_("Invalid status combination in verification items."))

	doc.verified_by = frappe.session.user
	doc.verified_on = frappe.utils.now_datetime()

	doc.save()
	app.save()

	return {"status": doc.overall_status, "app_status": app.status}
