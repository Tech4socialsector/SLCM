import frappe
import base64
import os

def get_file_b64(file_url):
    """
    Returns base64 encoded string of a file.
    Used in Jinja templates for PDF generation to avoid external HTTP requests.
    """
    if not file_url:
        return ""
    
    try:
        # If it's already a data URI, just return the base64 part
        if file_url.startswith("data:") and ";base64," in file_url:
            return file_url.split(";base64,")[1]

        # Resolve local path if it starts with /files or /private/files
        if file_url.startswith("/files/") or file_url.startswith("/private/files/"):
            path = frappe.get_site_path("public" if file_url.startswith("/files/") else "", file_url.lstrip("/"))
            if os.path.exists(path):
                with open(path, "rb") as f:
                    return base64.b64encode(f.read()).decode()

        # Fallback: Try to get via File DocType
        file_doc = frappe.get_doc("File", {"file_url": file_url})
        if file_doc:
            return base64.b64encode(file_doc.get_content()).decode()
            
    except Exception:
        # Log error only if it's not a simple missing file
        # frappe.log_error(f"get_file_b64 failed for {file_url}", "Jinja Utils")
        pass
        
    return ""
