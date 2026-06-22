# Copyright (c) 2026, Nishanth and contributors
# For license information, please see license.txt

import frappe
import csv
import io


# ── Page data APIs ────────────────────────────────────────────────

@frappe.whitelist()
def get_rfid_summary():
    """Full page load — stats + unlinked cards + linked cards + live feed."""

    stats = frappe.db.sql("""
        SELECT
            COUNT(*)                                            AS total_logs,
            SUM(student IS NOT NULL AND student != '')         AS linked_logs,
            SUM(student IS NULL OR student = '')               AS unlinked_logs,
            MAX(swipe_time)                                    AS last_swipe,
            MAX(source_id)                                     AS last_sql_id
        FROM `tabAttendance Log`
    """, as_dict=True)[0]

    student_stats = frappe.db.sql("""
        SELECT
            COUNT(*)                                            AS total_students,
            SUM(rfid_uid IS NOT NULL AND rfid_uid != '')       AS students_with_rfid,
            SUM(rfid_uid IS NULL OR rfid_uid = '')             AS students_without_rfid
        FROM `tabStudent Master`
    """, as_dict=True)[0]

    # Distinct RFID UIDs seen from SQL Server that are NOT linked to any student
    unlinked_cards = frappe.db.sql("""
        SELECT
            al.rfid_uid,
            COUNT(*)               AS swipe_count,
            MAX(al.swipe_time)     AS last_seen,
            MAX(al.device_id)      AS terminal_id,
            MAX(al.terminal_alias) AS terminal,
            MAX(al.location)       AS area
        FROM `tabAttendance Log` al
        WHERE al.student IS NULL OR al.student = ''
        GROUP BY al.rfid_uid
        ORDER BY last_seen DESC
        LIMIT 500
    """, as_dict=True)

    # Students already linked
    linked_students = frappe.db.sql("""
        SELECT
            sm.name         AS student_id,
            sm.first_name   AS student_name,
            sm.programme    AS programme,
            sm.batch_year,
            sm.department,
            sm.rfid_uid,
            COUNT(al.name)  AS total_swipes,
            MAX(al.swipe_time) AS last_swipe
        FROM `tabStudent Master` sm
        LEFT JOIN `tabAttendance Log` al ON al.student = sm.name
        WHERE sm.rfid_uid IS NOT NULL AND sm.rfid_uid != ''
        GROUP BY sm.name, sm.first_name, sm.programme, sm.batch_year, sm.department, sm.rfid_uid
        ORDER BY sm.first_name ASC
    """, as_dict=True)

    # Live feed — last 100 logs with all SQL Server source columns
    recent_logs = frappe.db.sql("""
        SELECT
            al.rfid_uid,
            al.student,
            sm.first_name       AS student_name,
            al.swipe_time,
            al.terminal_alias,
            al.location         AS area_alias,
            al.device_id,
            al.processed
        FROM `tabAttendance Log` al
        LEFT JOIN `tabStudent Master` sm ON sm.name = al.student
        ORDER BY al.swipe_time DESC
        LIMIT 100
    """, as_dict=True)

    return {
        "stats":           stats,
        "student_stats":   student_stats,
        "unlinked_cards":  unlinked_cards,
        "linked_students": linked_students,
        "recent_logs":     recent_logs,
    }


@frappe.whitelist()
def get_live_feed(since_swipe_time=None):
    """Incremental refresh every 30 s — only new logs + updated stats."""

    stats = frappe.db.sql("""
        SELECT
            COUNT(*)                                            AS total_logs,
            SUM(student IS NOT NULL AND student != '')         AS linked_logs,
            SUM(student IS NULL OR student = '')               AS unlinked_logs,
            MAX(swipe_time)                                    AS last_swipe,
            MAX(source_id)                                     AS last_sql_id
        FROM `tabAttendance Log`
    """, as_dict=True)[0]

    args = []
    where = ""
    if since_swipe_time:
        where = "WHERE al.swipe_time > %s"
        args.append(since_swipe_time)

    new_logs = frappe.db.sql(f"""
        SELECT
            al.rfid_uid,
            al.student,
            sm.first_name       AS student_name,
            al.swipe_time,
            al.terminal_alias,
            al.location         AS area_alias,
            al.device_id,
            al.processed
        FROM `tabAttendance Log` al
        LEFT JOIN `tabStudent Master` sm ON sm.name = al.student
        {where}
        ORDER BY al.swipe_time DESC
        LIMIT 50
    """, args, as_dict=True)

    return {"stats": stats, "new_logs": new_logs}


# ── Linking APIs ──────────────────────────────────────────────────

