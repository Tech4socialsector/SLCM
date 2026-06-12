"""
One-time utility to fix reports that were accidentally set to prepared_report=1
in the database, which causes the "This is a background report" error and the
TypeError: Cannot read properties of null (reading 'report_end_time') JS crash.

Run on the cloud server after deployment:
    bench execute slcm.api.fix_reports.reset_prepared_report_flags

Or call via API (System Manager only):
    POST /api/method/slcm.api.fix_reports.reset_prepared_report_flags
"""

import frappe


# Reports that must NEVER run as background/prepared reports
SCRIPT_REPORTS_TO_FIX = [
    "FLE Razorpay Settlement Report",
    "FLE Settlement Report",
]


@frappe.whitelist()
def reset_prepared_report_flags():
    """
    Resets prepared_report=0 for all live-API Script Reports in SLCM.
    Safe to run multiple times. Requires System Manager role.
    """
    if not frappe.has_permission("Report", "write"):
        frappe.throw("You do not have permission to run this.", frappe.PermissionError)

    fixed = []

    for report_name in SCRIPT_REPORTS_TO_FIX:
        if not frappe.db.exists("Report", report_name):
            frappe.logger().warning(f"fix_reports: Report '{report_name}' not found in DB — skipping.")
            continue

        current = frappe.db.get_value("Report", report_name, "prepared_report")
        if current:
            frappe.db.set_value("Report", report_name, {
                "prepared_report": 0,
                "timeout": 300,
            })
            # Also delete any stale Prepared Report documents that cause the JS crash
            stale = frappe.get_all(
                "Prepared Report",
                filters={"report_name": report_name},
                pluck="name",
            )
            for pr in stale:
                frappe.delete_doc("Prepared Report", pr, force=True)
                frappe.logger().info(f"fix_reports: Deleted stale Prepared Report '{pr}'")

            fixed.append(report_name)
            frappe.logger().info(
                f"fix_reports: Reset prepared_report=0 for '{report_name}'. "
                f"Deleted {len(stale)} stale Prepared Report doc(s)."
            )
        else:
            frappe.logger().info(f"fix_reports: '{report_name}' already has prepared_report=0 — no change needed.")

    frappe.db.commit()

    if fixed:
        msg = f"Fixed {len(fixed)} report(s): {', '.join(fixed)}. Please hard-refresh your browser (Ctrl+Shift+R)."
    else:
        msg = "All reports were already correctly configured. No changes made."

    frappe.logger().info(f"fix_reports: {msg}")
    return msg
