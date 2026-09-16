# Copyright (c) 2026, Azim Premji Foundation and contributors
# For license information, please see license.txt
"""
Fee Payment Zoho Journal Upload Report

Data source: the Razorpay Settlements API is the PRIMARY source of truth —
not local Fee Payment records. Local Fee Payment is used to enrich each
Razorpay payment with its fee-component breakdown, student name, and
department/course. Only Razorpay payments that match a local Fee Payment
(by reference_number) appear in this report — this is deliberately an
SLCM fee reconciliation report, not a general Razorpay ledger, so
unmatched Razorpay activity (other payments the account processes) never
shows up here.

Flow:
  1. Fetch settlements from /v1/settlements for the date range.
  2. Fetch per-payment recon items from /v1/settlements/recon/combined —
     gives each settlement's individual payments (entity_id = pay_xxx).
  3. For each recon item, look up the local Fee Payment whose
     reference_number matches that pay_xxx (any status except Cancelled)
     to get its fee-component breakdown via its Fee Demands. Items with no
     local match are dropped from the report entirely.
  4. Emit one Credit row per Fee Component per matched payment, plus one
     Debit row per SETTLEMENT for the sum of ITS MATCHED payments only
     (not the settlement's full Razorpay gross, which may include other,
     unrelated payments) — one bank credit per settlement, regardless of
     how many matched payments make it up.

Journal amounts:
  Sum of a settlement's Credit rows == that settlement's Debit row amount,
  so every settlement is balanced on its own.
"""

import io
import json
import time
from datetime import datetime, timezone

import frappe
import requests
from frappe import _
from frappe.utils import flt, formatdate, getdate, nowdate

# ── Razorpay API ──────────────────────────────────────────────────────────────
RAZORPAY_BASE = "https://api.razorpay.com/v1"
PAGE_SIZE     = 100
RECON_PG_SIZE = 1000

# The recon API is fetched once per calendar month covered by the date
# range; each call takes several seconds. Months are fetched CONCURRENTLY
# (see _fetch_recon_items) so a wide date range costs roughly one month's
# latency, not N months' — this just bounds how many run at once so a huge
# range (e.g. several years) doesn't open an unreasonable number of sockets.
MAX_RECON_WORKERS = 8

# ── Constants ─────────────────────────────────────────────────────────────────
DEFAULT_BANK_ACCOUNT = "UBI Bank General"
DEFAULT_PREFIX        = "JN-FP-"
DEFAULT_JOURNAL_TYPE  = "Both"
DEFAULT_CURRENCY      = "INR"
DEFAULT_DESCRIPTION   = "Fee Payment"
DEFAULT_DEPARTMENT    = ""
DEFAULT_COURSE        = ""

# Zoho Books required column order — do NOT change.
# NOTE: "Date of Settlement", "Settlement Reference No" and "Contact" are display
# labels only — they still map to the same underlying values (payment_date,
# reference_number) that Zoho's own template calls "Journal Date" and
# "Reference Number". Renaming them here means the exported file's header row
# will no longer match Zoho's default import template exactly.
# "Contact" is a fixed constant value ("Frappe") on every row, by request —
# the actual Student Master ID and display name are available separately in
# the trailing "Student ID" / "Student Name" columns below.
CONTACT_VALUE = "Frappe"
ZOHO_HEADERS = [
    "Date of Settlement", "Settlement Reference No", "Journal Number Prefix",
    "Journal Number Suffix", "Notes", "Journal Type", "Currency",
    "Account", "Description", "Contact", "Debit", "Credit",
    "Department", "Course",
]
ZOHO_FIELD_MAP = {
    "Date of Settlement":      "journal_date",
    "Settlement Reference No": "reference_number",
    "Journal Number Prefix":   "journal_number_prefix",
    "Journal Number Suffix":   "journal_number_suffix",
    "Notes":                   "notes",
    "Journal Type":            "journal_type",
    "Currency":                "currency",
    "Account":                 "account",
    "Description":             "description",
    "Contact":                 "contact_name",
    "Debit":                   "debit",
    "Credit":                  "credit",
    "Department":              "department",
    "Course":                  "course",
}

# Extra columns appended AFTER the 14 Zoho columns — for readability in Excel
# only. Zoho's importer reads columns by position/header among the 14 above
# and ignores anything past them, so these are safe to add without breaking
# the Zoho Books import mapping.
EXTRA_HEADERS = ["Student ID", "Student Name"]
EXTRA_FIELD_MAP = {
    "Student ID":   "student_id",
    "Student Name": "student_display_name",
}


# ── Entry point ───────────────────────────────────────────────────────────────

def execute(filters=None):
    # Defense in depth: frappe.desk.query_report.run() already enforces the
    # Report doctype's `roles` list before calling execute() when the report
    # is opened normally, but this check keeps behavior consistent with the
    # whitelisted export/defaults endpoints below, which do NOT get that
    # protection for free.
    _check_report_permission()

    filters = filters or {}
    config  = _resolve_config(filters)
    view    = (filters.get("view") or "Single Transactions").strip()

    try:
        settlements = _fetch_settlements(filters)
    except frappe.ValidationError:
        raise
    except Exception as exc:
        frappe.log_error(frappe.get_traceback(), "Fee Payment Zoho Journal Upload — Razorpay API")
        frappe.throw(
            _("Failed to fetch settlements from Razorpay: {0}").format(str(exc)),
            title=_("API Error"),
        )
        return _get_columns(view), [], None, None, []

    if not settlements:
        frappe.msgprint(
            _("No Razorpay settlements found for the selected date range."),
            indicator="orange", alert=True,
        )
        return _get_columns(view), [], None, None, []

    api_key, api_secret = _get_razorpay_credentials_or_throw()
    recon_items = _fetch_recon_items(auth=(api_key, api_secret), settlements=settlements)

    fee_payment_by_pay_id = _lookup_fee_payments_by_reference(
        {(item.get("entity_id") or item.get("payment_id") or "").strip() for item in recon_items}
    )

    rows, stats = _build_journal_rows(settlements, recon_items, fee_payment_by_pay_id, filters, config)

    if not rows:
        frappe.msgprint(
            _("No Razorpay payments in this date range matched a local Fee Payment record."),
            indicator="orange", alert=True,
        )
        return _get_columns(view), [], None, None, []

    if view == "Day Transactions":
        day_rows, day_stats = _build_day_rows(rows, config)
        return (
            _get_columns(view),
            day_rows,
            None,
            _get_chart(_daily_totals_from_rows(day_rows)),
            _get_report_summary(day_stats, view),
        )

    return (
        _get_columns(view),
        rows,
        None,
        _get_chart(stats["daily"]),
        _get_report_summary(stats, view),
    )


