import frappe
from frappe import _
from frappe.utils import add_days, nowdate

def is_user_on_leave(user, date=None):
    """
    Checks if a user has an approved leave application for the given date.
    """
    if not date:
        date = nowdate()
    
    # Check if HR module/Leave Application exists
    if not frappe.db.exists("DocType", "Leave Application"):
        return False
        
    leave = frappe.db.exists("Leave Application", {
        "employee_email": user, # Assuming email matches or there's a link
        "status": "Approved",
        "from_date": ["<=", date],
        "to_date": [">=", date]
    })
    
    if not leave:
        # Fallback check by User ID if email field is named differently or not present
        leave = frappe.db.exists("Leave Application", {
            "user": user,
            "status": "Approved",
            "from_date": ["<=", date],
            "to_date": [">=", date]
        })
        
    return bool(leave)

def get_sla_days(app_name):
    """
    Returns the configured SLA days for document verification based on the application's programme.
    """
    app_data = frappe.db.get_value("PACE Application", app_name, ["programme", "academic_year"], as_dict=True)
    if not app_data: return 2
    
    # Try finding config name using the same fallbacks as round robin
    config_name = frappe.db.get_value("PACE Verifier Mapping", 
        {"programme": app_data.programme, "parenttype": "PACE Verifier Configuration"}, 
        "parent")
    
    if not config_name:
        config_name = frappe.db.get_value("PACE Verifier Configuration", {
            "programme": app_data.programme,
            "academic_year": app_data.academic_year
        }, "name")
        
    if not config_name:
        config_name = frappe.db.get_value("PACE Verifier Configuration", {
            "academic_year": app_data.academic_year
        }, "name")

    if config_name:
        days = frappe.db.get_value("PACE Verifier Configuration", config_name, "days_to_verify")
        return int(days) if days else 2
    return 2

def assign_verifier_round_robin(verification_doc, force_reassign=False):
    """
    Assigns a verifier to the PACE Document Verification record based on the programme's 
    Round Robin configuration and sets the due date.
    Now supports programme-specific verifiers within the child table.
    """
    # 1. Get Programme and Academic Year from Application
    app_data = frappe.db.get_value("PACE Application", verification_doc.application, ["programme", "academic_year"], as_dict=True)
    if not app_data or not app_data.programme or not app_data.academic_year:
        return

    # 2. Fetch Configuration
    # First, try to find a configuration that has this specific programme in its verifiers list
    config_name = frappe.db.get_value("PACE Verifier Mapping", 
        {"programme": app_data.programme, "parenttype": "PACE Verifier Configuration"}, 
        "parent")
    
    if not config_name:
        # Fallback to parent level programme lookup
        config_name = frappe.db.get_value("PACE Verifier Configuration", {
            "programme": app_data.programme,
            "academic_year": app_data.academic_year
        }, "name")

    if not config_name:
        # Final fallback: any config for the Academic Year
        config_name = frappe.db.get_value("PACE Verifier Configuration", {
            "academic_year": app_data.academic_year
        }, "name")

    if not config_name:
        frappe.logger().info(f"PACE Assignment: No Verifier Configuration found for {app_data.programme} in {app_data.academic_year}")
        return

    config = frappe.get_doc("PACE Verifier Configuration", config_name)
    verifiers = config.verifiers
    
    if not verifiers:
        frappe.logger().info(f"PACE Assignment: No verifiers listed in configuration {config_name}")
        return

    # 3. Calculate Next Verifier with "Out of Office" and Programme Check
    total_verifiers = len(verifiers)
    last_index = config.last_assigned_index
    
    selected_verifier = None
    next_index = last_index
    
    # First Pass: Look for explicit programme matches
    for _ in range(total_verifiers):
        next_index = (next_index + 1) % total_verifiers
        v_row = verifiers[next_index]
        
        if v_row.programme == app_data.programme:
            candidate = v_row.user
            if not is_user_on_leave(candidate):
                selected_verifier = candidate
                break
                
    # Second Pass: If no explicit match found, look for global fallbacks (only if parent matches)
    if not selected_verifier:
        next_index = last_index # Reset search index for second pass
        for _ in range(total_verifiers):
            next_index = (next_index + 1) % total_verifiers
            v_row = verifiers[next_index]
            
            if not v_row.programme and config.programme == app_data.programme:
                candidate = v_row.user
                if not is_user_on_leave(candidate):
                    selected_verifier = candidate
                    break
            
    if not selected_verifier:
        frappe.logger().warning(f"PACE Assignment: No suitable verifier found for {app_data.programme}")
        return

    # 4. Update Verification Record
    if not verification_doc.assigned_verifier or force_reassign:
        old_verifier = verification_doc.assigned_verifier
        verification_doc.assigned_verifier = selected_verifier
        
        # Set Due Date based on SLA
        days = config.days_to_verify or 2
        verification_doc.due_date = add_days(nowdate(), days)
        verification_doc.is_overdue = 0
        
        # Sync back to PACE Application
        frappe.db.set_value("PACE Application", verification_doc.application, "assigned_verifier", selected_verifier)
        
        # 4.5. Update Permissions and ToDo
        update_verifier_permissions(verification_doc.name, old_verifier, selected_verifier)

        # 5. Persistent State Update for Round Robin
        if total_verifiers > 1:
            config.db_set("last_assigned_index", next_index)
            frappe.logger().info(f"PACE Assignment: Round Robin assigned to {selected_verifier} (Index: {next_index}) for {app_data.programme}")

