# Copyright (c) 2026, Azim Premji Foundation and contributors
# For license information, please see license.txt
"""
Razorpay Settlement Journal Upload Report

Fetches live settlement data directly from Razorpay API.
Groups by Settlement ID, auto-creates balanced Debit + Credit journal rows,
validates Debit = Credit before export, and produces a Zoho Books import-ready file.

Dynamic values resolved at runtime:
  - Credit account  → Razorpay Settings.merchant_account_name (fallback: filter)
  - Bank account    → filter (default: UBI Bank PACE 520101045120011)
  - Journal prefix  → filter (default: JN-FP-)
  - Journal suffix  → Frappe naming series counter (frappe.db.get_next_sequence)
  - Department      → filter (default: PACE)
  - Course          → filter (default: FLE)
  - Journal Date    → settlement_time (processed) or created_at (created/other)
  - Notes           → includes UTR when available
  - FLE Match       → cross-checked against FLE Payment Log.settlement_id
"""

import io
from datetime import datetime, timezone

import frappe
import requests
from frappe import _
from frappe.utils import flt, formatdate, getdate, nowdate

# ── API constants ─────────────────────────────────────────────────────────────
RAZORPAY_BASE = "https://api.razorpay.com/v1"
PAGE_SIZE     = 100

# ── Static defaults (overridable via filters or Razorpay Settings) ────────────
DEFAULT_CREDIT_ACCOUNT = "Foundation for a Legal Education Fee"
DEFAULT_DEBIT_ACCOUNT  = "UBI Bank PACE 520101045120011"
DEFAULT_CONTACT        = "Razorpay"
DEFAULT_PREFIX         = "JN-FP-"
DEFAULT_JOURNAL_TYPE   = "Both"
DEFAULT_CURRENCY       = "INR"
DEFAULT_DESCRIPTION    = "online"
DEFAULT_DEPARTMENT     = "PACE"
DEFAULT_COURSE         = "FLE"

# Zoho Books required column order (exact — do NOT change)
ZOHO_HEADERS = [
    "Journal Date", "Reference Number", "Journal Number Prefix",
    "Journal Number Suffix", "Notes", "Journal Type", "Currency",
    "Account", "Description", "Contact Name", "Debit", "Credit",
    "Department", "Course",
]
ZOHO_FIELD_MAP = {h: h.lower().replace(" ", "_") for h in ZOHO_HEADERS}
ZOHO_FIELD_MAP.update({
    "Journal Date":          "journal_date",
    "Reference Number":      "reference_number",
    "Journal Number Prefix": "journal_number_prefix",
    "Journal Number Suffix": "journal_number_suffix",
    "Journal Type":          "journal_type",
    "Contact Name":          "contact_name",
})


# ── Entry point ───────────────────────────────────────────────────────────────

def execute(filters=None):
    filters = filters or {}

    try:
        settlements = _fetch_settlements(filters)
    except frappe.ValidationError:
        raise
    except Exception as exc:
        frappe.log_error(frappe.get_traceback(), "Razorpay Settlement Journal Upload")
        frappe.throw(
            _("Failed to fetch settlements from Razorpay: {0}").format(str(exc)),
            title=_("API Error"),
        )
        return _get_columns(), []

    if not settlements:
        frappe.msgprint(
            _("No settlements found for the selected date range."),
            indicator="orange", alert=True,
        )
        return _get_columns(), [], None, None, []

    config  = _resolve_config(filters)
    fle_map = _build_fle_map(settlements, filters)
    data, stats = _build_journal_rows(settlements, filters, config, fle_map)

    return (
        _get_columns(),
        data,
        None,
        _get_chart(stats["daily"]),
        _get_report_summary(stats),
    )


# ── Dynamic config resolver ───────────────────────────────────────────────────

def _resolve_config(filters):
    """
    Build the runtime journal config.
    Priority: filter value → Razorpay Settings → hardcoded default.
    """
    # Pull Razorpay Settings once
    rzp_merchant_name = ""
    try:
        settings = frappe.get_doc("Razorpay Settings")
        rzp_merchant_name = (settings.get("merchant_account_name") or "").strip()
    except Exception:
        pass

    bank_account   = (filters.get("bank_account")   or "").strip() or rzp_merchant_name or DEFAULT_DEBIT_ACCOUNT
    credit_account = (filters.get("credit_account") or "").strip() or DEFAULT_CREDIT_ACCOUNT
    prefix         = (filters.get("journal_prefix")  or "").strip() or DEFAULT_PREFIX
    department     = (filters.get("department")      or "").strip() or DEFAULT_DEPARTMENT
    course         = (filters.get("course")          or "").strip() or DEFAULT_COURSE
    contact        = DEFAULT_CONTACT

    return {
        "bank_account":   bank_account,
        "credit_account": credit_account,
        "prefix":         prefix,
        "department":     department,
        "course":         course,
        "contact":        contact,
    }


# ── Columns ───────────────────────────────────────────────────────────────────

