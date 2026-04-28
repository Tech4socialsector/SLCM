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
    redirect_to = frappe.local.request.args.get("redirect", "") or \
                  frappe.local.request.args.get("next", "")

    if frappe.session.user != "Guest":
        user_type = frappe.db.get_value("User", frappe.session.user, "user_type") or "Website User"
        if user_type == "System User":
            frappe.local.flags.redirect_location = "/desk"
        else:
            frappe.local.flags.redirect_location = redirect_to or "/admission"
        raise frappe.Redirect

    context.redirect_to = redirect_to or "/admission"

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
    context.portal_logo    = portal_config.get("logo") or portal_config.get("portal_logo") or ""
    context.support_email  = portal_config.get("support_email") or ""
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
        active_cycle_name = frappe.db.get_value("Admission Cycle", {"status": "Active"}, "name")
        if active_cycle_name:
            row = frappe.db.get_value(
                "Admission Cycle",
                active_cycle_name,
                ["cycle_start_date", "cycle_end_date",
                 "application_start_date", "application_end_date"],
                as_dict=True,
            ) or {}
            active_cycle = frappe._dict({
                "name":                    active_cycle_name,
                "cycle_start_date":        getdate(row.get("cycle_start_date"))        if row.get("cycle_start_date")        else None,
                "cycle_end_date":          getdate(row.get("cycle_end_date"))          if row.get("cycle_end_date")          else None,
                "application_start_date":  getdate(row.get("application_start_date"))  if row.get("application_start_date")  else None,
                "application_end_date":    getdate(row.get("application_end_date"))    if row.get("application_end_date")    else None,
            })
    except Exception:
        frappe.log_error(frappe.get_traceback(), "login: active_cycle fetch")

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

    # ── Events from Portal Announcement (all, paginated client-side) ──
    event_items = []
    try:
        raw_events = frappe.get_all(
            "Portal Announcement",
            filters={"is_active": 1, "announcement_type": "Event", "status": "Published"},
            fields=[
                "name", "title", "summary", "event_date", "event_venue",
                "event_registration_url", "featured_image", "content",
            ],
            order_by="event_date asc",
            limit=50,
        )
        for ev in raw_events:
            ev_date = getdate(str(ev.event_date)[:10]) if ev.event_date else None
            _add(
                label=ev.title or "Event",
                date_obj=ev_date,
                badge="Event",
                item_type="event",
                extra={
                    "name":        ev.name,
                    "summary":     ev.summary or "",
                    "event_venue": ev.event_venue or "",
                    "reg_url":     ev.event_registration_url or "",
                    "image":       ev.featured_image or "",
                    "content":     ev.content or "",
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