def send_verifier_assignment_email(verifier, verification_records):
    """
    Sends the "PACE Verifier Assignment" email to the assigned verifier.
    verifier: user email
    verification_records: list of PACE Document Verification docs or names
    """
    try:
        if not verifier or not verification_records:
            return

        template_name = "PACE Verifier Assignment"
        
        targets = []
        for item in verification_records:
            if isinstance(item, str):
                doc = frappe.get_doc("PACE Document Verification", item)
            else:
                doc = item
                
            programme = frappe.db.get_value("PACE Application", doc.application, "programme")
            targets.append({
                "name": doc.application,
                "applicant_name": doc.applicant_name,
                "programme": programme,
                "due_date": frappe.utils.formatdate(doc.due_date)
            })

        args = {
            "verifier_name": frappe.db.get_value("User", verifier, "full_name") or verifier,
            "targets": targets
        }

        if not frappe.db.exists("Email Template", template_name):
            frappe.log_error(f"Email Template '{template_name}' not found. Cannot send verifier assignment email.", "PACE Assignment Notification Error")
            return

        email_template = frappe.get_doc("Email Template", template_name)
        subject = frappe.render_template(email_template.subject or "New PACE Document Verification Assignment", args)
        
        if email_template.get("use_html"):
            message = frappe.render_template(email_template.response_html, args)
        else:
            message = frappe.render_template(email_template.response, args)

        if not message:
            message = frappe.render_template(email_template.get("message") or "", args)

        # Send Email
        # Get reference for the first document in the list for email linking
        ref_doc = verification_records[0]
        ref_name = ref_doc.name if not isinstance(ref_doc, str) else ref_doc
        
        sender = None
        if email_template.get("email_account"):
            sender = frappe.db.get_value("Email Account", email_template.get("email_account"), "email_id") or email_template.get("email_account")

        frappe.sendmail(
            recipients=[verifier],
            sender=sender,
            subject=subject,
            message=message,
            reference_doctype="PACE Document Verification",
            reference_name=ref_name,
            now=False
        )
        
        # Add System Notification for Verifier Assignment
        if frappe.db.exists("User", verifier):
            frappe.get_doc({
                "doctype": "Notification Log",
                "for_user": verifier,
                "subject": "New PACE Verification Assignment",
                "type": "Alert",
                "email_content": message,
                "document_type": "PACE Document Verification",
                "document_name": ref_name,
                "from_user": frappe.session.user or "Administrator",
                "link": f"/app/pace-document-verification/{ref_name}"
            }).insert(ignore_permissions=True)
            
        frappe.logger().info(f"PACE Verifier Assignment Email queued for {verifier}")

    except Exception:
        frappe.log_error(frappe.get_traceback(), f"PACE Verifier Assignment Email Failed")

