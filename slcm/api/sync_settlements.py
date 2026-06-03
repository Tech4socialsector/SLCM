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
def run_sync_background():
    """
    Enqueue run_sync as a background job and return the job ID immediately.
    The caller polls /api/method/slcm.api.sync_settlements.get_sync_status?job_id=<id>
    to check progress.
    """
    job = frappe.enqueue(
        "slcm.api.sync_settlements.run_sync",
        queue="long",
        timeout=600,
        now=False,
        job_name="razorpay_settlement_sync",
    )
    return {"job_id": job.id if hasattr(job, "id") else "queued"}


@frappe.whitelist()
def get_sync_status(job_id=None):
    """
    Check the status of a background sync job.
    Returns: { status: "queued"|"started"|"finished"|"failed", result: "..." }
    """
    if not job_id:
        return {"status": "unknown", "result": ""}
    try:
        from rq.job import Job
        from redis import Redis
        conn   = Redis.from_url(frappe.conf.get("redis_queue") or "redis://localhost:11311")
        job    = Job.fetch(job_id, connection=conn)
        status = job.get_status()
        result = ""
        if status == "finished":
            result = str(job.result or "")
        elif status == "failed":
            result = str(job.exc_info or "Sync failed — check Error Log.")
        return {"status": str(status), "result": result}
    except Exception as e:
        return {"status": "unknown", "result": str(e)}


