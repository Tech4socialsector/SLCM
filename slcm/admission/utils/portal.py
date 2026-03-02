import frappe
import json
from frappe.utils import now, add_days, getdate, today


# ── CONFIG ────────────────────────────────────────────────────────

def get_portal_config():
    """Returns Applicant Portal Config singleton. Cached 5 min."""
    cached = frappe.cache().get_value("applicant_portal_config")
    if cached:
        return cached
    try:
        config = frappe.get_doc("Applicant Portal Config", "Applicant Portal Config", ignore_permissions=True)
        if not config.primary_color:
            try:
                config.primary_color = frappe.db.get_value(
                    "Institution Settings", "portal_theme_color") or "#1a237e"
            except Exception:
                config.primary_color = "#1a237e"
        frappe.cache().set_value("applicant_portal_config", config, expires_in_sec=300)
        return config
    except Exception:
        return frappe._dict({
            "portal_title": "Admissions Portal",
            "portal_subtitle": "",
            "portal_active": 1,
            "primary_color": "#1a237e",
            "secondary_color": "#ffffff",
            "skip_fee_check_for_testing": 1,
            "show_stage_progress": 1,
            "progress_style": "Steps",
            "allow_pdf_download": 1,
            "program_card_layout": "Grid",
            "show_intake_count": 0,
            "show_eligibility_hint": 0,
            "show_announcement": 0,
            "enable_email_notifications": 1,
            "enable_portal_notifications": 1,
            "footer_text": ""
        })


# ── FEE CHECK ─────────────────────────────────────────────────────

def can_proceed_past_fee(applicant):
    """
    Returns True if applicant can proceed (fee paid/waived or testing mode).
    """
    try:
        config = get_portal_config()
        if config.get("skip_fee_check_for_testing"):
            return True
        fee_status = frappe.db.get_value("Applicant", applicant, "application_fee_status")
        return fee_status in ("Paid", "Waived")
    except Exception:
        return True  # Fail open if config missing


# ── EDIT CHECK ────────────────────────────────────────────────────

def can_edit_application(applicant):
    """
    Returns True if applicant can still edit their submitted application.
    Based on Portal Config rules.
    """
    try:
        app_status = frappe.db.get_value("Applicant", applicant, "application_status")
        if app_status == "Draft":
            return True
        if app_status == "Locked":
            return False

        config = get_portal_config()
        if not config.get("allow_edit_after_submit"):
            return False

        until = config.get("edit_allowed_until")
        if until == "Never":
            return False
        if until == "Application End Date":
            cycle = frappe.db.get_value("Applicant", applicant, "admission_cycle")
            end_date = frappe.db.get_value("Admission Cycle", cycle, "end_date")
            if end_date:
                return getdate(today()) <= getdate(end_date)
            return False
        if until == "Fixed Days":
            days = config.get("edit_allowed_days") or 0
            submitted_on = frappe.db.get_value(
                "Application Form Response",
                {"applicant": applicant},
                "submitted_on"
            )
            if submitted_on:
                deadline = add_days(submitted_on, days)
                return getdate(today()) <= getdate(deadline)
        return False
    except Exception:
        return False


# ── PROGRAMS ──────────────────────────────────────────────────────

def get_active_programs():
    """
    Returns programs listed in the currently active Admission Cycle.
    Programs come from the 'programs' child table on Admission Cycle.
    """
    try:
        # Find active cycle
        active_cycles = frappe.get_all(
            "Admission Cycle",
            filters={"status": "Active"},
            fields=["name"],
            limit=1,
            ignore_permissions=True
        )
        if not active_cycles:
            return []
        active_cycle_name = active_cycles[0].name

        # Read programs from cycle's child table
        cycle_programs = frappe.get_all(
            "Admission Cycle Program",
            filters={
                "parent": active_cycle_name,
                "is_active": 1
            },
            fields=[
                "program", "program_name", "campus",
                "seats", "eligibility_hint", "brochure_url",
                "program_image", "program_media"
            ],
            order_by="program_name asc",
            ignore_permissions=True
        )

        result = []
        for cp in cycle_programs:
            # Get program abbreviation from Program master
            abbr = frappe.db.get_value(
                "Program", cp.program, "program_shortcode"
            ) or ""

            # Get campus name if set
            campus_name = ""
            if cp.campus:
                campus_name = frappe.db.get_value(
                    "Company", cp.campus, "company_name") or cp.campus

            result.append({
                "program": cp.program,
                "program_name": cp.program_name or cp.program,
                "program_abbreviation": abbr,
                "total_seats": cp.seats,
                "eligibility_hint": cp.eligibility_hint or "",
                "brochure_url": cp.brochure_url or "",
                "campus": cp.campus or "",
                "campus_name": campus_name,
                "admission_cycle": active_cycle_name,
                "program_image": cp.program_image or "",
                "program_media": cp.program_media or ""
            })

        return result
    except Exception as e:
        frappe.log_error(f"get_active_programs failed: {e}", "Portal")
        return []


