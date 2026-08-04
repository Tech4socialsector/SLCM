import frappe

def check_stuck_bulk_emails():
    threshold = frappe.utils.add_to_date(frappe.utils.now_datetime(), minutes=-5)
    stuck = frappe.get_all("Bulk Email",
        filters={
            "status": "In Progress",
            "last_heartbeat": ["<", threshold]
        },
        or_filters=[{"last_heartbeat": ["is", "not set"]}],
        pluck="name")

    for name in stuck:
        doc = frappe.get_doc("Bulk Email", name)
        
        # Reset any "Sending" rows back to "Queued" to allow retry
        for row in doc.recipients:
            if row.status == "Sending":
                row.status = "Queued"
                row.db_update()
        frappe.db.commit()

        doc.db_set("server_response",
            (doc.server_response or "") +
            f"\nAuto-recovery: job appeared stalled at {frappe.utils.now()} "
            f"(no progress for 5+ min) — re-enqueuing remaining "
            f"{len([r for r in doc.recipients if r.status == 'Queued'])} recipients.")
        frappe.db.commit()
        
        frappe.enqueue(
            method="slcm.slcm.doctype.bulk_email.bulk_email.process_bulk_email",
            queue="short", timeout=600, bulk_email_name=name
        )
