# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.model.document import Document
from frappe.utils import now_datetime, get_url, nowdate
from frappe.utils.pdf import get_pdf


class EntranceTestList(Document):

    def autoname(self):
        """
        Custom naming series for Entrance Test List records.

        Format: ETL-{academic_year}-###

        The numeric portion is 3 digits and is allocated sequentially per
        academic year.  If a record is deleted, its number becomes available
        again so the next created document will reuse the lowest unused
        index.  This mirrors the behaviour described by the user:

            ETL-2026-2027-001
            ETL-2026-2027-002  <-- deleted
            ETL-2026-2027-002  (new record takes the hole)

        We compute the smallest missing positive integer by querying existing
        document names and scanning for gaps.  If ``academic_year`` is not
        provided for some reason, fall back to a random hash like the default
        behaviour in Frappe.
        """

        # The field is mandatory in the doctype, but guard anyway.
        if self.academic_year:
            # prefix includes trailing dash
            prefix = f"ETL-{self.academic_year}-"

            # get all existing names that start with the prefix
            rows = frappe.db.sql(
                """SELECT name
                   FROM `tabEntrance Test List`
                   WHERE name LIKE %s""",
                prefix + "%",
                as_list=True,
            )

            used = set()
            import re

            pattern = re.compile(re.escape(prefix) + r"(\d{1,})$")
            for r in rows:
                name = r[0]
                m = pattern.match(name)
                if m:
                    try:
                        used.add(int(m.group(1)))
                    except ValueError:
                        # should not happen, ignore malformed names
                        pass

            # find first missing positive integer
            idx = 1
            while idx in used:
                idx += 1

            self.name = f"{prefix}{idx:03d}"
        else:
            # fallback - generate something unpredictable so document can still
            # be created without blowing up
            self.name = frappe.generate_hash(self.doctype, 6)

    @frappe.whitelist()
    def allocate_seats(self, providers, selected_applicants, allocation_date=None, entrance_test_name=None):
        """
        Admin selects:
          - providers             : list of Entrance Test Provider names (preferences)
          - selected_applicants   : list of child-table row names

        Logic:
          - Creates ONE Entrance Test Seat Allocation record per applicant.
          - Stores all selected providers in the 'assigned_preferences' child table.
          - Marks child record as 'Allocated' in entrance_test_applicant.
        """
        # Ensure metadata and database schema are synced with JSON files
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

        # Validate providers
        provider_list = []
        for pname in providers:
            pdoc = frappe.get_doc("Entrance Test Provider", pname)
            if not pdoc.active:
                frappe.throw(f"Provider '{pname}' is not active.")
            provider_list.append(pdoc)

        # Build lookup map for child table rows
        applicant_map = {app.name: app for app in self.entrance_test_applicant}

        created_count = 0

        for app_name in selected_applicants:
            app = applicant_map.get(app_name)
            if not app:
                continue

            # Skip if already processed
            if getattr(app, "allocation_status", "") == "Allocated":
                continue

            # Check if an allocation record already exists for this applicant/test
            existing_allocation = frappe.db.get_value("Entrance Test Seat Allocation", {
                "entrance_test_list": self.name,
                "applicant": app.applicant_id
            }, "name")

            if existing_allocation:
                allocation = frappe.get_doc("Entrance Test Seat Allocation", existing_allocation)
            else:
                # Create NEW single allocation record
                allocation = frappe.new_doc("Entrance Test Seat Allocation")
                allocation.entrance_test_list    = self.name
                allocation.academic_year         = self.academic_year
                allocation.admission_cycle       = self.admission_cycle
                allocation.campus                = self.campus
                allocation.program_level         = self.program_level
                allocation.entrance_test_name    = entrance_test_name

                # Applicant details
                allocation.applicant             = app.applicant_id
                allocation.candidate_name        = app.candidate_name
                allocation.program               = app.program
                allocation.email                 = app.email
                allocation.gender                = app.gender
                allocation.exempts_entrance_test = getattr(app, "exempts_entrance_test", 0)
                allocation.exempts_interview    = getattr(app, "exempts_interview", 0)
                allocation.allocation_status      = "Not Allocated"
                allocation.entrance_test_status   = "Scheduled"
            
            if entrance_test_name:
                allocation.entrance_test_name = entrance_test_name

            # If admin provided an allocation_date, set it on the allocation record.
            if allocation_date:
                try:
                    allocation.allocation_date = allocation_date
                except Exception:
                    allocation.allocation_date = allocation_date

            # Reset / Update preferences in child table
            allocation.set("assigned_preferences", [])
            for idx, pdoc in enumerate(provider_list, start=1):
                allocation.append("assigned_preferences", {
                    "provider": pdoc.name,
                    "center_name": pdoc.center_name,
                    "center_address": pdoc.center_address,
                    "preference_order": idx
                })

            allocation.save(ignore_permissions=True)

            # ── Resolve email: allocation.email → Applicant doctype fallback ──
            email = allocation.email or ""
            if not email and allocation.applicant:
                try:
                    app_email = frappe.db.get_value("Applicant", allocation.applicant, "email_id")
                    if app_email:
                        email = app_email
                except Exception:
                    pass

            # Send allocation notification email to applicant (if email resolved)
            if email:
                try:
                    _send_allocation_email(allocation, email)
                except Exception:
                    import traceback
                    frappe.log_error(
                        message=traceback.format_exc(),
                        title=f"Allocation Email Failed: {allocation.name}"
                    )
            else:
                frappe.log_error(
                    message=f"No email for applicant {allocation.applicant} ({allocation.name}). Email skipped.",
                    title="Allocation Email Skipped"
                )

            # ✅ Mark child row as "Allocated"
            app.allocation_status = "Allocated"
            created_count += 1

        self.save(ignore_permissions=True)
        frappe.db.commit()

        return created_count


