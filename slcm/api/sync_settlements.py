"""
Manual settlement sync — backfills settlement data into FLE Payment Log.

Call via bench console:
    frappe.call("slcm.api.sync_settlements.run_sync")

Or via API (System Manager only):
    POST /api/method/slcm.api.sync_settlements.run_sync
"""

import datetime

import frappe
import requests


RAZORPAY_BASE   = "https://api.razorpay.com/v1"
PAGE_SIZE       = 100   # max for /v1/settlements
RECON_PAGE_SIZE = 500   # max per page for /v1/settlements/{id}/recon/combined


@frappe.whitelist()
def diagnose_quick():
    """
    Fast diagnosis — no Razorpay API calls.
    Reads only the local FLE Payment Log table and returns counts in < 1 second.
    """
    total = frappe.db.count("FLE Payment Log")

    with_tid = frappe.db.sql(
        "SELECT COUNT(*) FROM `tabFLE Payment Log` WHERE transaction_id IS NOT NULL AND transaction_id != ''",
    )[0][0]

    without_tid = total - with_tid

    with_name = frappe.db.sql(
        "SELECT COUNT(*) FROM `tabFLE Payment Log` WHERE full_name IS NOT NULL AND full_name != ''",
    )[0][0]

    without_name = total - with_name

    with_settlement = frappe.db.sql(
        "SELECT COUNT(*) FROM `tabFLE Payment Log` WHERE settlement_id IS NOT NULL AND settlement_id != ''",
    )[0][0]

    without_settlement = total - with_settlement

    return {
        "total_fle_records":            total,
        "with_razorpay_payment_id":     with_tid,
        "missing_razorpay_payment_id":  without_tid,
        "with_contact_name":            with_name,
        "missing_contact_name":         without_name,
        "synced_with_settlement":       with_settlement,
        "not_yet_synced":               without_settlement,
    }


@frappe.whitelist()
def diagnose_missing_matches():
    """
    Diagnoses why Contact Name is blank in the settlement report.

    Uses /v1/settlements/recon/combined (same API as the report) to collect
    all settled payment IDs, then cross-checks against FLE Payment Log.
    """
    import json
    from datetime import datetime, timezone

    settings   = frappe.get_single("Razorpay Settings")
    api_key    = settings.api_key
    api_secret = settings.get_password("api_secret")
    if not api_key or not api_secret:
        frappe.throw("API credentials are missing in Razorpay Settings.")

    auth = (api_key, api_secret)

    # Step 1: fetch settlement list
    settlements = _fetch_all_settlements(auth)
    if not settlements:
        return {"error": "No settlements returned from Razorpay. Check API credentials."}

    setl_by_id = {s["id"]: s for s in settlements if s.get("id")}

    # Step 2: collect all payment IDs from recon/combined (same logic as the report)
    # Determine year-months from settlements
    year_months = set()
    for s in settlements:
        ts = s.get("created_at")
        if ts:
            try:
                dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
                year_months.add((dt.year, dt.month))
            except Exception:
                pass
    year_months = sorted(year_months)

    target_ids      = set(setl_by_id.keys())
    razorpay_pids   = set()   # pay_xxx IDs from recon
    recon_available = False

    for year, month in year_months:
        skip = 0
        while True:
            resp = requests.get(
                "https://api.razorpay.com/v1/settlements/recon/combined",
                auth=auth,
                params={"year": year, "month": month, "count": 1000, "skip": skip},
                timeout=60,
            )
            if resp.status_code == 404:
                break   # recon not enabled
            if not resp.ok:
                break

            recon_available = True
            items = resp.json().get("items", [])
            for item in items:
                if item.get("settlement_id") not in target_ids:
                    continue
                pid = item.get("entity_id") or item.get("payment_id") or ""
                if pid:
                    razorpay_pids.add(pid)

            if len(items) < 1000:
                break
            skip += 1000

    # Step 3: collect payment IDs from FLE Payment Log
    fle_rows = frappe.db.sql(
        """
        SELECT
            name,
            transaction_id,
            full_name,
            gateway_response
        FROM `tabFLE Payment Log`
        """,
        as_dict=True,
    )

    # Build FLE map — also try extracting pay_xxx from gateway_response
    # when transaction_id is NULL (Integration Request data format)
    fle_tid_map  = {}   # pay_xxx → full_name
    null_tid_rows = 0

    for r in fle_rows:
        tid = (r.transaction_id or "").strip()
        if not tid:
            # Try extracting from gateway_response JSON
            try:
                gw   = json.loads(r.gateway_response or "{}")
                tid  = (
                    gw.get("razorpay_payment_id")
                    or gw.get("payload", {}).get("payment", {}).get("entity", {}).get("id")
                    or ""
                )
            except Exception:
                pass
        if tid:
            fle_tid_map[tid] = r.full_name or ""
        else:
            null_tid_rows += 1

    # Step 4: cross-check
    matched    = [pid for pid in razorpay_pids if pid in fle_tid_map]
    unmatched  = [pid for pid in razorpay_pids if pid not in fle_tid_map]
    blank_name = [pid for pid in matched if not fle_tid_map.get(pid)]

    result = {
        "recon_api_available":           recon_available,
        "total_settlements":             len(settlements),
        "total_razorpay_payment_ids":    len(razorpay_pids),
        "total_fle_payment_log_records": len(fle_rows),
        "fle_rows_with_null_tid":        null_tid_rows,
        "matched_with_fle_log":          len(matched),
        "unmatched_no_fle_log":          len(unmatched),
        "matched_but_blank_name":        len(blank_name),
        "sample_unmatched_ids":          unmatched[:10],
        "sample_blank_name_ids":         blank_name[:10],
    }

    frappe.logger().info(f"diagnose_missing_matches: {result}")
    return result


