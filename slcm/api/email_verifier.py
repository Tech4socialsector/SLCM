import frappe
import requests
from frappe import _

@frappe.whitelist(allow_guest=True)
def verify_email(email):
    """
    Verifies an email address using Hunter.io API.
    Returns a structured response to the frontend.
    """
    if not email:
        return {"success": False, "error": "missing_email"}

    api_key = frappe.conf.get("hunter_api_key")
    if not api_key:
        frappe.log_error("Hunter API key not found in site_config.json", "Email Verification Error")
        return {"success": False, "error": "invalid_api_key"}

    url = "https://api.hunter.io/v2/email-verifier"
    params = {"email": email, "api_key": api_key}

    # Retry logic for transient errors (timeouts or 5xx)
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, params=params, timeout=10)
            status_code = response.status_code
            
            try:
                data = response.json()
            except ValueError:
                data = {}

            if status_code == 200:
                result = data.get("data", {})
                return {
                    "success": True,
                    "status": result.get("status"),
                    "score": result.get("score")
                }
            
            # Handle Hunter API Errors
            errors = data.get("errors", [])
            error_data = errors[0] if errors else {}
            
            if status_code == 401:
                frappe.log_error(f"Hunter API Unauthorized: {data}", "Email Verification Error")
                return {"success": False, "error": "invalid_api_key"}
            
            if status_code in [403, 429]:
                return {"success": False, "error": "rate_limit"}

            if status_code == 400 or status_code == 422:
                # Often occurs if the email format is rejected by Hunter before verification
                return {"success": True, "status": "invalid"}

            if status_code >= 500:
                if attempt < max_retries: continue # Retry
                return {"success": False, "error": "service_unavailable"}

            # Log other unexpected 4xx errors
            frappe.log_error(f"Hunter API Error {status_code}: {data}", "Email Verification Error")
            return {"success": False, "error": "unknown_error", "details": error_data.get("details")}

        except requests.exceptions.Timeout:
            if attempt < max_retries: continue # Retry
            return {"success": False, "error": "timeout"}
        except requests.exceptions.RequestException as e:
            if attempt < max_retries: continue # Retry
            frappe.log_error(f"Hunter API Request Exception: {str(e)}", "Email Verification Error")
            return {"success": False, "error": "service_unavailable"}
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Email Verification Error")
            return {"success": False, "error": "internal_error"}
