import frappe
import datetime
from frappe.utils import getdate, today, add_days


def _fmt_date(date_obj):
    """Return (month_str, day_str, display_str) for a date object."""
    if not date_obj:
        return "", "", ""
    try:
        if not isinstance(date_obj, datetime.date):
            date_obj = getdate(str(date_obj)[:10])
        month = date_obj.strftime("%b")   # "Apr"
        day   = date_obj.strftime("%d")   # "18"
        return month, day, f"{month} {day}"
    except Exception:
        return "", "", str(date_obj)


def get_context(context):
    redirect_to = (
        frappe.local.request.args.get("redirect-to", "") or
        frappe.local.request.args.get("redirect_to", "") or
        frappe.local.request.args.get("redirect", "") or
        frappe.local.request.args.get("next", "")
    )

    if frappe.session.user != "Guest":
        user_type = frappe.db.get_value("User", frappe.session.user, "user_type") or "Website User"
        if user_type == "System User":
            frappe.local.flags.redirect_location = "/desk"
        else:
            frappe.local.flags.redirect_location = redirect_to or "/merit-and-scholarship/admission_dashboard?panel=profile"
        raise frappe.Redirect

    context.redirect_to = redirect_to or "/merit-and-scholarship/admission_dashboard?panel=profile"

    from slcm.admission.utils.portal import get_portal_config
    portal_config = get_portal_config()
    context.portal_config = portal_config

    # Branding
    context.primary_color    = portal_config.get("primary_color")   or "#CB2929"
    context.secondary_color  = portal_config.get("secondary_color") or "#8B1A1A"
    context.institution_name = (
        portal_config.get("institution_name") or
        portal_config.get("portal_title") or "NLSIU"
    )
    context.portal_logo    = frappe.db.get_single_value("Institution Settings", "logo") or portal_config.get("logo") or portal_config.get("portal_logo") or ""
    context.support_email  = portal_config.get("support_email") or ""
    context.pace_support_email = portal_config.get("pace_support_email") or ""
    context.portal_tagline = portal_config.get("portal_tagline") or "Shaping Tomorrow's Legal Minds"

    # ── Announcements (all, paginated client-side - initial 3) ────────
    try:
        from slcm.admission.utils.web import get_public_announcements
        context.announcements = get_public_announcements()
    except Exception as e:
        frappe.log_error(title="Portal", message=f"login announcements failed: {e}")
        context.announcements = []

    # ── Active Admission Cycle ────────────────────────────────────────
    _today    = getdate(today())
    _tomorrow = add_days(_today, 1)

    active_cycle = None
    try:
        active_year = frappe.get_all("Academic Year", filters={"status": "Active"}, fields=["name"], limit=1)
        if active_year:
            admission_recs = frappe.get_all(
                "PACE Admission", 
                filters={"academic_year": active_year[0].name}, 
                fields=["name", "admission_close_date", "status", "academic_year"], 
                limit=1
            )
            if admission_recs:
                row = admission_recs[0]
                context.is_closed = row.get("status") == "Closed"
                context.display_year = row.get("academic_year")
                active_cycle = frappe._dict({
                    "name":                    row.get("name"),
                    "cycle_start_date":        None,
                    "cycle_end_date":          getdate(row.get("admission_close_date")) if row.get("admission_close_date") else None,
                    "application_start_date":  None,
                    "application_end_date":    getdate(row.get("admission_close_date")) if row.get("admission_close_date") else None,
                })
    except Exception:
        frappe.log_error(frappe.get_traceback(), "pace login: active_cycle fetch")

    context.active_cycle = active_cycle

    # ── Build Important Dates list ────────────────────────────────────
    date_items = []

    def _add(label, date_obj, badge="", item_type="cycle", extra=None):
        if not date_obj:
            return
        # Skip past dates — only show today and future
        if date_obj < _today:
            return
        month, day, disp = _fmt_date(date_obj)

        relative = ""
        if date_obj == _today:
            relative = "Today"
        elif date_obj == _tomorrow:
            relative = "Tomorrow"

        entry = frappe._dict({
            "label":        label,
            "date_obj":     date_obj,
            "date_display": disp,
            "date_month":   month,
            "date_day":     day,
            "badge":        badge,
            "relative":     relative,
            "type":         item_type,
        })
        if extra:
            entry.update(extra)
        date_items.append(entry)

    if active_cycle:
        if active_cycle.cycle_end_date:
            _add("Admission Cycle Closes", active_cycle.cycle_end_date, badge="Cycle")
        if active_cycle.application_start_date:
            _add("Application Form Opens", active_cycle.application_start_date, badge="Applications")
        if active_cycle.application_end_date:
            _add("Application Form Closes", active_cycle.application_end_date, badge="Deadline")

    # ── Events from Important Dates ──
    event_items = []
    try:
        raw_events = frappe.get_all(
            "Important Dates",
            filters={"is_active": 1, "portal_type": ["in", ["PACE", "Both"]]},
            fields=[
                "name", "title", "date", "url", "description",
            ],
            order_by="date asc",
            limit=50,
        )
        for ev in raw_events:
            ev_date = getdate(str(ev.date)[:10]) if ev.date else None
            _add(
                label=ev.title or "Event",
                date_obj=ev_date,
                badge="Event",
                item_type="event",
                extra={
                    "name":        ev.name,
                    "summary":     ev.description or "",
                    "event_venue": "",
                    "reg_url":     ev.url or "",
                    "image":       "",
                    "content":     ev.description or "",
                },
            )
            event_items.append(ev)
    except Exception as ex:
        frappe.log_error(title="Portal", message=f"login events failed: {ex}")

    # Sort: Today first → Tomorrow → future dates ascending → past dates ascending
    def _sort_key(item):
        d = item.get("date_obj")
        if d is None:               return (3, _today)
        if d == _today:             return (0, d)
        if d == _tomorrow:          return (1, d)
        if d >= _today:             return (2, d)
        return                             (4, d)      # past

    date_items.sort(key=_sort_key)

    context.important_dates = date_items
    context.is_logged_in    = bool(frappe.session.user and frappe.session.user != "Guest")
    context.events          = event_items

    context.no_cache   = 1
    context.csrf_token = frappe.local.session.data.csrf_token or ""
    context.title      = context.institution_name + " — Login"
    from frappe.utils import cint
    context.portal_disable_signup = cint(frappe.db.get_single_value("Website Settings", "disable_signup"))

    from frappe import _
    context.forgot_password_intro = _(
        "Enter the email you used to register. We will send a password reset link to that inbox."
    )
    context.register_email_hint = _(
        "We will send a verification email with a link to set your password."
    )