@frappe.whitelist()
def manual_reassign(name):
    """
    Triggered by Manager to manually re-assign a stuck record via Round Robin.
    """
    # Permission Check
    roles = frappe.get_roles()
    if "PACE Admission Manager" not in roles and "System Manager" not in roles and "Admission Admin" not in roles:
        frappe.throw(_("You are not authorized to re-assign records."))

    doc = frappe.get_doc("PACE Document Verification", name)
    
    # Force the Round Robin to pick a new person
    assign_verifier_round_robin(doc, force_reassign=True)
    doc.flags.ignore_assignment_email = True # on_update would send single email, we handle manually below
    doc.flags.ignore_permissions = True
    doc.save(ignore_permissions=True)
    
    # Notify
    send_verifier_assignment_email(doc.assigned_verifier, [doc])
    
    return doc.assigned_verifier

@frappe.whitelist()
def reassign_to_user(name, verifier):
    """
    Manually re-assign a record to a specific user chosen by the Manager.
    """
    # Permission Check
    roles = frappe.get_roles()
    if "PACE Admission Manager" not in roles and "System Manager" not in roles and "Admission Admin" not in roles:
        frappe.throw(_("You are not authorized to re-assign records."))

    if not verifier:
        frappe.throw(_("Please select a verifier."))

    doc = frappe.get_doc("PACE Document Verification", name)
    old_verifier = doc.assigned_verifier
    doc.assigned_verifier = verifier
    
    # Update due date based on configuration SLA
    days = get_sla_days(doc.application)
    doc.due_date = add_days(nowdate(), days)
    doc.is_overdue = 0
    
    doc.flags.ignore_assignment_email = True
    doc.flags.ignore_permissions = True
    doc.save(ignore_permissions=True)
    
    # 4. Sync back to PACE Application
    frappe.db.set_value("PACE Application", doc.application, "assigned_verifier", verifier, update_modified=True)
    
    # 5. Notify
    send_verifier_assignment_email(verifier, [doc])
    
    return _("Successfully re-assigned to {0}").format(verifier)

@frappe.whitelist()
def bulk_reassign_verifiers(names):
    """
    Called from List View to re-assign multiple records at once.
    """
    import json
    if isinstance(names, str):
        names = json.loads(names)

    # Permission Check
    roles = frappe.get_roles()
    if "PACE Admission Manager" not in roles and "System Manager" not in roles and "Admission Admin" not in roles:
        frappe.throw(_("You are not authorized to perform bulk re-assignment."))

    assignments = {} # verifier -> [docs]
    count = 0
    for name in names:
        doc = frappe.get_doc("PACE Document Verification", name)
        # Only re-assign if it's still pending
        if doc.status == "Pending":
            assign_verifier_round_robin(doc, force_reassign=True)
            doc.flags.ignore_assignment_email = True # Bulk batching handled manually below
            doc.flags.ignore_permissions = True
            doc.save(ignore_permissions=True)
            
            if doc.assigned_verifier not in assignments:
                assignments[doc.assigned_verifier] = []
            assignments[doc.assigned_verifier].append(doc)
            count += 1
    
    # Send batch emails
    for verifier, docs in assignments.items():
        send_verifier_assignment_email(verifier, docs)
    
    return count

@frappe.whitelist()
def get_overdue_for_verifier(verifier=None, show_all_pending=False):
    """
    Returns a list of overdue verification records, or all pending records if show_all_pending is True. 
    If verifier is provided, filters by that verifier.
    """
    if isinstance(show_all_pending, str):
        show_all_pending = show_all_pending.lower() in ["true", "1"]

    filters = {
        "status": "Pending"
    }
    or_filters = None
    if not show_all_pending:
        or_filters = [
            ["is_overdue", "=", 1],
            ["due_date", "<", nowdate()]
        ]
    
    if verifier and verifier.strip():
        # Handle "Unassigned" specifically if passed as a string
        if verifier == "Unassigned":
            filters["assigned_verifier"] = ["in", ["", None]]
        else:
            filters["assigned_verifier"] = verifier
        
    return frappe.get_all("PACE Document Verification", 
        filters=filters, 
        or_filters=or_filters,
        fields=["name", "applicant_name", "application", "assigned_verifier", "due_date", "is_overdue"],
        order_by="due_date asc")

