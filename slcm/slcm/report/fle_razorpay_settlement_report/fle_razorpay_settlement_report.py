"""
FLE Razorpay Settlement Report

Data model: one row per recon item (individual payment/refund within a settlement).

API calls made:
  GET /v1/settlements                    – paginated list of settlements
  GET /v1/settlements/{id}/recon         – per-settlement item breakdown

Enrichment: local FLE Payment Log is joined by transaction_id (= Razorpay
payment ID = recon entity_id) to pull contact name, student ID, and
payment method stored by the webhook handler.

Authentication order:
  1. Razorpay Settings DocType  (api_key / api_secret)
  2. site_config.json / frappe.conf  (razorpay_api_key / razorpay_api_secret)
"""

import json
from datetime import datetime, timezone

import frappe
import requests
from frappe import _

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RAZORPAY_BASE = "https://api.razorpay.com/v1"
PAGE_SIZE      = 100          # max per page allowed by Razorpay
DEFAULT_ACCOUNT = "Foundation for Legal Education"
DEFAULT_COURSE  = "Foundations for a Legal Education"

# ---------------------------------------------------------------------------
# Report entry point
# ---------------------------------------------------------------------------


def execute(filters=None):
    filters = filters or {}
    columns = _get_columns()
    try:
        data, summary = _get_data(filters)
    except frappe.ValidationError:
        raise
    except Exception as exc:
        frappe.log_error(frappe.get_traceback(), "FLE Razorpay Settlement Report")
        frappe.throw(
            _("Failed to fetch settlements from Razorpay: {0}").format(str(exc)),
            title=_("API Error"),
        )
        return columns, []

    message = _build_summary_message(summary)
    return columns, data, message


# ---------------------------------------------------------------------------
# Columns
# ---------------------------------------------------------------------------


def _get_columns():
    return [
        {"label": _("Settlement ID"),         "fieldname": "settlement_id",      "fieldtype": "Data",     "width": 190},
        {"label": _("Entity ID"),             "fieldname": "entity_id",          "fieldtype": "Data",     "width": 190},
        {"label": _("Currency"),              "fieldname": "currency",           "fieldtype": "Data",     "width":  70},
        {"label": _("Amount (₹)"),            "fieldname": "amount",             "fieldtype": "Currency", "width": 120},
        {"label": _("Fees (₹)"),              "fieldname": "fees",               "fieldtype": "Currency", "width": 110},
        {"label": _("Tax (₹)"),              "fieldname": "tax",                "fieldtype": "Currency", "width": 100},
        {"label": _("Net Amount (₹)"),        "fieldname": "net_amount",         "fieldtype": "Currency", "width": 130},
        {"label": _("Payment Method"),        "fieldname": "payment_method",     "fieldtype": "Data",     "width": 130},
        {"label": _("Payment Notes"),         "fieldname": "payment_notes",      "fieldtype": "Data",     "width": 210},
        {"label": _("Account"),              "fieldname": "account",            "fieldtype": "Data",     "width": 230},
        {"label": _("Contact Name"),          "fieldname": "contact_name",       "fieldtype": "Data",     "width": 160},
        {"label": _("Debit"),                "fieldname": "debit",              "fieldtype": "Currency", "width": 120},
        {"label": _("Credit"),               "fieldname": "credit",             "fieldtype": "Currency", "width": 120},
        {"label": _("Course"),               "fieldname": "course",             "fieldtype": "Data",     "width": 230},
        {"label": _("Student ID"),            "fieldname": "student_id",         "fieldtype": "Data",     "width": 140},
        {"label": _("Status"),               "fieldname": "status",             "fieldtype": "Data",     "width": 110},
        {"label": _("UTR"),                  "fieldname": "utr",                "fieldtype": "Data",     "width": 170},
        {"label": _("Entity Created At"),     "fieldname": "entity_created_at",  "fieldtype": "Datetime", "width": 160},
        {"label": _("Payment Captured At"),   "fieldname": "payment_captured_at","fieldtype": "Datetime", "width": 165},
        {"label": _("Settlement Created"),    "fieldname": "created_date",       "fieldtype": "Datetime", "width": 155},
        {"label": _("Settlement Processed"),  "fieldname": "processed_date",     "fieldtype": "Datetime", "width": 165},
    ]


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