# ── Columns ───────────────────────────────────────────────────────────────────

def _get_columns(view="Single Transactions"):
    columns = [
        {"label": _("Date of Settlement"),      "fieldname": "journal_date",          "fieldtype": "Date",     "width": 130},
        {"label": _("Settlement Reference No"), "fieldname": "reference_number",      "fieldtype": "Data",     "width": 170},
        {"label": _("Journal Number Prefix"),   "fieldname": "journal_number_prefix", "fieldtype": "Data",     "width": 145},
        {"label": _("Journal Number Suffix"),   "fieldname": "journal_number_suffix", "fieldtype": "Int",      "width": 145},
        {"label": _("Notes"),                   "fieldname": "notes",                 "fieldtype": "Data",     "width": 340},
        {"label": _("Journal Type"),            "fieldname": "journal_type",          "fieldtype": "Data",     "width":  85},
        {"label": _("Currency"),                "fieldname": "currency",              "fieldtype": "Data",     "width":  75},
        {"label": _("Account"),                 "fieldname": "account",               "fieldtype": "Data",     "width": 260},
        {"label": _("Description"),             "fieldname": "description",           "fieldtype": "Data",     "width": 100},
        # "Contact" is a fixed constant value ("Frappe") on every row, by
        # request — the actual Student Master ID/name are separate columns.
        {"label": _("Contact"),                 "fieldname": "contact_name",          "fieldtype": "Data",     "width": 100},
        {"label": _("Debit"),                   "fieldname": "debit",                 "fieldtype": "Currency", "width": 130},
        {"label": _("Credit"),                  "fieldname": "credit",                "fieldtype": "Currency", "width": 130},
        {"label": _("Department"),              "fieldname": "department",            "fieldtype": "Data",     "width": 110},
        {"label": _("Course"),                  "fieldname": "course",                "fieldtype": "Data",     "width": 130},
        # Display-only (never exported to Zoho)
        {"label": _("Row Type"),                "fieldname": "row_type",              "fieldtype": "Data",     "width":  85},
        {"label": _("Student ID"),              "fieldname": "student_id",
         "fieldtype": "Link" if view != "Day Transactions" else "Data",
         "options": "Student Master" if view != "Day Transactions" else None,
         "width": 140},
        {"label": _("Student Name"),            "fieldname": "student_display_name",  "fieldtype": "Data",    "width": 140},
    ]
    return columns


# ── Dynamic config ────────────────────────────────────────────────────────────

def _resolve_config(filters):
    return {
        "bank_account": (filters.get("bank_account") or "").strip() or DEFAULT_BANK_ACCOUNT,
        "prefix":       (filters.get("journal_prefix") or "").strip() or DEFAULT_PREFIX,
        "department":   (filters.get("department") or "").strip() or DEFAULT_DEPARTMENT,
        "course":       (filters.get("course") or "").strip() or DEFAULT_COURSE,
    }


# ── Razorpay settlement fetch ─────────────────────────────────────────────────

def _fetch_settlements(filters):
    api_key, api_secret = _get_razorpay_credentials_or_throw()
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


def _fetch_recon_items(auth, settlements):
    """
    Fetch per-payment recon from /v1/settlements/recon/combined, for the
    year/months these settlements fall in. Each item is one payment
    (entity_id = pay_xxx) within a settlement (settlement_id / settlement_utr).
    Returns [] gracefully if recon isn't enabled for this account (every
    month's call 404s).

    Months are fetched CONCURRENTLY (one HTTP round-trip is the dominant
    cost per month, and months are fully independent queries) — a 12-month
    range takes roughly as long as the single slowest month, not 12x that,
    so there's no need to cap how wide a date range can be.
    """
    if not settlements:
        return []

    target_sids = {s["id"] for s in settlements if s.get("id")}
    utr_to_sid  = {
        s["utr"]: s["id"]
        for s in settlements
        if s.get("utr") and s.get("id")
    }
    year_months = _year_months_from_settlements(settlements)
    if not year_months:
        return []

    import concurrent.futures

    results_by_month = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(year_months), MAX_RECON_WORKERS)) as pool:
        futures = {
            pool.submit(_fetch_recon_items_for_month, auth, year, month): (year, month)
            for year, month in year_months
        }
        for future in concurrent.futures.as_completed(futures):
            year, month = futures[future]
            try:
                results_by_month[(year, month)] = future.result()
            except Exception as exc:
                frappe.throw(
                    _("Failed to fetch Razorpay reconciliation data for {0}-{1}: {2}").format(
                        year, str(month).zfill(2), str(exc)
                    ),
                    title=_("API Error"),
                )

    # If every month says "recon not enabled" (404), the account simply
    # doesn't have recon — return [] rather than treating it as an error.
    if all(v is None for v in results_by_month.values()):
        return []

    seen_eids = set()
    all_items = []

    for year, month in year_months:
        items = results_by_month.get((year, month)) or []
        for item in items:
            sid = item.get("settlement_id") or ""
            if not sid:
                utr = item.get("settlement_utr") or ""
                sid = utr_to_sid.get(utr) or ""
            if sid not in target_sids:
                continue
            if not item.get("settlement_id") and sid:
                item["settlement_id"] = sid

            eid = (item.get("entity_id") or item.get("payment_id") or "").strip()
            if eid:
                if eid in seen_eids:
                    continue
                seen_eids.add(eid)

            all_items.append(item)

    return all_items


