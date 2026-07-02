# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.utils import cint

# Reuse the existing dashboard access check instead of duplicating it.
from slcm.slcm.page.slcm_analytics_dashboard.slcm_analytics_dashboard import (
    _require_dashboard_access,
)

# Number Card is a standard Frappe doctype: every card — whether hardcoded or
# added by an admin via the Workspace UI — already stores `document_type` and
# `filters_json`. Reading those live means this page needs zero per-card code:
# it works for any card that exists today or that an admin creates tomorrow.

MAX_LIST_COLUMNS = 8


def _pick_display_columns(doctype):
    """Choose a sensible set of columns for a doctype with no hand-authored mapping.

    Prefers the doctype's own list-view settings (`in_list_view` fields), falling
    back to the title/search fields, so any doctype renders a reasonable table
    without a hardcoded per-doctype column list.
    """
    meta = frappe.get_meta(doctype)

    columns = [df.fieldname for df in meta.fields if df.in_list_view and df.fieldtype not in
               ("Section Break", "Column Break", "Tab Break", "HTML", "Button")]

    if not columns:
        candidates = [meta.title_field, *(meta.search_fields or "").split(","), meta.get("subject_field")]
        columns = [c.strip() for c in candidates if c and meta.has_field(c.strip())]

    # "name" is always implicitly available and is what we link on — keep it first.
    columns = [c for c in dict.fromkeys(columns) if c != "name"]
    return columns[:MAX_LIST_COLUMNS]


@frappe.whitelist()
def get_card_meta(number_card, filters=None):
    """Resolve a Number Card into what the generic drilldown page needs to render:
    the target doctype, display columns, and title — all read live off the card
    (and, for workspace cards, the same filter-merge logic used to compute its value).
    """
    _require_dashboard_access()

    if not frappe.db.exists("Number Card", number_card):
        frappe.throw(f"Number Card {number_card!r} not found")

    card_doc = frappe.get_doc("Number Card", number_card)
    if not card_doc.document_type:
        frappe.throw(f"Number Card {number_card!r} has no document_type to drill into")

    if not frappe.has_permission(card_doc.document_type, "read"):
        frappe.throw("Not permitted", frappe.PermissionError)

    return {
        "document_type": card_doc.document_type,
        "label": card_doc.label,
        "columns": _pick_display_columns(card_doc.document_type),
        "title_field": frappe.get_meta(card_doc.document_type).title_field or "name",
    }


FILTERABLE_FIELDTYPES = ("Select", "Link", "Check")
MAX_FILTER_FIELDS = 4
MAX_LINK_OPTIONS = 200


def _pick_filterable_fields(document_type):
    """Choose a small set of Select/Link fields worth exposing as extra filters.

    Mirrors what Frappe's own List View sidebar offers — no hardcoded per-doctype
    list — so any doctype gets sensible ad-hoc filters without bespoke code.
    Prefers fields already shown as columns (most relevant to what the user sees),
    then fills in with any other in-standard-filter fields on the doctype.
    """
    meta = frappe.get_meta(document_type)
    display_columns = _pick_display_columns(document_type)

    def is_candidate(df):
        return (
            df.fieldtype in FILTERABLE_FIELDTYPES
            and df.fieldname not in ("name",)
            and not df.get("hidden")
        )

    candidates = [df for df in meta.fields if is_candidate(df)]
    # Column fields first (most relevant to the visible table), then the rest.
    candidates.sort(key=lambda df: 0 if df.fieldname in display_columns else 1)

    fields = []
    for df in candidates:
        if len(fields) >= MAX_FILTER_FIELDS:
            break
        entry = {
            "fieldname": df.fieldname,
            "label": df.label or df.fieldname,
            "fieldtype": df.fieldtype,
        }
        if df.fieldtype == "Select":
            entry["options"] = [{"value": o, "label": o} for o in (df.options or "").split("\n") if o]
        elif df.fieldtype == "Link":
            entry["doctype"] = df.options
            entry["options"] = []
            if df.options and frappe.db.exists("DocType", df.options):
                link_meta = frappe.get_meta(df.options)
                title_field = link_meta.title_field if link_meta.title_field and link_meta.has_field(link_meta.title_field) else None
                link_fetch_fields = ["name"] + ([title_field] if title_field else [])
                linked = frappe.get_list(
                    df.options,
                    fields=link_fetch_fields,
                    limit_page_length=MAX_LINK_OPTIONS,
                    order_by="modified desc",
                )
                entry["options"] = [
                    {"value": row["name"], "label": row.get(title_field) or row["name"]}
                    for row in linked
                ] if title_field else [{"value": row["name"], "label": row["name"]} for row in linked]
        fields.append(entry)

    return fields


@frappe.whitelist()
def get_filterable_fields(document_type):
    """Generic ad-hoc filter definitions for the drilldown page's filter bar."""
    _require_dashboard_access()
    if not frappe.has_permission(document_type, "read"):
        frappe.throw("Not permitted", frappe.PermissionError)
    return {"fields": _pick_filterable_fields(document_type)}


@frappe.whitelist()
def get_records(document_type, filters=None, columns=None, search=None, page=1, page_size=25):
    """Generic, doctype-agnostic paginated record fetch for the drilldown page.

    `filters` here are the ALREADY-RESOLVED filters (Number Card's filters_json
    merged with the dashboard's active filters) — computed server-side once by
    `get_workspace_dashboard_details` and handed back to the frontend verbatim,
    so this endpoint does not need to re-derive them.
    """
    _require_dashboard_access()

    if not frappe.has_permission(document_type, "read"):
        frappe.throw("Not permitted", frappe.PermissionError)

    if isinstance(filters, str):
        filters = frappe.parse_json(filters) if filters else []
    filters = filters or []

    if isinstance(columns, str):
        columns = json.loads(columns) if columns else None
    columns = columns or _pick_display_columns(document_type)

    if search:
        meta = frappe.get_meta(document_type)
        search_fields = [f for f in (columns or []) if meta.has_field(f) and
                          meta.get_field(f).fieldtype in ("Data", "Link", "Small Text", "Text")]
        if search_fields:
            like = f"%{search}%"
            or_filters = [[document_type, f, "like", like] for f in search_fields]
        else:
            or_filters = None
    else:
        or_filters = None

    page = cint(page) or 1
    page_size = cint(page_size) or 25
    offset = (page - 1) * page_size

    fields = ["name"] + [c for c in columns if c != "name"]

    rows = frappe.get_list(
        document_type,
        filters=filters,
        or_filters=or_filters,
        fields=fields,
        limit_start=offset,
        limit_page_length=page_size,
        order_by="modified desc",
    )
    total = frappe.db.count(document_type, filters=filters) if not or_filters else len(
        frappe.get_list(document_type, filters=filters, or_filters=or_filters, fields=["name"], limit_page_length=0)
    )

    return {"rows": rows, "total": total, "columns": columns}
