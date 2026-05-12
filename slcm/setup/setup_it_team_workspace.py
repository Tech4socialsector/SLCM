"""
Setup script for the IT Team workspace — creates Number Cards and Dashboard Charts.
Run with:
    bench --site slcm.local execute slcm.setup.setup_it_team_workspace.setup
"""
import frappe


# ---------------------------------------------------------------------------
# Number Card definitions
# ---------------------------------------------------------------------------
NUMBER_CARDS = [
    {
        "label": "Active Students",
        "document_type": "Student Master",
        "function": "Count",
        "filters_json": '[["Student Master","student_status","=","Active",false]]',
        "color": "#2490EF",
        "stats_time_interval": "Monthly",
        "show_percentage_stats": 1,
    },
    {
        "label": "Total ID Cards",
        "document_type": "ID Card Generation",
        "function": "Count",
        "filters_json": "[]",
        "color": "#7B3FE4",
        "stats_time_interval": "Monthly",
        "show_percentage_stats": 1,
    },
    {
        "label": "Active ID Cards",
        "document_type": "ID Card Generation",
        "function": "Count",
        "filters_json": '[["ID Card Generation","card_status","in","Generated,Printed",false]]',
        "color": "#28A745",
        "stats_time_interval": "Monthly",
        "show_percentage_stats": 1,
    },
    {
        "label": "Pending (Draft) Cards",
        "document_type": "ID Card Generation",
        "function": "Count",
        "filters_json": '[["ID Card Generation","card_status","=","Draft",false]]',
        "color": "#FFC107",
        "stats_time_interval": "Monthly",
        "show_percentage_stats": 1,
    },
    {
        "label": "Cancelled Cards",
        "document_type": "ID Card Generation",
        "function": "Count",
        "filters_json": '[["ID Card Generation","card_status","=","Cancelled",false]]',
        "color": "#DC3545",
        "stats_time_interval": "Monthly",
        "show_percentage_stats": 0,
    },
    {
        "label": "Print Log Entries",
        "document_type": "ID Card Print Log",
        "function": "Count",
        "filters_json": "[]",
        "color": "#17A2B8",
        "stats_time_interval": "Monthly",
        "show_percentage_stats": 1,
    },
]

# ---------------------------------------------------------------------------
# Dashboard Chart definitions
# ---------------------------------------------------------------------------
CHARTS = [
    {
        "chart_name": "ID Card Status Distribution",
        "chart_type": "Group By",
        "document_type": "ID Card Generation",
        "group_by_type": "Count",
        "group_by_based_on": "card_status",
        "type": "Donut",
        "timespan": "Last Year",
        "time_interval": "Monthly",
        "filters_json": "[]",
        "is_public": 1,
    },
    {
        "chart_name": "ID Cards Generated Over Time",
        "chart_type": "Count",
        "document_type": "ID Card Generation",
        "based_on": "creation",
        "timeseries": 1,
        "type": "Bar",
        "timespan": "Last Year",
        "time_interval": "Monthly",
        "filters_json": '[["ID Card Generation","card_status","!=","Cancelled",false]]',
        "is_public": 1,
        "color": "#7B3FE4",
    },
]


def setup():
    frappe.set_user("Administrator")

    # ------------------------------------------------------------------ #
    # 1. Number Cards                                                      #
    # ------------------------------------------------------------------ #
    created_cards = {}
    for card_def in NUMBER_CARDS:
        label = card_def["label"]
        if frappe.db.exists("Number Card", label):
            print(f"  [--] Number Card exists:  {label}")
            created_cards[label] = label
            continue

        card = frappe.get_doc({
            "doctype": "Number Card",
            "label": label,
            "document_type": card_def["document_type"],
            "function": card_def["function"],
            "filters_json": card_def["filters_json"],
            "color": card_def.get("color", "#2490EF"),
            "stats_time_interval": card_def.get("stats_time_interval", "Monthly"),
            "show_percentage_stats": card_def.get("show_percentage_stats", 1),
            "is_public": 1,
            "module": "SLCM",
        })
        card.insert(ignore_permissions=True)
        created_cards[label] = card.name
        print(f"  [OK] Created Number Card: {card.name}")

    frappe.db.commit()

    # ------------------------------------------------------------------ #
    # 2. Dashboard Charts                                                  #
    # ------------------------------------------------------------------ #
    created_charts = {}
    for chart_def in CHARTS:
        chart_name = chart_def["chart_name"]
        if frappe.db.exists("Dashboard Chart", {"chart_name": chart_name}):
            existing = frappe.db.get_value("Dashboard Chart", {"chart_name": chart_name}, "name")
            print(f"  [--] Dashboard Chart exists:  {chart_name}")
            created_charts[chart_name] = existing
            continue

        c = frappe.get_doc({
            "doctype": "Dashboard Chart",
            "chart_name": chart_name,
            "chart_type": chart_def.get("chart_type", "Count"),
            "document_type": chart_def.get("document_type"),
            "group_by_type": chart_def.get("group_by_type", "Count"),
            "group_by_based_on": chart_def.get("group_by_based_on"),
            "based_on": chart_def.get("based_on"),
            "timeseries": chart_def.get("timeseries", 0),
            "type": chart_def.get("type", "Bar"),
            "timespan": chart_def.get("timespan", "Last Year"),
            "time_interval": chart_def.get("time_interval", "Monthly"),
            "filters_json": chart_def.get("filters_json", "[]"),
            "is_public": chart_def.get("is_public", 1),
            "module": "SLCM",
            "color": chart_def.get("color"),
        })
        c.insert(ignore_permissions=True)
        created_charts[chart_name] = c.name
        print(f"  [OK] Created Dashboard Chart: {c.name}")

    frappe.db.commit()

    # ------------------------------------------------------------------ #
    # 3. Update Workspace                                                  #
    # ------------------------------------------------------------------ #
    _update_workspace(created_cards, created_charts)
    frappe.db.commit()
    print("\n  [OK] IT Team workspace updated successfully.")