def _fetch_recon_items_for_month(auth, year, month):
    """
    Fetch every page of recon items for one (year, month). Runs inside a
    worker thread — must not call frappe.throw/msgprint (not safe off the
    main request thread); returns None to signal "recon not enabled this
    month" (404), or a plain list of raw items otherwise. Pagination within
    a month stays sequential (each page's `skip` depends on the page-size
    check of the previous one) — only different months run concurrently.

    Fetching several months concurrently can trip Razorpay's per-second
    rate limit (HTTP 429) on whichever month's request lands last — retried
    with backoff (honoring Retry-After when present) rather than silently
    treated as "no more pages", which would return incomplete data for that
    month without any error ever surfacing.
    """
    items_for_month = []
    skip = 0
    while True:
        resp = _get_with_retry(
            f"{RAZORPAY_BASE}/settlements/recon/combined",
            auth=auth,
            params={"year": year, "month": month,
                    "count": RECON_PG_SIZE, "skip": skip},
            timeout=60,
        )

        if resp.status_code == 404:
            return None
        if not resp.ok:
            raise RuntimeError(
                f"Razorpay recon fetch failed for {year}-{month:02d}: "
                f"HTTP {resp.status_code} — {resp.text[:200]}"
            )

        items = resp.json().get("items") or []
        items_for_month.extend(items)

        if len(items) < RECON_PG_SIZE:
            break
        skip += RECON_PG_SIZE

    return items_for_month


def _get_with_retry(url, auth, params, timeout, max_retries=5):
    """
    GET with retry-with-backoff on HTTP 429 (rate limited), honoring the
    Retry-After header when Razorpay sends one. Any other response
    (success, 404, or a genuine error) is returned as-is on the first try —
    only rate limiting is worth retrying here.
    """
    for attempt in range(max_retries + 1):
        resp = requests.get(url, auth=auth, params=params, timeout=timeout)
        if resp.status_code != 429 or attempt == max_retries:
            return resp
        wait = flt(resp.headers.get("Retry-After") or (attempt + 1))
        time.sleep(min(wait, 10))
    return resp


def _year_months_from_settlements(settlements):
    year_months = set()
    for s in settlements:
        ts = s.get("created_at")
        if ts:
            try:
                dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
                year_months.add((dt.year, dt.month))
            except Exception:
                pass
    return sorted(year_months)


