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
            frappe.logger().info(f"PACE Assignment: Round Robin assigned to {selected_verifier} (Index: {next_index}) for {programme}")

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