@frappe.whitelist()
def transfer_verifications(from_verifier, to_verifier, names=None):
    """
    Transfers pending records from one verifier to another.
    """
    # Permission Check
    roles = frappe.get_roles()
    if "PACE Admission Manager" not in roles and "System Manager" not in roles and "Admission Admin" not in roles:
        frappe.throw(_("Unauthorized"))

    if not to_verifier:
        frappe.throw(_("Please select a 'To Verifier' (Assign To)."))

    # If names are not provided, we transfer ALL pending records for that verifier
    filters = {
        "status": "Pending"
    }
    if from_verifier:
        filters["assigned_verifier"] = from_verifier
        
    if names:
        import json
        if isinstance(names, str):
            names = json.loads(names)
        filters["name"] = ["in", names]

    records = frappe.get_all("PACE Document Verification", filters=filters, fields=["name", "application"])

    count = 0
    assigned_docs = []
    for rec in records:
        # Calculate new due date
        days = get_sla_days(rec.application)
        new_due_date = add_days(nowdate(), days)
        
        # 1. Update Verification Record (Using save() to ensure 'modified' is updated and hooks run)
        doc = frappe.get_doc("PACE Document Verification", rec.name)
        doc.assigned_verifier = to_verifier
        doc.due_date = new_due_date
        doc.is_overdue = 0
        doc.flags.ignore_assignment_email = True # Bulk batching handled manually below
        doc.flags.ignore_permissions = True
        doc.save(ignore_permissions=True)
        
        # 2. Update Parent Application
        frappe.db.set_value("PACE Application", rec.application, {
            "assigned_verifier": to_verifier
        }, update_modified=True)
        
        # 3. Update Permissions and ToDo (Already handled by save() via on_update, but kept for explicitness)
        # update_verifier_permissions(rec.name, from_verifier, to_verifier)
        
        assigned_docs.append(rec.name)
        count += 1
        
    # Notify
    if assigned_docs:
        send_verifier_assignment_email(to_verifier, assigned_docs)
        
    return count