def _get_columns():
    return [
        {"label": _("Journal Date"),           "fieldname": "journal_date",          "fieldtype": "Date",     "width": 110},
        {"label": _("Reference Number"),        "fieldname": "reference_number",      "fieldtype": "Data",     "width": 215},
        {"label": _("Journal Number Prefix"),   "fieldname": "journal_number_prefix", "fieldtype": "Data",     "width": 145},
        {"label": _("Journal Number Suffix"),   "fieldname": "journal_number_suffix", "fieldtype": "Int",      "width": 145},
        {"label": _("Notes"),                   "fieldname": "notes",                 "fieldtype": "Data",     "width": 370},
        {"label": _("Journal Type"),            "fieldname": "journal_type",          "fieldtype": "Data",     "width":  85},
        {"label": _("Currency"),                "fieldname": "currency",              "fieldtype": "Data",     "width":  75},
        {"label": _("Account"),                 "fieldname": "account",               "fieldtype": "Data",     "width": 280},
        {"label": _("Description"),             "fieldname": "description",           "fieldtype": "Data",     "width":  85},
        {"label": _("Contact Name"),            "fieldname": "contact_name",          "fieldtype": "Data",     "width": 115},
        {"label": _("Debit"),                   "fieldname": "debit",                 "fieldtype": "Currency", "width": 140},
        {"label": _("Credit"),                  "fieldname": "credit",                "fieldtype": "Currency", "width": 140},
        {"label": _("Department"),              "fieldname": "department",            "fieldtype": "Data",     "width":  90},
        {"label": _("Course"),                  "fieldname": "course",                "fieldtype": "Data",     "width":  70},
        # Display-only columns (excluded from Zoho export)
        {"label": _("Row Type"),                "fieldname": "row_type",              "fieldtype": "Data",     "width":  85},
        {"label": _("Settlement Status"),       "fieldname": "settlement_status",     "fieldtype": "Data",     "width": 120},
        {"label": _("Settlement Amount (₹)"),   "fieldname": "settlement_amount",     "fieldtype": "Currency", "width": 145},
        {"label": _("UTR"),                     "fieldname": "utr",                   "fieldtype": "Data",     "width": 175},
        {"label": _("FLE Match"),               "fieldname": "fle_match",             "fieldtype": "Data",     "width":  90},
    ]


# ── Journal row builder ───────────────────────────────────────────────────────

def _build_journal_rows(settlements, filters, config, fle_map):
    status_f  = (filters.get("settlement_status") or "").strip().lower()
    sid_f     = (filters.get("settlement_id")     or "").strip().lower()
    min_amt   = flt(filters.get("min_amount") or 0)
    max_amt   = flt(filters.get("max_amount") or 0)
    row_type_f = (filters.get("row_type") or "").strip()
    fle_only  = bool(filters.get("fle_only"))

    rows         = []
    suffix       = _next_suffix(config["prefix"])
    daily_totals = {}
    filtered_out = 0

    # Sort ascending by the actual journal date (settlement_time > created_at)
    settlements.sort(key=lambda s: s.get("settlement_time") or s.get("created_at") or 0)

    for s in settlements:
        settlement_id     = s.get("id") or ""
        amount_paise      = s.get("amount") or 0
        amount            = round(flt(amount_paise) / 100, 2)
        settlement_status = (s.get("status") or "").lower()
        utr               = (s.get("utr") or "").strip()

        # Use settlement_time for processed (actual bank credit date), else created_at
        ts = s.get("settlement_time") or s.get("created_at")
        settlement_date = _unix_to_date(ts)

        if not settlement_date or not settlement_id or amount <= 0:
            continue

        # ── Date filter (client-side guard — API filter can be loose) ────────
        if filters.get("from_date") and settlement_date < getdate(filters["from_date"]):
            continue
        if filters.get("to_date") and settlement_date > getdate(filters["to_date"]):
            continue

        # ── Status filter ────────────────────────────────────────────────────
        if status_f and status_f != "all" and settlement_status != status_f:
            filtered_out += 1
            continue

        # ── Settlement ID filter (partial) ───────────────────────────────────
        if sid_f and sid_f not in settlement_id.lower():
            filtered_out += 1
            continue

        # ── Amount range filter ──────────────────────────────────────────────
        if min_amt and amount < min_amt:
            filtered_out += 1
            continue
        if max_amt and amount > max_amt:
            filtered_out += 1
            continue

        # ── FLE match — check by settlement_id first, then by UTR ───────────
        fle_matched = (
            settlement_id in fle_map.get("by_settlement_id", set())
            or (utr and utr in fle_map.get("by_utr", set()))
        )
        if fle_only and not fle_matched:
            filtered_out += 1
            continue

        # ── Build dynamic Notes ──────────────────────────────────────────────
        date_str = formatdate(settlement_date, "dd-MM-yyyy")
        if utr:
            notes = (
                f"Online payment settlement on {date_str} "
                f"for bank account {config['bank_account']} | UTR: {utr}"
            )
        else:
            notes = (
                f"Online payment settlement on {date_str} "
                f"for bank account {config['bank_account']}"
            )

        daily_totals[str(settlement_date)] = (
            daily_totals.get(str(settlement_date), 0) + amount
        )

        shared = {
            "journal_date":          settlement_date,
            "reference_number":      settlement_id,
            "journal_number_prefix": config["prefix"],
            "journal_number_suffix": suffix,
            "notes":                 notes,
            "journal_type":          DEFAULT_JOURNAL_TYPE,
            "currency":              DEFAULT_CURRENCY,
            "description":           DEFAULT_DESCRIPTION,
            "contact_name":          config["contact"],
            "department":            config["department"],
            "course":                config["course"],
            "settlement_status":     settlement_status,
            "settlement_amount":     amount,
            "utr":                   utr,
            "fle_match":             "Yes" if fle_matched else "No",
        }

        credit_row = {**shared, "account": config["credit_account"], "debit": 0,      "credit": amount, "row_type": "Credit"}
        debit_row  = {**shared, "account": config["bank_account"],   "debit": amount, "credit": 0,      "row_type": "Debit"}

        if not row_type_f or row_type_f == "All":
            rows.append(credit_row)
            rows.append(debit_row)
        elif row_type_f == "Credit":
            rows.append(credit_row)
        elif row_type_f == "Debit":
            rows.append(debit_row)

        suffix += 1

    rows.sort(key=lambda r: (r["journal_date"], r["journal_number_suffix"], r["row_type"]))

    total_debit  = round(sum(r["debit"]  for r in rows), 2)
    total_credit = round(sum(r["credit"] for r in rows), 2)
    # Only count debit rows to avoid double-counting
    total_amount = round(sum(r["settlement_amount"] for r in rows if r["row_type"] == "Debit"), 2)
    balanced     = abs(total_debit - total_credit) < 0.01

    stats = {
        "total_settlements": len({r["reference_number"] for r in rows}),
        "total_rows":        len(rows),
        "filtered_out":      filtered_out,
        "total_amount":      total_amount,
        "total_debit":       total_debit,
        "total_credit":      total_credit,
        "balanced":          balanced,
        "daily":             daily_totals,
        "config":            config,
    }
    return rows, stats