def get_campus_options(program):
    """
    Returns campus options for a program from the active cycle.
    Only relevant if enable_multi_campus = ON.
    """
    try:
        multi = frappe.db.get_single_value(
            "Institution Settings", "enable_multi_campus"
        )
        if not multi:
            return []

        active_cycles = frappe.get_all(
            "Admission Cycle",
            filters={"status": "Active"},
            fields=["name"],
            limit=1,
            ignore_permissions=True
        )
        if not active_cycles:
            return []
        active_cycle = active_cycles[0].name

        # Get all campus entries for this program in the active cycle
        entries = frappe.get_all(
            "Admission Cycle Program",
            filters={
                "parent": active_cycle,
                "parenttype": "Admission Cycle",
                "program": program,
                "is_active": 1
            },
            fields=["campus"],
            ignore_permissions=True
        )

        result = []
        for e in entries:
            if not e.campus:
                continue
            name = frappe.db.get_value(
                "Company", e.campus, "company_name") or e.campus
            result.append({"campus": e.campus, "campus_name": name})

        return result
    except Exception as e:
        frappe.log_error(f"get_campus_options failed: {e}", "Portal")
        return []


# ── FORM ──────────────────────────────────────────────────────────

def get_application_form(program, cycle):
    """Returns form fields for a program+cycle combination."""
    try:
        form = frappe.db.get_value(
            "Program Form Mapping",
            {"program": program, "admission_cycle": cycle}, "form"
        )
        if not form:
            return None
        form_doc = frappe.get_doc("Application Form Config", form, ignore_permissions=True)
        fields = []
        for f in sorted(form_doc.fields or [], key=lambda x: x.sequence or 0):
            fields.append({
                "fieldname": f.field_label.lower().replace(" ", "_").replace("/", "_"),
                "label": f.field_label,
                "fieldtype": f.field_type,
                "mandatory": int(f.mandatory or 0),
                "options": f.options or "",
                "sequence": f.sequence or 0
            })
        return {
            "form_name": form_doc.name,
            "form_version": form_doc.version or 1,
            "fields": fields
        }
    except Exception as e:
        frappe.log_error(f"get_application_form failed: {e}", "Portal")
        return None



# ── APPLICANT ─────────────────────────────────────────────────────

@frappe.whitelist()
def get_or_create_applicant(email, full_name, mobile, cycle, program=None, campus_preferences=None):
    """
    Returns existing Applicant for email+cycle or creates new Draft.
    Enforces one program per cycle.
    campus_preferences: list of {"campus": "...", "preference_order": 1}
    """
    try:
        existing = frappe.db.get_value(
            "Applicant", {"email": email, "admission_cycle": cycle}, "name"
        )
        if existing:
            return frappe.get_doc("Applicant", existing)

        doc = frappe.get_doc({
            "doctype": "Applicant",
            "candidate_name": full_name,
            "email": email,
            "mobile_number": mobile or "",
            "admission_cycle": cycle,
            "application_status": "Draft",
            "application_fee_status": "Pending"
        })

        # Add campus preferences if multi-campus
        if campus_preferences:
            for pref in campus_preferences:
                doc.append("campus_preferences", {
                    "campus": pref.get("campus"),
                    "program": program,
                    "preference_order": pref.get("preference_order"),
                    "status": "Pending"
                })

        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        # Log creation
        frappe.get_doc({
            "doctype": "Admission Audit Log",
            "action": "Applicant Created",
            "reference_doctype": "Applicant",
            "reference_name": doc.name,
            "performed_by": frappe.session.user,
            "reason": "New applicant registered via portal"
        }).insert(ignore_permissions=True)

        return doc
    except Exception as e:
        frappe.log_error(f"get_or_create_applicant failed: {e}", "Portal")
        frappe.throw("Could not create applicant record. Please try again.")


