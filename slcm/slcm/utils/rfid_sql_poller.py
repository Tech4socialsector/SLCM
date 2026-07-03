# Copyright (c) 2026, Nishanth and contributors
# For license information, please see license.txt

"""
RFID SQL Server Poller
======================
Pulls new rows from dbo.iclock_trans_ajim (or the configured view) on the
remote MS SQL Server and inserts them as Attendance Log records in Frappe.

Flow:
  1. Read last_processed_id from Attendance Settings (watermark)
  2. SELECT rows WHERE Id > last_processed_id ORDER BY Id ASC
  3. For each row:
       a. Skip if source_id already exists in Attendance Log (idempotent)
       b. Resolve emp_code → Student via Student RFID Card
       c. Insert Attendance Log record (processed=0 so the existing
          process_pending_logs scheduler picks it up next)
  4. Update last_processed_id in Attendance Settings
  5. Commit

The scheduler job at * * * * * (process_pending_logs) converts these raw
logs into Student Attendance records automatically, right after this poller
runs in the same minute.

This poller is registered at * * * * * (the shortest interval Frappe's
cron scheduler supports) so new swipes appear within ~1-2 minutes on the
worst path. Admins can also call poll_now() manually, or click "Refresh
Now" on the RFID Card Management page, to pull immediately on demand.
"""

import frappe
from frappe.utils import now_datetime


# ---------------------------------------------------------------------------
# Main entry point (called by scheduler)
# ---------------------------------------------------------------------------