def send_overdue_notification_to_verifier(verifier, records, notification_type):
    """
    Sends grouped notifications (email + system) to a verifier based on type.
    notification_type: 'recurring_pending', 'final_expired'
    """
    if not verifier or not records:
        return

    try:
        # Map notification types to Email Template Names
        template_map = {
            "recurring_pending": "PACE Pending Verification Reminder",
            "final_expired": "PACE Final Verification Due Expired"
        }
        
        template_name = template_map.get(notification_type)
        if not template_name or not frappe.db.exists("Email Template", template_name):
            frappe.logger().error(f"Email Template '{template_name}' not found for type '{notification_type}'.")
            return

        # Get Verifier details
        verifier_full_name = frappe.db.get_value("User", verifier, "full_name") or verifier
        
        # Prepare context
        args = {
            "verifier_full_name": verifier_full_name,
            "records": records,
            "notification_type": notification_type
        }

        # 1. Load Email Template and handle CC
        email_template = frappe.get_doc("Email Template", template_name)
        
        cc_list = []
        cc_field_value = email_template.get("cc")
        if cc_field_value:
            # Handle both semicolon and comma separated lists
            cc_list = [c.strip() for c in cc_field_value.replace(";", ",").split(",") if c.strip()]

        # 2. Render Content
        subject = frappe.render_template(email_template.subject, args)
        
        message = ""
        if email_template.get("use_html") and email_template.get("response_html"):
            message = frappe.render_template(email_template.response_html, args)
        elif email_template.get("response"):
            message = frappe.render_template(email_template.response, args)

        if not message:
            message = frappe.render_template(email_template.get("message") or "", args)

        # 3. Send Email
        sender = None
        if email_template.get("email_account"):
            sender = frappe.db.get_value("Email Account", email_template.get("email_account"), "email_id") or email_template.get("email_account")

        if frappe.db.exists("Email Account", {"default_outgoing": 1, "enable_outgoing": 1}) or sender:
            frappe.sendmail(
                recipients=[verifier],
                sender=sender,
                cc=cc_list,
                subject=subject,
                message=message,
                now=False
            )
            from slcm.pace.doctype.pace_reminder_email_log.pace_reminder_email_log import log_pace_reminder_email
            log_pace_reminder_email(
                recipient=verifier,
                subject=subject,
                reminder_type="Verifier Overdue Reminder" if notification_type == "final_expired" else "Verifier Pending Reminder",
                sender=sender,
                reference_doctype="PACE Document Verification",
                reference_name=records[0]["name"], # Corrected to use the verification record name
                email_template=template_name
            )
            frappe.logger().info(f"PACE {notification_type} Notification sent to {verifier} with CC: {cc_list}")
        else:
            frappe.logger().warning(f"Skipping {notification_type} Email for {verifier}: No default outgoing Email Account found.")
            from slcm.pace.doctype.pace_reminder_email_log.pace_reminder_email_log import log_pace_reminder_email
            log_pace_reminder_email(
                recipient=verifier,
                subject=subject,
                reminder_type="Verifier Overdue Reminder" if notification_type == "final_expired" else "Verifier Pending Reminder",
                status="Failed",
                reference_doctype="PACE Document Verification",
                reference_name=records[0]["name"],
                email_template=template_name,
                error_log="No default outgoing Email Account found"
            )

        # 4. System Notification (Bell Icon) & Update Date Fields
        today = nowdate()
        date_field_map = {
            "recurring_pending": "last_pending_reminder_sent_on",
            "final_expired": "due_email_sent_on"
        }
        date_field = date_field_map.get(notification_type)

        for rec in records:
            # Create Notification Log (Bell Icon)
            # We use type="Alert" which is the standard for in-app notifications
            if frappe.db.exists("User", verifier):
                frappe.get_doc({
                    "doctype": "Notification Log",
                    "for_user": verifier,
                    "subject": f"PACE Verification: {notification_type.replace('_', ' ').title()}",
                    "type": "Alert",
                    "email_content": f"Update for application {rec['application']} ({notification_type})",
                    "document_type": "PACE Document Verification",
                    "document_name": rec["name"],
                    "from_user": frappe.session.user or "Administrator",
                    "link": f"/app/pace-document-verification/{rec['name']}"
                }).insert(ignore_permissions=True)

            # Update the specific date field on the record
            if date_field:
                frappe.db.set_value("PACE Document Verification", rec["name"], date_field, today)
        
        return True

    except Exception:
        frappe.log_error(frappe.get_traceback(), f"PACE {notification_type} Notification Error")
        return False