def _send_allocation_email(allocation, email):
    """Send a premium result/allocation email to the applicant."""
    from frappe.utils import get_url
    url = get_url("/merit-and-scholarship/admission_dashboard?panel=applications")

    prefs_html = ""
    if getattr(allocation, 'assigned_preferences', None):
        prefs_html = '<div style="margin-top:15px; border-top:1px solid #eee; padding-top:10px;"><strong>Assigned Center Options:</strong><ul style="margin:10px 0; padding-left:20px; color:#555;">'
        for p in allocation.assigned_preferences:
            prefs_html += f"<li>{getattr(p, 'preference_order', '')}. {p.center_name or p.provider} ({p.provider})</li>"
        prefs_html += "</ul></div>"

    msg = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: auto; border: 1px solid #eee; padding: 20px; border-radius: 10px; line-height: 1.6; color: #333;">
        <h2 style="color: #1565c0; border-bottom: 2px solid #1565c0; padding-bottom: 10px; margin-top: 0;">Entrance Test — Seat Allocation</h2>
        <p>Dear {allocation.candidate_name or allocation.applicant},</p>
        <p>We are pleased to inform you that your registration for the entrance test has been processed. You can now proceed to <strong>choose your preferred test center</strong>.</p>
        
        <div style="background: #f8f9fa; border-radius: 8px; padding: 15px; margin: 20px 0;">
            <p style="margin: 0 0 10px 0;"><strong>Test Details:</strong></p>
            <table style="width:100%; border-collapse: collapse; font-size: 14px;">
                <tr><td style="padding:5px 0; color:#666;">Application No:</td><td style="padding:5px 0; font-weight:bold;">{allocation.applicant}</td></tr>
                <tr><td style="padding:5px 0; color:#666;">Entrance Test:</td><td style="padding:5px 0; font-weight:bold;">{allocation.entrance_test_name or allocation.entrance_test_list}</td></tr>
                <tr><td style="padding:5px 0; color:#666;">Campus:</td><td style="padding:5px 0; font-weight:bold;">{allocation.campus}</td></tr>
                <tr><td style="padding:5px 0; color:#666;">Program:</td><td style="padding:5px 0; font-weight:bold;">{allocation.program}</td></tr>
            </table>
            {prefs_html}
        </div>

        <p>Please click the button below to log in and select your center from the available options. Seats are allocated on a first-come, first-served basis.</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{url}" style="display:inline-block; padding:12px 28px; background:#1565c0; color:#fff; border-radius:6px; text-decoration:none; font-weight:bold; font-size: 16px;">Choose Your Test Center</a>
        </div>
        
        <p style="color:#666; font-size:12px; border-top:1px solid #eee; padding-top:15px; margin-bottom: 0;">
            Record Reference: {allocation.name}<br>
            If the button doesn't work, copy this link: {url}
        </p>
    </div>
    """

    frappe.sendmail(
        recipients=[email],
        subject=f"Entrance Test Seat Allocation — {allocation.candidate_name or allocation.applicant}",
        message=msg,
        reference_doctype="Entrance Test Seat Allocation",
        reference_name=allocation.name
    )


# ─────────────────────────────────────────────────────────────────────────────
# Applicant-facing APIs
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_applicant_preferences(applicant_id, entrance_test_list):
    """
    Returns the preferences from the SINGLE allocation record for this applicant.
    Priority given to rescheduled preferences if active.
    """
    allocation_name = frappe.db.get_value("Entrance Test Seat Allocation", {
        "applicant": applicant_id,
        "entrance_test_list": entrance_test_list
    }, "name")

    if not allocation_name:
        return []

    allocation = frappe.get_doc("Entrance Test Seat Allocation", allocation_name)
    
    # Check if we should serve rescheduled preferences
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
    """
    Called when applicant confirms their chosen provider from the SAME record.
    Initial allocation path.
    """
    allocation = frappe.get_doc("Entrance Test Seat Allocation", allocation_name)

    if allocation.allocation_status == "Allocated":
        frappe.throw("You have already been allocated a seat.")

    provider = frappe.get_doc("Entrance Test Provider", selected_provider)

    # Find first room with available capacity
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
            seat_number   = f"{room.room_name}-{new_reserved:02d}"
            break

    if not assigned_room:
        frappe.throw(
            f"Sorry, '{provider.center_name}' is now full. "
            "Please choose another preference center."
        )

    # Update the SINGLE record
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

    # Update room reserved count on provider
    assigned_room.room_reserved_seats     = new_reserved
    assigned_room.room_available_capacity = (assigned_room.room_capacity or 0) - new_reserved
    provider.save(ignore_permissions=True)

    frappe.db.commit()

    # Generate and store admit card automatically
    generate_and_store_admit_card(allocation, is_rescheduled=False)

    return {
        "seat_number":    seat_number,
        "room_name":      assigned_room.room_name,
        "center_name":    provider.center_name,
        "center_address": provider.center_address,
    }


@frappe.whitelist()
def confirm_rescheduled_preference(allocation_name, selected_provider):
    """
    Called when applicant confirms their chosen provider for a RESCHEDULED test.
    """
    allocation = frappe.get_doc("Entrance Test Seat Allocation", allocation_name)

    if allocation.re_allocation_status == "Allocated":
        frappe.throw("You have already been allocated a seat for the rescheduled test.")

    provider = frappe.get_doc("Entrance Test Provider", selected_provider)

    # Find first room with available capacity
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
            seat_number   = f"{room.room_name}-{new_reserved:02d}"
            break

    if not assigned_room:
        frappe.throw(
            f"Sorry, '{provider.center_name}' is now full. "
            "Please choose another preference center."
        )

    # Update the RE fields
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

    # Update room reserved count on provider
    assigned_room.room_reserved_seats     = new_reserved
    assigned_room.room_available_capacity = (assigned_room.room_capacity or 0) - new_reserved
    provider.save(ignore_permissions=True)

    frappe.db.commit()

    # Generate and store admit card automatically for rescheduled test
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
    """
    Generates the admit card using the manual template (bypassing Print Formats)
    and attaches it to the Entrance Test Seat Allocation record.
    If html_content is provided (from the portal), it uses that to generate the PDF.
    If is_rescheduled is True, stores in reschedule_admit_card field.
    """
    if isinstance(allocation, str):
        allocation = frappe.get_doc("Entrance Test Seat Allocation", allocation)
        
    # Generate PDF using the manual template in the eligibility portal
    pdf_content = None
    try:
        from frappe.utils.pdf import get_pdf
        
        if html_content:
            # Clean up the HTML from any JS script tags if present
            import re
            html_content = re.sub(r'<script\b[^>]*>([\s\S]*?)<\/script>', '', html_content)
            html = html_content
        else:
            from slcm.www.eligibility.entrance_test_seat_allocation import get_admit_card_html
            html = get_admit_card_html(allocation, is_rescheduled)
            
        pdf_content = get_pdf(html)
    except Exception as e:
        import traceback
        frappe.log_error(
            message=traceback.format_exc(),
            title=f"Admit Card Generation Error for {allocation.name}"
        )
        return None
    
    field_to_update = "reschedule_admit_card" if is_rescheduled else "admit_card"
    # Ensure the Admit Card is saved in public storage with the requested naming convention
    file_name = f"Admit_Card_{allocation.applicant}.pdf"
    if is_rescheduled:
        file_name = f"Admit_Card_{allocation.applicant}_Rescheduled.pdf"

    # Remove old file from the SPECIFIC field if exists
    old_file_url = getattr(allocation, field_to_update)
    if old_file_url:
        try:
            old_file_name = frappe.db.get_value("File", {"file_url": old_file_url}, "name")
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
    # Update allocation record
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
    