def _update_workspace(cards, charts):
    import json

    content = [
        # ── Section: Overview ─────────────────────────────────────────────
        {"id": "ws-hdr-overview", "type": "header",
         "data": {"text": "<b>Overview</b>", "col": 12}},

        {"id": "ws-nc-students",  "type": "number_card",
         "data": {"number_card_name": "Active Students",        "col": 3}},
        {"id": "ws-nc-total",     "type": "number_card",
         "data": {"number_card_name": "Total ID Cards",         "col": 3}},
        {"id": "ws-nc-active",    "type": "number_card",
         "data": {"number_card_name": "Active ID Cards",        "col": 3}},
        {"id": "ws-nc-draft",     "type": "number_card",
         "data": {"number_card_name": "Pending (Draft) Cards",  "col": 3}},

        # ── Section: Charts ────────────────────────────────────────────────
        {"id": "ws-hdr-charts", "type": "header",
         "data": {"text": "<b>Analytics</b>", "col": 12}},

        {"id": "ws-chart-status", "type": "chart",
         "data": {"chart_name": "ID Card Status Distribution",  "col": 6}},
        {"id": "ws-chart-trend",  "type": "chart",
         "data": {"chart_name": "ID Cards Generated Over Time", "col": 6}},

        # ── Section: Quick Actions ─────────────────────────────────────────
        {"id": "ws-hdr-actions", "type": "header",
         "data": {"text": "<b>Quick Actions</b>", "col": 12}},

        {"id": "ws-sc-tool",     "type": "shortcut",
         "data": {"shortcut_name": "ID Card Generation Tool",     "col": 3}},
        {"id": "ws-sc-gen",      "type": "shortcut",
         "data": {"shortcut_name": "ID Card Generation",          "col": 3}},
        {"id": "ws-sc-template", "type": "shortcut",
         "data": {"shortcut_name": "ID Card Template",            "col": 3}},
        {"id": "ws-sc-student",  "type": "shortcut",
         "data": {"shortcut_name": "Student Master",              "col": 3}},

        # ── Section: Logs & Audit ──────────────────────────────────────────
        {"id": "ws-hdr-logs", "type": "header",
         "data": {"text": "<b>Logs &amp; Audit</b>", "col": 12}},

        {"id": "ws-sc-tool-log",  "type": "shortcut",
         "data": {"shortcut_name": "ID Card Generation Tool Log", "col": 3}},
        {"id": "ws-sc-print-log", "type": "shortcut",
         "data": {"shortcut_name": "ID Card Print Log",           "col": 3}},
        {"id": "ws-nc-print-log", "type": "number_card",
         "data": {"number_card_name": "Print Log Entries",        "col": 3}},
        {"id": "ws-nc-cancelled", "type": "number_card",
         "data": {"number_card_name": "Cancelled Cards",          "col": 3}},
    ]

    shortcuts = [
        {
            "label": "ID Card Generation Tool",
            "type": "URL",
            "url": "/app/id-card-generation-tool",
            "color": "Purple",
            "doc_view": "List",
        },
        {
            "label": "ID Card Generation",
            "type": "DocType",
            "link_to": "ID Card Generation",
            "color": "Blue",
            "doc_view": "List",
            "stats_filter": "[]",
        },
        {
            "label": "ID Card Template",
            "type": "DocType",
            "link_to": "ID Card Template",
            "color": "Green",
            "doc_view": "List",
            "stats_filter": "[]",
        },
        {
            "label": "Student Master",
            "type": "DocType",
            "link_to": "Student Master",
            "color": "Cyan",
            "doc_view": "List",
            "stats_filter": "[]",
        },
        {
            "label": "ID Card Generation Tool Log",
            "type": "DocType",
            "link_to": "ID Card Generation Tool Log",
            "color": "Grey",
            "doc_view": "List",
            "stats_filter": "[]",
        },
        {
            "label": "ID Card Print Log",
            "type": "DocType",
            "link_to": "ID Card Print Log",
            "color": "Grey",
            "doc_view": "List",
            "stats_filter": "[]",
        },
    ]

    number_cards_ws = [
        {"number_card_name": name, "label": name}
        for name in [
            "Active Students",
            "Total ID Cards",
            "Active ID Cards",
            "Pending (Draft) Cards",
            "Cancelled Cards",
            "Print Log Entries",
        ]
    ]

    charts_ws = [
        {"chart_name": "ID Card Status Distribution",  "label": "ID Card Status Distribution"},
        {"chart_name": "ID Cards Generated Over Time", "label": "ID Cards Generated Over Time"},
    ]

    ws = frappe.get_doc("Workspace", "IT Team")
    ws.content = json.dumps(content)

    # rebuild shortcuts child table
    ws.set("shortcuts", [])
    for s in shortcuts:
        ws.append("shortcuts", s)

    # rebuild number_cards child table
    ws.set("number_cards", [])
    for nc in number_cards_ws:
        ws.append("number_cards", nc)

    # rebuild charts child table
    ws.set("charts", [])
    for ch in charts_ws:
        ws.append("charts", ch)

    ws.save(ignore_permissions=True)