def check_overdue_verifications(current_item=0, total_items=0):
    """
    Scheduled job to notify verifiers/managers about pending and overdue records.
    Should be called daily at 10 AM.
    """
    from frappe.utils import getdate
    today_str = nowdate()
    today = getdate(today_str)
    
    # 1. Get ALL Pending records to process in a single loop
    records = frappe.get_all("PACE Document Verification", filters={
        "status": "Pending"
    }, fields=["name", "assigned_verifier", "application", "due_date", "status", "due_email_sent_on", "last_pending_reminder_sent_on", "is_overdue"])

    if not records:
        return 0

    from slcm.pace.doctype.pace_reminder_email_configuration.pace_reminder_email_configuration import is_reminder_enabled
    pending_enabled = is_reminder_enabled("enable_verifier_pending_reminder")
    overdue_enabled = is_reminder_enabled("enable_verifier_overdue_reminder")

    if not pending_enabled and not overdue_enabled:
        return 0

    verifier_due_map = {}
    verifier_alert_map = {}

    for i, doc in enumerate(records):
        if total_items > 0:
            frappe.publish_realtime("progress", {
                "progress": [current_item + i, total_items],
                "title": "PACE Reminders",
                "description": f"Processing Verifier Notifications: {doc.application}"
            }, user=frappe.session.user)

        if not doc.due_date:
            continue

        doc_due_date = getdate(doc.due_date) if doc.due_date else None
        
        # Case A: Record is Overdue (Passed the due date)
        if doc_due_date and doc_due_date < today:
            # Update 'Is Overdue' flag in UI if not already set
            if not doc.get("is_overdue"):
                frappe.db.set_value("PACE Document Verification", doc.name, "is_overdue", 1)
            
            if not overdue_enabled:
                continue

            # Send "Final Due Expired" notification ONLY ONCE
            if not doc.due_email_sent_on:
                if doc.assigned_verifier:
                    if doc.assigned_verifier not in verifier_due_map:
                        verifier_due_map[doc.assigned_verifier] = []
                    verifier_due_map[doc.assigned_verifier].append(doc)
            
            # CRITICAL: Once overdue, we stop sending any "Pending Reminder" emails.
            # We continue to the next record to avoid falling into Priority 2 logic.
            continue

        # Case B: Record is Pending but NOT yet overdue (today <= due_date)
        if not pending_enabled:
            continue

        # Send Daily Alert Email (recurring_pending)
        last_alert_sent = getdate(doc.last_pending_reminder_sent_on) if doc.last_pending_reminder_sent_on else None
        if last_alert_sent != today:
            if doc.assigned_verifier:
                if doc.assigned_verifier not in verifier_alert_map:
                    verifier_alert_map[doc.assigned_verifier] = []
                verifier_alert_map[doc.assigned_verifier].append(doc)

    # 2. Send Grouped Emails
    sent_count = 0
    # Send Due Emails (First time expiry - Final notification)
    for verifier, docs in verifier_due_map.items():
        if send_overdue_notification_to_verifier(verifier, docs, notification_type="final_expired"):
            sent_count += 1

    # Send Alert Emails (Daily reminders before due date)
    for verifier, docs in verifier_alert_map.items():
        if send_overdue_notification_to_verifier(verifier, docs, notification_type="recurring_pending"):
            sent_count += 1
            
    return sent_count

@frappe.whitelist()
def get_verifier_stats(verifier_list, programme=None, academic_year=None):
    """
    Returns statistics (Total, Verified, Pending) for a list of verifiers.
    verifier_list can be a list of user emails or a list of dicts with {'user': ..., 'programme': ...}
    """
    import json
    if isinstance(verifier_list, str):
        verifier_list = json.loads(verifier_list)
        
    stats = {}
    for item in verifier_list:
        if isinstance(item, dict):
            verifier = item.get('user')
            row_programme = item.get('programme') or programme
        else:
            verifier = item
            row_programme = programme
            
        if not verifier: continue
        
        # Base filters
        filters = {"assigned_verifier": verifier}
        
        if row_programme:
            filters["programme"] = row_programme
        if academic_year:
            filters["academic_year"] = academic_year

        total = frappe.db.count("PACE Document Verification", filters)
        
        verified_filters = filters.copy()
        verified_filters["status"] = "Verified"
        verified = frappe.db.count("PACE Document Verification", verified_filters)
        
        pending_filters = filters.copy()
        pending_filters["status"] = ["in", ["Pending", "Returned for Correction"]]
        pending = frappe.db.count("PACE Document Verification", pending_filters)
        
        key = f"{verifier}:{row_programme or ''}"
        row_stats = {
            "total_assigned": total,
            "verified": verified,
            "pending": pending
        }
        stats[key] = row_stats
        
        # Fallback / aggregated verifier key
        if verifier not in stats:
            stats[verifier] = row_stats.copy()
        else:
            stats[verifier]["total_assigned"] += total
            stats[verifier]["verified"] += verified
            stats[verifier]["pending"] += pending
        
    return stats