def _get_data(filters):
    api_key, api_secret = _get_credentials()
    auth = (api_key, api_secret)

    from_ts, to_ts = _date_filters_to_unix(filters)
    status_filter  = (filters.get("status") or "").strip().lower()

    settlements = _fetch_all_settlements(auth, from_ts, to_ts)

    if not settlements:
        frappe.msgprint(
            _("No settlements found from Razorpay for the selected filters."),
            indicator="blue",
            alert=True,
        )
        return [], {}

    # Build local enrichment map: razorpay_payment_id → {contact_name, student_id, …}
    local_map = _build_local_map()

    data = []
    total_amount = total_fees = total_tax = total_net = 0.0

    for s in settlements:
        sid             = s.get("id", "")
        utr             = s.get("utr") or ""
        status          = "settled" if utr else "pending"
        created_date    = _unix_to_datetime(s.get("created_at"))
        processed_date  = _unix_to_datetime(s.get("settlement_time") or s.get("created_at"))

        # Settlement-level amounts (paise → rupees) used as fallback
        s_amount = _paise_to_rupees(s.get("amount", 0))
        s_fees   = _paise_to_rupees(s.get("fees",   0))
        s_tax    = _paise_to_rupees(s.get("tax",    0))
        s_net    = round(s_amount - s_fees - s_tax, 2)

        if status_filter and status != status_filter:
            continue

        recon_items = _fetch_recon_items(auth, sid)

        # ── Fallback: no recon items → emit one settlement-level row ─────────
        if not recon_items:
            total_amount += s_amount
            total_fees   += s_fees
            total_tax    += s_tax
            total_net    += s_net
            data.append(_make_row(
                settlement_id=sid,
                entity_id="",
                amount=s_amount, fees=s_fees, tax=s_tax, net_amount=s_net,
                debit=s_amount, credit=s_net,
                payment_method="", payment_notes="",
                contact_name="", student_id="",
                status=status.capitalize(), utr=utr,
                entity_created_at=None, payment_captured_at=None,
                created_date=created_date, processed_date=processed_date,
            ))
            continue

        for item in recon_items:
            entity_id   = item.get("entity_id") or item.get("payment_id") or ""
            item_amount = _paise_to_rupees(item.get("amount", 0))
            item_fees   = _paise_to_rupees(item.get("fee",    0))
            item_tax    = _paise_to_rupees(item.get("tax",    0))
            net_amount  = round(item_amount - item_fees - item_tax, 2)

            # Use Razorpay-reported debit/credit when non-zero, else derive
            item_debit  = _paise_to_rupees(item.get("debit",  0))
            item_credit = _paise_to_rupees(item.get("credit", 0))
            debit  = item_debit  if item_debit  else item_amount
            credit = item_credit if item_credit else net_amount

            entity_created_at   = _unix_to_datetime(item.get("created_at"))
            payment_captured_at = _unix_to_datetime(item.get("posted_at") or item.get("settled_at"))
            item_utr            = item.get("settlement_utr") or utr

            recon_description = item.get("description") or item.get("order_receipt") or ""

            local           = local_map.get(entity_id) or {}
            contact_name    = local.get("contact_name",   "")
            student_id      = local.get("student_id",     "")
            payment_method  = local.get("payment_method", "")
            local_notes     = local.get("payment_notes",  "")
            payment_notes   = recon_description or local_notes

            total_amount += item_amount
            total_fees   += item_fees
            total_tax    += item_tax
            total_net    += net_amount

            data.append(_make_row(
                settlement_id=sid,
                entity_id=entity_id,
                amount=item_amount, fees=item_fees, tax=item_tax, net_amount=net_amount,
                debit=debit, credit=credit,
                payment_method=payment_method, payment_notes=payment_notes,
                contact_name=contact_name, student_id=student_id,
                status=status.capitalize(), utr=item_utr,
                entity_created_at=entity_created_at,
                payment_captured_at=payment_captured_at,
                created_date=created_date, processed_date=processed_date,
            ))

    summary = {
        "count":        len(data),
        "total_amount": round(total_amount, 2),
        "total_fees":   round(total_fees,   2),
        "total_tax":    round(total_tax,    2),
        "total_net":    round(total_net,    2),
    }
    return data, summary


# ---------------------------------------------------------------------------
# Row builder
# ---------------------------------------------------------------------------


def _make_row(
    settlement_id, entity_id,
    amount, fees, tax, net_amount,
    debit, credit,
    payment_method, payment_notes,
    contact_name, student_id,
    status, utr,
    entity_created_at, payment_captured_at,
    created_date, processed_date,
):
    return {
        "settlement_id":       settlement_id,
        "entity_id":           entity_id,
        "currency":            "INR",
        "amount":              amount,
        "fees":                fees,
        "tax":                 tax,
        "net_amount":          net_amount,
        "payment_method":      payment_method,
        "payment_notes":       payment_notes,
        "account":             DEFAULT_ACCOUNT,
        "contact_name":        contact_name,
        "debit":               debit,
        "credit":              credit,
        "course":              DEFAULT_COURSE,
        "student_id":          student_id,
        "status":              status,
        "utr":                 utr,
        "entity_created_at":   entity_created_at,
        "payment_captured_at": payment_captured_at,
        "created_date":        created_date,
        "processed_date":      processed_date,
    }


# ---------------------------------------------------------------------------
# Razorpay API helpers
# ---------------------------------------------------------------------------


def _fetch_all_settlements(auth, from_ts=None, to_ts=None):
    """Paginate through /v1/settlements and return all items."""
    settlements = []
    skip = 0

    while True:
        params = {"count": PAGE_SIZE, "skip": skip}
        if from_ts:
            params["from"] = from_ts
        if to_ts:
            params["to"] = to_ts

        resp = requests.get(
            f"{RAZORPAY_BASE}/settlements",
            auth=auth,
            params=params,
            timeout=30,
        )
        _raise_for_razorpay_error(resp)

        payload = resp.json()
        items   = payload.get("items", [])
        settlements.extend(items)

        if len(items) < PAGE_SIZE:
            break
        skip += PAGE_SIZE

    return settlements


