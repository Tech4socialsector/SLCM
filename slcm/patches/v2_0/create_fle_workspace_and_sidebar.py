"""
Patch: create_fle_workspace_and_sidebar
========================================
Creates the FLE Workspace page and FLE Workspace Sidebar on a fresh site
if they do not already exist.

This patch runs exactly ONCE per site (Frappe tracks it in __Patch).
- Fresh install  : FLE records are missing → created here.
- Re-deploy      : patch already ran → skipped entirely → any FLE
                   customisations made by the cloud admin are preserved.

FLE is intentionally excluded from model sync and fixtures so that the
cloud admin can freely customise the FLE workspace without those changes
being wiped on every bench migrate.
"""

import frappe


def execute():
    _create_fle_workspace()
    _create_fle_sidebar()
    frappe.db.commit()


def _create_fle_workspace():
    if frappe.db.exists("Workspace", "FLE"):
        return

    workspace = frappe.get_doc({
        "doctype": "Workspace",
        "name": "FLE",
        "label": "FLE",
        "title": "FLE",
        "module": "SLCM",
        "app": "slcm",
        "icon": "book-open",
        "indicator_color": "green",
        "public": 1,
        "for_user": "",
        "parent_page": "",
        "is_hidden": 0,
        "hide_custom": 0,
        "sequence_id": 23.0,
        "type": "Workspace",
        "content": (
            '[{"id":"fle-hdr","type":"paragraph","data":{"text":'
            '"<span class=\\"h4\\"><b>Foundations for a Legal Education</b></span>",'
            '"col":12}},{"id":"fle-sc1","type":"shortcut","data":{'
            '"shortcut_name":"Foundations for a Legal Education","col":4}}]'
        ),
        "shortcuts": [
            {
                "label": "Foundations for a Legal Education",
                "link_to": "Foundations for a Legal Education",
                "type": "DocType",
                "color": "Green",
                "doc_view": "List",
                "stats_filter": "[]",
            }
        ],
    })
    workspace.flags.ignore_permissions = True
    workspace.flags.ignore_mandatory = True
    workspace.insert()


def _create_fle_sidebar():
    if frappe.db.exists("Workspace Sidebar", "FLE"):
        return

    sidebar = frappe.get_doc({
        "doctype": "Workspace Sidebar",
        "name": "FLE",
        "title": "FLE",
        "module": "SLCM",
        "app": "slcm",
        "standard": 1,
        "header_icon": "book-open",
        "items": [
            {
                "type": "Link",
                "label": "Home",
                "link_to": "FLE",
                "link_type": "Workspace",
                "icon": "home",
                "child": 0,
                "collapsible": 1,
                "indent": 0,
                "keep_closed": 0,
                "show_arrow": 0,
            },
            {
                "type": "Section Break",
                "label": "Courses",
                "link_type": "DocType",
                "icon": "arrow-right",
                "child": 0,
                "collapsible": 1,
                "indent": 0,
                "keep_closed": 0,
                "show_arrow": 0,
            },
            {
                "type": "Link",
                "label": "Foundations for a Legal Education",
                "link_to": "Foundations for a Legal Education",
                "link_type": "DocType",
                "icon": "layers",
                "child": 1,
                "collapsible": 1,
                "indent": 0,
                "keep_closed": 0,
                "show_arrow": 0,
            },
        ],
    })
    sidebar.flags.ignore_permissions = True
    sidebar.flags.ignore_mandatory = True
    sidebar.insert()