def save_application_response(applicant, form_config, responses_dict, is_final=False):
    """
    Save or update Application Form Response.
    is_final=True → locks record, updates applicant status to Submitted.
    Respects can_edit_application() check.
    """
    try:
        existing = frappe.db.get_value(
            "Application Form Response",
            {"applicant": applicant, "form_config": form_config}, "name"
        )
        if existing:
            doc = frappe.get_doc("Application Form Response", existing)
            if not doc.is_draft:
                if not can_edit_application(applicant):
                    frappe.throw("Application is submitted and editing is not permitted.")
                # Re-open for edit
                doc.is_draft = 1

        else:
            cycle = frappe.db.get_value("Applicant", applicant, "admission_cycle")
            doc = frappe.new_doc("Application Form Response")
            doc.applicant = applicant
            doc.admission_cycle = cycle
            doc.form_config = form_config
            doc.is_draft = 1

        doc.responses = json.dumps(responses_dict, ensure_ascii=False)
        doc.last_saved_on = now()

        if is_final:
            doc.lock()
            frappe.db.set_value("Applicant", applicant, "application_status", "Submitted")
            frappe.db.commit()
            # Audit log
            frappe.get_doc({
                "doctype": "Admission Audit Log",
                "action": "Application Submitted",
                "reference_doctype": "Applicant",
                "reference_name": applicant,
                "performed_by": frappe.session.user,
                "reason": "Applicant submitted application via portal"
            }).insert(ignore_permissions=True)
            # Notification
            from slcm.admission.utils.notifications import notify_applicant
            notify_applicant(
                applicant=applicant,
                notification_type="Stage Update",
                message="Your application has been submitted successfully.",
                action_url="/applicant-portal"
            )
        else:
            doc.save(ignore_permissions=True)
            frappe.db.commit()

        return {"success": True, "name": doc.name, "is_draft": doc.is_draft}
    except Exception as e:
        frappe.log_error(f"save_application_response failed: {e}", "Portal")
        return {"success": False, "error": str(e)}


# ── STAGE PROGRESS ────────────────────────────────────────────────

def get_stage_progress(applicant):
    """Returns ordered list of stages with status for this applicant."""
    try:
        app = frappe.get_doc("Applicant", applicant)
        cycle = app.admission_cycle
        if not cycle:
            return []
        stages = frappe.get_all(
            "Admission Stage Config",
            filters={"admission_cycle": cycle, "is_enabled": 1},
            fields=["stage_name", "sequence", "stage_type"],
            order_by="sequence asc"
        )
        current = app.get("current_stage") or ""
        result = []
        passed = False
        for s in stages:
            if s.stage_name == current:
                status = "Active"
                passed = True
            elif not passed:
                status = "Completed"
            else:
                status = "Pending"
            result.append({
                "stage_name": s.stage_name,
                "stage_type": s.stage_type,
                "sequence": s.sequence,
                "status": status
            })
        return result
    except Exception as e:
        frappe.log_error(f"get_stage_progress failed: {e}", "Portal")
        return []


def get_campus_status(applicant):
    """Returns per-campus status for multi-campus applicants."""
    try:
        prefs = frappe.get_all(
            "Applicant Campus Preference",
            filters={"parent": applicant},
            fields=["campus", "program", "preference_order", "status"],
            order_by="preference_order asc"
        )
        result = []
        for p in prefs:
            campus_name = frappe.db.get_value("Company", p.campus, "company_name") or p.campus
            result.append({
                "campus": p.campus,
                "campus_name": campus_name,
                "program": p.program,
                "preference_order": p.preference_order,
                "status": p.status or "Pending"
            })
        return result
    except Exception as e:
        frappe.log_error(f"get_campus_status failed: {e}", "Portal")
        return []


