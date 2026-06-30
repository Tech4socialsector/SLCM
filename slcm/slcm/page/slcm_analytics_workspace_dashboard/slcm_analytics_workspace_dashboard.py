# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import json
import frappe

# Re-export all analytics methods from the existing dashboard so the JS can call them
# via this page's method path without duplicating backend logic.
from slcm.slcm.page.slcm_analytics_dashboard.slcm_analytics_dashboard import (
    _require_dashboard_access,
    _build_filters,
    get_filter_options,
    get_overview_stats,
    get_student_analytics,
    get_attendance_analytics,
    get_examination_analytics,
    get_fees_analytics,
    get_hostel_analytics,
    get_placement_analytics,
    get_programme_analytics,
    get_admission_analytics,
    get_idcard_analytics,
    get_venue_analytics,
    get_promotion_analytics,
    get_ticketing_analytics,
    get_rfid_analytics,
    get_drilldown_data,
)

# Re-register all imported functions as whitelisted under this module's path.
# Frappe resolves @whitelist by checking the function's module at call time,
# so we must wrap each one rather than rely on the import alone.

get_filter_options   = frappe.whitelist()(get_filter_options)
get_overview_stats   = frappe.whitelist()(get_overview_stats)
get_student_analytics    = frappe.whitelist()(get_student_analytics)
get_attendance_analytics = frappe.whitelist()(get_attendance_analytics)
get_examination_analytics = frappe.whitelist()(get_examination_analytics)
get_fees_analytics   = frappe.whitelist()(get_fees_analytics)
get_hostel_analytics = frappe.whitelist()(get_hostel_analytics)
get_placement_analytics  = frappe.whitelist()(get_placement_analytics)
get_programme_analytics  = frappe.whitelist()(get_programme_analytics)
get_admission_analytics  = frappe.whitelist()(get_admission_analytics)
get_idcard_analytics     = frappe.whitelist()(get_idcard_analytics)
get_venue_analytics      = frappe.whitelist()(get_venue_analytics)
get_promotion_analytics  = frappe.whitelist()(get_promotion_analytics)
get_ticketing_analytics  = frappe.whitelist()(get_ticketing_analytics)
get_rfid_analytics       = frappe.whitelist()(get_rfid_analytics)
get_drilldown_data       = frappe.whitelist()(get_drilldown_data)

# ── Module registry ───────────────────────────────────────────────────────────

# Ordered list of all analytics modules.  `workspace` is the label of the
# Frappe Workspace that this analytics section corresponds to — used to
# determine whether the module is "available" (i.e. the workspace exists).
# None means always available (overview).
ANALYTICS_MODULES = [
    {"key": "overview",    "label": "Overview",    "icon": "📊", "workspace": None},
    {"key": "admission",   "label": "Admission",   "icon": "🎯", "workspace": "Admission"},
    {"key": "students",    "label": "Students",    "icon": "🎓", "workspace": "Student Registration"},
    {"key": "programme",   "label": "Programme",   "icon": "📚", "workspace": "Programme Management"},
    {"key": "attendance",  "label": "Attendance",  "icon": "📋", "workspace": "Attendance"},
    {"key": "examination", "label": "Examination", "icon": "📝", "workspace": "Examination Management"},
    {"key": "fees",        "label": "Fees",        "icon": "💰", "workspace": "Fees Management"},
    {"key": "hostel",      "label": "Hostel",      "icon": "🏠", "workspace": "Hostel Management"},
    {"key": "placement",   "label": "Placement",   "icon": "💼", "workspace": "Placement"},
    {"key": "idcard",      "label": "ID Card",     "icon": "🪪", "workspace": "IT Team"},
    {"key": "venue",       "label": "Venue",       "icon": "🏛️", "workspace": "Venue Bookings"},
    {"key": "promotion",   "label": "Promotion",   "icon": "🎖️", "workspace": "Promotions"},
    {"key": "ticketing",   "label": "Ticketing",   "icon": "🎫", "workspace": "Helpdesk"},
]

_DEFAULTS_KEY = "slcm_workspace_analytics_modules"


