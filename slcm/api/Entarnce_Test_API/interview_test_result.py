import frappe
import json
from frappe import _dict
from frappe.utils import now_datetime, get_url_to_form


@frappe.whitelist(allow_guest=True, methods=["POST"])
def upload_interview_result():
    """
    POST API endpoint to upload/store a single interview result.

    Minimal payload (only `applicant` and `interview_status` are required):
    {
        "applicant": "APP-2026-00002",
        "interview_status": "Attended",
        "interview_score": 78.5,
        "interview_result_status": "Pass"
    }

    Returns JSON with status and details.
    """
    try:
        data = frappe.request.get_json()
        if not data:
            frappe.throw("No data provided in request body")

        required = ["applicant", "interview_status"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            frappe.throw(f"Missing required fields: {', '.join(missing)}")

        applicant = data.get("applicant")
        interview_status = data.get("interview_status")
        interview_score = data.get("interview_score")
        interview_result_status = data.get("interview_result_status")

        if not frappe.db.exists("Interview Seat Allocation", applicant):
            frappe.throw(f"Interview Seat Allocation record for applicant '{applicant}' does not exist.")

        doc = frappe.get_doc("Interview Seat Allocation", applicant)

        # Optionally update context fields if provided
        for fld in ("interview_list", "academic_year", "admission_cycle", "campus", "program_level"):
            if fld in data and data.get(fld) and getattr(doc, fld, None) != data.get(fld):
                setattr(doc, fld, data.get(fld))

        valid_statuses = ["Scheduled", "Attended", "Absent", "Selected", "Rejected", "Withheld"]
        if interview_status not in valid_statuses:
            frappe.throw(f"Invalid interview_status. Allowed values: {', '.join(valid_statuses)}")

        doc.interview_status = interview_status

        # Apply score/result when attended
        if interview_status == "Attended":
            if interview_score is not None and interview_score != "":
                try:
                    doc.interview_score = float(interview_score)
                except Exception:
                    frappe.throw("interview_score must be a number")

            # If caller explicitly provided a result status, validate and use it.
            if interview_result_status:
                valid_result_statuses = ["Pass", "Fail", "Withheld", "Pending"]
                if interview_result_status not in valid_result_statuses:
                    frappe.throw(f"Invalid interview_result_status. Allowed: {', '.join(valid_result_statuses)}")
                doc.interview_result_status = interview_result_status
            else:
                # Auto-determine result status from score when possible.
                # Priority: payload `passing_score` -> Interview List field `passing_score` -> default 50
                passing_score = None
                if data.get("passing_score") is not None:
                    try:
                        passing_score = float(data.get("passing_score"))
                    except Exception:
                        passing_score = None

                if passing_score is None and getattr(doc, "interview_list", None):
                    try:
                        passing_score = frappe.db.get_value("Interview List", doc.interview_list, "passing_score")
                        if passing_score is not None:
                            passing_score = float(passing_score)
                    except Exception:
                        passing_score = None

                if passing_score is None:
                    passing_score = 50.0

                # If no score was provided, leave as Pending
                if doc.interview_score is None:
                    doc.interview_result_status = "Pending"
                else:
                    doc.interview_result_status = "Pass" if doc.interview_score >= passing_score else "Fail"

        elif interview_status == "Absent":
            doc.interview_result_status = "Pending"
            doc.interview_score = 0

        if interview_status in ["Attended", "Absent"]:
            doc.attendance_marked_on = now_datetime()

        doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": "success",
            "message": "Interview result uploaded successfully",
            "document_name": doc.name,
            "details": {
                "applicant": doc.applicant,
                "interview_status": doc.interview_status,
                "interview_score": doc.interview_score,
                "interview_result_status": doc.interview_result_status,
                "rank": doc.rank,
                "attendance_marked_on": str(doc.attendance_marked_on) if doc.attendance_marked_on else None,
                "form_url": get_url_to_form("Interview Seat Allocation", doc.name)
            }
        }

    except frappe.ValidationError as e:
        frappe.log_error(title="Interview Result Upload - Validation Error", message=str(e))
        return {"status": "error", "message": str(e), "error_type": "ValidationError"}
    except Exception as e:
        frappe.log_error(title="Interview Result Upload - Error", message=str(e))
        return {"status": "error", "message": f"An error occurred: {str(e)}", "error_type": "ServerError"}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def upload_bulk_interview_results():
    """
    POST endpoint to upload bulk interview results.

    Accepts either:
      - {"results": [ {..}, {..} ] }
      - a single object (it will be wrapped into a list)
    """
    try:
        data = frappe.request.get_json()
        if not data:
            frappe.throw("No results provided in request body. Expected object or {'results':[...]}.")

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
        success = 0
        failed = 0

        for idx, payload in enumerate(results_list, start=1):
            try:
                # set request json so single function can read it
                frappe.request._cached_json = (payload, None)
                resp = upload_interview_result()
                if resp.get("status") == "success":
                    success += 1
                else:
                    failed += 1
                resp["record_index"] = idx
                responses.append(resp)
            except Exception as e:
                failed += 1
                responses.append({"record_index": idx, "status": "error", "message": str(e), "applicant": payload.get("applicant")})

        return {"status": "success" if failed == 0 else "partial",
                "message": f"Bulk upload completed. {success} successful, {failed} failed",
                "total_records": len(results_list),
                "successful": success,
                "failed": failed,
                "results": responses}

    except Exception as e:
        frappe.log_error(title="Bulk Interview Upload - Error", message=str(e))
        return {"status": "error", "message": f"Bulk upload failed: {str(e)}", "error_type": "ServerError"}


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_interview_result_by_applicant(applicant):
    """
    GET endpoint to fetch Interview Seat Allocation for an applicant.
    """
    try:
        if not applicant:
            frappe.throw("Applicant ID is required")

        if not frappe.db.exists("Interview Seat Allocation", applicant):
            frappe.throw(f"No record found for applicant '{applicant}'")

        doc = frappe.get_doc("Interview Seat Allocation", applicant)
        return {"status": "success", "data": {
            "applicant": doc.applicant,
            "candidate_name": doc.candidate_name,
            "program": doc.program,
            "interview_list": doc.interview_list,
            "academic_year": doc.academic_year,
            "admission_cycle": doc.admission_cycle,
            "interview_status": doc.interview_status,
            "interview_score": doc.interview_score,
            "interview_result_status": doc.interview_result_status,
            "rank": doc.rank,
            "result_published": doc.result_published,
            "attendance_marked_on": str(doc.attendance_marked_on) if doc.attendance_marked_on else None
        }}

    except Exception as e:
        frappe.log_error(title="Get Interview Result - Error", message=str(e))
        return {"status": "error", "message": str(e), "error_type": "ServerError"}