def _next_suffix(prefix):
    """
    Return the next journal number suffix.
    Uses Frappe's naming series mechanism via `tabSeries` — the canonical
    way to get auto-incrementing counters without a custom column.
    Falls back to 1 if the series doesn't exist yet.
    """
    series_name = f"{prefix}.####"
    try:
        current = frappe.db.get_value("Series", series_name, "current") or 0
        return int(current) + 1
    except Exception:
        try:
            result = frappe.db.sql(
                "SELECT current FROM `tabSeries` WHERE name = %s", (series_name,)
            )
            return int(result[0][0]) + 1 if result else 1
        except Exception:
            return 1


# ── FLE Payment Log cross-reference ──────────────────────────────────────────

def _build_fle_map(settlements=None, filters=None):
    """
    Build a set of Razorpay settlement IDs that have matching FLE Payment Log records.

    Three-layer matching (each layer adds to the matched set):

    Layer 1 — Direct DB fields (fastest, no extra API call):
        FLE Payment Log.settlement_id  → matches settlement.id
        FLE Payment Log.settlement_utr → matches settlement.utr

    Layer 2 — transaction_id cross-reference via recon API:
        Fetch recon items (pay_xxx per settlement_id) from Razorpay.
        Look up each pay_xxx in FLE Payment Log.transaction_id.
        If found → that settlement_id is matched.
        This is the primary method used by FLE Razorpay Settlement Report.

    Layer 3 — gateway_response JSON extraction:
        Parse FLE Payment Log.gateway_response for razorpay_payment_id.
        Cross-check against recon pay_xxx values.

    Returns a dict:
        {
          "by_settlement_id": set of matched settlement_ids,
          "by_utr":           set of matched settlement_utrs,
        }
    """
    empty = {"by_settlement_id": set(), "by_utr": set()}

    if not frappe.db.table_exists("FLE Payment Log"):
        return empty

    settlements = settlements or []
    filters     = filters or {}

    try:
        # ── Layer 1: direct DB field match ───────────────────────────────────
        db_rows = frappe.db.sql(
            """
            SELECT settlement_id, settlement_utr
            FROM `tabFLE Payment Log`
            WHERE (settlement_id  IS NOT NULL AND settlement_id  != '')
               OR (settlement_utr IS NOT NULL AND settlement_utr != '')
            """,
            as_dict=True,
        )
        matched_sids = {r.settlement_id  for r in db_rows if r.settlement_id}
        matched_utrs = {r.settlement_utr for r in db_rows if r.settlement_utr}

        # ── Layer 2 + 3: recon pay_xxx → FLE transaction_id lookup ───────────
        # Only run when fle_only filter is on (avoid extra API call otherwise)
        if filters.get("fle_only") and settlements:
            # Build FLE lookup maps from transaction_id and gateway_response
            fle_db_rows = frappe.db.sql(
                """
                SELECT transaction_id, gateway_response
                FROM `tabFLE Payment Log`
                WHERE transaction_id IS NOT NULL AND transaction_id != ''
                   OR gateway_response IS NOT NULL
                """,
                as_dict=True,
            )

            # pay_xxx set from transaction_id
            fle_pay_ids = set()
            for r in fle_db_rows:
                tid = (r.transaction_id or "").strip()
                if tid.startswith("pay_"):
                    fle_pay_ids.add(tid)
                # Also parse gateway_response for pay_xxx
                if r.gateway_response and not tid.startswith("pay_"):
                    try:
                        import json as _json
                        gw  = _json.loads(r.gateway_response)
                        pid = (
                            gw.get("razorpay_payment_id")
                            or gw.get("payload", {}).get("payment", {})
                               .get("entity", {}).get("id")
                            or ""
                        ).strip()
                        if pid.startswith("pay_"):
                            fle_pay_ids.add(pid)
                    except Exception:
                        pass

            if fle_pay_ids:
                # Fetch recon items for all settlements to get pay_xxx → settlement_id mapping
                api_key, api_secret = _get_credentials()
                auth = (api_key, api_secret)

                # Determine year-months from settlements
                year_months = set()
                for s in settlements:
                    ts = s.get("created_at")
                    if ts:
                        try:
                            from datetime import timezone as _tz
                            dt = datetime.fromtimestamp(int(ts), tz=_tz.utc)
                            year_months.add((dt.year, dt.month))
                        except Exception:
                            pass

                target_sids = {s["id"] for s in settlements if s.get("id")}

                for year, month in sorted(year_months):
                    skip = 0
                    while True:
                        try:
                            resp = requests.get(
                                f"{RAZORPAY_BASE}/settlements/recon/combined",
                                auth=auth,
                                params={"year": year, "month": month,
                                        "count": 1000, "skip": skip},
                                timeout=45,
                            )
                        except Exception:
                            break

                        if not resp.ok:
                            break

                        items = resp.json().get("items") or []
                        for item in items:
                            sid = item.get("settlement_id") or ""
                            if sid not in target_sids:
                                continue
                            pay_id = (
                                item.get("entity_id")
                                or item.get("payment_id")
                                or ""
                            ).strip()
                            if pay_id and pay_id in fle_pay_ids:
                                matched_sids.add(sid)
                                # Also add the UTR for this settlement
                                s_data = next(
                                    (s for s in settlements if s.get("id") == sid), {}
                                )
                                utr = s_data.get("utr") or ""
                                if utr:
                                    matched_utrs.add(utr)

                        if len(items) < 1000:
                            break
                        skip += 1000

        return {"by_settlement_id": matched_sids, "by_utr": matched_utrs}

    except Exception:
        frappe.log_error(frappe.get_traceback(), "FLE Map Build Error")
        return empty


