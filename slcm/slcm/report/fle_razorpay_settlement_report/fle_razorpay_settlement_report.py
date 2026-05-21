"""
FLE Razorpay Settlement Report

Fetches live data directly from the Razorpay API on every run.

API calls:
  GET /v1/settlements                 – paginated settlement list with metadata
  GET /v1/settlements/recon/combined  – per-payment breakdown (requires year+month params)

Local enrichment: joins FLE Payment Log by transaction_id to get student name,
student ID, and payment method stored by the webhook handler.

Auth priority:
  1. Razorpay Settings DocType (api_key / api_secret)
  2. site_config.json (razorpay_api_key / razorpay_api_secret)
"""

import json
from datetime import datetime, timezone

import frappe
import requests
from frappe import _

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RAZORPAY_BASE   = "https://api.razorpay.com/v1"
PAGE_SIZE       = 100
RECON_PAGE_SIZE = 1000
DEFAULT_ACCOUNT = "Foundation for Legal Education"
DEFAULT_COURSE  = "Foundations for a Legal Education"

# ---------------------------------------------------------------------------
# Entry point
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
        {"label": _("Settlement ID"),        "fieldname": "settlement_id",      "fieldtype": "Data",     "width": 190},
        {"label": _("Transaction ID"),       "fieldname": "transaction_id",     "fieldtype": "Data",     "width": 190},
        {"label": _("Entity ID"),            "fieldname": "entity_id",          "fieldtype": "Data",     "width": 190},
        {"label": _("Currency"),             "fieldname": "currency",           "fieldtype": "Data",     "width":  70},
        {"label": _("Amount (₹)"),           "fieldname": "amount",             "fieldtype": "Currency", "width": 120},
        {"label": _("Fees (₹)"),             "fieldname": "fees",               "fieldtype": "Currency", "width": 110},
        {"label": _("Tax (₹)"),              "fieldname": "tax",                "fieldtype": "Currency", "width": 100},
        {"label": _("Net Amount (₹)"),       "fieldname": "net_amount",         "fieldtype": "Currency", "width": 130},
        {"label": _("Payment Method"),       "fieldname": "payment_method",     "fieldtype": "Data",     "width": 130},
        {"label": _("Payment Notes"),        "fieldname": "payment_notes",      "fieldtype": "Data",     "width": 210},
        {"label": _("Account"),              "fieldname": "account",            "fieldtype": "Data",     "width": 230},
        {"label": _("Contact Name"),         "fieldname": "contact_name",       "fieldtype": "Data",     "width": 160},
        {"label": _("Debit"),                "fieldname": "debit",              "fieldtype": "Currency", "width": 120},
        {"label": _("Credit"),               "fieldname": "credit",             "fieldtype": "Currency", "width": 120},
        {"label": _("Course"),               "fieldname": "course",             "fieldtype": "Data",     "width": 230},
        {"label": _("Student ID"),           "fieldname": "student_id",         "fieldtype": "Data",     "width": 140},
        {"label": _("Status"),               "fieldname": "status",             "fieldtype": "Data",     "width": 110},
        {"label": _("UTR"),                  "fieldname": "utr",                "fieldtype": "Data",     "width": 170},
        {"label": _("Entity Created At"),    "fieldname": "entity_created_at",  "fieldtype": "Datetime", "width": 160},
        {"label": _("Payment Captured At"),  "fieldname": "payment_captured_at","fieldtype": "Datetime", "width": 165},
        {"label": _("Settlement Created"),   "fieldname": "created_date",       "fieldtype": "Datetime", "width": 155},
        {"label": _("Settlement Processed"), "fieldname": "processed_date",     "fieldtype": "Datetime", "width": 165},
    ]


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