def _get_razorpay_credentials_or_throw():
    """
    Same resolution order as razorpay_settlement_journal_upload.py: Razorpay
    Settings doctype first, then site_config.json keys. Unlike the Fee
    Payment lookup used to have, this report's ENTIRE dataset now comes from
    Razorpay, so a missing configuration must stop the report with a clear
    message rather than silently returning nothing.
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


def _unix_to_date(ts):
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).date()
    except Exception:
        return None


# ── Local Fee Payment enrichment ──────────────────────────────────────────────

def _lookup_fee_payments_by_reference(pay_ids):
    """
    Find the local Fee Payment (if any) whose reference_number matches each
    Razorpay pay_xxx, and load its fee-component breakdown, student name,
    and department/course. Payments recorded purely in Razorpay with no
    local Fee Payment (or vice versa) are handled by the caller — this
    just returns whatever local matches exist.

    Matches regardless of Fee Payment status (Draft included) — Razorpay
    already settled the money, so a match shouldn't be dropped just because
    someone hasn't clicked Submit locally yet. Only Cancelled records are
    excluded, since those represent payments that were reversed/voided.

    Returns dict: pay_xxx -> {fee_payment, student, student_name, program,
    department, components: [(account_name, amount), ...]}
    """
    pay_ids = {p for p in pay_ids if p}
    if not pay_ids:
        return {}

    payments = frappe.db.sql(
        """
        SELECT
            fp.name              AS fee_payment,
            fp.reference_number  AS reference_number,
            fp.student            AS student,
            fp.student_name       AS student_name,
            fp.program            AS program,
            fp.amount             AS amount
        FROM `tabFee Payment` fp
        WHERE fp.reference_number IN %(pay_ids)s
          AND fp.status != 'Cancelled'
        """,
        {"pay_ids": list(pay_ids)},
        as_dict=True,
    )
    if not payments:
        return {}

    payment_names = [p.fee_payment for p in payments]
    demand_rows = frappe.db.sql(
        """
        SELECT
            fpdr.parent            AS fee_payment,
            fpdr.amount_allocated  AS amount_allocated,
            fd.fee_component       AS fee_component,
            fd.description         AS demand_description
        FROM `tabFee Payment Demand Row` fpdr
        LEFT JOIN `tabFee Demand` fd ON fd.name = fpdr.fee_demand
        WHERE fpdr.parent IN %(names)s
        """,
        {"names": payment_names},
        as_dict=True,
    )
    demands_by_payment = {}
    for row in demand_rows:
        demands_by_payment.setdefault(row.fee_payment, []).append(row)

    programs = {p.program for p in payments if p.program}
    dept_by_program = {}
    if programs:
        for r in frappe.db.get_all(
            "Programme", filters={"name": ["in", list(programs)]},
            fields=["name", "department"],
        ):
            dept_by_program[r.name] = r.department or ""

    component_names = {
        d.fee_component for rows in demands_by_payment.values() for d in rows if d.fee_component
    }
    ledger_by_component = {}
    if component_names:
        for r in frappe.db.get_all(
            "Fee Component", filters={"name": ["in", list(component_names)]},
            fields=["name", "ledger"],
        ):
            ledger_by_component[r.name] = r.ledger or ""

    result = {}
    for p in payments:
        demands = demands_by_payment.get(p.fee_payment, [])
        result[p.reference_number] = {
            "fee_payment":  p.fee_payment,
            "student":      p.student,
            "student_name": p.student_name or "",
            "program":      p.program or "",
            "department":   dept_by_program.get(p.program, ""),
            "components":   _split_by_component(demands, ledger_by_component, flt(p.amount)),
        }
    return result


def _split_by_component(demands, ledger_by_component, payment_amount):
    """Group a payment's allocated demand amounts by Fee Component.
    Returns a list of (account_name, amount) tuples.
    """
    totals = {}
    for d in demands:
        comp   = d.fee_component or d.demand_description or "Unallocated Fee"
        ledger = ledger_by_component.get(d.fee_component, "") if d.fee_component else ""
        account_name = ledger or comp
        totals[account_name] = totals.get(account_name, 0) + flt(d.amount_allocated)

    # Guard against demand allocations not summing to the full payment amount
    # (partial allocation / unlinked balance) — plug the gap as "Unallocated Fee"
    allocated_total = round(sum(totals.values()), 2)
    remainder = round(payment_amount - allocated_total, 2)
    if abs(remainder) >= 0.01:
        totals["Unallocated Fee"] = totals.get("Unallocated Fee", 0) + remainder

    return [(k, v) for k, v in totals.items() if abs(v) >= 0.01]


# ── Journal row builder ───────────────────────────────────────────────────────

def _build_journal_rows(settlements, recon_items, fee_payment_by_pay_id, filters, config):
    """
    One Credit row per Fee Component per payment, sourced only from Razorpay
    payments that matched a local Fee Payment record (by reference_number).
    Razorpay payments with no matching Fee Payment are excluded from the
    report entirely — this is deliberately an SLCM fee reconciliation report,
    not a general Razorpay ledger, so unmatched settlement noise doesn't
    appear in the export.

    One Debit row per SETTLEMENT for the sum of ITS MATCHED payments only
    (not the settlement's full gross amount) — a settlement can include
    other, unrelated payments this report has no business reporting on.
    """
    settlements_by_id = {s["id"]: s for s in settlements if s.get("id")}

    # Group recon items (individual payments) by settlement_id
    items_by_settlement = {}
    for item in recon_items:
        sid = item.get("settlement_id") or ""
        if sid:
            items_by_settlement.setdefault(sid, []).append(item)

    rows         = []
    suffix       = _next_suffix(config["prefix"])
    daily_totals = {}

    for sid, items in items_by_settlement.items():
        settlement = settlements_by_id.get(sid)
        if not settlement:
            continue

        ts = settlement.get("settlement_time") or settlement.get("created_at")
        settlement_date = _unix_to_date(ts)
        if not settlement_date:
            continue

        # Client-side date guard, matching the razorpay report's pattern
        if filters.get("from_date") and settlement_date < getdate(filters["from_date"]):
            continue
        if filters.get("to_date") and settlement_date > getdate(filters["to_date"]):
            continue

        utr = (settlement.get("utr") or "").strip()
        date_str = formatdate(settlement_date, "dd-MM-yyyy")

        settlement_credits = []   # (account_name, amount, student_id, student_name, dept, course)
        gross_amount = 0

        for item in items:
            entity_type = (item.get("type") or item.get("entity_type") or "").lower()
            if entity_type and entity_type not in ("payment", ""):
                continue  # skip refunds/adjustments — only actual payments

            pay_id = (item.get("entity_id") or item.get("payment_id") or "").strip()
            amt    = round(flt(item.get("amount") or 0) / 100, 2)  # paise -> rupees
            if amt <= 0:
                continue

            match = fee_payment_by_pay_id.get(pay_id)
            if not match or not match["components"]:
                # No local Fee Payment for this Razorpay payment — excluded
                # from the report; this is a Fee Payment reconciliation
                # report, not a general Razorpay ledger.
                continue

            gross_amount += amt
            total_alloc = round(sum(v for _, v in match["components"]), 2)
            # Scale each component proportionally if the recon amount and
            # the local Fee Payment amount ever disagree, so this
            # payment's credits still sum exactly to the recon amount.
            scale = (amt / total_alloc) if total_alloc else 1
            for account_name, comp_amount in match["components"]:
                settlement_credits.append((
                    account_name, round(comp_amount * scale, 2),
                    match["student"], match["student_name"],
                    match["department"], match["program"],
                ))

        if gross_amount <= 0:
            continue

        daily_totals[str(settlement_date)] = daily_totals.get(str(settlement_date), 0) + gross_amount

        notes = (
            f"Razorpay settlement on {date_str}"
            + (f" | UTR: {utr}" if utr else "")
        )

        shared = {
            "journal_date":          settlement_date,
            "reference_number":      sid,
            "journal_number_prefix": config["prefix"],
            "journal_number_suffix": suffix,
            "notes":                 notes,
            "journal_type":          DEFAULT_JOURNAL_TYPE,
            "currency":              DEFAULT_CURRENCY,
            "description":           DEFAULT_DESCRIPTION,
            # "Contact" is a fixed constant value on every row, by request —
            # the actual Student Master ID/name are separate fields below.
            "contact_name":          CONTACT_VALUE,
        }

        for account_name, comp_amount, student_id, student_name, dept, program in settlement_credits:
            rows.append({
                **shared,
                "account":              account_name,
                "debit":                0,
                "credit":               comp_amount,
                "department":           dept or config["department"],
                "course":               program or config["course"],
                "student_id":           student_id,
                "student_display_name": student_name,
                "row_type":             "Credit",
            })

        rows.append({
            **shared,
            "account":              config["bank_account"],
            "debit":                gross_amount,
            "credit":               0,
            "department":           config["department"],
            "course":               config["course"],
            "student_id":           "",
            "student_display_name": "",
            "row_type":             "Debit",
        })

        suffix += 1

    rows.sort(key=lambda r: (r["journal_date"], r["journal_number_suffix"], r["row_type"]))

    total_debit  = round(sum(r["debit"]  for r in rows), 2)
    total_credit = round(sum(r["credit"] for r in rows), 2)
    balanced     = abs(total_debit - total_credit) < 0.01

    stats = {
        "total_payments": len({r["reference_number"] for r in rows}),
        "total_rows":     len(rows),
        "total_debit":    total_debit,
        "total_credit":   total_credit,
        "balanced":       balanced,
        "daily":          daily_totals,
    }
    return rows, stats


def _build_day_rows(single_rows, config):
    """
    Derive the "Day Transactions" sheet from the exact same rows already
    produced for "Single Transactions" — never re-queried or re-derived from
    Fee Payment directly, so the two sheets can never disagree on which
    payments are included.

    One Credit row per (Date of Settlement, Account) and one Debit row per
    (Date of Settlement, Account) — i.e. every account is consolidated across
    all payments settled on the same day, keeping the per-account/component
    breakdown intact while collapsing individual payments together.
    """
    groups = {}   # (date, row_type, account) -> accumulated amount
    order  = []   # first-seen order of the group keys, for stable output

    for r in single_rows:
        key = (r["journal_date"], r["row_type"], r["account"])
        if key not in groups:
            groups[key] = {
                "debit":  0,
                "credit": 0,
                "date":   r["journal_date"],
                "account": r["account"],
                "row_type": r["row_type"],
                "student_ids":   [],   # first-seen order, de-duplicated
                "student_names": [],
            }
            order.append(key)
        groups[key]["debit"]  += flt(r["debit"])
        groups[key]["credit"] += flt(r["credit"])
        student_id   = r.get("student_id") or ""
        student_name = r.get("student_display_name") or ""
        if student_id and student_id not in groups[key]["student_ids"]:
            groups[key]["student_ids"].append(student_id)
        if student_name and student_name not in groups[key]["student_names"]:
            groups[key]["student_names"].append(student_name)

    day_rows  = []
    suffix_by_date = {}
    next_suffix = _next_suffix(config["prefix"])

    for key in order:
        g = groups[key]
        date = g["date"]
        if date not in suffix_by_date:
            suffix_by_date[date] = next_suffix
            next_suffix += 1

        date_str = formatdate(date, "dd-MM-yyyy")
        day_rows.append({
            "journal_date":          date,
            "reference_number":      f"DAY-{date_str}",
            "journal_number_prefix": config["prefix"],
            "journal_number_suffix": suffix_by_date[date],
            "notes":                 f"Consolidated fee payments settled on {date_str}",
            "journal_type":          DEFAULT_JOURNAL_TYPE,
            "currency":              DEFAULT_CURRENCY,
            "account":               g["account"],
            "description":           DEFAULT_DESCRIPTION,
            "contact_name":          CONTACT_VALUE,
            "student_id":            _join_students(g["student_ids"]),
            "student_display_name":  _join_students(g["student_names"]),
            "debit":                 round(g["debit"], 2)  if g["debit"]  else 0,
            "credit":                round(g["credit"], 2) if g["credit"] else 0,
            "department":            "",
            "course":                "",
            "row_type":              g["row_type"],
        })

    day_rows.sort(key=lambda r: (r["journal_date"], r["journal_number_suffix"], r["row_type"]))

    total_debit  = round(sum(r["debit"]  for r in day_rows), 2)
    total_credit = round(sum(r["credit"] for r in day_rows), 2)
    total_days   = len({r["journal_date"] for r in day_rows})

    return day_rows, {
        "total_days":   total_days,
        "total_rows":   len(day_rows),
        "total_debit":  total_debit,
        "total_credit": total_credit,
        "balanced":     abs(total_debit - total_credit) < 0.01,
    }


def _daily_totals_from_rows(rows):
    """Sum Credit amounts per Date of Settlement, for the trend chart."""
    totals = {}
    for r in rows:
        if r.get("row_type") != "Credit":
            continue
        key = str(r["journal_date"])
        totals[key] = totals.get(key, 0) + flt(r["credit"])
    return totals


def _join_students(names):
    """Comma-separated student names for a consolidated Day Transactions row.
    Truncates long lists so the cell stays readable, e.g. "A, B, C +4 more".
    """
    if not names:
        return "Students"
    max_shown = 5
    if len(names) <= max_shown:
        return ", ".join(names)
    return ", ".join(names[:max_shown]) + f" +{len(names) - max_shown} more"


def _next_suffix(prefix):
    series_name = f"{prefix}.####"
    try:
        result = frappe.db.sql(
            "SELECT current FROM `tabSeries` WHERE name = %s", (series_name,)
        )
        return int(result[0][0]) + 1 if result else 1
    except Exception:
        return 1


# ── Summary cards ─────────────────────────────────────────────────────────────

def _get_report_summary(stats, view="Single Transactions"):
    balanced = stats.get("balanced", False)
    first_card = (
        {
            "value":     stats.get("total_days", 0),
            "label":     _("Settlement Days"),
            "datatype":  "Int",
            "indicator": "Blue",
        }
        if view == "Day Transactions" else
        {
            "value":     stats.get("total_payments", 0),
            "label":     _("Settlements"),
            "datatype":  "Int",
            "indicator": "Blue",
        }
    )
    return [
        first_card,
        {
            "value":     stats["total_rows"],
            "label":     _("Journal Rows"),
            "datatype":  "Int",
            "indicator": "Blue",
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
            "indicator": "Green",
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
            "datasets": [{"name": _("Amount (₹)"), "values": [daily_totals[d] for d in sorted_days]}],
        },
        "type":        "bar",
        "colors":      ["#5e64ff"],
        "axisOptions": {"xIsSeries": True},
    }


# ── Utilities ─────────────────────────────────────────────────────────────────

def _format_zoho_date(val):
    try:
        return formatdate(val, "dd-MM-yyyy")
    except Exception:
        return str(val) if val else ""


def _cell(value, header):
    if value is None:
        return ""
    if header == "Date of Settlement":
        return _format_zoho_date(value)
    if header in ("Debit", "Credit"):
        v = flt(value)
        return v if v else ""
    return str(value) if value else ""


# ── Zoho Books export ─────────────────────────────────────────────────────────

# Must match the Report doctype's own `roles` list (see
# fee_payment_zoho_journal_upload.json). Frappe only enforces that role
# restriction when the report is opened through the standard report-viewer
# path (frappe.desk.query_report.run) — a whitelisted function's dotted path
# can be called directly via /api/method/... by ANY logged-in user regardless
# of role, since frappe.whitelist() itself has no doctype/report awareness.
# This report exposes settlement amounts, student names, and bank account
# details, so both entry points enforce the same roles explicitly.
ALLOWED_ROLES = {"System Manager", "Accounts Manager", "Accounts User"}


def _check_report_permission():
    if not (set(frappe.get_roles(frappe.session.user)) & ALLOWED_ROLES):
        frappe.throw(
            _("You do not have permission to access this report."),
            frappe.PermissionError,
        )


@frappe.whitelist()
def download_zoho_upload_file(filters=None, file_format="csv"):
    """
    Generate Zoho Books–compatible journal upload file (14 columns only).
    Hard-blocks export if Debit != Credit.
    """
    _check_report_permission()

    import base64

    if isinstance(filters, str):
        try:
            filters = json.loads(filters)
        except Exception:
            filters = {}
    filters = filters or {}

    config      = _resolve_config(filters)
    settlements = _fetch_settlements(filters)
    if not settlements:
        frappe.throw(_("No Razorpay settlements found for the selected date range."))

    api_key, api_secret = _get_razorpay_credentials_or_throw()
    recon_items = _fetch_recon_items(auth=(api_key, api_secret), settlements=settlements)
    fee_payment_by_pay_id = _lookup_fee_payments_by_reference(
        {(item.get("entity_id") or item.get("payment_id") or "").strip() for item in recon_items}
    )

    rows, stats = _build_journal_rows(settlements, recon_items, fee_payment_by_pay_id, filters, config)
    if not rows:
        frappe.throw(_("No Razorpay payments in this date range matched a local Fee Payment record."))

    if not stats["balanced"]:
        diff = round(stats["total_debit"] - stats["total_credit"], 2)
        frappe.throw(
            _(
                "Export blocked — journal is not balanced.<br>"
                "Total Debit: ₹{0} | Total Credit: ₹{1} | Difference: ₹{2}"
            ).format(
                f"{stats['total_debit']:,.2f}",
                f"{stats['total_credit']:,.2f}",
                f"{diff:,.2f}",
            ),
            title=_("Validation Failed — Unbalanced Journal"),
        )

    from_d     = filters.get("from_date", "")
    to_d       = filters.get("to_date", nowdate())
    date_label = f"{from_d}_{to_d}".strip("_") or nowdate()

    if file_format == "xlsx":
        day_rows, day_stats = _build_day_rows(rows, config)
        # Same source rows in both sheets — totals must reconcile by construction.
        if round(day_stats["total_debit"] - stats["total_debit"], 2) != 0 or \
           round(day_stats["total_credit"] - stats["total_credit"], 2) != 0:
            frappe.throw(
                _("Internal error — Day Transactions total does not reconcile with Single Transactions."),
                title=_("Validation Failed"),
            )
        content, filename, mime = _build_xlsx(rows, day_rows, date_label, stats, day_stats, config)
    else:
        content, filename, mime = _build_csv(rows, date_label)

    return {
        "filename":     filename,
        "content":      base64.b64encode(content).decode("utf-8"),
        "mime":         mime,
        "row_count":    len(rows),
        "balanced":     stats["balanced"],
        "total_debit":  stats["total_debit"],
        "total_credit": stats["total_credit"],
    }


@frappe.whitelist()
def get_dynamic_defaults():
    _check_report_permission()
    return {
        "bank_account":   DEFAULT_BANK_ACCOUNT,
        "journal_prefix": DEFAULT_PREFIX,
        "department":     DEFAULT_DEPARTMENT,
        "course":         DEFAULT_COURSE,
    }


# ── CSV builder ───────────────────────────────────────────────────────────────

def _build_csv(rows, date_label):
    import csv
    all_headers = ZOHO_HEADERS + EXTRA_HEADERS
    all_field_map = {**ZOHO_FIELD_MAP, **EXTRA_FIELD_MAP}
    buf    = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(all_headers)
    for r in rows:
        writer.writerow([_cell(r.get(all_field_map[h]), h) for h in all_headers])
    content  = buf.getvalue().encode("utf-8-sig")
    filename = f"zoho_fee_journal_{date_label}.csv"
    return content, filename, "text/csv"


# ── XLSX builder ──────────────────────────────────────────────────────────────

# Shared style constants (used by both data sheets and the Summary sheet)
_PURPLE    = "5E64FF"
_INDIGO    = "3949AB"
_WHITE     = "FFFFFF"
_GREEN_BG  = "E8F5E9"
_BLUE_BG   = "E3F2FD"
_STRIPE    = "F7F8FF"
_TOTAL_BG  = "E8EAF6"
_OK_CLR    = "2E7D32"
_ERR_CLR   = "C62828"
_BD        = "C5CAE9"


def _write_journal_sheet(ws, rows, stats, title):
    """
    Render one Zoho-format journal sheet (header banner + column headers +
    data rows + TOTAL row) into an already-created worksheet. Shared by the
    "Single Transactions" and "Day Transactions" sheets so both are always
    rendered with identical column layout and formatting.

    Columns are the 14 required Zoho fields, followed by the extra
    Student ID / Student Name columns (EXTRA_HEADERS) — Zoho's importer only
    reads the first 14 by position, so the trailing columns are ignored by
    Zoho but visible here for reference.
    """
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    all_headers   = ZOHO_HEADERS + EXTRA_HEADERS
    all_field_map = {**ZOHO_FIELD_MAP, **EXTRA_FIELD_MAP}

    thin_s  = Side(style="thin",   color=_BD)
    thick_s = Side(style="medium", color=_PURPLE)
    t_bdr   = Border(left=thin_s,  right=thin_s,  top=thin_s,  bottom=thin_s)
    h_bdr   = Border(left=thick_s, right=thick_s, top=thick_s, bottom=thick_s)

    n_cols     = len(all_headers)
    debit_col  = all_headers.index("Debit")  + 1
    credit_col = all_headers.index("Credit") + 1

    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "D3"

    ws.row_dimensions[1].height = 30
    ws.append([""] * n_cols)
    tc = ws.cell(row=1, column=1, value=title)
    tc.font      = Font(bold=True, size=10, color=_WHITE, name="Calibri")
    tc.fill      = PatternFill("solid", fgColor=_PURPLE)
    tc.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n_cols)

    ws.row_dimensions[2].height = 34
    ws.append(all_headers)
    for ci, h in enumerate(all_headers, 1):
        cell = ws.cell(row=2, column=ci)
        cell.font      = Font(bold=True, color=_WHITE, size=10, name="Calibri")
        cell.fill      = PatternFill("solid", fgColor=_INDIGO if h in ZOHO_FIELD_MAP else "5C6BC0")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border    = h_bdr

    for ri, r in enumerate(rows, 3):
        rt = r.get("row_type", "")
        bg = PatternFill("solid", fgColor=_GREEN_BG if rt == "Credit"
                          else _BLUE_BG if rt == "Debit"
                          else (_STRIPE if ri % 2 == 0 else _WHITE))
        ws.row_dimensions[ri].height = 16

        for ci, h in enumerate(all_headers, 1):
            val  = _cell(r.get(all_field_map[h]), h)
            cell = ws.cell(row=ri, column=ci, value=val)
            cell.fill = bg; cell.border = t_bdr

            if h in ("Debit", "Credit"):
                cell.font          = Font(bold=bool(val), size=9, name="Calibri",
                                          color="1565C0" if h == "Debit" else "2E7D32")
                cell.number_format = "#,##0.00"
                cell.alignment     = Alignment(horizontal="right", vertical="center")
            elif h == "Date of Settlement":
                cell.font      = Font(size=9, name="Calibri")
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif h in ("Journal Number Suffix", "Journal Type", "Currency",
                       "Department", "Course"):
                cell.font      = Font(size=9, name="Calibri")
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif h == "Account":
                clr = "6A1B9A" if rt == "Credit" else "1565C0"
                cell.font      = Font(size=9, name="Calibri", color=clr)
                cell.alignment = Alignment(vertical="center")
            elif h == "Contact":
                cell.font      = Font(size=9, name="Calibri", color="00695C")
                cell.alignment = Alignment(vertical="center")
            else:
                cell.font      = Font(size=9, name="Calibri")
                cell.alignment = Alignment(vertical="center")

    total_ri = len(rows) + 3
    ws.row_dimensions[total_ri].height = 22
    for ci in range(1, n_cols + 1):
        cell = ws.cell(row=total_ri, column=ci)
        cell.fill      = PatternFill("solid", fgColor=_TOTAL_BG)
        cell.font      = Font(bold=True, size=10, name="Calibri", color="1A237E")
        cell.border    = h_bdr
        cell.alignment = Alignment(horizontal="right", vertical="center")
        if ci == 1:
            cell.value     = "TOTAL"
            cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        elif ci == debit_col:
            cell.value = stats["total_debit"]; cell.number_format = "#,##0.00"
        elif ci == credit_col:
            cell.value = stats["total_credit"]; cell.number_format = "#,##0.00"

    for ci, h in enumerate(all_headers, 1):
        vals   = [str(_cell(r.get(all_field_map[h]), h) or "") for r in rows]
        maxlen = max(len(str(h)), *(len(v) for v in vals)) if vals else len(str(h))
        ws.column_dimensions[get_column_letter(ci)].width = min(maxlen + 3, 50)


def _build_xlsx(rows, day_rows, date_label, stats, day_stats, config):
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    except ImportError:
        frappe.throw(_("openpyxl is not installed. Run: bench pip install openpyxl"))

    PURPLE, WHITE   = _PURPLE, _WHITE
    OK_CLR, ERR_CLR = _OK_CLR, _ERR_CLR
    balanced        = stats.get("balanced", False)

    wb = openpyxl.Workbook()

    # ── Sheet 1: Single Transactions ──────────────────────────────────────────
    ws = wb.active
    ws.title = "Single Transactions"
    _write_journal_sheet(
        ws, rows, stats,
        f"Single Transactions  |  Zoho Books Import  |  {date_label}",
    )

    # ── Sheet 2: Day Transactions ─────────────────────────────────────────────
    ws_day = wb.create_sheet("Day Transactions")
    _write_journal_sheet(
        ws_day, day_rows, day_stats,
        f"Day Transactions (consolidated by Date of Settlement)  |  Zoho Books Import  |  {date_label}",
    )

    # ── Sheet 3: Summary ──────────────────────────────────────────────────────
    ws2 = wb.create_sheet("Summary")
    ws2.sheet_view.showGridLines = False
    ws2.column_dimensions["A"].width = 34
    ws2.column_dimensions["B"].width = 26

    s_hdr   = Font(bold=True, color=WHITE, size=10, name="Calibri")
    s_hfill = PatternFill("solid", fgColor=PURPLE)
    s_lbl   = Font(bold=True, size=10, name="Calibri", color="424242")
    s_val   = Font(size=10, name="Calibri")
    s_ok    = Font(bold=True, size=10, name="Calibri", color=OK_CLR)
    s_err   = Font(bold=True, size=10, name="Calibri", color=ERR_CLR)
    s_bdr   = Border(
        left=Side(style="thin", color="CCCCCC"), right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"),  bottom=Side(style="thin", color="CCCCCC"),
    )

    reconciled = (
        round(stats["total_debit"]  - day_stats["total_debit"],  2) == 0
        and round(stats["total_credit"] - day_stats["total_credit"], 2) == 0
    )

    summary_rows = [
        ("Report Details", ""),
        ("Report Name",   "Fee Payment Zoho Journal Upload"),
        ("Date Range",    date_label),
        ("Generated On",  nowdate()),
        ("", ""),
        ("Journal Configuration", ""),
        ("Default Bank Account", config.get("bank_account") or DEFAULT_BANK_ACCOUNT),
        ("Journal Prefix",       config.get("prefix")       or DEFAULT_PREFIX),
        ("", ""),
        ("Payment Statistics", ""),
        ("Total Settlements",                stats["total_payments"]),
        ("Single Transactions — Rows",      stats["total_rows"]),
        ("Day Transactions — Rows",         day_stats["total_rows"]),
        ("", ""),
        ("Single Transactions — Totals", ""),
        ("Total Debit",                 stats["total_debit"]),
        ("Total Credit",                stats["total_credit"]),
        ("Difference (Debit − Credit)", round(stats["total_debit"] - stats["total_credit"], 2)),
        ("", ""),
        ("Day Transactions — Totals", ""),
        ("Total Debit",                 day_stats["total_debit"]),
        ("Total Credit",                day_stats["total_credit"]),
        ("Difference (Debit − Credit)", round(day_stats["total_debit"] - day_stats["total_credit"], 2)),
        ("", ""),
        ("Validation", ""),
        ("Debit = Credit",                     "YES — Balanced ✓" if balanced else "NO — UNBALANCED ✗"),
        ("Single = Day Transactions Totals",   "YES — Reconciled ✓" if reconciled else "NO — MISMATCH ✗"),
        ("Ready for Import", "YES" if balanced else "NO — Fix before importing"),
    ]

    ws2.row_dimensions[1].height = 28
    t2 = ws2.cell(row=1, column=1, value="Zoho Books Journal Upload — Summary")
    t2.font = Font(bold=True, size=13, color=PURPLE, name="Calibri")
    t2.alignment = Alignment(horizontal="left", vertical="center")
    ws2.merge_cells("A1:B1")

    for ri, (label, value) in enumerate(summary_rows, 2):
        ws2.row_dimensions[ri].height = 18
        cl = ws2.cell(row=ri, column=1, value=label)
        cv = ws2.cell(row=ri, column=2, value=value)
        if not label:
            continue
        if value == "":
            cl.font = s_hdr; cl.fill = s_hfill
            cl.alignment = Alignment(horizontal="left", vertical="center", indent=1)
            ws2.merge_cells(start_row=ri, start_column=1, end_row=ri, end_column=2)
            continue
        cl.font = s_lbl; cl.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        cl.border = s_bdr; cv.border = s_bdr
        if label in ("Total Debit", "Total Credit", "Difference (Debit − Credit)"):
            cv.number_format = "#,##0.00"; cv.font = s_val
        elif label in ("Debit = Credit", "Ready for Import"):
            cv.font = s_ok if balanced else s_err
        elif label == "Single = Day Transactions Totals":
            cv.font = s_ok if reconciled else s_err
        else:
            cv.font = s_val
        cv.alignment = Alignment(
            horizontal="right" if isinstance(value, (int, float)) else "left",
            vertical="center",
        )

    # ── Sheet 3: Instructions ─────────────────────────────────────────────────
    ws3 = wb.create_sheet("Import Instructions")
    ws3.sheet_view.showGridLines = False
    ws3.column_dimensions["A"].width = 90

    steps = [
        ("Zoho Books Journal Import — Step-by-step Guide", True),
        ("", False),
        ("Step 1 — Choose ONE sheet to import: 'Single Transactions' (one row", False),
        ("per payment) or 'Day Transactions' (consolidated by settlement date).", False),
        ("Do not import both — they represent the same payments at two levels", False),
        ("of detail and importing both would double-count the amounts.", False),
        ("Step 2 — Check 'Summary' sheet: Debit = Credit must show YES, and", False),
        ("'Single = Day Transactions Totals' must show Reconciled.", False),
        ("Step 3 — In Zoho Books: Accountant → Journal → ⋮ → Import Journals.", False),
        ("Step 4 — Upload this XLSX file (or the CSV version, single-transaction only).", False),
        ("Step 5 — Map columns if prompted, preview and confirm.", False),
        ("", False),
        ("Sheet Notes", True),
        ("Data source: Razorpay Settlements API, filtered to payments that", False),
        ("matched a local Fee Payment record (by Reference / Transaction Number).", False),
        ("Unmatched Razorpay activity is excluded from this report entirely.", False),
        ("Single Transactions — one Credit row per Fee Component for each matched", False),
        ("payment within a settlement, plus one Debit row per SETTLEMENT for the", False),
        ("sum of ITS MATCHED payments only (not the settlement's full Razorpay", False),
        ("gross, which may include other, unrelated payments).", False),
        ("Day Transactions — the same rows above, grouped by Date of Settlement", False),
        ("and Account: all credits/debits for an account on one date become a", False),
        ("single row. Derived directly from Single Transactions, so totals match.", False),
        ("", False),
        ("Column Reference", True),
        ("Date of Settlement    — dd-MM-yyyy  (e.g. 21-02-2026)", False),
        ("Settlement Reference No — Razorpay Settlement ID (setl_xxx)", False),
        ("Journal Number Prefix — Configured prefix  (default: JN-FP-)", False),
        ("Journal Number Suffix — Auto-incremented integer", False),
        ("Notes                 — Settlement date and UTR", False),
        ("Account               — Must exactly match Zoho Books chart of accounts", False),
        ("Contact               — Frappe record reference (Student Master ID), not the name", False),
        ("Debit / Credit        — Only one value per row; other is blank", False),
        ("Student ID / Student Name — extra columns after the 14 Zoho fields, populated", False),
        ("only when the payment matched a local Fee Payment record; Zoho ignores them.", False),
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
        f"zoho_fee_journal_{date_label}.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