def _get_user_accessible_workspace_labels():
    """
    Return the set of Workspace labels that the current user can actually see.

    Frappe workspace visibility rules:
      1. A public workspace (public=1) that has no for_user — visible to all
         users whose roles permit access to the module.
      2. A workspace with for_user = current user — that user's personal copy
         (created when they customise the sidebar); it overrides the public one.
      3. A workspace hidden by the user is stored with for_user=user and
         is_hidden=1; we skip those.

    We also respect whether the user has at least one permitted role for
    the module by checking frappe.has_permission on the Workspace doc.
    """
    user = frappe.session.user

    # 1. All public workspaces (no for_user) — these are the system defaults
    # for_user may be stored as NULL or "" depending on Frappe version, so match both.
    public_ws = frappe.db.get_all(
        "Workspace",
        filters=[["public", "=", 1], ["for_user", "in", ["", None]]],
        fields=["name", "label", "is_hidden"],
    )

    # 2. User-specific customised workspace copies
    user_ws = frappe.db.get_all(
        "Workspace",
        filters={"for_user": user},
        fields=["name", "label", "is_hidden"],
    )
    user_ws_labels = {ws["label"] for ws in user_ws}

    # Build the final visible set:
    # Start from public workspaces; if the user has a personal copy, use that
    # instead (it may be hidden or have a different config).
    visible = set()

    for ws in public_ws:
        label = ws["label"]
        if label in user_ws_labels:
            # User has a personal copy — check whether they hid it
            personal = next(w for w in user_ws if w["label"] == label)
            if not personal.get("is_hidden"):
                visible.add(label)
        else:
            # No personal copy → use the public default (always visible)
            if not ws.get("is_hidden"):
                visible.add(label)

    # Also add any user-created workspaces that have no public counterpart
    for ws in user_ws:
        if not ws.get("is_hidden"):
            visible.add(ws["label"])

    return visible


def _get_workspace_shortcuts(workspace_label):
    """
    Return the shortcut links defined in a Workspace so the frontend can
    provide quick-navigation buttons within each analytics module section.
    """
    # Try user's personal copy first, then fall back to any public workspace.
    ws = frappe.db.get_value(
        "Workspace",
        {"label": workspace_label, "for_user": frappe.session.user},
        "name",
    )
    if not ws:
        # for_user can be NULL or "" — use OR-style filter via sql
        rows = frappe.db.get_all(
            "Workspace",
            filters=[["label", "=", workspace_label], ["for_user", "in", ["", None]], ["public", "=", 1]],
            fields=["name"],
            limit=1,
        )
        ws = rows[0]["name"] if rows else None
    if not ws:
        return []

    shortcuts = frappe.db.get_all(
        "Workspace Shortcut",
        filters={"parent": ws},
        fields=["label", "type", "link_to", "url", "color", "icon"],
        order_by="idx asc",
    )
    return shortcuts


@frappe.whitelist()
def get_workspace_modules():
    """
    Return the ordered analytics module list annotated with:
      - available : workspace exists AND is visible in the user's sidebar
      - enabled   : user has toggled it on (from saved config, or default=available)
      - shortcuts : quick-links pulled live from the workspace definition
    """
    _require_dashboard_access()

    user_visible_labels = _get_user_accessible_workspace_labels()

    # Load persisted user preference
    saved_raw = frappe.defaults.get_user_default(_DEFAULTS_KEY)
    saved_list = None
    if saved_raw:
        try:
            saved_list = json.loads(saved_raw)
        except (json.JSONDecodeError, TypeError):
            saved_list = None

    result = []
    for mod in ANALYTICS_MODULES:
        ws_label = mod["workspace"]

        # 'overview' has no workspace — always available
        if ws_label is None:
            available = True
        else:
            available = ws_label in user_visible_labels

        if saved_list is None:
            # First visit: enable every available module automatically
            enabled = available
        else:
            enabled = mod["key"] in saved_list and available

        # Fetch shortcuts from the workspace definition (live, so edits reflect)
        shortcuts = []
        if ws_label and available:
            try:
                shortcuts = _get_workspace_shortcuts(ws_label)
            except Exception:
                shortcuts = []

        result.append({
            "key":       mod["key"],
            "label":     mod["label"],
            "icon":      mod["icon"],
            "workspace": ws_label,
            "available": available,
            "enabled":   enabled,
            "shortcuts": shortcuts,
        })

    return {
        "modules":          result,
        "has_saved_config": saved_list is not None,
    }


@frappe.whitelist()
def save_workspace_config(enabled_modules):
    """
    Persist the user's chosen module list.
    `enabled_modules` may arrive as a JSON string (Frappe serialises list args).
    'overview' is always forced in since the dashboard always shows a summary.
    """
    _require_dashboard_access()

    if isinstance(enabled_modules, str):
        try:
            enabled_modules = json.loads(enabled_modules)
        except (json.JSONDecodeError, TypeError):
            frappe.throw("Invalid module list format.")

    valid_keys = {m["key"] for m in ANALYTICS_MODULES}
    bad = [k for k in enabled_modules if k not in valid_keys]
    if bad:
        frappe.throw(f"Unknown module key(s): {bad}")

    # Always keep overview in the list
    keys = list(enabled_modules)
    if "overview" not in keys:
        keys.insert(0, "overview")

    frappe.defaults.set_user_default(_DEFAULTS_KEY, json.dumps(keys))
    return {"status": "ok", "enabled_modules": keys}