@frappe.whitelist()
def run_sync():
    """
    Sync settlement data into FLE Payment Log using /v1/settlements/recon/combined.

    Matching strategy (tried in order for each recon item):
      1. transaction_id  == pay_xxx from recon entity_id / payment_id
      2. transaction_id  == pay_xxx extracted from gateway_response JSON
      3. gateway_response contains the order_id from the recon item

    Fallback (settlement-level, no per-payment recon needed):
      4. For every settlement whose UTR is not yet in any FLE Payment Log row,
         write settlement_id + settlement_utr + settlement_date directly onto
         FLE Payment Log rows whose paid_amount matches the settlement amount
         and whose settlement_id is still blank — this covers cases where the
         recon endpoint returns no items or entity_ids don't match.
    """
    import json
    from datetime import datetime, timezone

    settings   = frappe.get_single("Razorpay Settings")
    api_key    = settings.api_key
    api_secret = settings.get_password("api_secret")

    if not api_key or not api_secret:
        frappe.throw("API credentials are missing in Razorpay Settings.")

    auth = (api_key, api_secret)

    # ── Step 1: fetch all settlements ─────────────────────────────────────────
    settlements = _fetch_all_settlements(auth)
    if not settlements:
        return "No settlements found from Razorpay."

    setl_by_id = {s["id"]: s for s in settlements if s.get("id")}

    # ── Step 2: build FLE Payment Log lookup maps ─────────────────────────────
    # Map 1: pay_xxx → log name  (from transaction_id field directly)
    # Map 2: pay_xxx → log name  (extracted from gateway_response JSON)
    # Map 3: order_id → log name (from gateway_response JSON)
    fle_rows = frappe.db.sql(
        """
        SELECT name, transaction_id, paid_amount, settlement_id, gateway_response
        FROM `tabFLE Payment Log`
        WHERE payment_status IN ('Captured', 'Authorized', 'Paid')
           OR payment_status IS NULL
        """,
        as_dict=True,
    )

    by_tid      = {}   # pay_xxx  → name
    by_gw_pay   = {}   # pay_xxx  → name  (from gateway_response)
    by_order_id = {}   # order_id → name  (from gateway_response)

    for r in fle_rows:
        # Direct transaction_id
        tid = (r.transaction_id or "").strip()
        if tid and tid.startswith("pay_") and tid not in by_tid:
            by_tid[tid] = r.name

        # Parse gateway_response for pay_xxx and order_id
        gw_pay = gw_order = ""
        if r.gateway_response:
            try:
                gw = json.loads(r.gateway_response)
                # Integration Request format: {"razorpay_payment_id": "pay_xxx", "razorpay_order_id": "order_xxx"}
                gw_pay   = (gw.get("razorpay_payment_id") or "").strip()
                gw_order = (gw.get("razorpay_order_id")   or "").strip()
                # Webhook format: payload.payment.entity.id
                if not gw_pay:
                    gw_pay = (
                        gw.get("payload", {})
                           .get("payment", {})
                           .get("entity", {})
                           .get("id") or ""
                    ).strip()
                if not gw_order:
                    gw_order = (
                        gw.get("payload", {})
                           .get("payment", {})
                           .get("entity", {})
                           .get("order_id") or ""
                    ).strip()
            except Exception:
                pass

        if gw_pay and gw_pay.startswith("pay_") and gw_pay not in by_gw_pay:
            by_gw_pay[gw_pay] = r.name
        if gw_order and gw_order not in by_order_id:
            by_order_id[gw_order] = r.name

    # ── Step 3: determine year-months to query recon ──────────────────────────
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

    if not year_months:
        return "Could not determine date range from settlements."

    # ── Step 4: fetch recon items and match to FLE Payment Log ───────────────
    total_updated  = 0
    recon_fetched  = 0
    recon_matched  = 0
    recon_skipped  = 0
    updated_names  = set()   # avoid double-updating the same log row

    def _resolve_log(item):
        """Try all matching strategies; return (log_name, pay_id) or (None, '')."""
        pay_id = (
            item.get("entity_id")
            or item.get("payment_id")
            or item.get("razorpay_payment_id")
            or ""
        ).strip()
        order_id = (item.get("order_id") or "").strip()

        if pay_id:
            name = by_tid.get(pay_id) or by_gw_pay.get(pay_id)
            if name:
                return name, pay_id
        if order_id:
            name = by_order_id.get(order_id)
            if name:
                return name, pay_id
        return None, pay_id

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
                frappe.logger().warning(
                    "sync_settlements: recon/combined returned 404 — not enabled on this account."
                )
                break

            if not resp.ok:
                frappe.logger().error(
                    f"sync_settlements: recon error {resp.status_code}: {resp.text[:200]}"
                )
                break

            items = resp.json().get("items") or []
            recon_fetched += len(items)

            for item in items:
                entity_type = (item.get("type") or item.get("entity_type") or "").lower()
                if entity_type and entity_type not in ("payment", ""):
                    continue

                log_name, pay_id = _resolve_log(item)

                if not log_name:
                    recon_skipped += 1
                    if pay_id:
                        frappe.logger().debug(
                            f"sync_settlements: no FLE match for pay_id={pay_id}"
                        )
                    continue

                if log_name in updated_names:
                    continue

                # Settlement metadata
                sid    = item.get("settlement_id") or ""
                s_data = setl_by_id.get(sid) or {}
                utr    = s_data.get("utr") or ""
                status = s_data.get("status") or "processed"

                settlement_date = None
                ts = s_data.get("settlement_time") or s_data.get("created_at")
                if ts:
                    try:
                        settlement_date = datetime.fromtimestamp(int(ts), tz=timezone.utc).date()
                    except Exception:
                        pass

                fee_paise    = int(item.get("fee")    or item.get("fees") or 0)
                tax_paise    = int(item.get("tax")    or 0)
                credit_paise = int(item.get("credit") or item.get("amount") or 0)

                frappe.db.set_value("FLE Payment Log", log_name, {
                    "settlement_id":     sid,
                    "settlement_utr":    utr,
                    "settlement_date":   settlement_date,
                    "settlement_status": status,
                    "gateway_fees":      round(fee_paise    / 100, 2),
                    "gateway_tax":       round(tax_paise    / 100, 2),
                    "net_settled":       round(credit_paise / 100, 2),
                }, update_modified=False)

                updated_names.add(log_name)
                total_updated += 1
                recon_matched += 1

            if len(items) < RECON_PAGE_SIZE:
                break
            skip += RECON_PAGE_SIZE

    # ── Step 5: UTR-based fallback ────────────────────────────────────────────
    # For FLE Payment Log rows that already have settlement_utr populated
    # (written by the webhook on settlement.processed), write the settlement_id
    # and other metadata from the settlements list.
    # This handles the case where recon/combined has no per-payment entity_ids.
    fallback_updated = 0
    utr_to_settlement = {
        s.get("utr"): s for s in settlements
        if s.get("utr") and s.get("id")
    }

    if utr_to_settlement:
        utr_rows = frappe.db.sql(
            """
            SELECT name, settlement_utr
            FROM `tabFLE Payment Log`
            WHERE settlement_utr IS NOT NULL
              AND settlement_utr != ''
              AND (settlement_id IS NULL OR settlement_id = '')
            """,
            as_dict=True,
        )
        for row in utr_rows:
            if row.name in updated_names:
                continue
            s = utr_to_settlement.get(row.settlement_utr)
            if not s:
                continue

            sid    = s.get("id") or ""
            status = s.get("status") or "processed"
            ts     = s.get("settlement_time") or s.get("created_at")
            settlement_date = None
            if ts:
                try:
                    settlement_date = datetime.fromtimestamp(int(ts), tz=timezone.utc).date()
                except Exception:
                    pass

            frappe.db.set_value("FLE Payment Log", row.name, {
                "settlement_id":     sid,
                "settlement_date":   settlement_date,
                "settlement_status": status,
            }, update_modified=False)

            updated_names.add(row.name)
            fallback_updated += 1

    frappe.db.commit()

    total_all = total_updated + fallback_updated
    msg = (
        f"Sync complete. "
        f"Scanned {recon_fetched} recon items across {len(year_months)} month(s). "
        f"Matched {recon_matched} via payment ID, "
        f"{fallback_updated} via UTR fallback. "
        f"Total updated: {total_all} FLE Payment Log record(s). "
        + (f"Unmatched recon items: {recon_skipped}." if recon_skipped else "All items matched.")
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


