# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json
import re
import traceback
from frappe.model.document import Document
from frappe.utils import get_url
from frappe.utils.pdf import get_pdf


class EntranceTestList(Document):

    def autoname(self):
        """
        Custom naming series for Entrance Test List records.
        """
        if self.academic_year:
            prefix = f"ETL-{self.academic_year}-"

            rows = frappe.db.sql(
                """SELECT name
                   FROM `tabEntrance Test List`
                   WHERE name LIKE %s""",
                prefix + "%",
                as_list=True,
            )

            used = set()

            pattern = re.compile(re.escape(prefix) + r"(\d{1,})$")
            for r in rows:
                name = r[0]
                m = pattern.match(name)
                if m:
                    try:
                        used.add(int(m.group(1)))
                    except ValueError:
                        pass

            idx = 1
            while idx in used:
                idx += 1

            self.name = f"{prefix}{idx:03d}"
        else:
            self.name = frappe.generate_hash(self.doctype, 6)

    @frappe.whitelist()
    def allocate_seats(self, providers, selected_applicants, allocation_date=None, entrance_test_name=None):
        """
        Logic:
          - Creates ONE Entrance Test Seat Allocation record per applicant.
          - Stores all selected providers in the 'assigned_preferences' child table.
          - Marks child record as 'Allocated' in entrance_test_applicant.
        """
        frappe.reload_doc("admission", "doctype", "entrance_test_preference_assigned")
        frappe.reload_doc("admission", "doctype", "entrance_test_seat_allocation")
        frappe.clear_cache(doctype="Entrance Test Seat Allocation")
        
        if isinstance(providers, str):
            providers = json.loads(providers)
        if isinstance(selected_applicants, str):
            selected_applicants = json.loads(selected_applicants)

        if not providers:
            frappe.throw("No providers selected.")
        if not selected_applicants:
            frappe.throw("No applicants selected.")

        provider_list = []
        for pname in providers:
            pdoc = frappe.get_doc("Entrance Test Provider", pname)
            if not pdoc.active:
                frappe.throw(f"Provider '{pname}' is not active.")
            provider_list.append(pdoc)

        applicant_map = {app.name: app for app in self.entrance_test_applicant}

        created_count = 0
        total_applicants = len(selected_applicants)

        for i, app_name in enumerate(selected_applicants):
            # Publish progress to the UI
            frappe.publish_progress(
                float(i + 1) / total_applicants * 100, 
                title=_("Allocating Entrance Test Seats..."),
 
                description=f"Processing {i + 1} of {total_applicants}"
            )

            app = applicant_map.get(app_name)
            if not app:
                continue

            if getattr(app, "allocation_status", "") == "Allocated":
                continue

            existing_allocation = frappe.db.get_value("Entrance Test Seat Allocation", {
                "entrance_test_list": self.name,
                "applicant": app.applicant_id
            }, "name")

            if existing_allocation:
                allocation = frappe.get_doc("Entrance Test Seat Allocation", existing_allocation)
            else:
                allocation = frappe.new_doc("Entrance Test Seat Allocation")
                allocation.entrance_test_list    = self.name
                allocation.academic_year         = self.academic_year
                allocation.admission_cycle       = self.admission_cycle
                allocation.campus                = self.campus
                allocation.program_level         = self.program_level
                allocation.entrance_test_name    = entrance_test_name

                allocation.applicant             = app.applicant_id
                allocation.candidate_name        = app.candidate_name
                allocation.program               = app.program
                allocation.email                 = app.email
                allocation.gender                = app.gender
                allocation.entrance_test         = getattr(app, "entrance_test", 0)
                allocation.intereview            = getattr(app, "intereview", 0)
                allocation.exempts_entrance_test = getattr(app, "exempts_entrance_test", 0)
                allocation.exempts_interview    = getattr(app, "exempts_interview", 0)
                allocation.allocation_status      = "Not Allocated"
                allocation.entrance_test_status   = "Scheduled"
            
            if entrance_test_name:
                allocation.entrance_test_name = entrance_test_name

            if allocation_date:
                allocation.allocation_date = allocation_date

            allocation.set("assigned_preferences", [])
            for idx, pdoc in enumerate(provider_list, start=1):
                allocation.append("assigned_preferences", {
                    "provider": pdoc.name,
                    "center_name": pdoc.center_name,
                    "center_address": pdoc.center_address,
                    "preference_order": idx
                })

            # Fetch categories from Applicant
            if allocation.applicant and (not allocation.category or allocation.is_new()):
                try:
                    app_doc = frappe.get_doc("Applicant", allocation.applicant)
                    app_categories = app_doc._get_applicant_categories()
                    if not allocation.category:
                        for cat in app_categories:
                            allocation.append("category", {"category": cat})
                except Exception:
                    pass

            allocation.save(ignore_permissions=True)

            email = allocation.email or ""
            if not email and allocation.applicant:
                try:
                    app_email = frappe.db.get_value("Applicant", allocation.applicant, "email")
                    if app_email:
                        email = app_email
                except Exception:
                    pass

            if email:
                try:
                    _send_allocation_email(allocation, email)
                    _send_allocation_notification(allocation, email)
                except Exception:
                    frappe.log_error(
                        message=traceback.format_exc(),
                        title=f"Allocation Email/Notification Failed: {allocation.name}"
                    )

            app.allocation_status = "Allocated"
            created_count += 1
            
            # Commit periodically or after each to update progress and UI
            if i % 5 == 0:
                frappe.db.commit()

        self.save(ignore_permissions=True)
        frappe.db.commit()

        return created_count