def generate_application_pdf(applicant):
    """Generates application PDF using template from Portal Config."""
    try:
        config = get_portal_config()
        if not config.get("allow_pdf_download"):
            frappe.throw("PDF download is not enabled.")
        template_name = config.get("application_template")
        if not template_name:
            frappe.throw("No application PDF template configured.")

        template = frappe.get_doc("Offer Letter Template", template_name)
        app = frappe.get_doc("Applicant", applicant)

        response_name = frappe.db.get_value(
            "Application Form Response", {"applicant": applicant}, "name"
        )
        responses = {}
        if response_name:
            r = frappe.get_doc("Application Form Response", response_name)
            responses = r.get_responses_dict()

        context = {
            "applicant_name": app.get("candidate_name", ""),
            "applicant_id": app.applicant_id,
            "admission_cycle": app.get("admission_cycle", ""),
            "application_date": str(app.creation or "")[:10]
        }
        for k, v in responses.items():
            context[f"responses.{k}"] = v

        content = template.content or ""
        for key, value in context.items():
            content = content.replace("{{" + key + "}}", str(value or ""))

        from frappe.utils.pdf import get_pdf
        pdf_bytes = get_pdf(content)

        filename = f"Application_{applicant}.pdf"
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": filename,
            "content": pdf_bytes,
            "is_private": 1,
            "attached_to_doctype": "Applicant",
            "attached_to_name": applicant
        })
        file_doc.insert(ignore_permissions=True)
        return {"success": True, "file_url": file_doc.file_url}
    except Exception as e:
        frappe.log_error(f"generate_application_pdf failed: {e}", "Portal")
        return {"success": False, "error": str(e)}


# ── WHITELISTED API ENDPOINTS ─────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def api_get_portal_config():
    config = get_portal_config()
    return {k: config.get(k) for k in [
        "portal_title", "portal_subtitle", "hero_image", "primary_color",
        "secondary_color", "portal_active", "maintenance_message",
        "show_announcement", "header_announcement", "program_card_layout",
        "show_intake_count", "show_eligibility_hint", "show_stage_progress",
        "progress_style", "allow_pdf_download", "footer_text",
        "contact_email", "contact_phone", "skip_fee_check_for_testing",
        "fee_pending_message", "allow_edit_after_submit",
        "allow_document_upload_after_submit",
        "enable_portal_notifications", "submission_message"
    ]}

@frappe.whitelist(allow_guest=True)
def api_get_programs():
    return get_active_programs()

@frappe.whitelist(allow_guest=True)
def api_get_campus_options(program):
    return get_campus_options(program)

@frappe.whitelist(allow_guest=True)
def api_get_form(program, cycle):
    return get_application_form(program, cycle)

@frappe.whitelist()
def api_get_my_application():
    email = frappe.session.user
    app = frappe.db.get_value(
        "Applicant",
        {"email": email},
        ["name", "application_status", "application_fee_status",
         "admission_cycle", "current_stage", "candidate_name", "applicant_id"],
        as_dict=True
    )
    return app

@frappe.whitelist()
def api_autosave(applicant, form_config, responses):
    data = json.loads(responses) if isinstance(responses, str) else responses
    return save_application_response(applicant, form_config, data, is_final=False)

@frappe.whitelist()
def api_submit(applicant, form_config, responses):
    data = json.loads(responses) if isinstance(responses, str) else responses
    res = save_application_response(applicant, form_config, data, is_final=True)
    if res.get("success"):
        # Increment application count on the cycle program row
        try:
            applicant_doc = frappe.get_doc("Applicant", applicant)
            increment_application_count(
                applicant_doc.program,
                applicant_doc.admission_cycle
            )
        except Exception:
            pass  # non-blocking
    return res

@frappe.whitelist()
def api_get_stage_progress(applicant):
    return get_stage_progress(applicant)

@frappe.whitelist()
def api_get_campus_status(applicant):
    return get_campus_status(applicant)

