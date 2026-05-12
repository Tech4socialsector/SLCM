import frappe
import hashlib

def verify_checksum(file_url, stored_checksum):
    try:
        file_doc = frappe.get_doc("File", {"file_url": file_url})
        content = file_doc.get_content()
        if isinstance(content, str):
            content = content.encode("utf-8")
        computed = hashlib.sha256(content).hexdigest()
        return computed == stored_checksum
    except Exception as e:
        frappe.log_error(str(e), "Checksum Verification Error")
        return False

def lock_documents(applicant_name):
    docs = frappe.get_all(
        "Applicant Document",
        filters={"applicant": applicant_name, "is_locked": 0},
        fields=["name"]
    )
    for doc in docs:
        frappe.db.set_value(
            "Applicant Document", doc.name, "is_locked", 1
        )
    frappe.db.commit()

def get_required_documents(program, category):
    required = [
        "10th Certificate",
        "12th Certificate",
        "ID Proof",
        "Photo"
    ]
    if category in ["SC", "ST", "OBC", "EWS"]:
        required.append("Category Certificate")
    if category == "PwD":
        required.append("PwD Certificate")
    if "PhD" in (program or ""):
        required.append("Research Proposal")
    return required

def check_document_completeness(applicant_name):
    applicant = frappe.get_doc("Applicant", applicant_name)
    required = get_required_documents(
        applicant.program,
        applicant.whether_scstobc_ncl
    )
    uploaded = frappe.get_all(
        "Applicant Document",
        filters={"applicant": applicant_name},
        fields=["document_type"]
    )
    uploaded_types = [d.document_type for d in uploaded]
    missing = [r for r in required if r not in uploaded_types]
    return {
        "required": required,
        "uploaded": uploaded_types,
        "missing": missing,
        "is_complete": len(missing) == 0
    }