def _fetch_recon_items(auth, settlement_id):
    """
    Fetch all recon items for a settlement from /v1/settlements/{id}/recon.
    Handles pagination internally.
    """
    items = []
    skip  = 0

    while True:
        resp = requests.get(
            f"{RAZORPAY_BASE}/settlements/{settlement_id}/recon",
            auth=auth,
            params={"count": PAGE_SIZE, "skip": skip},
            timeout=30,
        )

        # 404 means no recon data for this settlement – treat as empty
        if resp.status_code == 404:
            break

        _raise_for_razorpay_error(resp)

        payload    = resp.json()
        page_items = payload.get("items", [])
        items.extend(page_items)

        if len(page_items) < PAGE_SIZE:
            break
        skip += PAGE_SIZE

    return items


def _raise_for_razorpay_error(resp):
    if resp.status_code == 401:
        frappe.throw(
            _("Razorpay authentication failed. Check API Key and Secret in Razorpay Settings."),
            title=_("Authentication Error"),
        )
    if not resp.ok:
        frappe.throw(
            _("Razorpay API error {0}: {1}").format(resp.status_code, resp.text[:300]),
            title=_("API Error"),
        )


# ---------------------------------------------------------------------------
# Local enrichment
# ---------------------------------------------------------------------------


def _build_local_map():
    """
    Return dict keyed by Razorpay payment_id (= recon entity_id) from
    FLE Payment Log rows. Values carry contact / student / payment-method info.
    """
    if not frappe.db.table_exists("FLE Payment Log"):
        return {}

    rows = frappe.db.sql(
        """
        SELECT
            fpl.transaction_id           AS payment_id,
            fpl.full_name                AS contact_name,
            fpl.reference_no             AS student_id,
            fpl.gateway_response         AS gateway_response,
            fpl.account_number_or_upi_id AS upi_or_account
        FROM `tabFLE Payment Log` fpl
        WHERE fpl.transaction_id IS NOT NULL
          AND fpl.transaction_id != ''
        """,
        as_dict=True,
    )

    local_map = {}
    for row in rows:
        pid = row.payment_id
        if pid in local_map:
            continue
        method, notes = _parse_gateway_response(row.gateway_response, row.upi_or_account)
        local_map[pid] = {
            "contact_name":   row.contact_name or "",
            "student_id":     row.student_id   or "",
            "payment_method": method,
            "payment_notes":  notes,
        }
    return local_map


def _parse_gateway_response(gateway_response, upi_or_account):
    method = ""
    notes  = upi_or_account or ""

    if not gateway_response:
        return method, notes

    try:
        resp   = json.loads(gateway_response)
        entity = resp.get("payload", {}).get("payment", {}).get("entity", resp)

        method = entity.get("method") or ""
        parts  = []
        for key in ("bank", "wallet", "vpa", "description"):
            val = entity.get(key) or ""
            if val:
                parts.append(str(val))
        if parts:
            notes = " | ".join(parts)
    except Exception:
        pass

    return method.title() if method else "", notes


# ---------------------------------------------------------------------------
# Credential resolution
# ---------------------------------------------------------------------------


def _get_credentials():
    """
    Priority: Razorpay Settings DocType → site_config / frappe.conf
    """
    try:
        settings = frappe.get_doc("Razorpay Settings")
        key    = settings.api_key
        secret = settings.get_password("api_secret")
        if key and secret:
            return key, secret
    except Exception:
        pass

    key = secret = None
    for attr in ("razorpay_api_key", "razorpay_key_id"):
        key = frappe.conf.get(attr)
        if key:
            break
    for attr in ("razorpay_api_secret", "razorpay_key_secret"):
        secret = frappe.conf.get(attr)
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


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _paise_to_rupees(paise):
    try:
        return round(int(paise) / 100, 2)
    except (TypeError, ValueError):
        return 0.0


def _unix_to_datetime(ts):
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    except (TypeError, ValueError, OSError):
        return None


def _date_filters_to_unix(filters):
    from_ts = to_ts = None
    from_date = filters.get("from_date")
    to_date   = filters.get("to_date")

    if from_date:
        try:
            dt = datetime.strptime(str(from_date), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            from_ts = int(dt.timestamp())
        except ValueError:
            pass

    if to_date:
        try:
            dt = datetime.strptime(str(to_date), "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
            to_ts = int(dt.timestamp())
        except ValueError:
            pass

    return from_ts, to_ts


# ---------------------------------------------------------------------------
# Summary message
# ---------------------------------------------------------------------------


def _build_summary_message(summary):
    if not summary.get("count"):
        return None

    lines = [
        "<b>Summary</b>",
        f"Total Payments    : {summary['count']}",
        f"Total Amount (₹)  : {summary['total_amount']:,.2f}",
        f"Total Fees (₹)    : {summary['total_fees']:,.2f}",
        f"Total Tax (₹)     : {summary['total_tax']:,.2f}",
        f"Net Total (₹)     : {summary['total_net']:,.2f}",
    ]
    return "<br>".join(lines)