def merge_filters_for_doctype(doctype, base_filters, dashboard_filters):
    if not doctype or not dashboard_filters:
        return base_filters

    meta = frappe.get_meta(doctype)
    merged = list(base_filters) if base_filters else []

    # We want to map standard keys:
    # academic_year, term, program, cohort, student_status
    mapping = {
        "academic_year": ["academic_year"],
        "term": ["academic_term", "term"],
        "program": ["program", "programme"],
        "cohort": ["cohort", "programme"],
        "student_status": ["student_status", "status"],
    }

    for filter_key, val in dashboard_filters.items():
        # Normalise: skip empty, unwrap single-item lists to plain values
        if val is None or val == "" or val == []:
            continue
        if isinstance(val, list):
            val = [v for v in val if v]
            if not val:
                continue
            if len(val) == 1:
                val = val[0]

        target_fields = mapping.get(filter_key, [filter_key])
        matched_field = None
        for tf in target_fields:
            if meta.has_field(tf):
                matched_field = tf
                break

        if matched_field:
            # Check if this field is already filtered in base_filters to avoid duplication or conflict
            already_filtered = False
            for f in merged:
                if isinstance(f, (list, tuple)) and len(f) >= 3:
                    field_name = f[0] if len(f) == 3 else f[1]
                    if field_name == matched_field:
                        already_filtered = True
                        if len(f) == 3:
                            if isinstance(f, tuple):
                                idx = merged.index(f)
                                f_list = list(f)
                                f_list[2] = val
                                merged[idx] = f_list
                            else:
                                f[2] = val
                        elif len(f) == 4:
                            if isinstance(f, tuple):
                                idx = merged.index(f)
                                f_list = list(f)
                                f_list[3] = val
                                merged[idx] = f_list
                            else:
                                f[3] = val
                        break
            if not already_filtered:
                op = "in" if isinstance(val, list) else "="
                merged.append([doctype, matched_field, op, val])

    return merged


