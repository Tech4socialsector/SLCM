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
    @frappe.whitelist()
    def allocate_seats(self, providers, selected_applicants, allocation_date=None, entrance_test_name=None, allocation_type=None):
        """
        Logic:
          - If allocation_type == "Allocate Directly":
              - Directly allocates seat to selected entrance test centre.
              - Decrements available capacity & updates reserved seats.
              - Generates Admit Card PDF immediately.
              - Sends email WITH Admit Card attached.
          - If allocation_type == "Allow Applicant Selection":
              - Stores selected centres in assigned_preferences child table.
              - Keeps allocation_status as 'Not Allocated'.
              - Sends email notifying applicant to select preference on portal.
              - Admit card generated later when applicant confirms preference on portal.
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

        if not allocation_type:
            allocation_type = "Allow Applicant Selection"

        provider_list = []
        for pname in providers:
            pdoc = frappe.get_doc("Entrance Test Provider", pname)
            if not pdoc.active:
                frappe.throw(f"Provider '{pname}' is not active.")
            provider_list.append(pdoc)

        applicant_map = {app.name: app for app in self.entrance_test_applicant}

        created_count = 0
        unallocated_list = []
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

            cycle_name = self.admission_cycle
            program_name = getattr(app, "program", None)
            program_level_name = self.program_level

            app_doc = None
            app_pwd = 0
            if getattr(app, "pwd", 0) == 1:
                app_pwd = 1

            if getattr(app, "applicant_id", None):
                try:
                    app_doc = frappe.get_doc("Applicant", app.applicant_id)
                    if not cycle_name:
                        cycle_name = app_doc.admission_cycle
                    if not program_name:
                        program_name = app_doc.program
                    if not program_level_name:
                        program_level_name = app_doc.program_level
                    if (getattr(app_doc, "pwd", "") or "").strip().lower() == "yes":
                        app_pwd = 1
                except Exception:
                    pass

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

                allocation.applicant             = app.applicant_id
                allocation.candidate_name        = app.candidate_name
                allocation.program               = app.program
                allocation.email                 = app.email
                allocation.gender                = app.gender
                allocation.pwd                   = app_pwd
                allocation.entrance_test         = getattr(app, "entrance_test", 0)
                allocation.intereview            = getattr(app, "intereview", 0)
                allocation.exempts_entrance_test = getattr(app, "exempts_entrance_test", 0)
                allocation.exempts_interview     = getattr(app, "exempts_interview", 0)
                allocation.allocation_status      = "Not Allocated"
                allocation.entrance_test_status   = "Scheduled"
            
            allocation.pwd = app_pwd

            test_cfg = _resolve_entrance_test_details_from_cycle(cycle_name, program_name, program_level_name)

            resolved_test_name = test_cfg.get("entrance_test_name") or entrance_test_name
            resolved_test_date = test_cfg.get("entrance_test_date") or allocation_date
            resolved_start_time = test_cfg.get("start_time")
            resolved_end_time = test_cfg.get("end_time")

            if resolved_test_name:
                allocation.entrance_test_name = resolved_test_name

            if resolved_test_date:
                if resolved_start_time:
                    allocation.allocation_date = f"{resolved_test_date} {resolved_start_time}"
                else:
                    allocation.allocation_date = str(resolved_test_date)
            elif allocation_date:
                allocation.allocation_date = allocation_date

            if resolved_start_time:
                allocation.start_time = resolved_start_time
            if resolved_end_time:
                allocation.end_time = resolved_end_time

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

            if allocation_type == "Allocate Directly":
                sel_provider = None
                failure_reason = None

                for pdoc in provider_list:
                    # Check PWD facility
                    if app_pwd and not getattr(pdoc, "pwd_accessible", 0):
                        failure_reason = f"Centre '{pdoc.center_name}' does not have facility to accommodate PWD students."
                        continue

                    # Check total capacity
                    avail = pdoc.available_capacity or 0
                    if avail <= 0:
                        failure_reason = f"Centre '{pdoc.center_name}' has no available capacity."
                        continue

                    # Check programme capacity if defined
                    prog_capacity_ok = True
                    if hasattr(pdoc, "programme_capacity") and pdoc.programme_capacity and allocation.program:
                        for r in pdoc.programme_capacity:
                            if r.program == allocation.program:
                                if (r.available_capacity or 0) <= 0:
                                    prog_capacity_ok = False
                                    failure_reason = f"Centre '{pdoc.center_name}' has no available capacity for programme '{allocation.program}'."
                                break

                    if not prog_capacity_ok:
                        continue

                    sel_provider = pdoc
                    break

                if not sel_provider:
                    unallocated_list.append({
                        "name": app.candidate_name or "Unknown",
                        "applicant_id": app.applicant_id or app_name,
                        "reason": failure_reason or "Selected centre is not available or full."
                    })
                    continue

                if hasattr(sel_provider, "programme_capacity") and sel_provider.programme_capacity and allocation.program:
                    for r in sel_provider.programme_capacity:
                        if r.program == allocation.program:
                            r.reserved_seats = (r.reserved_seats or 0) + 1
                            r.available_capacity = max(0, (r.capacity or 0) - r.reserved_seats)
                            break

                sel_provider.reserved_seats = (sel_provider.reserved_seats or 0) + 1
                sel_provider.calculate_capacity()
                sel_provider.save(ignore_permissions=True)

                seat_number = f"{(sel_provider.reserved_seats):02d}"
                allocation.entrance_test_provider = sel_provider.name
                allocation.center_name            = sel_provider.center_name
                allocation.center_address         = sel_provider.center_address
                allocation.seat_number            = seat_number
                allocation.allocation_status      = "Allocated"
                allocation.allocated_by           = frappe.session.user
                allocation.save(ignore_permissions=True)

                # Generate Admit Card PDF immediately for direct allocation
                generate_and_store_admit_card(allocation, is_rescheduled=False)
            else:
                if app_pwd:
                    has_pwd_center = any(getattr(pdoc, "pwd_accessible", 0) for pdoc in provider_list)
                    if not has_pwd_center:
                        unallocated_list.append({
                            "name": app.candidate_name or "Unknown",
                            "applicant_id": app.applicant_id or app_name,
                            "reason": "None of the selected centres have PWD accessibility facility."
                        })
                        continue

                allocation.allocation_status = "Not Allocated"
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
            
            # Commit periodically
            if i % 5 == 0:
                frappe.db.commit()

        self.save(ignore_permissions=True)
        frappe.db.commit()

        return {
            "allocated_count": created_count,
            "unallocated": unallocated_list
        }


def _send_allocation_email(allocation, email):
    """Send a formal Entrance Test Centre Selection / Allocation email to the applicant."""
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
            cc_list = [c.strip() for c in cc_field_value.replace(";", ",").split(",") if c.strip()]
        
        if message_body:
            attachments = []
            if allocation.allocation_status == "Allocated" and getattr(allocation, "admit_card_download", None):
                attachments.append({
                    "file_url": allocation.admit_card_download
                })

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
                    attachments=attachments,
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

    avail = (provider.available_capacity or 0)
    if avail <= 0:
        frappe.throw(
            f"Sorry, '{provider.center_name}' is now full. "
            "Please choose another preference center."
        )

    # Check and update specific Programme Capacity row if present
    if hasattr(provider, "programme_capacity") and provider.programme_capacity and allocation.program:
        for r in provider.programme_capacity:
            if r.program == allocation.program:
                r_avail = r.available_capacity if r.available_capacity is not None else max(0, (r.capacity or 0) - (r.reserved_seats or 0))
                if r_avail <= 0:
                    frappe.throw(
                        f"Sorry, '{provider.center_name}' has no available capacity for programme '{allocation.program}'."
                    )
                r.reserved_seats = (r.reserved_seats or 0) + 1
                r.available_capacity = max(0, (r.capacity or 0) - r.reserved_seats)
                break

    new_reserved = (provider.reserved_seats or 0) + 1
    seat_number  = f"{new_reserved:02d}"

    allocation.entrance_test_provider = selected_provider
    allocation.center_name            = provider.center_name
    allocation.center_address         = provider.center_address
    allocation.seat_number            = seat_number
    allocation.allocation_status      = "Allocated"
    allocation.allocated_by           = frappe.session.user
    allocation.save(ignore_permissions=True)

    provider.calculate_capacity()
    provider.save(ignore_permissions=True)

    frappe.db.commit()

    generate_and_store_admit_card(allocation, is_rescheduled=False)

    return {
        "seat_number":    seat_number,
        "room_name":      "",
        "center_name":    provider.center_name,
        "center_address": provider.center_address,
    }


@frappe.whitelist()
def confirm_rescheduled_preference(allocation_name, selected_provider):
    allocation = frappe.get_doc("Entrance Test Seat Allocation", allocation_name)

    if allocation.re_allocation_status == "Allocated":
        frappe.throw("You have already been allocated a seat for the rescheduled test.")

    provider = frappe.get_doc("Entrance Test Provider", selected_provider)

    avail = (provider.available_capacity or 0)
    if avail <= 0:
        frappe.throw(
            f"Sorry, '{provider.center_name}' is now full. "
            "Please choose another preference center."
        )

    # Check and update specific Programme Capacity row if present
    if hasattr(provider, "programme_capacity") and provider.programme_capacity and allocation.program:
        for r in provider.programme_capacity:
            if r.program == allocation.program:
                r_avail = r.available_capacity if r.available_capacity is not None else max(0, (r.capacity or 0) - (r.reserved_seats or 0))
                if r_avail <= 0:
                    frappe.throw(
                        f"Sorry, '{provider.center_name}' has no available capacity for programme '{allocation.program}'."
                    )
                r.reserved_seats = (r.reserved_seats or 0) + 1
                r.available_capacity = max(0, (r.capacity or 0) - r.reserved_seats)
                break

    new_reserved = (provider.reserved_seats or 0) + 1
    seat_number  = f"{new_reserved:02d}"

    allocation.re_entrance_test_provider = selected_provider
    allocation.re_center_name            = provider.center_name
    allocation.re_center_address         = provider.center_address
    allocation.re_seat_number            = seat_number
    allocation.re_allocation_status      = "Allocated"
    allocation.re_allocated_by           = frappe.session.user
    allocation.save(ignore_permissions=True)

    provider.calculate_capacity()
    provider.save(ignore_permissions=True)

    frappe.db.commit()

    generate_and_store_admit_card(allocation, is_rescheduled=True)

    return {
        "seat_number":    seat_number,
        "room_name":      "",
        "center_name":    provider.center_name,
        "center_address": provider.center_address,
    }


def _get_remaining_capacity(provider_name):
    """Total remaining seats for a provider."""
    try:
        provider = frappe.get_doc("Entrance Test Provider", provider_name)
        return max(0, (provider.available_capacity or 0))
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
        "is_private": 1
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


def _resolve_entrance_test_details_from_cycle(cycle_name, program=None, program_level=None):
    """
    Dynamically fetch Entrance Test Details from Admission Cycle based on:
    1) exact programme match
    2) programme_level match
    3) fallback to first row in child table
    """
    if not cycle_name:
        return {}

    rows = frappe.get_all(
        "Entrance Test Details",
        filters={"parent": cycle_name, "parenttype": "Admission Cycle"},
        fields=["programme", "programme_level", "entrance_test_name", "entrance_test_date", "start_time", "end_time", "idx"],
        order_by="idx asc",
    )
    if not rows:
        return {}

    if program:
        for row in rows:
            if (row.get("programme") or "").strip() == (program or "").strip() and row.get("entrance_test_name"):
                return row

    if program_level:
        for row in rows:
            if (row.get("programme_level") or "").strip() == (program_level or "").strip() and row.get("entrance_test_name"):
                return row

    for row in rows:
        if row.get("entrance_test_name"):
            return row

    return {}