def _send_allocation_email(allocation, email):
    """Send a formal Entrance Test Center Selection email to the applicant."""
    try:
        template_name = "Entrance Test Allocation"
        if not frappe.db.exists("Email Template", template_name):
            frappe.log_error(f"Email Template '{template_name}' not found.", "Email Sending Error")
            return

        template = frappe.get_doc("Email Template", template_name)
        
        doc_dict = allocation.as_dict()
        doc_dict["assigned_preferences"] = [p.as_dict() for p in allocation.assigned_preferences]
        
        args = {
            "doc": doc_dict,
            "portal_url": get_url("/merit-and-scholarship/admission_dashboard?panel=applications")
        }

        subject = frappe.render_template(template.subject, args)
        
        # Determine the content field correctly
        message_body = ""
        if template.get("use_html"):
            message_body = frappe.render_template(template.response_html, args)
        else:
            message_body = frappe.render_template(template.response, args)

        if not message_body:
            message_body = frappe.render_template(template.get("message") or "", args)
            
        # Robust CC handling from the manual 'cc' field added to Email Template
        cc_list = []
        cc_field_value = template.get("cc")
        if cc_field_value:
            # Split by comma or semicolon, strip whitespace, and filter out empties
            cc_list = [c.strip() for c in cc_field_value.replace(";", ",").split(",") if c.strip()]
        
        if message_body:
            try:
                # Use now=False to queue the email.
                sender = None
                if template.get("email_account"):
                    sender = frappe.db.get_value("Email Account", template.get("email_account"), "email_id") or template.get("email_account")

                frappe.sendmail(
                    recipients=[email],
                    sender=sender,
                    cc=cc_list,
                    subject=subject,
                    message=message_body,
                    reference_doctype="Entrance Test Seat Allocation",
                    reference_name=allocation.name,
                    now=False
                )
                frappe.logger().info(f"Entrance Test Allocation Email queued successfully to {email} for {allocation.name}")
            except Exception:
                frappe.log_error(traceback.format_exc(), f"Entrance Test Allocation Email Queueing Failed: {allocation.name}")
    except Exception:
        frappe.log_error(message=traceback.format_exc(), title=f"Allocation Email Failed: {allocation.name}")


@frappe.whitelist()
def get_applicant_preferences(applicant_id, entrance_test_list):
    allocation_name = frappe.db.get_value("Entrance Test Seat Allocation", {
        "applicant": applicant_id,
        "entrance_test_list": entrance_test_list
    }, "name")

    if not allocation_name:
        return []

    try:
        allocation = frappe.get_doc("Entrance Test Seat Allocation", allocation_name, ignore_permissions=True)
    except frappe.DoesNotExistError:
        return []
    
    use_rescheduled = getattr(allocation, "is_rescheduled", 0) == 1 and \
                      getattr(allocation, "re_allocation_status", "") in ["Preferences Assigned", "Allocated", "Reallocated"]
    
    pref_field = "re_assigned_preferences" if use_rescheduled else "assigned_preferences"
    status_field = "re_allocation_status" if use_rescheduled else "allocation_status"
    seat_field = "re_seat_number" if use_rescheduled else "seat_number"
    room_field = "re_room_name" if use_rescheduled else "room_name"

    preferences = []
    for p in allocation.get(pref_field):
        preferences.append({
            "entrance_test_provider": p.provider,
            "center_name": p.center_name,
            "center_address": p.center_address,
            "preference_order": p.preference_order,
            "is_full": _get_remaining_capacity(p.provider) <= 0,
            "allocation_status": getattr(allocation, status_field),
            "seat_number": getattr(allocation, seat_field),
            "room_name": getattr(allocation, room_field)
        })

    return preferences