@frappe.whitelist()
def api_download_pdf(applicant):
    return generate_application_pdf(applicant)

@frappe.whitelist()
def api_get_notifications(applicant):
    from slcm.admission.utils.notifications import get_notifications, get_unread_count
    return {
        "notifications": get_notifications(applicant, limit=10),
        "unread_count": get_unread_count(applicant)
    }

@frappe.whitelist()
def api_mark_notifications_read(applicant):
    from slcm.admission.utils.notifications import mark_all_read
    mark_all_read(applicant)
    return {"success": True}

@frappe.whitelist()
def api_can_edit(applicant):
    return {"can_edit": can_edit_application(applicant)}

@frappe.whitelist()
def api_can_proceed_past_fee(applicant):
    return {"can_proceed": can_proceed_past_fee(applicant)}


# ── ANNOUNCEMENTS ─────────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def api_get_announcements(program=None, cycle=None, campus=None, limit=20):
    """
    Returns published announcements for the portal.
    Filters by targeting (global + matching targeted records).
    Works for guests — allow_guest=True.
    """
    try:
        filters = [
            ["status", "=", "Published"],
            ["show_on_portal", "=", 1]
        ]
        announcements = frappe.get_all(
            "Portal Announcement",
            filters=filters,
            fields=[
                "name", "title", "announcement_type", "summary",
                "featured_image", "publish_date", "expiry_date",
                "event_date", "event_venue", "event_registration_url",
                "target_audience", "target_program", "target_cycle",
                "target_campus", "view_count"
            ],
            order_by="publish_date desc",
            limit=int(limit),
            ignore_permissions=True
        )

        # Filter by targeting
        result = []
        for ann in announcements:
            if ann.target_audience == "Global":
                result.append(ann)
            elif ann.target_audience == "By Program" and program and ann.target_program == program:
                result.append(ann)
            elif ann.target_audience == "By Cycle" and cycle and ann.target_cycle == cycle:
                result.append(ann)
            elif ann.target_audience == "By Campus" and campus and ann.target_campus == campus:
                result.append(ann)

        return result
    except Exception as e:
        frappe.log_error(f"api_get_announcements failed: {e}", "Portal")
        return []


@frappe.whitelist(allow_guest=True)
def api_get_announcement_detail(name):
    """Returns full content of a single announcement."""
    try:
        doc = frappe.get_doc("Portal Announcement", name, ignore_permissions=True)
        if doc.status != "Published" or not doc.show_on_portal:
            return None
        return {
            "name": doc.name,
            "title": doc.title,
            "announcement_type": doc.announcement_type,
            "content": doc.content,
            "summary": doc.summary,
            "featured_image": doc.featured_image,
            "publish_date": str(doc.publish_date or ""),
            "expiry_date": str(doc.expiry_date or ""),
            "event_date": str(doc.event_date or ""),
            "event_venue": doc.event_venue or "",
            "event_registration_url": doc.event_registration_url or "",
            "view_count": doc.view_count or 0
        }
    except Exception as e:
        frappe.log_error(f"api_get_announcement_detail failed: {e}", "Portal")
        return None


@frappe.whitelist(allow_guest=True)
def api_increment_view_count(name):
    """Increments view count for an announcement."""
    try:
        current = frappe.db.get_value("Portal Announcement", name, "view_count") or 0
        frappe.db.set_value("Portal Announcement", name, "view_count", current + 1)
        frappe.db.commit()
        return {"success": True}
    except Exception as e:
        frappe.log_error(f"api_increment_view_count failed: {e}", "Portal")
        return {"success": False}


# ── PROGRAM MEDIA ─────────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def api_get_program_media(program=None):
    """
    Returns media for a program, or all featured media if no program given.
    Works for guests — allow_guest=True.
    """
    try:
        filters = {"is_active": 1}
        if program:
            filters["program"] = program
        else:
            filters["is_featured"] = 1

        media_gallery = frappe.get_all(
            "Program Media",
            filters=filters,
            fields=[
                "name", "program",
                "brochure_pdf",
                "is_featured",
                "media_gallery"
            ],
            ignore_permissions=True
        )
        media = []
        for item in media_gallery.media_gallery:
            media.append({
                "media_type": item.media_type,
                "file_url": item.file,
                "sequence": item.sequence,
                "caption": item.caption
            })

        return media
    except Exception as e:
        frappe.log_error(f"api_get_program_media failed: {e}", "Portal")
        return []