def poll_rfid_swipes():
    """
    Scheduled entry point.  Silently exits when RFID or SQL Server is not
    configured so it never breaks the scheduler loop.
    """
    try:
        cfg = frappe.get_single("Attendance Settings")

        if not cfg.enable_rfid:
            return

        if not cfg.mssql_server:
            return

        _run_poll(cfg)

    except Exception as e:
        frappe.log_error(
            title="RFID SQL Poller — Unhandled Error",
            message=frappe.get_traceback()
        )


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def _run_poll(cfg):
    """Pull rows from SQL Server and write Attendance Logs."""
    from slcm.slcm.utils.mssql_connection import get_mssql_connection

    last_id = int(cfg.mssql_last_processed_id or 0)
    # Whitelist view name to only alphanumeric, dots, underscores — prevents SQL injection
    import re
    raw_view = (cfg.mssql_view or "dbo.iclock_trans_ajim").strip()
    view = re.sub(r"[^\w\.]", "", raw_view) or "dbo.iclock_trans_ajim"
    batch   = 500   # max rows per run to avoid memory spikes

    conn = get_mssql_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT TOP {batch}
                Id,
                emp_code,
                punch_time,
                terminal_id,
                terminal_alias,
                area_alias
            FROM {view}
            WHERE Id > ?
            ORDER BY Id ASC
            """,
            last_id
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    if not rows:
        return

    imported   = 0
    skipped    = 0
    max_id     = last_id
    rfid_cache = {}   # emp_code → {student, rfid_uid} or None

    for row in rows:
        sql_id         = row[0]
        emp_code       = (row[1] or "").strip()
        punch_time     = row[2]          # datetime object from pyodbc
        terminal_id    = str(row[3] or "")
        terminal_alias = (row[4] or "").strip()
        area_alias     = (row[5] or "").strip()

        if sql_id > max_id:
            max_id = sql_id

        if not emp_code or not punch_time:
            skipped += 1
            continue

        # --- Idempotency: skip if this SQL row was already imported ----------
        # Use sql_id > 0 guard so manual logs (source_id=NULL/0) are never matched
        if sql_id and frappe.db.exists("Attendance Log", {"source": "RFID", "source_id": sql_id}):
            skipped += 1
            continue

        # --- Resolve emp_code → Student RFID Card → Student -----------------
        if emp_code not in rfid_cache:
            rfid_cache[emp_code] = _resolve_rfid(emp_code)

        rfid_info = rfid_cache[emp_code]

        # We always import the raw log regardless of whether the card was
        # found; student field stays blank and a human / admin can fix it.
        rfid_uid = rfid_info["rfid_uid"] if rfid_info else emp_code
        student  = rfid_info["student"]  if rfid_info else None

        try:
            doc = frappe.get_doc({
                "doctype":        "Attendance Log",
                "rfid_uid":       rfid_uid,
                "student":        student,
                "swipe_time":     punch_time,
                "device_id":      terminal_id,
                "location":       area_alias,
                "terminal_alias": terminal_alias,
                "source":         "RFID",
                "source_id":      sql_id,
                "processed":      0,
            })
            doc.insert(ignore_permissions=True)
            imported += 1
        except Exception:
            frappe.log_error(
                title=f"RFID Poller — Failed to insert log for emp {emp_code} (SQL id {sql_id})",
                message=frappe.get_traceback()
            )

    # --- Persist watermark ---------------------------------------------------
    if max_id > last_id:
        frappe.db.set_single_value(
            "Attendance Settings", "mssql_last_processed_id", max_id
        )

    frappe.db.commit()

    if imported or skipped:
        frappe.logger("rfid_poller").info(
            f"RFID Poller: imported={imported}, skipped={skipped}, "
            f"max_id={max_id}, ran_at={now_datetime()}"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_rfid(emp_code):
    """
    Resolve emp_code → student.
    Lookup order:
      1. Student Master.rfid_uid  (direct match — preferred)
      2. Student RFID Card.rfid_uid (separate card record)
    Returns {"rfid_uid": emp_code, "student": <name>} or None.
    """
    # 1. Direct match on Student Master
    student = frappe.db.get_value("Student Master", {"rfid_uid": emp_code}, "name")
    if student:
        return {"rfid_uid": emp_code, "student": student}

    # 2. Separate RFID card record
    card = frappe.db.get_value(
        "Student RFID Card",
        {"rfid_uid": emp_code, "card_status": "Active"},
        ["rfid_uid", "student"],
        as_dict=True
    )
    return card or None


# ---------------------------------------------------------------------------
# Whitelisted manual trigger (for admin use / testing)
# ---------------------------------------------------------------------------

@frappe.whitelist()
def poll_now():
    """
    Manually trigger the poller from the browser or bench console.

    bench execute slcm.slcm.utils.rfid_sql_poller.poll_now
    """
    try:
        cfg = frappe.get_single("Attendance Settings")
        if not cfg.mssql_server:
            return {"success": False, "message": "SQL Server not configured in Attendance Settings."}
        _run_poll(cfg)
        new_last = frappe.db.get_single_value("Attendance Settings", "mssql_last_processed_id")
        return {
            "success": True,
            "message": f"Poll complete. Last processed SQL ID: {new_last}"
        }
    except Exception as e:
        frappe.log_error(title="RFID poll_now error", message=frappe.get_traceback())
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def reset_watermark(new_id=0):
    """
    Reset the last-processed-id watermark.  Use when re-importing from scratch
    or after a data migration.

    bench execute slcm.slcm.utils.rfid_sql_poller.reset_watermark --kwargs '{"new_id": 0}'
    """
    frappe.only_for("System Manager")
    frappe.db.set_single_value("Attendance Settings", "mssql_last_processed_id", int(new_id))
    frappe.db.commit()
    return {"success": True, "message": f"Watermark reset to {new_id}"}


@frappe.whitelist()
def rematch_unlinked_logs():
    """
    Re-scan all Attendance Log records where student is NULL and try to
    resolve them again against the current Student Master / RFID Card data.

    Call this after admin has set rfid_uid values on Student Master records
    so that previously imported logs get linked to the correct student.

    bench execute slcm.slcm.utils.rfid_sql_poller.rematch_unlinked_logs
    """
    unlinked = frappe.db.sql("""
        SELECT name, rfid_uid FROM `tabAttendance Log`
        WHERE (student IS NULL OR student = '')
        ORDER BY name ASC
    """, as_dict=True)

    if not unlinked:
        return {"success": True, "matched": 0, "still_unmatched": 0,
                "message": "No unlinked logs found."}

    matched        = 0
    still_unmatched = 0
    cache          = {}

    for log in unlinked:
        rfid_uid = log.rfid_uid
        if rfid_uid not in cache:
            cache[rfid_uid] = _resolve_rfid(rfid_uid)

        info = cache[rfid_uid]
        if info and info.get("student"):
            frappe.db.set_value("Attendance Log", log.name, "student", info["student"])
            matched += 1
        else:
            still_unmatched += 1

    frappe.db.commit()
    return {
        "success": True,
        "matched": matched,
        "still_unmatched": still_unmatched,
        "message": f"Matched {matched} logs. {still_unmatched} still unmatched (RFID UID not set on any student)."
    }