def _get_data(filters):
    # --- Validate dates -------------------------------------------------------
    from_date = filters.get("from_date")
    to_date   = filters.get("to_date")

    if from_date and to_date:
        try:
            fd = datetime.strptime(str(from_date), "%Y-%m-%d")
            td = datetime.strptime(str(to_date),   "%Y-%m-%d")
            if fd > td:
                frappe.throw(
                    _("From Date ({0}) cannot be after To Date ({1}). Please fix your date filters.").format(
                        from_date, to_date
                    ),
                    title=_("Invalid Date Range"),
                )
        except ValueError:
            pass

    api_key, api_secret = _get_credentials()
    auth = (api_key, api_secret)

    from_ts, to_ts = _date_filters_to_unix(from_date, to_date)

    # Client-side filters (applied after data is fetched from Razorpay)
    status_filter         = (filters.get("status")         or "").strip().lower()
    payment_method_filter = (filters.get("payment_method") or "").strip().lower()
    settlement_id_filter  = (filters.get("settlement_id")  or "").strip()
    search_filter         = (filters.get("search")         or "").strip().lower()
    min_amount_filter     = filters.get("min_amount") or 0
    max_amount_filter     = filters.get("max_amount") or 0
    missing_data_filter   = (filters.get("missing_data")   or "").strip().lower()

    # Step 1: fetch settlement list (metadata + UTR)
    settlements = _fetch_all_settlements(auth, from_ts, to_ts)

    if not settlements:
        frappe.msgprint(
            _("No settlements found from Razorpay for the selected date range."),
            indicator="blue",
            alert=True,
        )
        return [], {}

    setl_by_id  = {s["id"]: s for s in settlements if s.get("id")}
    setl_by_utr = {s["utr"]: s["id"] for s in settlements if s.get("utr")}

    # Step 2: fetch per-payment recon breakdown
    recon_items = _fetch_combined_recon(
        auth,
        settlement_ids=list(setl_by_id.keys()),
        from_date=from_date,
        to_date=to_date,
        settlements=settlements,
    )

    # Step 3: enrich from local FLE Payment Log
    local_map = _build_local_map()

    data = []
    total_amount = total_fees = total_tax = total_net = 0.0
    matched_settlement_ids = set()

    for item in recon_items:
        item_sid = (
            item.get("settlement_id")
            or setl_by_utr.get(item.get("settlement_utr", ""))
            or ""
        )
        s   = setl_by_id.get(item_sid) or {}
        utr = item.get("settlement_utr") or s.get("utr") or ""

        # A recon item is settled when it has a UTR (linked to a processed settlement)
        status = "settled" if utr else "pending"
        if status_filter and status != status_filter:
            continue

        # Settlement ID filter
        if settlement_id_filter and settlement_id_filter not in item_sid.lower():
            continue

        entity_id      = item.get("entity_id") or item.get("payment_id") or ""
        transaction_id = item.get("payment_id") or entity_id

        item_amount = _paise_to_rupees(item.get("amount", 0))
        item_fees   = _paise_to_rupees(item.get("fee",    0))
        item_tax    = _paise_to_rupees(item.get("tax",    0))
        net_amount  = round(item_amount - item_fees - item_tax, 2)

        # Amount range filter
        if min_amount_filter and item_amount < float(min_amount_filter):
            continue
        if max_amount_filter and item_amount > float(max_amount_filter):
            continue

        r_debit  = _paise_to_rupees(item.get("debit",  0))
        r_credit = _paise_to_rupees(item.get("credit", 0))
        debit  = r_debit  if r_debit  else item_amount
        credit = r_credit if r_credit else net_amount

        entity_created_at   = _unix_to_datetime(item.get("created_at"))
        payment_captured_at = _unix_to_datetime(item.get("posted_at") or item.get("settled_at"))

        notes_from_api = item.get("description") or item.get("order_receipt") or ""
        local          = local_map.get(transaction_id) or local_map.get(entity_id) or {}
        contact_name   = local.get("contact_name",   "")
        student_id     = local.get("student_id",     "")
        payment_method = local.get("payment_method", "")
        payment_notes  = notes_from_api or local.get("payment_notes", "")

        # Payment method filter
        if payment_method_filter and payment_method_filter not in payment_method.lower():
            continue

        # Search filter — name, student ID, transaction ID, UTR
        if search_filter:
            haystack = " ".join([
                contact_name, student_id, transaction_id, entity_id, utr, payment_notes
            ]).lower()
            if search_filter not in haystack:
                continue

        # Missing data filter
        if missing_data_filter == "contact name is blank"  and contact_name:
            continue
        if missing_data_filter == "contact name is filled" and not contact_name:
            continue
        if missing_data_filter == "student id is blank"    and student_id:
            continue
        if missing_data_filter == "student id is filled"   and not student_id:
            continue
        if missing_data_filter == "payment method is blank"  and payment_method:
            continue
        if missing_data_filter == "payment method is filled" and not payment_method:
            continue

        created_date   = _unix_to_datetime(s.get("created_at"))
        processed_date = _unix_to_datetime(s.get("settlement_time") or s.get("created_at"))

        total_amount += item_amount
        total_fees   += item_fees
        total_tax    += item_tax
        total_net    += net_amount
        matched_settlement_ids.add(item_sid)

        data.append(_make_row(
            settlement_id=item_sid,
            transaction_id=transaction_id,
            entity_id=entity_id,
            amount=item_amount, fees=item_fees, tax=item_tax, net_amount=net_amount,
            debit=debit, credit=credit,
            payment_method=payment_method, payment_notes=payment_notes,
            contact_name=contact_name, student_id=student_id,
            status=status.capitalize(), utr=utr,
            entity_created_at=entity_created_at,
            payment_captured_at=payment_captured_at,
            created_date=created_date, processed_date=processed_date,
        ))

    # Step 4: fallback rows for settlements that had no recon items
    for s in settlements:
        sid = s.get("id", "")
        if sid in matched_settlement_ids:
            continue

        utr    = s.get("utr") or ""
        status = "settled" if utr else "pending"
        if status_filter and status != status_filter:
            continue
        if settlement_id_filter and settlement_id_filter not in sid.lower():
            continue

        s_amount = _paise_to_rupees(s.get("amount", 0))
        s_fees   = _paise_to_rupees(s.get("fees",   0))
        s_tax    = _paise_to_rupees(s.get("tax",    0))
        s_net    = round(s_amount - s_fees - s_tax, 2)

        total_amount += s_amount
        total_fees   += s_fees
        total_tax    += s_tax
        total_net    += s_net

        data.append(_make_row(
            settlement_id=sid,
            transaction_id="", entity_id="",
            amount=s_amount, fees=s_fees, tax=s_tax, net_amount=s_net,
            debit=s_amount, credit=s_net,
            payment_method="", payment_notes="",
            contact_name="", student_id="",
            status=status.capitalize(), utr=utr,
            entity_created_at=None, payment_captured_at=None,
            created_date=_unix_to_datetime(s.get("created_at")),
            processed_date=_unix_to_datetime(s.get("settlement_time") or s.get("created_at")),
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
    settlement_id, transaction_id, entity_id,
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
        "transaction_id":      transaction_id,
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


def _fetch_combined_recon(auth, settlement_ids, from_date=None, to_date=None, settlements=None):
    """
    Fetch payment-level items from GET /v1/settlements/recon/combined.

    - Requires year + month query params (Razorpay limitation — no from/to timestamps).
    - Iterates each year-month in the requested date range.
    - Keeps only items whose settlement_id is in our target set.
    - Items with settlement_id=None are included when they belong to a settlement
      that exists in our set (matched via settlement_utr).
    - Returns [] gracefully when the endpoint is not enabled (404).
    """
    if not settlement_ids:
        return []

    target_ids  = set(settlement_ids)
    year_months = _resolve_year_months(from_date, to_date, settlements)

    if not year_months:
        return []

    # Build UTR → settlement_id map so we can match items that lack settlement_id
    utr_to_sid = {}
    if settlements:
        for s in settlements:
            if s.get("utr") and s.get("id"):
                utr_to_sid[s["utr"]] = s["id"]

    seen_entity_ids = set()
    all_items       = []

    for year, month in year_months:
        skip = 0
        while True:
            resp = requests.get(
                f"{RAZORPAY_BASE}/settlements/recon/combined",
                auth=auth,
                params={"year": year, "month": month, "count": RECON_PAGE_SIZE, "skip": skip},
                timeout=60,
            )

            if resp.status_code == 404:
                # Feature not enabled on this Razorpay account — return what we have
                return all_items

            _raise_for_razorpay_error(resp)

            payload    = resp.json()
            page_items = payload.get("items", [])

            for item in page_items:
                sid = item.get("settlement_id")

                # Try to resolve settlement_id from UTR when it's missing
                if not sid:
                    utr = item.get("settlement_utr") or ""
                    sid = utr_to_sid.get(utr)

                # Only keep items belonging to our settlements
                if sid not in target_ids:
                    continue

                # Attach resolved settlement_id back to the item for downstream use
                if not item.get("settlement_id") and sid:
                    item["settlement_id"] = sid

                eid = item.get("entity_id") or item.get("payment_id") or ""
                if eid and eid in seen_entity_ids:
                    continue
                if eid:
                    seen_entity_ids.add(eid)

                all_items.append(item)

            if len(page_items) < RECON_PAGE_SIZE:
                break
            skip += RECON_PAGE_SIZE

    return all_items


def _resolve_year_months(from_date, to_date, settlements):
    """
    Return a sorted list of (year, month) tuples covering the requested range.

    Priority:
      1. from_date / to_date filter strings ("YYYY-MM-DD")
      2. Derived from the settlement created_at timestamps (fallback)
    """
    year_months = set()

    if from_date and to_date:
        try:
            start = datetime.strptime(str(from_date), "%Y-%m-%d")
            end   = datetime.strptime(str(to_date),   "%Y-%m-%d")
            # Ensure we never iterate backwards
            if start <= end:
                y, m = start.year, start.month
                while (y, m) <= (end.year, end.month):
                    year_months.add((y, m))
                    m += 1
                    if m > 12:
                        m = 1
                        y += 1
        except ValueError:
            pass
    elif from_date:
        try:
            d = datetime.strptime(str(from_date), "%Y-%m-%d")
            year_months.add((d.year, d.month))
        except ValueError:
            pass

    if not year_months and settlements:
        for s in settlements:
            ts = s.get("created_at")
            if ts:
                try:
                    dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
                    year_months.add((dt.year, dt.month))
                except Exception:
                    pass

    return sorted(year_months)


def _raise_for_razorpay_error(resp):
    if resp.status_code == 401:
        frappe.throw(
            _(
                "Razorpay authentication failed. "
                "Check your API Key and Secret in <b>Razorpay Settings</b>."
            ),
            title=_("Authentication Error"),
        )
    if not resp.ok:
        try:
            err_body = resp.json().get("error", {}).get("description", resp.text[:300])
        except Exception:
            err_body = resp.text[:300]
        frappe.throw(
            _("Razorpay API error {0}: {1}").format(resp.status_code, err_body),
            title=_("API Error"),
        )


# ---------------------------------------------------------------------------
# Local enrichment from FLE Payment Log
# ---------------------------------------------------------------------------


def _build_local_map():
    """
    Return a dict keyed by Razorpay pay_xxx ID → {contact_name, student_id, payment_method, payment_notes}
    built from ALL FLE Payment Log rows.

    Key resolution order per row:
      1. transaction_id field (set directly on insert when available)
      2. razorpay_payment_id extracted from gateway_response JSON
         (Integration Request data format: {"razorpay_payment_id": "pay_xxx", ...})
      3. id inside gateway_response payload.payment.entity (webhook format)
    """
    if not frappe.db.table_exists("FLE Payment Log"):
        return {}

    rows = frappe.db.sql(
        """
        SELECT
            transaction_id           AS transaction_id,
            full_name                AS contact_name,
            reference_no             AS student_id,
            gateway_response,
            account_number_or_upi_id AS upi_or_account
        FROM `tabFLE Payment Log`
        """,
        as_dict=True,
    )

    local_map = {}
    for row in rows:
        # Resolve the Razorpay pay_xxx ID
        pid = (row.transaction_id or "").strip()

        if not pid or not pid.startswith("pay_"):
            # transaction_id is blank or a bank RRN — extract pay_xxx from gateway_response
            pid = _extract_razorpay_pid(row.gateway_response)

        if not pid:
            continue
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


def _extract_razorpay_pid(gateway_response):
    """Extract a Razorpay pay_xxx ID from the gateway_response JSON blob."""
    if not gateway_response:
        return ""
    try:
        data = json.loads(gateway_response)
        # Format 1: Integration Request data {"razorpay_payment_id": "pay_xxx"}
        pid = data.get("razorpay_payment_id") or ""
        if pid and pid.startswith("pay_"):
            return pid
        # Format 2: webhook payload {"payload": {"payment": {"entity": {"id": "pay_xxx"}}}}
        pid = data.get("payload", {}).get("payment", {}).get("entity", {}).get("id") or ""
        if pid and pid.startswith("pay_"):
            return pid
    except Exception:
        pass
    return ""


def _parse_gateway_response(gateway_response, upi_or_account):
    method = ""
    notes  = upi_or_account or ""

    if not gateway_response:
        return method, notes

    try:
        resp   = json.loads(gateway_response)
        # Support both webhook-style payload and raw Razorpay payment objects
        entity = resp.get("payload", {}).get("payment", {}).get("entity", resp)
        method = entity.get("method") or ""
        parts  = [
            str(entity[k])
            for k in ("bank", "wallet", "vpa", "description")
            if entity.get(k)
        ]
        if parts:
            notes = " | ".join(parts)
    except Exception:
        pass

    return method.title() if method else "", notes


# ---------------------------------------------------------------------------
# Credential resolution
# ---------------------------------------------------------------------------


def _get_credentials():
    """Priority: Razorpay Settings DocType → site_config.json / frappe.conf"""
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
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError):
        return None


def _date_filters_to_unix(from_date, to_date):
    from_ts = to_ts = None
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
    return "<br>".join([
        "<b>Summary</b>",
        f"Total Payments    : {summary['count']}",
        f"Total Amount (₹)  : {summary['total_amount']:,.2f}",
        f"Total Fees (₹)    : {summary['total_fees']:,.2f}",
        f"Total Tax (₹)     : {summary['total_tax']:,.2f}",
        f"Net Total (₹)     : {summary['total_net']:,.2f}",
    ])