# ── PROGRAM STATUS & SEAT AVAILABILITY ───────────────────────────

@frappe.whitelist(allow_guest=True)
def api_get_program_status(program, cycle):
    """
    Returns open/closed status and seat availability for a program.
    Reads seat data from Program Reservation Policy.
    Portal uses this to show Filling Fast / Seats Filled badges
    and to enable or disable the Apply Now button.
    """
    try:
        from frappe.utils import now, get_datetime

        result = {
            "program": program,
            "cycle": cycle,
            "is_open": True,
            "close_reason": None,
            "total_seats": 0,
            "filled_seats": 0,
            "available_seats": 0,
            "seat_pct_filled": 0,
            "application_count": 0,
            "max_applications": 0,
            "show_filling_fast": False,
            "show_seats_filled": False
        }

        cycle_doc = frappe.get_doc("Admission Cycle", cycle, ignore_permissions=True)

        # Check application end date at cycle level
        if cycle_doc.application_end:
            if get_datetime(now()) > get_datetime(cycle_doc.application_end):
                result["is_open"] = False
                result["close_reason"] = "application_date_passed"
                return result

        # Find program row
        prog_row = None
        for p in (cycle_doc.programs or []):
            if p.program == program:
                prog_row = p
                break

        if not prog_row:
            result["is_open"] = False
            result["close_reason"] = "program_not_in_cycle"
            return result

        result["application_count"] = prog_row.application_count or 0
        result["max_applications"] = prog_row.max_applications or 0

        # Check max applications
        max_app = prog_row.max_applications or 0
        if max_app > 0 and (prog_row.application_count or 0) >= max_app:
            result["is_open"] = False
            result["close_reason"] = "max_applications_reached"

        # Read seat data from Program Reservation Policy
        reservation_policy = prog_row.get("reservation_policy")
        if reservation_policy:
            try:
                policy = frappe.get_doc(
                    "Program Reservation Policy", reservation_policy, ignore_permissions=True
                )
                total = policy.total_seats or 0
                filled = policy.total_filled or 0
                available = policy.total_available or 0

                result["total_seats"] = total
                result["filled_seats"] = filled
                result["available_seats"] = available

                if total > 0:
                    pct = (filled / total) * 100
                    result["seat_pct_filled"] = round(pct, 1)
                    # Filling Fast: 90% or more filled but not 100%
                    result["show_filling_fast"] = pct >= 90 and filled < total
                    result["show_seats_filled"] = filled >= total
                    if filled >= total:
                        result["is_open"] = False
                        result["close_reason"] = "seats_filled"
            except Exception:
                pass  # No policy yet — seats info not available
        else:
            # Fallback to seats field on program row
            result["total_seats"] = prog_row.seats or 0

        return result

    except Exception as e:
        frappe.log_error(f"api_get_program_status failed: {e}", "Portal")
        return {
            "is_open": True, "close_reason": None,
            "show_filling_fast": False, "show_seats_filled": False
        }


@frappe.whitelist(allow_guest=True)
def api_get_all_program_statuses(cycle):
    """
    Returns status for all active programs in the cycle.
    Called once on portal load to avoid multiple API calls.
    """
    try:
        cycle_doc = frappe.get_doc("Admission Cycle", cycle, ignore_permissions=True)
        statuses = {}
        for p in (cycle_doc.programs or []):
            if p.is_active:
                statuses[p.program] = api_get_program_status(p.program, cycle)
        return statuses
    except Exception as e:
        frappe.log_error(f"api_get_all_program_statuses failed: {e}", "Portal")
        return {}


# ── APPLICATION FEE ───────────────────────────────────────────────

