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
        verification_doc.assigned_verifier = selected_verifier
        
        # Set Due Date based on SLA
        days = config.days_to_verify or 2
        verification_doc.due_date = add_days(nowdate(), days)
        
        # Sync back to PACE Application
        frappe.db.set_value("PACE Application", verification_doc.application, "assigned_verifier", selected_verifier)
        
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
        frappe.sendmail(
            recipients=[verifier],
            subject=subject,
            message=message,
            now=False
        )
        
        frappe.logger().info(f"PACE Verifier Assignment Email queued for {verifier}")

    except Exception:
        import traceback
        frappe.log_error(traceback.format_exc(), f"PACE Verifier Assignment Email Failed")

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
    doc.assigned_verifier = verifier
    
    # Update due date based on configuration SLA
    programme, academic_year = frappe.db.get_value("PACE Application", doc.application, ["programme", "academic_year"])
    days = frappe.db.get_value("PACE Verifier Configuration", {"programme": programme, "academic_year": academic_year}, "days_to_verify") or 2
    doc.due_date = add_days(nowdate(), days)
    
    doc.save(ignore_permissions=True)
    
    # Sync back to PACE Application
    frappe.db.set_value("PACE Application", doc.application, "assigned_verifier", verifier)
    
    # Notify
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
        if doc.overall_status == "Pending":
            assign_verifier_round_robin(doc, force_reassign=True)
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
def get_overdue_for_verifier(verifier=None):
    """
    Returns a list of overdue verification records. 
    If verifier is provided, filters by that verifier.
    """
    filters = {
        "overall_status": "Pending",
        "is_overdue": 1
    }
    
    if verifier and verifier.strip():
        # Handle "Unassigned" specifically if passed as a string
        if verifier == "Unassigned":
            filters["assigned_verifier"] = ["in", ["", None]]
        else:
            filters["assigned_verifier"] = verifier
        
    return frappe.get_all("PACE Document Verification", 
        filters=filters, 
        fields=["name", "applicant_name", "application", "assigned_verifier", "due_date"],
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
        "overall_status": "Pending"
    }
    if from_verifier:
        filters["assigned_verifier"] = from_verifier
        
    if names:
        import json
        if isinstance(names, str):
            names = json.loads(names)
        filters["name"] = ["in", names]

    records = frappe.get_all("PACE Document Verification", filters=filters, fields=["name", "application"])
    
    # Get SLA days for due date reset
    def get_sla_days(app_name):
        prog, year = frappe.db.get_value("PACE Application", app_name, ["programme", "academic_year"])
        days = frappe.db.get_value("PACE Verifier Configuration", {"programme": prog, "academic_year": year}, "days_to_verify")
        return int(days) if days else 2

    count = 0
    assigned_docs = []
    for rec in records:
        # Calculate new due date
        days = get_sla_days(rec.application)
        new_due_date = add_days(nowdate(), days)
        
        # Update Verification Record (Resetting Overdue status)
        frappe.db.set_value("PACE Document Verification", rec.name, {
            "assigned_verifier": to_verifier,
            "due_date": new_due_date,
            "is_overdue": 0
        })
        
        # Update Parent Application
        frappe.db.set_value("PACE Application", rec.application, "assigned_verifier", to_verifier)
        
        # Update ToDo
        frappe.db.sql("""
            UPDATE `tabToDo` SET owner = %s WHERE reference_type = 'PACE Document Verification' 
            AND reference_name = %s AND status = 'Open'
        """, (to_verifier, rec.name))
        
        assigned_docs.append(rec.name)
        count += 1
        
    # Notify
    if assigned_docs:
        send_verifier_assignment_email(to_verifier, assigned_docs)
        
    return count

def check_overdue_verifications():
    """
    Scheduled job to flag overdue verification records and notify managers.
    """
    today = nowdate()
    
    # 1. Find pending verifications that are past due
    overdue_records = frappe.get_all("PACE Document Verification", filters={
        "overall_status": "Pending",
        "due_date": ["<", today],
        "is_overdue": 0
    }, fields=["name", "assigned_verifier", "application", "due_date"])

    if not overdue_records:
        return

    for rec in overdue_records:
        # Flag as overdue
        frappe.db.set_value("PACE Document Verification", rec.name, "is_overdue", 1)
        
        # Log it
        frappe.logger().warning(f"PACE Verification Overdue: {rec.name} (Assigned to: {rec.assigned_verifier})")

    # 2. Notify Admission Managers
    # Find users with "PACE Admission Manager" or "Admission Admin" roles
    managers = frappe.get_all("Has Role", filters={
        "role": ["in", ["PACE Admission Manager", "Admission Admin"]],
        "parenttype": "User"
    }, fields=["parent"])
    
    manager_emails = list(set([m.parent for m in managers]))
    
    if manager_emails:
        subject = _("Alert: Overdue PACE Document Verifications")
        
        # Create a simple table for the email
        rows = ""
        for rec in overdue_records:
            rows += f"<tr><td>{rec.name}</td><td>{rec.application}</td><td>{rec.assigned_verifier}</td><td>{rec.due_date}</td></tr>"
            
        message = f"""
        <h3>Overdue Verification Alert</h3>
        <p>The following PACE Document Verification records have exceeded their assigned SLA:</p>
        <table border="1" cellpadding="5" style="border-collapse: collapse; width: 100%;">
            <thead>
                <tr style="background-color: #f2f2f2;">
                    <th>Record</th>
                    <th>Application</th>
                    <th>Assigned Verifier</th>
                    <th>Due Date</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
        <p>Please review and reassign if necessary.</p>
        """
        
        frappe.sendmail(
            recipients=manager_emails,
            subject=subject,
            message=message,
            now=False
        )
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
        
        # Build application filter based on programme and academic year
        app_filters = {}
        if row_programme:
            app_filters["programme"] = row_programme
        if academic_year:
            app_filters["academic_year"] = academic_year
            
        if app_filters:
            app_names = frappe.get_all("PACE Application", filters=app_filters, pluck="name")
            if app_names:
                filters["application"] = ["in", app_names]
            else:
                # If no apps match programme/year, then all stats are 0
                stats[verifier] = {"total_assigned": 0, "verified": 0, "pending": 0}
                continue

        total = frappe.db.count("PACE Document Verification", filters)
        
        verified_filters = filters.copy()
        verified_filters["overall_status"] = "Verified"
        verified = frappe.db.count("PACE Document Verification", verified_filters)
        
        pending_filters = filters.copy()
        pending_filters["overall_status"] = "Pending"
        pending = frappe.db.count("PACE Document Verification", pending_filters)
        
        # Use a key that includes programme if needed, or just the verifier 
        # (Assuming verifier only appears once in the list for this logic)
        stats[verifier] = {
            "total_assigned": total,
            "verified": verified,
            "pending": pending
        }
        
    return stats