def update_verifier_permissions(doc_name, old_verifier, new_verifier):
    """
    Manages document sharing and ToDo ownership when verifiers change.
    Uses standard native Frappe assignment APIs inside an administrative context block.
    """
    import json
    doctype = "PACE Document Verification"

    # 1. Clear all existing verifier assignments safely and SILENTLY
    # We avoid assign_to.clear() because it sends unwanted "assignment removed" emails.
    frappe.db.delete("ToDo", {
        "reference_type": doctype,
        "reference_name": doc_name,
        "status": "Open"
    })

    # 1.5. Standard API to clear all previous sharing (DocShare) entries for this document
    shares = frappe.db.get_all("DocShare", filters={
        "share_doctype": doctype,
        "share_name": doc_name
    }, fields=["name", "user"])
    
    for share in shares:
        if share.user != new_verifier:
            try:
                # Bypass permissions using the flags dictionary instead of changing the user session
                frappe.share.remove(doctype, doc_name, share.user, flags={"ignore_permissions": True})
            except Exception:
                frappe.log_error(frappe.get_traceback(), "PACE Unshare Error")

    # 2. Assign the new verifier manually (creating ToDo & DocShare) to prevent Frappe sending duplicate default email notifications
    if new_verifier:
        # Pre-share the document with the verifier using backend flags to bypass the permission check.
        # This prevents the 'assign_add' function from attempting its own share and throwing a PermissionError.
        try:
            frappe.share.add_docshare(doctype, doc_name, new_verifier, flags={"ignore_share_permission": True})
        except Exception:
            frappe.log_error(frappe.get_traceback(), "PACE Pre-Share Sync Error")

        try:
            if not frappe.db.exists("ToDo", {
                "reference_type": doctype,
                "reference_name": doc_name,
                "status": "Open",
                "allocated_to": new_verifier
            }):
                todo = frappe.get_doc({
                    "doctype": "ToDo",
                    "allocated_to": new_verifier,
                    "reference_type": doctype,
                    "reference_name": str(doc_name),
                    "description": _("Assigned for Document Verification"),
                    "priority": "Medium",
                    "status": "Open",
                    "date": nowdate(),
                    "assigned_by": frappe.session.user or "Administrator"
                })
                todo.flags.ignore_assignment_email = True # We send a custom professional email instead
                todo.insert(ignore_permissions=True)

            # Share document with the verifier if they don't have permission
            doc = frappe.get_doc(doctype, doc_name)
            if not frappe.has_permission(doc=doc, user=new_verifier):
                frappe.share.add(doctype, doc_name, new_verifier, flags={"ignore_share_permission": True})

        except Exception:
            frappe.log_error(frappe.get_traceback(), "PACE Assignment Sync Error")

    # 3. Keep standard UI _assign field synced (Always, even if new_verifier is None)
    try:
        assignments = frappe.db.get_values(
            "ToDo",
            {
                "reference_type": doctype,
                "reference_name": str(doc_name),
                "status": ("not in", ("Cancelled", "Closed")),
                "allocated_to": ("is", "set"),
            },
            "allocated_to",
            pluck=True,
        )
        # Ensure we have a list and deduplicate
        assignments = list(set(assignments))
        frappe.db.set_value(doctype, doc_name, "_assign", json.dumps(assignments) if assignments else "", update_modified=False)
    except Exception:
        pass

@frappe.whitelist()
def check_duplicate_verifier_mapping(academic_year, user, programme, current_docname=None):
    """
    Checks if a programme is already configured for a verifier in the same Academic Year.
    Called from client side to avoid permission errors on the child doctype.
    """
    exists = frappe.db.sql("""
        SELECT pvc.name, pvm.user
        FROM `tabPACE Verifier Mapping` pvm
        JOIN `tabPACE Verifier Configuration` pvc ON pvm.parent = pvc.name
        WHERE pvc.academic_year = %s
          AND pvm.programme = %s
          AND pvc.name != %s
    """, (academic_year, programme, current_docname or ""))
    
    if exists:
        return {
            "parent": exists[0][0],
            "user": exists[0][1]
        }
    return None