# ── Summary cards ─────────────────────────────────────────────────────────────

def _get_report_summary(stats):
    balanced = stats.get("balanced", False)
    return [
        {
            "value":     stats["total_settlements"],
            "label":     _("Settlements"),
            "datatype":  "Int",
            "indicator": "Blue",
        },
        {
            "value":     stats["total_rows"],
            "label":     _("Journal Rows"),
            "datatype":  "Int",
            "indicator": "Blue",
        },
        {
            "value":     stats["total_amount"],
            "label":     _("Settlement Amount (₹)"),
            "datatype":  "Currency",
            "currency":  "INR",
            "indicator": "Green",
        },
        {
            "value":     stats["total_debit"],
            "label":     _("Total Debit (₹)"),
            "datatype":  "Currency",
            "currency":  "INR",
            "indicator": "Blue",
        },
        {
            "value":     stats["total_credit"],
            "label":     _("Total Credit (₹)"),
            "datatype":  "Currency",
            "currency":  "INR",
            "indicator": "Blue",
        },
        {
            "value":     "Balanced ✓" if balanced else "UNBALANCED ✗",
            "label":     _("Debit = Credit"),
            "datatype":  "Data",
            "indicator": "Green" if balanced else "Red",
        },
    ]


# ── Trend chart ───────────────────────────────────────────────────────────────

def _get_chart(daily_totals):
    if not daily_totals:
        return None
    sorted_days = sorted(daily_totals)
    return {
        "data": {
            "labels":   [formatdate(d, "dd MMM") for d in sorted_days],
            "datasets": [{"name": _("Settlement Amount (₹)"), "values": [daily_totals[d] for d in sorted_days]}],
        },
        "type":        "bar",
        "colors":      ["#5e64ff"],
        "axisOptions": {"xIsSeries": True},
    }


# ── Razorpay API ──────────────────────────────────────────────────────────────