@frappe.whitelist()
def backfill_contact_names():
    """
    One-time backfill: copies candidate_name and email_address from the linked
    'Foundations for a Legal Education' document into any FLE Payment Log rows
    where full_name is blank.

    Run after deployment to fix all existing records:
        bench execute slcm.api.sync_settlements.backfill_contact_names
    Or via API button in the report.
    """
    rows = frappe.db.sql(
        """
        SELECT fpl.name, fpl.reference_no
        FROM `tabFLE Payment Log` fpl
        WHERE (fpl.full_name IS NULL OR fpl.full_name = '')
          AND fpl.reference_no IS NOT NULL
          AND fpl.reference_no != ''
        """,
        as_dict=True,
    )

    updated = 0
    for row in rows:
        fle = frappe.db.get_value(
            "Foundations for a Legal Education",
            row.reference_no,
            ["candidate_name", "email_address"],
            as_dict=True,
        )
        if not fle:
            continue
        frappe.db.set_value("FLE Payment Log", row.name, {
            "full_name": fle.candidate_name or "",
            "email":     fle.email_address  or "",
        }, update_modified=False)
        updated += 1

    frappe.db.commit()
    msg = f"Backfilled contact name/email for {updated} FLE Payment Log records."
    frappe.logger().info(msg)
    return msg


@frappe.whitelist()
def run_sync():
    settings   = frappe.get_single("Razorpay Settings")
    api_key    = settings.api_key
    api_secret = settings.get_password("api_secret")

    if not api_key or not api_secret:
        frappe.throw("API credentials are missing in Razorpay Settings.")

    auth = (api_key, api_secret)

    # Fetch all settlements (paginated)
    settlements     = _fetch_all_settlements(auth)
    total_updated   = 0
    total_processed = 0

    for st in settlements:
        settlement_id = st.get("id")
        if not settlement_id:
            continue

        utr    = st.get("utr") or ""
        status = st.get("status") or "processed"

        settlement_date = None
        created_at      = st.get("created_at")
        if created_at:
            try:
                settlement_date = datetime.datetime.utcfromtimestamp(int(created_at)).date()
            except Exception:
                pass

        recon_items = _fetch_settlement_recon(settlement_id, auth)
        updated     = 0

        for item in recon_items:
            # Razorpay recon/combined uses entity_type; skip refunds
            entity_type = item.get("type") or item.get("entity_type") or ""
            if entity_type and entity_type not in ("payment", ""):
                continue

            # Razorpay uses different field names across API versions
            rzp_payment_id = (
                item.get("razorpay_payment_id")
                or item.get("entity_id")
                or item.get("payment_id")
                or ""
            )
            if not rzp_payment_id:
                continue

            log_name = frappe.db.get_value(
                "FLE Payment Log",
                {"transaction_id": rzp_payment_id},
                "name",
            )
            if not log_name:
                continue

            fee_paise    = item.get("fee") or item.get("fees") or 0
            tax_paise    = item.get("tax") or 0
            credit_paise = item.get("credit") or item.get("amount") or 0

            frappe.db.set_value("FLE Payment Log", log_name, {
                "settlement_id":     settlement_id,
                "settlement_utr":    utr,
                "settlement_date":   settlement_date,
                "settlement_status": status,
                "gateway_fees":      round(fee_paise / 100, 2),
                "gateway_tax":       round(tax_paise / 100, 2),
                "net_settled":       round(credit_paise / 100, 2),
            })
            updated += 1

        frappe.logger().info(
            f"Sync: Settlement {settlement_id} (UTR: {utr}) — updated {updated} FLE Payment Log records."
        )
        total_updated   += updated
        total_processed += 1

    frappe.db.commit()

    msg = (
        f"Sync complete. Processed {total_processed} settlements, "
        f"updated {total_updated} FLE Payment Log records."
    )
    frappe.logger().info(msg)
    return msg


def _fetch_all_settlements(auth):
    """Paginate through /v1/settlements and return all items."""
    settlements = []
    skip        = 0

    while True:
        resp = requests.get(
            f"{RAZORPAY_BASE}/settlements",
            auth=auth,
            params={"count": PAGE_SIZE, "skip": skip},
            timeout=30,
        )
        if not resp.ok:
            frappe.log_error(
                f"Razorpay /settlements error {resp.status_code}: {resp.text[:300]}",
                "sync_settlements",
            )
            frappe.throw(
                f"Razorpay API error {resp.status_code}: {resp.text[:300]}"
            )

        items = resp.json().get("items", [])
        settlements.extend(items)

        if len(items) < PAGE_SIZE:
            break
        skip += PAGE_SIZE

    return settlements


def _fetch_settlement_recon(settlement_id, auth):
    """Fetch all recon items for one settlement (paginated)."""
    items = []
    skip  = 0

    while True:
        resp = requests.get(
            f"{RAZORPAY_BASE}/settlements/{settlement_id}/recon/combined",
            auth=auth,
            params={"count": RECON_PAGE_SIZE, "skip": skip},
            timeout=30,
        )

        if resp.status_code == 404:
            # Recon endpoint not enabled on this Razorpay account
            frappe.logger().warning(
                f"sync_settlements: recon/combined not available for {settlement_id} (404)"
            )
            break

        if not resp.ok:
            frappe.logger().error(
                f"sync_settlements: recon error for {settlement_id}: "
                f"{resp.status_code} {resp.text[:200]}"
            )
            break

        batch = resp.json().get("items") or []
        items.extend(batch)

        if len(batch) < RECON_PAGE_SIZE:
            break
        skip += RECON_PAGE_SIZE

    return items