@frappe.whitelist()
def link_rfid_to_student(rfid_uid, student):
    """
    Assign rfid_uid to a Student Master record.
    Backfills all existing Attendance Logs for that UID.
    """
    rfid_uid = (rfid_uid or "").strip()
    student  = (student  or "").strip()

    if not rfid_uid or not student:
        frappe.throw("Both RFID UID and Student are required.")

    # Prevent duplicate assignment
    existing = frappe.db.get_value("Student Master", {"rfid_uid": rfid_uid}, "name")
    if existing and existing != student:
        frappe.throw(
            f"RFID UID <b>{rfid_uid}</b> is already assigned to student <b>{existing}</b>. "
            "Remove it from that student first."
        )

    # Check student exists
    if not frappe.db.exists("Student Master", student):
        frappe.throw(f"Student '{student}' not found.")

    frappe.db.set_value("Student Master", student, "rfid_uid", rfid_uid)

    # Backfill existing logs
    frappe.db.sql("""
        UPDATE `tabAttendance Log`
        SET student = %s
        WHERE rfid_uid = %s AND (student IS NULL OR student = '')
    """, (student, rfid_uid))

    frappe.db.commit()

    linked = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabAttendance Log`
        WHERE rfid_uid = %s AND student = %s
    """, (rfid_uid, student), as_list=True)[0][0]
    student_name = frappe.db.get_value("Student Master", student, "first_name")

    return {
        "success": True,
        "message": f"RFID <b>{rfid_uid}</b> linked to <b>{student_name}</b>. {linked} log(s) updated."
    }


@frappe.whitelist()
def unlink_rfid_from_student(student):
    """Remove the rfid_uid from a Student Master record."""
    frappe.only_for("System Manager")
    if not frappe.db.exists("Student Master", student):
        frappe.throw(f"Student '{student}' not found.")
    old_uid = frappe.db.get_value("Student Master", student, "rfid_uid")
    frappe.db.set_value("Student Master", student, "rfid_uid", None)
    frappe.db.commit()
    return {"success": True, "message": f"RFID UID '{old_uid}' removed from student."}


# ── Export for vendor ─────────────────────────────────────────────

@frappe.whitelist()
def get_export_data():
    """
    Returns student list for vendor — columns the vendor needs to
    program RFID cards: Student ID, Name, Programme, Batch, Department.
    Excludes students who already have an RFID UID assigned.
    """
    rows = frappe.db.sql("""
        SELECT
            sm.name         AS student_id,
            sm.first_name   AS student_name,
            sm.programme    AS programme,
            sm.batch_year   AS batch_year,
            sm.department   AS department,
            sm.official_email_id AS email
        FROM `tabStudent Master` sm
        WHERE sm.rfid_uid IS NULL OR sm.rfid_uid = ''
        ORDER BY sm.programme, sm.batch_year, sm.first_name
    """, as_dict=True)

    return rows


# ── Bulk import (CSV upload) ──────────────────────────────────────

@frappe.whitelist()
def bulk_import_rfid(csv_data):
    """
    Accept CSV text with columns: student_id, rfid_uid
    Links each student to their RFID UID and backfills logs.

    Returns per-row results so UI can show exactly what succeeded/failed.
    """
    frappe.only_for("System Manager")

    results = {"linked": [], "skipped": [], "errors": []}

    try:
        reader = csv.DictReader(io.StringIO(csv_data))
    except Exception as e:
        frappe.throw(f"Invalid CSV: {e}")

    for i, row in enumerate(reader, start=2):  # row 1 = header
        student_id = (row.get("student_id") or row.get("Student ID") or "").strip()
        rfid_uid   = (row.get("rfid_uid")   or row.get("RFID UID")   or "").strip()

        if not student_id or not rfid_uid:
            results["skipped"].append({"row": i, "reason": "Empty student_id or rfid_uid"})
            continue

        if not frappe.db.exists("Student Master", student_id):
            results["errors"].append({
                "row": i, "student_id": student_id, "rfid_uid": rfid_uid,
                "reason": f"Student '{student_id}' not found in system"
            })
            continue

        existing = frappe.db.get_value("Student Master", {"rfid_uid": rfid_uid}, "name")
        if existing and existing != student_id:
            results["errors"].append({
                "row": i, "student_id": student_id, "rfid_uid": rfid_uid,
                "reason": f"RFID UID already assigned to {existing}"
            })
            continue

        try:
            frappe.db.set_value("Student Master", student_id, "rfid_uid", rfid_uid)
            frappe.db.sql("""
                UPDATE `tabAttendance Log`
                SET student = %s
                WHERE rfid_uid = %s AND (student IS NULL OR student = '')
            """, (student_id, rfid_uid))
            student_name = frappe.db.get_value("Student Master", student_id, "first_name")
            results["linked"].append({
                "row": i, "student_id": student_id,
                "student_name": student_name, "rfid_uid": rfid_uid
            })
        except Exception as e:
            results["errors"].append({
                "row": i, "student_id": student_id, "rfid_uid": rfid_uid,
                "reason": str(e)
            })

    frappe.db.commit()

    total = len(results["linked"])
    errors = len(results["errors"])
    return {
        "success": True,
        "message": f"Import complete: {total} linked, {errors} error(s).",
        "results": results
    }