def _fetch_settlements(filters):
    api_key, api_secret = _get_credentials()
    auth    = (api_key, api_secret)
    from_ts = _date_to_unix(filters.get("from_date"), end_of_day=False)
    to_ts   = _date_to_unix(filters.get("to_date"),   end_of_day=True)

    settlements = []
    skip = 0

    while True:
        params = {"count": PAGE_SIZE, "skip": skip}
        if from_ts:
            params["from"] = from_ts
        if to_ts:
            params["to"] = to_ts

        resp = requests.get(f"{RAZORPAY_BASE}/settlements", auth=auth, params=params, timeout=30)
        _raise_for_status(resp)

        items = resp.json().get("items") or []
        settlements.extend(items)

        if len(items) < PAGE_SIZE:
            break
        skip += PAGE_SIZE

    return settlements


def _get_credentials():
    try:
        settings = frappe.get_doc("Razorpay Settings")
        key    = settings.api_key
        secret = settings.get_password("api_secret")
        if key and secret:
            return key, secret
    except Exception:
        pass

    key = secret = None
    for k_attr in ("razorpay_api_key", "razorpay_key_id"):
        key = frappe.conf.get(k_attr)
        if key:
            break
    for s_attr in ("razorpay_api_secret", "razorpay_key_secret"):
        secret = frappe.conf.get(s_attr)
        if secret:
            break

    if key and secret:
        return key, secret

    frappe.throw(
        _(
            "Razorpay API credentials not found. "
            "Configure them in <b>Razorpay Settings</b> or in "
            "<code>site_config.json</code> as "
            "<code>razorpay_api_key</code> / <code>razorpay_api_secret</code>."
        ),
        title=_("Missing Configuration"),
    )


def _raise_for_status(resp):
    if resp.status_code == 401:
        frappe.throw(
            _("Razorpay authentication failed. Check your API Key and Secret in <b>Razorpay Settings</b>."),
            title=_("Authentication Error"),
        )
    if not resp.ok:
        try:
            err = resp.json().get("error", {}).get("description", resp.text[:300])
        except Exception:
            err = resp.text[:300]
        frappe.throw(
            _("Razorpay API error {0}: {1}").format(resp.status_code, err),
            title=_("API Error"),
        )


# ── Utilities ─────────────────────────────────────────────────────────────────

def _unix_to_date(ts):
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).date()
    except Exception:
        return None


def _date_to_unix(date_str, end_of_day=False):
    if not date_str:
        return None
    try:
        from datetime import time as dtime
        d = getdate(date_str)
        t = dtime(23, 59, 59) if end_of_day else dtime(0, 0, 0)
        return int(datetime.combine(d, t).replace(tzinfo=timezone.utc).timestamp())
    except Exception:
        return None


def _format_zoho_date(val):
    try:
        return formatdate(val, "dd-MM-yyyy")
    except Exception:
        return str(val) if val else ""


def _cell(value, header):
    if value is None:
        return ""
    if header == "Journal Date":
        return _format_zoho_date(value)
    if header in ("Debit", "Credit", "Settlement Amount (₹)", "Settlement Amount"):
        v = flt(value)
        return v if v else ""
    return str(value) if value else ""


# ── Zoho Books export (whitelisted — called from JS buttons) ──────────────────

@frappe.whitelist()
def download_zoho_upload_file(filters=None, file_format="csv"):
    """
    Generate a Zoho Books–compatible journal upload file (14 required columns only).
    Hard-blocks export if Debit ≠ Credit (validation must pass).
    """
    import base64
    import json

    if isinstance(filters, str):
        try:
            filters = json.loads(filters)
        except Exception:
            filters = {}
    filters = filters or {}

    settlements = _fetch_settlements(filters)
    if not settlements:
        frappe.throw(_("No settlements found for the selected date range."))

    config  = _resolve_config(filters)
    fle_map = _build_fle_map(settlements, filters)
    rows, stats = _build_journal_rows(settlements, filters, config, fle_map)

    if not rows:
        frappe.throw(_("No journal rows matched the applied filters."))

    # ── Hard validation: block export if unbalanced ───────────────────────────
    if not stats["balanced"]:
        diff = round(stats["total_debit"] - stats["total_credit"], 2)
        frappe.throw(
            _(
                "Export blocked — journal is not balanced.<br>"
                "Total Debit: ₹{0} | Total Credit: ₹{1} | Difference: ₹{2}<br><br>"
                "This should not happen with correct Razorpay data. "
                "Check your filters or contact support."
            ).format(
                f"{stats['total_debit']:,.2f}",
                f"{stats['total_credit']:,.2f}",
                f"{diff:,.2f}",
            ),
            title=_("Validation Failed — Unbalanced Journal"),
        )

    # ── Always export exactly the 14 Zoho Books columns — no display columns ──
    headers   = ZOHO_HEADERS
    field_map = ZOHO_FIELD_MAP

    from_d     = filters.get("from_date", "")
    to_d       = filters.get("to_date", nowdate())
    date_label = f"{from_d}_{to_d}".strip("_") or nowdate()

    if file_format == "xlsx":
        content, filename, mime = _build_xlsx(rows, headers, field_map, date_label, stats, config)
    else:
        content, filename, mime = _build_csv(rows, headers, field_map, date_label)

    return {
        "filename":  filename,
        "content":   base64.b64encode(content).decode("utf-8"),
        "mime":      mime,
        "row_count": len(rows),
        "balanced":  stats["balanced"],
        "total_debit":  stats["total_debit"],
        "total_credit": stats["total_credit"],
    }


