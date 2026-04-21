import frappe
import json
from frappe.model.document import Document


class MeritList(Document):

    def autoname(self):
        from frappe.model.naming import make_autoname
        if not self.admission_cycle or not self.campus:
            frappe.throw("Admission Cycle and Campus are required for naming.")

        # Use codes instead of names to keep it short
        cycle_code = frappe.db.get_value("Admission Cycle", self.admission_cycle, "cycle_code") or self.admission_cycle
        campus_code = frappe.db.get_value("Campus", self.campus, "campus_code") or self.campus
        
        cycle = cycle_code.replace(" ", "").upper()
        campus = campus_code.replace(" ", "").upper()
        level = (self.program_level or "ALL").upper()

        self.name = make_autoname(f"ML-{cycle}-{campus}-{level}-.#####")

    def validate(self):
        self.validate_uniqueness()

    def validate_uniqueness(self):
        """
        Ensures only one PUBLISHED Merit List exists per Campus, Admission Cycle, and Program Level.
        """
        if self.status != "Published":
            return

        filters = {
            "campus": self.campus,
            "admission_cycle": self.admission_cycle,
            "program_level": self.program_level,
            "status": "Published",
            "name": ["!=", self.name]
        }

        existing = frappe.db.exists("Merit List", filters)
        if existing:
            from frappe.utils import get_link_to_form
            link = get_link_to_form("Merit List", existing)
            frappe.throw(
                f"A Merit List is already PUBLISHED for Campus '{self.campus}', "
                f"Admission Cycle '{self.admission_cycle}' and Program Level '{self.program_level or 'All'}'. "
                f"Unpublish it first if you need to publish this one. "
                f"<br><br>Existing Published Merit List: {link}",
                title="Duplicate Published Merit List"
            )


@frappe.whitelist()
def create_seat_allocation(merit_list_name, selected_applicants):
    """
    Creates a Seat Allocation from selected applicant names.
    Fetches merit data (score, ranks) from the Merit List child table.
    Returns the name of the created Seat Allocation.
    """
    if isinstance(selected_applicants, str):
        selected_applicants = json.loads(selected_applicants)

    if not selected_applicants:
        frappe.throw("No applicants selected.", title="Empty Selection")

    merit = frappe.get_doc("Merit List", merit_list_name)

    # Build a lookup map: applicant ID -> merit row data
    merit_data = {
        row.applicant_id: row
        for row in merit.merit_applicants
    }

    # Create Seat Allocation
    alloc = frappe.new_doc("Seat Allocation")
    alloc.admission_cycle = merit.admission_cycle
    alloc.campus = merit.campus
    alloc.program_level = merit.program_level
    alloc.merit_list = merit_list_name
    alloc.status = "Draft"

    for applicant_id in selected_applicants:
        row = merit_data.get(applicant_id)
        # Skip Rejected applicants — they must not receive a seat allocation
        if row and row.status == "Rejected":
            continue
        alloc.append("selection_applicant", {
            "applicant_id": row.applicant_id if row else applicant_id,
            "candidate_name": row.candidate_name if row else None,
            "program": row.program if row else None,
            "total_score": row.total_score if row else 0,
            "overall_rank": row.overall_rank if row else None,
            "selection_status": "Draft"
        })

    if not alloc.selection_applicant:
        frappe.throw("No eligible applicants to allocate. Rejected applicants cannot be added to a Seat Allocation.", title="No Eligible Applicants")

    alloc.total_selected = len(alloc.selection_applicant)
    alloc.insert()
    
    # Run automatic allocation logic immediately
    alloc.allocate_seats()
    
    frappe.db.commit()

    return alloc.name


@frappe.whitelist()
def publish_merit_list(merit_list_name):
    """
    Publishes the Merit List so students can view their scores
    on the applicant results portal page.
    Sets status to 'Published' and records an audit log.
    Also updates the Application Status of all applicants in the list to 'Merit Published'.
    """
    doc = frappe.get_doc("Merit List", merit_list_name)

    if doc.status == "Published":
        frappe.throw(f"Merit List '{merit_list_name}' is already published.")

    if doc.docstatus != 1:
        frappe.throw("Merit List must be submitted before publishing.")

    doc.status = "Published"
    doc.save()

    # Update Applicant status
    for row in doc.merit_applicants:
        if row.applicant_id:
            new_status = "Merit Published"
            if row.status == "Selected":
                new_status = "Merit Selected"
            elif row.status == "Rejected":
                new_status = "Merit Rejected"
            elif row.status == "Waitlisted":
                new_status = "Merit Waitlisted"
                
            frappe.db.set_value("Applicant", row.applicant_id, "application_status", new_status)

    # Audit log
    frappe.get_doc({
        "doctype": "Admission Audit Log",
        "action": "Modified",
        "reference_doctype": "Merit List",
        "reference_name": merit_list_name,
        "performed_by": frappe.session.user,
        "reason": f"Merit List {merit_list_name} published by {frappe.session.user}"
    }).insert(ignore_permissions=True)

    # Trigger notifications in background - pass name only for robustness
    frappe.enqueue(
        method="slcm.admission.doctype.merit_list.merit_list.trigger_merit_notifications",
        queue="long",
        merit_list_name=doc.name
    )

    frappe.db.commit()
    return {"status": "Published"}


