import frappe
import json
from frappe import _dict
from frappe.utils import now_datetime, get_url_to_form


@frappe.whitelist(allow_guest=True)
def upload_entrance_test_result():
    """
    POST API endpoint to upload/store entrance test results.
    
    Expected JSON payload:
    {
        "applicant": "APP-001",
        "entrance_test_list": "ETL-001",
        "academic_year": "2025-2026",
        "admission_cycle": "AC-2025",
        "campus": "Main Campus",
        "program_level": "UG",
        "entrance_test_status": "Attended",
        "total_marks": 200,
        "part_a_total_marks_scored": 40,
        "part_a_all_india_rank": 1000,
        "part_b_total_marks_scored": 45,
        "part_b_all_india_rank": 500,
        "result_status": "Pass"
    }
    
    Returns:
    {
        "status": "success",
        "message": "Result uploaded successfully",
        "document_name": "APP-001",
        "details": {...}
    }
    """
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
                # keep existing context unless it needs updating
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
        
        # Save the document (before_save handles cumulative calculation)
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        
        # Return success response
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
        frappe.log_error(
            title="Entrance Test Result Upload - Validation Error",
            message=str(e)
        )
        return {
            "status": "error",
            "message": str(e),
            "error_type": "ValidationError"
        }
    
    except Exception as e:
        frappe.log_error(
            title="Entrance Test Result Upload - Error",
            message=str(e)
        )
        return {
            "status": "error",
            "message": f"An error occurred while uploading result: {str(e)}",
            "error_type": "ServerError"
        }


@frappe.whitelist(allow_guest=True)
def upload_bulk_entrance_test_results():
    """
    POST API endpoint to upload/store bulk entrance test results.
    
    Expected JSON payload:
    {
        "results": [
            {
                "applicant": "APP-001",
                "entrance_test_list": "ETL-001",
                "academic_year": "2025-2026",
                "admission_cycle": "AC-2025",
                "campus": "Main Campus",
                "program_level": "UG",
                "entrance_test_status": "Attended",
                "score_obtained": 85,
                "total_score": 100,
                "result_status": "Pass"
            },
            ...
        ]
    }
    
    Returns:
    {
        "status": "success",
        "message": "Bulk results uploaded",
        "total_records": 2,
        "successful": 2,
        "failed": 0,
        "results": [...]
    }
    """
    try:
        data = frappe.request.get_json()

        if not data:
            frappe.throw("No results provided in request body. Expected a JSON object or {'results': [...]}.")

        # allow either a wrapper object or a single record
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
        
        # Process each result
        responses = []
        successful_count = 0
        failed_count = 0
        
        for idx, result_data in enumerate(results_list, start=1):
            try:
                # Temporarily set the JSON data in frappe.request for processing
                frappe.request._cached_json = (result_data, None)
                
                # Call the single upload function
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
        
        # Return bulk upload response
        return {
            "status": "success" if failed_count == 0 else "partial",
            "message": f"Bulk upload completed. {successful_count} successful, {failed_count} failed",
            "total_records": len(results_list),
            "successful": successful_count,
            "failed": failed_count,
            "results": responses
        }
    
    except Exception as e:
        frappe.log_error(
            title="Bulk Entrance Test Result Upload - Error",
            message=str(e)
        )
        return {
            "status": "error",
            "message": f"Bulk upload failed: {str(e)}",
            "error_type": "ServerError"
        }


@frappe.whitelist(allow_guest=True)
def get_result_by_applicant(applicant):
    """
    GET API endpoint to retrieve entrance test result for a specific applicant.
    
    Args:
        applicant: Applicant ID (e.g., APP-001)
    
    Returns:
    {
        "status": "success",
        "data": {
            "applicant": "APP-001",
            "entrance_test_status": "Attended",
            "score_obtained": 85,
            "total_score": 100,
            "result_status": "Pass",
            "entrance_test_rank": 1,
            ...
        }
    }
    """
    try:
        if not applicant:
            frappe.throw("Applicant ID is required")
        
        # Check if record exists
        if not frappe.db.exists("Entrance Test Seat Allocation", applicant):
            frappe.throw(f"No record found for applicant '{applicant}'")
        
        # Get the document
        doc = frappe.get_doc("Entrance Test Seat Allocation", applicant)
        
        # Return the data
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
    
    except Exception as e:
        frappe.log_error(
            title="Get Result - Error",
            message=str(e)
        )
        return {
            "status": "error",
            "message": str(e),
            "error_type": "ServerError"
        }