@frappe.whitelist()
def confirm_applicant_preference(allocation_name, selected_provider):
    allocation = frappe.get_doc("Entrance Test Seat Allocation", allocation_name)

    if allocation.allocation_status == "Allocated":
        frappe.throw("You have already been allocated a seat.")

    provider = frappe.get_doc("Entrance Test Provider", selected_provider)

    assigned_room = None
    new_reserved  = None
    seat_number   = None

    for room in provider.provider_room:
        if not getattr(room, "active", 1):
            continue
        capacity = room.room_capacity or 0
        reserved = room.room_reserved_seats or 0
        if (capacity - reserved) > 0:
            assigned_room = room
            new_reserved  = reserved + 1
            seat_number   = f"{new_reserved:02d}"
            break

    if not assigned_room:
        frappe.throw(
            f"Sorry, '{provider.center_name}' is now full. "
            "Please choose another preference center."
        )

    allocation.entrance_test_provider = selected_provider
    allocation.center_name            = provider.center_name
    allocation.center_address         = provider.center_address
    allocation.room_code              = assigned_room.room_code
    allocation.room_name              = assigned_room.room_name
    allocation.building               = assigned_room.building
    allocation.floor                  = assigned_room.floor
    allocation.seat_number            = seat_number
    allocation.allocation_status      = "Allocated"
    allocation.allocated_by           = frappe.session.user
    allocation.save(ignore_permissions=True)

    assigned_room.room_reserved_seats     = new_reserved
    assigned_room.room_available_capacity = (assigned_room.room_capacity or 0) - new_reserved
    provider.save(ignore_permissions=True)

    frappe.db.commit()

    generate_and_store_admit_card(allocation, is_rescheduled=False)

    return {
        "seat_number":    seat_number,
        "room_name":      assigned_room.room_name,
        "center_name":    provider.center_name,
        "center_address": provider.center_address,
    }


@frappe.whitelist()
def confirm_rescheduled_preference(allocation_name, selected_provider):
    allocation = frappe.get_doc("Entrance Test Seat Allocation", allocation_name)

    if allocation.re_allocation_status == "Allocated":
        frappe.throw("You have already been allocated a seat for the rescheduled test.")

    provider = frappe.get_doc("Entrance Test Provider", selected_provider)

    assigned_room = None
    new_reserved  = None
    seat_number   = None

    for room in provider.provider_room:
        if not getattr(room, "active", 1):
            continue
        capacity = room.room_capacity or 0
        reserved = room.room_reserved_seats or 0
        if (capacity - reserved) > 0:
            assigned_room = room
            new_reserved  = reserved + 1
            seat_number   = f"{new_reserved:02d}"
            break

    if not assigned_room:
        frappe.throw(
            f"Sorry, '{provider.center_name}' is now full. "
            "Please choose another preference center."
        )

    allocation.re_entrance_test_provider = selected_provider
    allocation.re_center_name            = provider.center_name
    allocation.re_center_address         = provider.center_address
    allocation.re_room_code              = assigned_room.room_code
    allocation.re_room_name              = assigned_room.room_name
    allocation.re_building               = assigned_room.building
    allocation.re_floor                  = assigned_room.floor
    allocation.re_seat_number            = seat_number
    allocation.re_allocation_status      = "Allocated"
    allocation.re_allocated_by           = frappe.session.user
    allocation.save(ignore_permissions=True)

    assigned_room.room_reserved_seats     = new_reserved
    assigned_room.room_available_capacity = (assigned_room.room_capacity or 0) - new_reserved
    provider.save(ignore_permissions=True)

    frappe.db.commit()

    generate_and_store_admit_card(allocation, is_rescheduled=True)

    return {
        "seat_number":    seat_number,
        "room_name":      assigned_room.room_name,
        "center_name":    provider.center_name,
        "center_address": provider.center_address,
    }


