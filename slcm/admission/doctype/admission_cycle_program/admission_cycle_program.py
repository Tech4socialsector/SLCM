
import frappe
from frappe.model.document import Document
import json
from frappe import _

class AdmissionCycleProgram(Document):
    pass

@frappe.whitelist()
def save_categories(admission_cycle, program, total_seats, status, policy_document, reservation_rows, existing_policy=None, payment_gateway=None, payment_receipt_template=None):
    if isinstance(reservation_rows, str):
        reservation_rows = json.loads(reservation_rows)

    # If existing_policy is provided, this is an UPDATE — skip duplicate check
    if existing_policy:
        if not frappe.db.exists("Program Reservation Policy", existing_policy):
            frappe.throw(_("Reservation Policy {0} not found.").format(existing_policy))
        doc = frappe.get_doc("Program Reservation Policy", existing_policy)
    else:
        # NEW record — check for duplicates
        existing = frappe.db.get_value(
            "Program Reservation Policy",
            {"admission_cycle": admission_cycle, "program": program},
            "name"
        )
        if existing:
            frappe.throw(
                _("A reservation policy already exists for {0} in Cycle {1}. Only one policy per program per cycle is allowed.").format(program, admission_cycle)
            )
        doc = frappe.new_doc("Program Reservation Policy")
        doc.admission_cycle = admission_cycle
        doc.program = program

    doc.total_seats = total_seats
    doc.status = status
    doc.policy_document = policy_document or ""
    doc.payment_gateway = payment_gateway
    doc.payment_receipt_template = payment_receipt_template

    # Clear and re-add category rows
    doc.set("categories", [])

    for r in reservation_rows:
        doc.append("categories", {
            "reservation_quota": r.get("category"),
            "category_name": r.get("category_name"),
            "priority": r.get("priority"),
            "percentage": r.get("percentage"),
            "seats": r.get("allocated_seats"),
            "application_fee": r.get("application_fee")
        })

    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)

    frappe.db.commit()
    
    # Get updated modified timestamp of the parent Admission Cycle
    new_modified = frappe.db.get_value("Admission Cycle", admission_cycle, "modified")
    
    return {
        "policy_name": doc.name,
        "new_modified": new_modified
    }

@frappe.whitelist()
def save_program_media(program, active, brochure_pdf, media_rows, parent_doctype, parent_name):
    """
    Save or update Program Media for a given Program.

    - Doc name is always set to the Program name.
    - If a Program Media doc with name == program already exists, it is updated.
    - If not, a new doc is created with name = program.
    """
    if isinstance(media_rows, str):
        media_rows = json.loads(media_rows)

    active = int(active) if active else 0

    # Check if Program Media doc already exists with name = program
    if frappe.db.exists("Program Media", program):
        doc = frappe.get_doc("Program Media", program)
    else:
        doc = frappe.new_doc("Program Media")
        doc.name = program          # Set doc name = program name
        doc.program = program

    doc.is_active = active
    doc.brochure_pdf = brochure_pdf or ""

    # Clear and re-add child rows
    doc.set("media_gallery", [])

    for row in media_rows:
        if not row.get("media_type") or not row.get("file_url"):
            frappe.throw(_("Media Type and File are mandatory for all rows."))

        doc.append("media_gallery", {
            "media_type": row.get("media_type"),
            "file": row.get("file_url"),
            "sequence": int(row.get("sequence") or 1),
            "caption": row.get("caption") or ""
        })

    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)

    frappe.db.commit()

    return doc.name