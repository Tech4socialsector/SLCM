import frappe
from frappe.utils import now
import hashlib

def log_audit_trail(doctype, name, action, field=None,
                    old_value=None, new_value=None, legal_relevance="General"):
    try:
        log = frappe.get_doc({
            "doctype": "Admission Audit Log",
            "reference_doctype": doctype,
            "reference_name": name,
            "action": action,
            "field_changed": field or "",
            "old_value": str(old_value) if old_value is not None else "",
            "new_value": str(new_value) if new_value is not None else "",
            "user": frappe.session.user,
            "timestamp": now(),
            "ip_address": frappe.local.request_ip
                if hasattr(frappe.local, "request_ip") else "",
            "legal_relevance": legal_relevance
        })
        log.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(str(e), "Audit Log Error")

def enforce_reservation_policy(cycle, campus, program):
    admission_year = frappe.db.get_value(
        "Admission Cycle", cycle, "admission_year"
    )
    policies = frappe.get_all("Reservation Policy", {
        "program": program,
        "academic_year": admission_year
    }, ["category", "mandated_percentage", "mandated_seats", "legal_reference"])
    return policies

def check_reservation_compliance(seat_matrix_name):
    matrix = frappe.get_doc("Campus Seat Matrix", seat_matrix_name)
    policies = enforce_reservation_policy(
        matrix.admission_cycle, matrix.campus, matrix.program
    )
    violations = []
    for policy in policies:
        actual = next(
            (r for r in matrix.reservation_breakdown
             if r.category == policy.category), None
        )
        if not actual:
            violations.append(
                f"Missing category: {policy.category}"
                f" (Ref: {policy.legal_reference})"
            )
        elif actual.total_seats < policy.mandated_seats:
            violations.append(
                f"{policy.category}: Required {policy.mandated_seats} seats, "
                f"found {actual.total_seats} "
                f"(Ref: {policy.legal_reference})"
            )
    return violations

def verify_document_integrity(applicant_name):
    documents = frappe.get_all("Applicant Document", {
        "applicant": applicant_name
    }, ["name", "file", "checksum", "document_type"])

    tampered = []
    for doc in documents:
        if doc.file and doc.checksum:
            try:
                file_doc = frappe.get_doc(
                    "File", {"file_url": doc.file}
                )
                content = file_doc.get_content()
                if isinstance(content, str):
                    content = content.encode("utf-8")
                computed = hashlib.sha256(content).hexdigest()
                if computed != doc.checksum:
                    tampered.append({
                        "document": doc.name,
                        "document_type": doc.document_type,
                        "status": "TAMPERED"
                    })
                    log_audit_trail(
                        "Applicant Document", doc.name,
                        "Modified", "file",
                        doc.checksum, computed, "Document"
                    )
            except Exception as e:
                frappe.log_error(str(e), "Document Integrity Check Error")
    return tampered

def get_rti_export(admission_cycle=None):
    filters = {}
    if admission_cycle:
        filters["reference_name"] = ["like", f"%{admission_cycle}%"]
    logs = frappe.get_all("Admission Audit Log",
        filters=filters,
        fields=["reference_doctype", "reference_name", "action",
               "field_changed", "old_value", "new_value",
               "user", "timestamp", "ip_address", "legal_relevance"],
        order_by="timestamp asc"
    )
    return logs

def block_enrollment_without_documents(applicant_name):
    from slcm.admission_managment.utils.documents import check_document_completeness
    result = check_document_completeness(applicant_name)
    if not result["is_complete"]:
        frappe.throw(
            f"Cannot confirm enrollment. Missing documents: "
            f"{', '.join(result['missing'])}",
            title="Documents Incomplete"
        )
    unverified = frappe.db.count("Applicant Document", {
        "applicant": applicant_name,
        "is_verified": 0
    })
    if unverified > 0:
        frappe.throw(
            f"Cannot confirm enrollment. {unverified} document(s) "
            f"are not yet verified by Admission Officer.",
            title="Verification Pending"
        )
    return True