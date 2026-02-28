
import frappe
from frappe.model.document import Document
import json
from frappe import _

class AdmissionCycleProgram(Document):
    pass

@frappe.whitelist()
def save_categories(admission_cycle,
                    program,
                    total_seats,
                    status,
                    policy_document,
                    reservation_rows):

    if isinstance(reservation_rows, str):
        reservation_rows = json.loads(reservation_rows)

    doc = frappe.new_doc("Program Reservation Policy")

    doc.admission_cycle = admission_cycle
    doc.program = program
    doc.total_seats = total_seats
    doc.status = status
    doc.policy_document = policy_document

    doc.set("categories", [])

    for row in reservation_rows:
        doc.append("categories", {
            "reservation_quota": row.get("category"),
            "category_name": row.get("category_name"),
            "percentage": row.get("percentage"),
            "application_fee": row.get("application_fee"),
            "seats": row.get("allocated_seats"),
        })

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return doc.name


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