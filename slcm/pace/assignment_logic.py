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
    """
    # 1. Get Programme and Academic Year from Application
    app_data = frappe.db.get_value("PACE Application", verification_doc.application, ["programme", "academic_year"], as_dict=True)
    if not app_data or not app_data.programme or not app_data.academic_year:
        return

    # 2. Fetch Configuration for the specific Year + Programme
    config_name = frappe.db.get_value("PACE Verifier Configuration", {
        "programme": app_data.programme,
        "academic_year": app_data.academic_year
    }, "name")
    if not config_name:
        frappe.logger().info(f"PACE Assignment: No Verifier Configuration found for programme {app_data.programme} in {app_data.academic_year}")
        return

    config = frappe.get_doc("PACE Verifier Configuration", config_name)
    verifiers = config.verifiers
    
    if not verifiers:
        frappe.logger().info(f"PACE Assignment: No verifiers listed in configuration for {programme}")
        return

    # 3. Calculate Next Verifier with "Out of Office" Check
    total_verifiers = len(verifiers)
    last_index = config.last_assigned_index
    
    selected_verifier = None
    next_index = last_index
    
    # We loop through all verifiers once to find someone who is NOT on leave
    for _ in range(total_verifiers):
        next_index = (next_index + 1) % total_verifiers
        candidate = verifiers[next_index].user
        
        if not is_user_on_leave(candidate):
            selected_verifier = candidate
            break
            
    if not selected_verifier:
        frappe.logger().warning(f"PACE Assignment: All configured verifiers for {programme} are currently on leave.")
        # Fallback: assign to the first one anyway if nobody is available, 
        # or leave blank for Manager to handle? Let's leave it blank and notify.
        return

    # 4. Update Verification Record
    if not verification_doc.assigned_verifier or force_reassign:
        verification_doc.assigned_verifier = selected_verifier
        
        # Set Due Date based on SLA
        days = config.days_to_verify or 2
        verification_doc.due_date = add_days(nowdate(), days)
        
        # --- NEW: Sync back to PACE Application ---
        frappe.db.set_value("PACE Application", verification_doc.application, "assigned_verifier", selected_verifier)
        
        # 5. Persistent State Update for Round Robin
        if total_verifiers > 1:
            config.db_set("last_assigned_index", next_index)
            frappe.logger().info(f"PACE Assignment: Round Robin assigned to {selected_verifier} (Index: {next_index}) for {app_data.programme}")

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

    count = 0
    for name in names:
        doc = frappe.get_doc("PACE Document Verification", name)
        # Only re-assign if it's still pending
        if doc.overall_status == "Pending":
            assign_verifier_round_robin(doc, force_reassign=True)
            doc.save(ignore_permissions=True)
            count += 1
    
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
        filters["assigned_verifier"] = verifier
        
    return frappe.get_all("PACE Document Verification", filters=filters, fields=["name", "applicant_name", "application", "assigned_verifier", "due_date"])

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
        
        count += 1
        
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