def trigger_merit_notifications(merit_list_name):
    """
    Background task to send merit list notifications.
    Refetches the document based on name for serialization safety.
    """
    try:
        doc = frappe.get_doc("Merit List", merit_list_name)
        send_merit_published_emails(doc)
        send_merit_published_notifications(doc)
        # Ensure changes are committed in the background worker
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(f"Failed to send merit list notifications for {merit_list_name}: {str(e)}\n\n{frappe.get_traceback()}", "Merit List Notification Error")


def send_merit_published_notifications(doc):
    """
    Creates Notification Log entries for all applicants in the merit list.
    """
    for row in doc.merit_applicants:
        if not row.applicant_id:
            continue
            
        applicant_email = frappe.db.get_value("Applicant", row.applicant_id, "email")
        if not applicant_email:
            continue
            
        # The applicant's email is used as their User ID in the portal
        if frappe.db.exists("User", applicant_email):
            try:
                # Custom Title and Message as requested by the user
                message_body = f"""
                    <p>The merit list <strong>"{doc.name}"</strong> has been published.</p>
                    <p>Your rank and merit score are now available. Please check your result and admission status.</p>
                    <p><a href="/my-applications?app={row.applicant_id}" style="color: #16a34a; font-weight: bold;">Click here to view your result.</a></p>
                """
                
                frappe.get_doc({
                    "doctype": "Notification Log",
                    "subject": "Merit List Published",
                    "for_user": applicant_email,
                    "type": "Alert",
                    "email_content": message_body,
                    "document_type": "Merit List",
                    "document_name": doc.name,
                    "from_user": frappe.session.user,
                    "link": f"/my-applications?app={row.applicant_id}"
                }).insert(ignore_permissions=True)
            except Exception:
                # Silently fail for individual notification logs if one user has issues
                pass


def send_merit_published_emails(doc):
    """
    Sends notification emails to all applicants in the merit list using 'Merit List Template'.
    """
    template_name = "Merit List Template"
    
    # Use formatted date
    pub_date = frappe.utils.format_date(doc.modified or frappe.utils.now(), "dd MMMM yyyy")

    for row in doc.merit_applicants:
        if not row.applicant_id:
            continue

        applicant_email = frappe.db.get_value("Applicant", row.applicant_id, "email")
        if not applicant_email:
            continue

        # Prepare context for the template
        context = {
            "candidate_name": row.candidate_name,
            "merit_list_name": doc.name,
            "overall_rank": row.overall_rank or "—",
            "total_score": row.total_score or "0",
            "published_date": pub_date,
            "portal_link": frappe.utils.get_url("/my-applications")
        }

        # Fetch and render template from the 'Email Template' DocType
        if not frappe.db.exists("Email Template", template_name):
            frappe.log_error(f"Missing Email Template: '{template_name}'. Notifications skipped for {doc.name}.", "Email Template Missing")
            break # Exit loop if template is missing to avoid multiple error logs
            
        template_doc = frappe.get_doc("Email Template", template_name)
        
        # Determine the content field correctly based on 'use_html' toggle
        if template_doc.get("use_html"):
            template_body = template_doc.response_html
        else:
            template_body = template_doc.response
            
        if not template_body:
            # Fallback for some versions/configurations
            template_body = template_doc.get("message")
            
        if not template_body:
            continue

        template_subject = template_doc.subject or "Merit List Published"
        rendered_subject = frappe.render_template(template_subject, context)
        rendered_content = frappe.render_template(template_body, context)

        if not rendered_content:
            continue

        # Robust CC handling from the manual 'cc' field added to Email Template
        cc_list = []
        cc_field_value = template_doc.get("cc")
        if cc_field_value:
            # Split by comma or semicolon, strip whitespace, and filter out empties
            cc_list = [c.strip() for c in cc_field_value.replace(";", ",").split(",") if c.strip()]

        # Send email
        try:
            # Use now=False for standard asynchronous delivery via Email Queue.
            frappe.sendmail(
                recipients=[applicant_email],
                cc=cc_list,
                subject=rendered_subject,
                message=rendered_content,
                reference_doctype="Merit List",
                reference_name=doc.name,
                now=False
            )
            frappe.logger().info(f"Merit List Notification Email queued successfully to {applicant_email} for {doc.name}")
        except Exception:
            import traceback
            frappe.log_error(traceback.format_exc(), f"Merit List Notification Email Queueing Failed: {doc.name}")


@frappe.whitelist()
def unpublish_merit_list(merit_list_name):
    """
    Reverts the Merit List status to 'Generated', hiding scores from students.
    Also reverts the Application Status of all applicants in the list to 'Submitted'.
    """
    doc = frappe.get_doc("Merit List", merit_list_name)

    if doc.status != "Published":
        frappe.throw("Merit List is not currently published.")

    doc.status = "Generated"
    doc.save()

    # Revert Applicant status
    for row in doc.merit_applicants:
        if row.applicant_id:
            # Revert to Submitted if it was any Merit status
            current_status = frappe.db.get_value("Applicant", row.applicant_id, "application_status")
            if current_status in ["Merit Published", "Merit Selected", "Merit Rejected", "Merit Waitlisted"]:
                frappe.db.set_value("Applicant", row.applicant_id, "application_status", "Submitted")

    # Audit log
    frappe.get_doc({
        "doctype": "Admission Audit Log",
        "action": "Unpublished",
        "reference_doctype": "Merit List",
        "reference_name": merit_list_name,
        "performed_by": frappe.session.user,
        "reason": f"Merit List {merit_list_name} unpublished by {frappe.session.user}. It is now open for corrections or regeneration."
    }).insert(ignore_permissions=True)

    frappe.db.commit()
    return {"status": "Generated"}