@frappe.whitelist()
def get_workspace_dashboard_details(workspace_name, filters=None):
    """
    Given a workspace/dashboard name and filters, get all number cards and charts
    along with their calculated values and datasets.
    """
    _require_dashboard_access()

    if isinstance(filters, str):
        filters = frappe.parse_json(filters)
    if not filters:
        filters = {}

    # Check if a standard Dashboard with this name exists first
    is_dashboard = False
    doc = None
    if frappe.db.exists("Dashboard", workspace_name):
        doc = frappe.get_doc("Dashboard", workspace_name)
        is_dashboard = True
    else:
        user = frappe.session.user
        # Try user's personal copy first
        ws = frappe.db.get_value("Workspace", {"label": workspace_name, "for_user": user}, "name")
        if not ws:
            # Fall back to public workspace — for_user may be NULL or "" in different Frappe versions
            rows = frappe.db.get_all(
                "Workspace",
                filters=[["label", "=", workspace_name], ["for_user", "in", ["", None]], ["public", "=", 1]],
                fields=["name"],
                limit=1,
            )
            ws = rows[0]["name"] if rows else None
        if ws:
            doc = frappe.get_doc("Workspace", ws)

    if not doc:
        return {"cards": [], "charts": [], "is_dashboard": False}

    cards = []
    charts = []

    from frappe.desk.doctype.dashboard_chart.dashboard_chart import get as get_chart_data

    def _get_card_value(card_name, card_doc, merged_filters):
        """
        Compute the number card value directly, bypassing get_result's
        frappe.parse_json(doc) path which can behave unexpectedly when
        passed a Document object on newer Python versions.
        """
        from frappe.utils import flt
        sql_map = {"Count": "COUNT", "Sum": "SUM", "Average": "AVG",
                   "Minimum": "MIN", "Maximum": "MAX"}
        fn = sql_map.get(card_doc.function, "COUNT")
        arg = "*" if fn == "COUNT" else (card_doc.aggregate_function_based_on or "*")
        _filters = list(merged_filters) if merged_filters else []
        res = frappe.get_list(
            card_doc.document_type,
            fields=[{fn: arg, "as": "result"}],
            filters=_filters,
            parent_doctype=card_doc.parent_document_type,
        )
        return flt(res[0]["result"] if res else 0)

    def _get_card_diff(card_doc, merged_filters, current_val):
        """Compute month-over-month percentage change."""
        if not card_doc.show_percentage_stats:
            return None
        try:
            from frappe.utils import add_to_date, flt
            interval_map = {
                "Daily": {"days": -1}, "Weekly": {"weeks": -1},
                "Monthly": {"months": -1}, "Yearly": {"years": -1},
            }
            kwargs = interval_map.get(card_doc.stats_time_interval, {"months": -1})
            prev_date = add_to_date(frappe.utils.now(), **kwargs)
            _filters = list(merged_filters) if merged_filters else []
            _filters.append([card_doc.document_type, "creation", "<", prev_date])
            from frappe.utils import flt as _flt
            sql_map = {"Count": "COUNT", "Sum": "SUM", "Average": "AVG",
                       "Minimum": "MIN", "Maximum": "MAX"}
            fn = sql_map.get(card_doc.function, "COUNT")
            arg = "*" if fn == "COUNT" else (card_doc.aggregate_function_based_on or "*")
            res = frappe.get_list(
                card_doc.document_type,
                fields=[{fn: arg, "as": "result"}],
                filters=_filters,
                parent_doctype=card_doc.parent_document_type,
            )
            prev_val = _flt(res[0]["result"] if res else 0)
            if prev_val == 0:
                return None
            return round(((current_val / prev_val) - 1) * 100.0, 1)
        except Exception:
            return None

    def _process_card(card_name, label_override=None):
        if not frappe.db.exists("Number Card", card_name):
            return None
        try:
            card_doc = frappe.get_doc("Number Card", card_name)
            card_filters = frappe.parse_json(card_doc.filters_json or "[]")
            mf = merge_filters_for_doctype(card_doc.document_type, card_filters, filters)
            val = _get_card_value(card_name, card_doc, mf)
            diff = _get_card_diff(card_doc, mf, val)
            return {
                "name": card_doc.name,
                "label": label_override or card_doc.label,
                "value": val,
                "diff": diff,
                "color": card_doc.color,
                "document_type": card_doc.document_type,
                "show_percentage_stats": card_doc.show_percentage_stats,
                "stats_time_interval": card_doc.stats_time_interval,
            }
        except Exception as e:
            frappe.log_error(f"Number card {card_name} in {workspace_name}: {e}")
            return None

    def _process_chart(chart_name, label_override=None):
        if not frappe.db.exists("Dashboard Chart", chart_name):
            return None
        try:
            chart_doc = frappe.get_doc("Dashboard Chart", chart_name)
            label = label_override or chart_doc.chart_name

            if chart_doc.chart_type == "Report":
                return {
                    "name": chart_doc.name,
                    "label": label,
                    "type": chart_doc.type,
                    "chart_type": "Report",
                    "report_name": chart_doc.report_name,
                    "use_report_chart": chart_doc.use_report_chart,
                    "x_field": chart_doc.x_field,
                    "y_axis": [{"y_field": y.y_field} for y in getattr(chart_doc, "y_axis", [])],
                    "filters_json": chart_doc.filters_json,
                }

            chart_filters = frappe.parse_json(chart_doc.filters_json or "[]")
            mf = merge_filters_for_doctype(chart_doc.document_type, chart_filters, filters)
            chart_data = get_chart_data(chart_name=chart_name, filters=json.dumps(mf))
            return {
                "name": chart_doc.name,
                "label": label,
                "type": chart_doc.type,
                "document_type": chart_doc.document_type,
                "group_by_field": (
                    chart_doc.group_by_based_on
                    if chart_doc.chart_type == "Group By"
                    else chart_doc.based_on
                ),
                "chart_data": chart_data,
            }
        except Exception as e:
            frappe.log_error(f"Chart {chart_name} in {workspace_name}: {e}")
            return None

    if is_dashboard:
        for card_link in getattr(doc, "cards", []):
            result = _process_card(card_link.card)
            if result:
                cards.append(result)
        for chart_link in getattr(doc, "charts", []):
            result = _process_chart(chart_link.chart)
            if result:
                charts.append(result)
    else:
        for card_link in getattr(doc, "number_cards", []):
            result = _process_card(card_link.number_card_name, card_link.label)
            if result:
                cards.append(result)
        for chart_link in getattr(doc, "charts", []):
            result = _process_chart(chart_link.chart_name, chart_link.label)
            if result:
                charts.append(result)

    return {"cards": cards, "charts": charts, "is_dashboard": is_dashboard}


@frappe.whitelist()
def get_workspace_shortcut_links(workspace_label):
    """Return shortcut link definitions for any workspace by label."""
    _require_dashboard_access()
    return _get_workspace_shortcuts(workspace_label)