@frappe.whitelist()
def get_dynamic_defaults():
    """
    Return runtime defaults for the report filters.
    Called on page load to populate bank_account from Razorpay Settings.
    """
    bank_account   = DEFAULT_DEBIT_ACCOUNT
    credit_account = DEFAULT_CREDIT_ACCOUNT
    try:
        settings = frappe.get_doc("Razorpay Settings")
        if settings.get("merchant_account_name"):
            bank_account = settings.merchant_account_name
    except Exception:
        pass
    return {
        "bank_account":   bank_account,
        "credit_account": credit_account,
        "journal_prefix": DEFAULT_PREFIX,
        "department":     DEFAULT_DEPARTMENT,
        "course":         DEFAULT_COURSE,
    }


# ── CSV builder ───────────────────────────────────────────────────────────────

def _build_csv(rows, headers, field_map, date_label):
    import csv
    buf    = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for r in rows:
        writer.writerow([_cell(r.get(field_map[h]), h) for h in headers])
    content  = buf.getvalue().encode("utf-8-sig")   # BOM for Excel
    filename = f"zoho_journal_{date_label}.csv"
    return content, filename, "text/csv"


# ── XLSX builder ──────────────────────────────────────────────────────────────

def _build_xlsx(rows, headers, field_map, date_label, stats, config):
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        frappe.throw(_("openpyxl is not installed. Run: bench pip install openpyxl"))

    # ── Colour palette ────────────────────────────────────────────────────────
    PURPLE     = "5E64FF"
    PURPLE_DK  = "1A237E"
    WHITE      = "FFFFFF"
    CREDIT_BG  = "E8F5E9"   # light green  — credit rows
    DEBIT_BG   = "E3F2FD"   # light blue   — debit rows
    STRIPE_BG  = "F7F8FF"   # very light   — alternate rows
    TOTAL_BG   = "E8EAF6"
    OK_CLR     = "2E7D32"
    ERR_CLR    = "C62828"
    BORDER_CLR = "C5CAE9"

    def _side(style="thin"):
        return Side(style=style, color=BORDER_CLR)

    thin_b  = Border(left=_side(), right=_side(), top=_side(), bottom=_side())
    thick_b = Border(left=_side("medium"), right=_side("medium"),
                     top=_side("medium"), bottom=_side("medium"))

    balanced  = stats["balanced"]
    n_cols    = len(headers)
    debit_col  = next((i + 1 for i, h in enumerate(headers) if h == "Debit"),  None)
    credit_col = next((i + 1 for i, h in enumerate(headers) if h == "Credit"), None)

    wb = openpyxl.Workbook()

    # ════════════════════════════════════════════════════════════════════════
    # Sheet 1 — Journal Upload  (the actual Zoho Books import data)
    # ════════════════════════════════════════════════════════════════════════
    ws = wb.active
    ws.title = "Journal Upload"
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "C3"          # freeze Journal Date + Reference Number + header

    # ── Row 1: Title banner ──────────────────────────────────────────────────
    ws.row_dimensions[1].height = 32
    ws.append([""] * n_cols)

    dept   = config.get("department") or DEFAULT_DEPARTMENT
    course = config.get("course")     or DEFAULT_COURSE
    bank   = config.get("bank_account") or DEFAULT_DEBIT_ACCOUNT
    title_val = (
        f"Razorpay Settlement Journal  |  Zoho Books Import  |  "
        f"{date_label}  |  {dept} / {course}  |  Bank: {bank}"
    )
    tc = ws.cell(row=1, column=1, value=title_val)
    tc.font      = Font(bold=True, size=11, color=WHITE, name="Calibri")
    tc.fill      = PatternFill("solid", fgColor=PURPLE)
    tc.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n_cols)

    # ── Row 2: Column headers ────────────────────────────────────────────────
    ws.row_dimensions[2].height = 36
    ws.append(headers)
    for ci, h in enumerate(headers, 1):
        cell = ws.cell(row=2, column=ci)
        cell.font      = Font(bold=True, color=WHITE, size=10, name="Calibri")
        cell.fill      = PatternFill("solid", fgColor="3949AB")   # slightly darker header
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border    = thick_b

    # ── Rows 3+: Data ────────────────────────────────────────────────────────
    for ri, r in enumerate(rows, 3):
        rt = r.get("row_type", "")
        if rt == "Credit":
            bg = PatternFill("solid", fgColor=CREDIT_BG)
        elif rt == "Debit":
            bg = PatternFill("solid", fgColor=DEBIT_BG)
        else:
            bg = PatternFill("solid", fgColor=STRIPE_BG if ri % 2 == 0 else WHITE)

        ws.row_dimensions[ri].height = 16

        for ci, h in enumerate(headers, 1):
            val  = _cell(r.get(field_map[h]), h)
            cell = ws.cell(row=ri, column=ci, value=val)
            cell.fill   = bg
            cell.border = thin_b

            if h in ("Debit", "Credit"):
                cell.font          = Font(bold=bool(val), size=9, name="Calibri",
                                          color="1565C0" if h == "Debit" else "2E7D32")
                cell.number_format = "#,##0.00"
                cell.alignment     = Alignment(horizontal="right", vertical="center")
            elif h == "Journal Date":
                cell.font      = Font(size=9, name="Calibri")
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif h in ("Journal Number Suffix", "Journal Type", "Currency", "Department", "Course"):
                cell.font      = Font(size=9, name="Calibri")
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif h == "Account":
                clr = "6A1B9A" if rt == "Credit" else "1565C0"
                cell.font      = Font(size=9, name="Calibri", color=clr)
                cell.alignment = Alignment(vertical="center")
            else:
                cell.font      = Font(size=9, name="Calibri")
                cell.alignment = Alignment(vertical="center")

    # ── Total row ─────────────────────────────────────────────────────────────
    total_ri = len(rows) + 3
    ws.row_dimensions[total_ri].height = 22
    for ci in range(1, n_cols + 1):
        cell = ws.cell(row=total_ri, column=ci)
        cell.fill      = PatternFill("solid", fgColor=TOTAL_BG)
        cell.font      = Font(bold=True, size=10, name="Calibri", color=PURPLE_DK)
        cell.border    = thick_b
        cell.alignment = Alignment(horizontal="right", vertical="center")
        if ci == 1:
            cell.value     = "TOTAL"
            cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        elif ci == debit_col:
            cell.value         = stats["total_debit"]
            cell.number_format = "#,##0.00"
        elif ci == credit_col:
            cell.value         = stats["total_credit"]
            cell.number_format = "#,##0.00"

    # ── Balance validation row ────────────────────────────────────────────────
    bal_ri = total_ri + 1
    ws.row_dimensions[bal_ri].height = 20
    bal_text   = "✓  Debit = Credit — Balanced. Ready for Zoho Books import." if balanced \
                 else "✗  UNBALANCED — Do NOT import. Contact support."
    bal_colour = OK_CLR if balanced else ERR_CLR
    bc = ws.cell(row=bal_ri, column=1, value=bal_text)
    bc.font      = Font(bold=True, size=10, color=bal_colour, name="Calibri")
    bc.fill      = PatternFill("solid", fgColor="E8F5E9" if balanced else "FFEBEE")
    bc.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.merge_cells(start_row=bal_ri, start_column=1, end_row=bal_ri, end_column=n_cols)

    # ── Auto-size columns ─────────────────────────────────────────────────────
    for ci, h in enumerate(headers, 1):
        col_letter = get_column_letter(ci)
        vals   = [str(_cell(r.get(field_map[h]), h) or "") for r in rows]
        maxlen = max(len(str(h)), *(len(v) for v in vals)) if vals else len(str(h))
        # Notes column — cap narrower so the sheet isn't impossibly wide
        cap = 42 if h == "Notes" else 55
        ws.column_dimensions[col_letter].width = min(maxlen + 3, cap)

    # ════════════════════════════════════════════════════════════════════════
    # Sheet 2 — Summary
    # ════════════════════════════════════════════════════════════════════════
    ws2 = wb.create_sheet("Summary")
    ws2.sheet_view.showGridLines = False
    ws2.column_dimensions["A"].width = 34
    ws2.column_dimensions["B"].width = 26

    s_hdr_font = Font(bold=True, color=WHITE, size=10, name="Calibri")
    s_hdr_fill = PatternFill("solid", fgColor=PURPLE)
    s_lbl_font = Font(bold=True, size=10, name="Calibri", color="424242")
    s_val_font = Font(size=10, name="Calibri")
    s_ok_font  = Font(bold=True, size=10, name="Calibri", color=OK_CLR)
    s_err_font = Font(bold=True, size=10, name="Calibri", color=ERR_CLR)
    s_border   = Border(
        left=Side(style="thin", color="CCCCCC"), right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"),  bottom=Side(style="thin", color="CCCCCC"),
    )

    summary_rows = [
        ("Report Details", ""),
        ("Report Name",          "Razorpay Settlement Journal Upload"),
        ("Date Range",           date_label),
        ("Generated On",         nowdate()),
        ("", ""),
        ("Journal Configuration", ""),
        ("Credit Account",        config.get("credit_account") or DEFAULT_CREDIT_ACCOUNT),
        ("Bank Account (Debit)",  config.get("bank_account")   or DEFAULT_DEBIT_ACCOUNT),
        ("Journal Prefix",        config.get("prefix")         or DEFAULT_PREFIX),
        ("Department",            config.get("department")     or DEFAULT_DEPARTMENT),
        ("Course",                config.get("course")         or DEFAULT_COURSE),
        ("", ""),
        ("Settlement Statistics", ""),
        ("Total Settlements",     stats["total_settlements"]),
        ("Total Journal Rows",    stats["total_rows"]),
        ("Filtered Out",          stats.get("filtered_out", 0)),
        ("", ""),
        ("Amounts (INR)", ""),
        ("Total Settlement Amount", stats["total_amount"]),
        ("Total Debit",              stats["total_debit"]),
        ("Total Credit",             stats["total_credit"]),
        ("Difference (Debit − Credit)", round(stats["total_debit"] - stats["total_credit"], 2)),
        ("", ""),
        ("Validation", ""),
        ("Debit = Credit",   "YES — Balanced ✓" if balanced else "NO — UNBALANCED ✗"),
        ("Ready for Import", "YES" if balanced else "NO — Fix before importing"),
    ]

    # Title
    ws2.row_dimensions[1].height = 30
    t = ws2.cell(row=1, column=1, value="Zoho Books Journal Upload — Summary")
    t.font = Font(bold=True, size=13, color=PURPLE, name="Calibri")
    t.alignment = Alignment(horizontal="left", vertical="center")
    ws2.merge_cells("A1:B1")

    for ri, (label, value) in enumerate(summary_rows, 2):
        ws2.row_dimensions[ri].height = 18
        c_lbl = ws2.cell(row=ri, column=1, value=label)
        c_val = ws2.cell(row=ri, column=2, value=value)

        if not label:
            continue
        if value == "":
            c_lbl.font      = s_hdr_font
            c_lbl.fill      = s_hdr_fill
            c_lbl.alignment = Alignment(horizontal="left", vertical="center", indent=1)
            ws2.merge_cells(start_row=ri, start_column=1, end_row=ri, end_column=2)
            continue

        c_lbl.font      = s_lbl_font
        c_lbl.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        c_lbl.border    = s_border
        c_val.border    = s_border

        if label in ("Total Settlement Amount", "Total Debit", "Total Credit",
                     "Difference (Debit − Credit)"):
            c_val.number_format = "#,##0.00"
            c_val.font          = s_val_font
        elif label in ("Debit = Credit", "Ready for Import"):
            c_val.font = s_ok_font if balanced else s_err_font
        elif label in ("Total Settlements", "Total Journal Rows", "Filtered Out"):
            c_val.font = s_val_font
        else:
            c_val.font = s_val_font

        c_val.alignment = Alignment(
            horizontal="right" if isinstance(value, (int, float)) else "left",
            vertical="center",
        )

    # ════════════════════════════════════════════════════════════════════════
    # Sheet 3 — Import Instructions
    # ════════════════════════════════════════════════════════════════════════
    ws3 = wb.create_sheet("Import Instructions")
    ws3.sheet_view.showGridLines = False
    ws3.column_dimensions["A"].width = 90

    steps = [
        ("Zoho Books Journal Import — Step-by-step Guide", True),
        ("", False),
        ("Step 1 — Open the 'Journal Upload' sheet and verify the data.", False),
        ("Step 2 — Check 'Summary' sheet: Debit = Credit must show YES.", False),
        ("Step 3 — In Zoho Books: Accountant → Journal → ⋮ → Import Journals.", False),
        ("Step 4 — Upload this XLSX file (or the CSV version).", False),
        ("Step 5 — Map columns if prompted, preview and confirm the import.", False),
        ("", False),
        ("Column Reference", True),
        ("Journal Date          — dd-MM-yyyy  (e.g. 21-02-2026)", False),
        ("Reference Number      — Razorpay Settlement ID  (setl_xxx)", False),
        ("Journal Number Prefix — Prefix configured in report filters  (default: JN-FP-)", False),
        ("Journal Number Suffix — Auto-incremented integer", False),
        ("Notes                 — Includes bank account name and UTR for processed settlements", False),
        ("Account               — Must exactly match Zoho Books chart of accounts", False),
        ("Debit / Credit        — Only one value per row; the other is blank", False),
        ("Department            — As set in report filter  (default: PACE)", False),
        ("Course                — As set in report filter  (default: FLE)", False),
    ]

    for ri, (text, heading) in enumerate(steps, 1):
        ws3.row_dimensions[ri].height = 18
        cell = ws3.cell(row=ri, column=1, value=text)
        cell.font = (
            Font(bold=True, size=11, color=PURPLE, name="Calibri") if heading
            else Font(size=10, name="Calibri", color="424242")
        )
        cell.alignment = Alignment(vertical="center")

    buf = io.BytesIO()
    wb.save(buf)
    return (
        buf.getvalue(),
        f"zoho_journal_{date_label}.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
