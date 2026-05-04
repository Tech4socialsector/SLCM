# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import json
import frappe


# ── Helpers ──────────────────────────────────────────────────────────────────────

def _get_attach_fieldnames():
    """Return the set of Attach/Attach Image fieldnames from the doctype meta."""
    try:
        meta = frappe.get_meta("Transcript Template")
        return {f.fieldname for f in meta.fields if f.fieldtype in ("Attach", "Attach Image")}
    except Exception:
        return set()


def _sanitise_data(data, attach_fields):
    """
    Strip keys that are not valid doctype fields (prevents mass-assignment of
    internal Frappe fields). Also validates Attach Image values: they must be
    proper URL paths or empty — never base64 data URIs.
    """
    # Keys that must never come from the client
    BLOCKED = {"doctype", "docstatus", "owner", "creation", "__islocal", "__unsaved"}

    cleaned = {}
    for k, v in data.items():
        if k in BLOCKED:
            continue
        # Attach/Image fields: reject base64 data URIs — they break Frappe's file system
        if k in attach_fields and isinstance(v, str) and v.startswith("data:"):
            frappe.throw(
                frappe._(
                    "Field '{0}' contains a raw base64 image. "
                    "Please use the Upload button to upload the file via Frappe's "
                    "file manager before saving."
                ).format(k)
            )
        cleaned[k] = v

    return cleaned


# ── Public API ────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_templates(search=""):
    """Return all Transcript Templates for the list view."""
    or_filters = None
    if search:
        or_filters = {
            "template_name": ("like", f"%{search}%"),
            "template_type": ("like", f"%{search}%"),
        }

    templates = frappe.get_all(
        "Transcript Template",
        fields=[
            "name", "template_name", "template_type",
            "page_size", "orientation", "is_default",
            "institute_logo", "institute_name",
            "modified", "modified_by",
        ],
        or_filters=or_filters,
        order_by="is_default desc, modified desc",
        limit=200,
    )
    return {"templates": templates}


@frappe.whitelist()
def get_template(name):
    """Return the full data dict for a single Transcript Template."""
    if not frappe.db.exists("Transcript Template", name):
        frappe.throw(frappe._("Template '{0}' not found.").format(name))

    doc = frappe.get_doc("Transcript Template", name)
    return doc.as_dict()


@frappe.whitelist()
def save_template(data):
    """
    Create or update a Transcript Template document.

    ``data`` is a JSON string (or already-parsed dict) that may contain any
    subset of the doctype fields. Unknown/blocked fields are stripped before
    saving. Attach Image values must be server-side URLs — base64 data URIs are
    rejected with a clear error message.
    """
    if isinstance(data, str):
        data = json.loads(data)

    if not isinstance(data, dict):
        frappe.throw(frappe._("Invalid data format."))

    attach_fields = _get_attach_fieldnames()
    data          = _sanitise_data(data, attach_fields)

    template_name = (data.get("template_name") or "").strip()
    if not template_name:
        frappe.throw(frappe._("Template Name is required."))

    # Determine the document name — could differ from template_name if renamed
    doc_name = data.get("name") or template_name

    if frappe.db.exists("Transcript Template", doc_name):
        doc = frappe.get_doc("Transcript Template", doc_name)
        doc.update(data)
        doc.save(ignore_permissions=False)
    else:
        doc = frappe.new_doc("Transcript Template")
        doc.update(data)
        doc.insert(ignore_permissions=False)

    frappe.db.commit()
    return doc.as_dict()


@frappe.whitelist()
def delete_template(name):
    """Delete a Custom Transcript Template. System templates cannot be deleted."""
    if not frappe.db.exists("Transcript Template", name):
        frappe.throw(frappe._("Template '{0}' not found.").format(name))

    ttype = frappe.db.get_value("Transcript Template", name, "template_type")
    if ttype == "System":
        frappe.throw(frappe._("System templates cannot be deleted."))

    frappe.delete_doc("Transcript Template", name, ignore_permissions=False)
    frappe.db.commit()
    return {"success": True}


@frappe.whitelist()
def set_default(name):
    """Mark one template as the default; removes the flag from all others."""
    if not frappe.db.exists("Transcript Template", name):
        frappe.throw(frappe._("Template '{0}' not found.").format(name))

    # Clear existing default across all records
    frappe.db.sql(
        "UPDATE `tabTranscript Template` SET is_default = 0 WHERE is_default = 1"
    )
    frappe.db.set_value("Transcript Template", name, "is_default", 1)
    frappe.db.commit()
    return {"success": True, "default": name}


@frappe.whitelist()
def seed_default_templates():
    """
    Insert the built-in System template on first run.
    Safe to call multiple times (idempotent — only inserts when missing).
    """
    defaults = [
        {
            "template_name":          "Default Transcript Template",
            "template_type":          "System",
            "page_size":              "A4",
            "orientation":            "Portrait",
            "is_default":             1,
            "show_institute_logo":    1,
            "logo_alignment":         "Center",
            "logo_width":             120,
            "show_institute_address": 1,
            "header_title":           "OFFICIAL TRANSCRIPT OF ACADEMIC RECORDS",
            "show_student_photo":     1,
            "show_registration_id":   1,
            "show_cgpa":              1,
            "show_credits":           1,
            "show_semester_wise":     1,
            "show_watermark":         0,
            "watermark_opacity":      15,
        },
    ]

    created = []
    for tmpl in defaults:
        if not frappe.db.exists("Transcript Template", tmpl["template_name"]):
            try:
                doc = frappe.new_doc("Transcript Template")
                doc.update(tmpl)
                doc.insert(ignore_permissions=True)
                created.append(tmpl["template_name"])
            except Exception as exc:
                frappe.log_error(frappe.get_traceback(), f"Transcript seed failed: {tmpl['template_name']}")

    if created:
        frappe.db.commit()

    return {"seeded": created}