@frappe.whitelist(allow_guest=False)
def api_get_application_fee(program, cycle, category=None):
    """
    Returns application fee for a program based on applicant's declared category.
    Reads from Program Reservation Policy → categories → application_fee.
    Falls back to first category row (General) if no match.
    """
    try:
        # Get reservation_policy link from cycle program row
        cycle_doc = frappe.get_doc("Admission Cycle", cycle, ignore_permissions=True)
        reservation_policy = None
        for row in (cycle_doc.programs or []):
            if row.program == program:
                reservation_policy = row.get("reservation_policy")
                break

        if not reservation_policy:
            return {
                "fee_amount": 0,
                "fee_label": "Application Fee",
                "category": None,
                "category_name": "General"
            }

        policy = frappe.get_doc("Program Reservation Policy", reservation_policy, ignore_permissions=True)
        fee, label, cat = policy.get_fee_for_category(category)

        cat_name = ""
        if cat:
            cat_name = frappe.db.get_value(
                "Program Reservation Category",
                {"parent": reservation_policy, "category": cat},
                "category_name"
            ) or cat

        return {
            "fee_amount": fee,
            "fee_label": label,
            "category": cat,
            "category_name": cat_name
        }

    except Exception as e:
        frappe.log_error(f"api_get_application_fee failed: {e}", "Portal")
        return {"fee_amount": 0, "fee_label": "Application Fee",
                "category": None, "category_name": ""}



# ── INCREMENT APPLICATION COUNT ───────────────────────────────────

def increment_application_count(program, cycle):
    """
    Called internally when an application is submitted.
    Increments application_count on the matching Admission Cycle Program row.
    """
    try:
        cycle_doc = frappe.get_doc("Admission Cycle", cycle, ignore_permissions=True)
        for row in (cycle_doc.programs or []):
            if row.program == program:
                current = row.application_count or 0
                frappe.db.set_value(
                    "Admission Cycle Program",
                    row.name,
                    "application_count",
                    current + 1
                )
                frappe.db.commit()
                return True
        return False
    except Exception as e:
        frappe.log_error(
            f"increment_application_count failed: {e}", "Portal"
        )
        return False


@frappe.whitelist(allow_guest=True)
def api_get_program_images(program_media=None, program_image=None):
    """
    Returns image list for a program card carousel.
    Priority: Program Media gallery images first,
    fallback to single program_image.
    """
    images = []

    if program_media:
        try:
            media_doc = frappe.get_doc("Program Media", program_media, ignore_permissions=True)
            for img in media_doc.get("images") or []:
                if img.get("image"):
                    images.append({
                        "url": img.image,
                        "caption": img.get("caption") or ""
                    })
        except Exception:
            pass

    if not images and program_image:
        images.append({
            "url": program_image,
            "caption": ""
        })

    return images


@frappe.whitelist(allow_guest=True)
def api_get_hero_slides():
    """
    Returns all slides for the hero banner carousel.
    hero_image is always slide 1.
    slideshow_images child table provides slides 2, 3, 4...
    Returns empty list if neither is set — JS shows text-only hero.
    """
    try:
        config = frappe.get_single("Applicant Portal Config")
        slides = []

        # Slide 1: hero_image (always first if set)
        hero_image = config.get("hero_image")
        if hero_image:
            slides.append({
                "url": hero_image,
                "caption": config.get("portal_title") or "",
                "link_url": ""
            })

        # Slides 2+: slideshow_images child table
        for row in config.get("slideshow_images") or []:
            if row.get("image"):
                slides.append({
                    "url": row.image,
                    "caption": row.get("caption") or "",
                    "link_url": row.get("link_url") or ""
                })

        return slides

    except Exception as e:
        frappe.log_error(f"api_get_hero_slides error: {e}", "Portal API")
        return []


@frappe.whitelist()
def api_mark_notification_read(notification_id):
    """Mark a single Applicant Notification as read."""
    try:
        if frappe.db.exists("Applicant Notification", notification_id):
            notif = frappe.get_doc(
                "Applicant Notification", notification_id
            )
            if notif.applicant == frappe.session.user:
                notif.db_set("is_read", 1)
                return {"success": True}
        return {"success": False, "error": "Not found or not authorized"}
    except Exception as e:
        return {"success": False, "error": str(e)}