def _get_remaining_capacity(provider_name):
    """Total remaining seats across all active rooms for a provider."""
    try:
        provider = frappe.get_doc("Entrance Test Provider", provider_name)
        total = 0
        for room in provider.provider_room:
            if not getattr(room, "active", 1):
                continue
            capacity = room.room_capacity or 0
            reserved = room.room_reserved_seats or 0
            total   += max(0, capacity - reserved)
        return total
    except Exception:
        return 0

@frappe.whitelist()
def generate_and_store_admit_card(allocation, is_rescheduled=False, html_content=None):
    if isinstance(allocation, str):
        allocation = frappe.get_doc("Entrance Test Seat Allocation", allocation)
        
    pdf_content = None
    try:
        if html_content:
            html_content = re.sub(r'<script\b[^>]*>([\s\S]*?)<\/script>', '', html_content)
            html = html_content
        else:
            from slcm.www.eligibility.entrance_test_seat_allocation import get_admit_card_html
            html = get_admit_card_html(allocation, is_rescheduled)
            
        pdf_content = get_pdf(html)
    except Exception as e:
        frappe.log_error(
            message=traceback.format_exc(),
            title=f"Admit Card Generation Error for {allocation.name}"
        )
        return None
    
    random_hash = frappe.generate_hash(length=4)
    field_to_update = "re_admit_card_download" if is_rescheduled else "admit_card_download"
    file_name = f"Admit_Card_{allocation.applicant}_{random_hash}.pdf"
    if is_rescheduled:
        file_name = f"Admit_Card_{allocation.applicant}_Rescheduled_{random_hash}.pdf"

    old_file_url = getattr(allocation, field_to_update)
    if old_file_url:
        try:
            old_file_name = frappe.db.get_value("File", {
                "file_url": old_file_url,
                "attached_to_doctype": allocation.doctype,
                "attached_to_name": allocation.name,
                "attached_to_field": field_to_update
            }, "name")
            if old_file_name:
                frappe.delete_doc("File", old_file_name, ignore_permissions=True)
        except Exception:
            pass

    _file = frappe.get_doc({
        "doctype": "File",
        "file_name": file_name,
        "attached_to_doctype": allocation.doctype,
        "attached_to_name": allocation.name,
        "attached_to_field": field_to_update,
        "content": pdf_content,
        "is_private": 0
    })
    _file.save(ignore_permissions=True)    
    values = {
        field_to_update: _file.file_url,
        "admit_card_generated": 1
    }
    if not allocation.admit_card_number:
        values["admit_card_number"] = f"AC-{allocation.name}"
        
    frappe.db.set_value(allocation.doctype, allocation.name, values)
    allocation.update(values)
    frappe.db.commit()
    
    return _file.file_url


def _send_allocation_notification(allocation, email):
    """Creates a Notification Log entry for the applicant."""
    if not email:
        return
    
    # The applicant's email is used as their User ID in the portal
    if frappe.db.exists("User", email):
        try:
            # Custom Title and Message similar to Merit List
            message_body = f"""
                <p>An entrance test seat has been allocated for you in <strong>"{allocation.entrance_test_list}"</strong>.</p>
                <p>Please check your admission dashboard to view the details and select your preferred center.</p>
                <p><a href="/merit-and-scholarship/admission_dashboard?panel=applications" style="color: #16a34a; font-weight: bold;">Click here to view details.</a></p>
            """
            
            frappe.get_doc({
                "doctype": "Notification Log",
                "subject": "Entrance Test Seat Allocated",
                "for_user": email,
                "type": "Alert",
                "email_content": message_body,
                "document_type": "Entrance Test Seat Allocation",
                "document_name": allocation.name,
                "from_user": frappe.session.user,
                "link": "/merit-and-scholarship/admission_dashboard?panel=applications"
            }).insert(ignore_permissions=True)
        except Exception:
            # Silently fail for individual notification logs if one user has issues, but log it
            frappe.log_error(message=frappe.get_traceback(), title=f"Allocation Notification Failed: {allocation.name}")
