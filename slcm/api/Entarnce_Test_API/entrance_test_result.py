import frappe
import json
from frappe import _, _dict
from frappe.utils import now_datetime, get_url_to_form


def check_exam_cell_permission():
	"""Ensures the caller is logged in and has an administrative / Exam Cell role."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	user_roles = frappe.get_roles(user)
	allowed_roles = ["Exam Cell", "System Manager", "Entrance Test Admin", "Administrator"]
	if not any(role in user_roles for role in allowed_roles) and user != "Administrator":
		frappe.throw(_("Not permitted"), frappe.PermissionError)


@frappe.whitelist()
def upload_entrance_test_result():
	"""
	POST API endpoint to upload/store entrance test results.
	Requires an authenticated user with Exam Cell / Admin role.
	"""
	check_exam_cell_permission()

	try:
		# Get JSON data from request
		data = frappe.request.get_json()

		if not data:
			frappe.throw("No data provided in request body")

		# only applicant and status are required; other fields may be used for
		# additional validation or updates if supplied.
		required_fields = ["applicant", "entrance_test_status"]

		missing = [f for f in required_fields if not data.get(f)]
		if missing:
			frappe.throw(f"Missing required fields: {', '.join(missing)}")

		applicant = data.get("applicant")
		entrance_test_status = data.get("entrance_test_status")

		total_marks = data.get("total_marks")
		part_a_score = data.get("part_a_total_marks_scored")
		part_a_rank = data.get("part_a_all_india_rank")
		part_b_score = data.get("part_b_total_marks_scored")
		part_b_rank = data.get("part_b_all_india_rank")

		result_status = data.get("result_status")

		# look up the existing allocation record
		if not frappe.db.exists("Entrance Test Seat Allocation", applicant):
			frappe.throw(
				f"Entrance Test Seat Allocation record for applicant '{applicant}' does not exist."
			)
		doc = frappe.get_doc("Entrance Test Seat Allocation", applicant)

		# if the caller has supplied context fields, we can optionally verify or update them
		for fld in ("entrance_test_list", "academic_year", "admission_cycle", "campus", "program_level"):
			if fld in data and data.get(fld) and getattr(doc, fld, None) != data.get(fld):
				setattr(doc, fld, data.get(fld))

		# validate status
		valid_statuses = ["Attended", "Absent", "Rescheduled", "Not Scheduled", "Scheduled"]
		if entrance_test_status not in valid_statuses:
			frappe.throw(f"Invalid entrance_test_status. Allowed values: {', '.join(valid_statuses)}")
		doc.entrance_test_status = entrance_test_status

		# status-specific updates
		if entrance_test_status == "Attended":
			if total_marks is not None:
				doc.total_marks = int(total_marks)
			if part_a_score is not None:
				doc.part_a_total_marks_scored = float(part_a_score)
			if part_a_rank is not None:
				doc.part_a_all_india_rank = int(part_a_rank)
			if part_b_score is not None:
				doc.part_b_total_marks_scored = float(part_b_score)
			if part_b_rank is not None:
				doc.part_b_all_india_rank = int(part_b_rank)

			if result_status:
				valid_result_statuses = ["Pass", "Fail", "Absent", "Withheld", "Disqualified"]
				if result_status not in valid_result_statuses:
					frappe.throw(f"Invalid result_status. Allowed values: {', '.join(valid_result_statuses)}")
				doc.result_status = result_status
		elif entrance_test_status == "Absent":
			doc.result_status = "Absent"
			doc.part_a_total_marks_scored = 0
			doc.part_b_total_marks_scored = 0
			doc.part_a_all_india_rank = 0
			doc.part_b_all_india_rank = 0
			doc.entrance_test_rank = 0
			doc.percentile = 0.0

		if entrance_test_status in ["Attended", "Absent"]:
			doc.attendance_marked_on = now_datetime()

		# Save the document
		doc.save(ignore_permissions=True)
		frappe.db.commit()

		return {
			"status": "success",
			"message": "Entrance test result uploaded successfully",
			"document_name": doc.name,
			"details": {
				"applicant": doc.applicant,
				"entrance_test_status": doc.entrance_test_status,
				"part_a_total_marks_scored": doc.part_a_total_marks_scored,
				"part_a_all_india_rank": doc.part_a_all_india_rank,
				"part_b_total_marks_scored": doc.part_b_total_marks_scored,
				"part_b_all_india_rank": doc.part_b_all_india_rank,
				"total_marks_secured_in_part_a_b": doc.total_marks_secured_in_part_a_b,
				"percentage": doc.percentage,
				"percentile": doc.percentile,
				"result_status": doc.result_status,
				"entrance_test_rank": doc.entrance_test_rank,
				"attendance_marked_on": str(doc.attendance_marked_on) if doc.attendance_marked_on else None,
				"form_url": get_url_to_form("Entrance Test Seat Allocation", doc.name)
			}
		}

	except frappe.ValidationError as e:
		frappe.log_error(title="Entrance Test Result Upload - Validation Error", message=str(e))
		return {"status": "error", "message": str(e), "error_type": "ValidationError"}

	except Exception as e:
		frappe.log_error(title="Entrance Test Result Upload - Error", message=str(e))
		return {"status": "error", "message": f"An error occurred while uploading result: {str(e)}", "error_type": "ServerError"}


@frappe.whitelist()
def upload_bulk_entrance_test_results():
	"""
	POST API endpoint to upload/store bulk entrance test results.
	Requires an authenticated user with Exam Cell / Admin role.
	"""
	check_exam_cell_permission()

	try:
		data = frappe.request.get_json()

		if not data:
			frappe.throw("No results provided in request body. Expected a JSON object or {'results': [...]}.")

		if isinstance(data, dict) and "results" in data:
			results_list = data.get("results") or []
		elif isinstance(data, dict):
			results_list = [data]
		else:
			frappe.throw("Unexpected payload format. Provide an object or {'results':[...]}.")

		if not isinstance(results_list, list):
			frappe.throw("Results must be a list of objects")

		if len(results_list) == 0:
			frappe.throw("Results list cannot be empty")

		responses = []
		successful_count = 0
		failed_count = 0

		for idx, result_data in enumerate(results_list, start=1):
			try:
				frappe.request._cached_json = (result_data, None)
				response = upload_entrance_test_result()

				if response.get("status") == "success":
					successful_count += 1
				else:
					failed_count += 1

				response["record_index"] = idx
				responses.append(response)

			except Exception as e:
				failed_count += 1
				responses.append({
					"record_index": idx,
					"status": "error",
					"message": str(e),
					"applicant": result_data.get("applicant", "Unknown")
				})

		return {
			"status": "success" if failed_count == 0 else "partial",
			"message": f"Bulk upload completed. {successful_count} successful, {failed_count} failed",
			"total_records": len(results_list),
			"successful": successful_count,
			"failed": failed_count,
			"results": responses
		}

	except Exception as e:
		frappe.log_error(title="Bulk Entrance Test Result Upload - Error", message=str(e))
		return {
			"status": "error",
			"message": f"Bulk upload failed: {str(e)}",
			"error_type": "ServerError"
		}


@frappe.whitelist()
def get_result_by_applicant(applicant):
	"""
	GET API endpoint to retrieve entrance test result for a specific applicant.
	Requires authentication and ownership or Exam Cell / Admin role.
	"""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	try:
		if not applicant:
			frappe.throw("Applicant ID is required")

		if not frappe.db.exists("Entrance Test Seat Allocation", applicant):
			frappe.throw(f"No record found for applicant '{applicant}'")

		# Security check: Ownership or Staff Role
		user_roles = frappe.get_roles(user)
		is_staff = any(role in user_roles for role in ["Exam Cell", "System Manager", "Entrance Test Admin", "Administrator"]) or user == "Administrator"

		if not is_staff:
			alloc_email = frappe.db.get_value("Entrance Test Seat Allocation", applicant, "email")
			app_email = frappe.db.get_value("Applicant", {"name": applicant}, "email")
			if not (alloc_email and alloc_email.strip().lower() == user.strip().lower()) and not (app_email and app_email.strip().lower() == user.strip().lower()):
				frappe.throw(_("Not permitted"), frappe.PermissionError)

		doc = frappe.get_doc("Entrance Test Seat Allocation", applicant)

		return {
			"status": "success",
			"data": {
				"applicant": doc.applicant,
				"candidate_name": doc.candidate_name,
				"program": doc.program,
				"entrance_test_list": doc.entrance_test_list,
				"academic_year": doc.academic_year,
				"admission_cycle": doc.admission_cycle,
				"entrance_test_status": doc.entrance_test_status,
				"part_a_total_marks_scored": doc.part_a_total_marks_scored,
				"part_a_all_india_rank": doc.part_a_all_india_rank,
				"part_b_total_marks_scored": doc.part_b_total_marks_scored,
				"part_b_all_india_rank": doc.part_b_all_india_rank,
				"total_marks_secured_in_part_a_b": doc.total_marks_secured_in_part_a_b,
				"percentage": doc.percentage,
				"percentile": doc.percentile,
				"result_status": doc.result_status,
				"entrance_test_rank": doc.entrance_test_rank,
				"result_published": doc.result_published,
				"attendance_marked_on": str(doc.attendance_marked_on) if doc.attendance_marked_on else None
			}
		}

	except frappe.PermissionError:
		raise

	except Exception as e:
		frappe.log_error(title="Get Result - Error", message=str(e))
		return {
			"status": "error",
			"message": str(e),
			"error_type": "ServerError"
		}
