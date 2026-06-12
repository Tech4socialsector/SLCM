# Copyright (c) 2026, Nishanth and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

_SELF_SERVICE_GATE = {
    # preference_field: settings_permission_field
    "theme_mode":            "allow_theme_override",
    "primary_color_override":"allow_theme_override",
    "font_size_pref":        "allow_font_size_override",
    "layout_density_pref":   "allow_density_override",
    "hide_today_schedule":   "allow_dashboard_customization",
    "hide_pending_evaluations":"allow_dashboard_customization",
    "hide_class_statistics": "allow_dashboard_customization",
    "hide_workload_summary": "allow_dashboard_customization",
    "hide_leave_status":     "allow_dashboard_customization",
    "default_course_view":   "allow_dashboard_customization",
    "notify_assignment_submission": "allow_notification_settings",
    "notify_attendance_discrepancy":"allow_notification_settings",
    "notify_student_query":        "allow_notification_settings",
    "notify_leave_request_update": "allow_notification_settings",
    "notify_marks_due":            "allow_notification_settings",
    "email_digest_frequency":      "allow_notification_settings",
}


class FacultyPortalUserPreferences(Document):
    def validate(self):
        self._enforce_owner()
        self._validate_color()
        self._enforce_self_service_gates()

    def _enforce_owner(self):
        """Faculty may only save preferences for themselves."""
        if "System Manager" in frappe.get_roles() or frappe.session.user == "Administrator":
            return
        if self.faculty_user != frappe.session.user:
            frappe.throw(
                "You can only edit your own Faculty Portal preferences.",
                frappe.PermissionError,
            )

    def _validate_color(self):
        if not self.primary_color_override:
            return
        import re
        if not re.match(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$", self.primary_color_override.strip()):
            frappe.throw("Primary Color Override must be a valid hex color (e.g. #1e3a5f or #fff)")

    def _enforce_self_service_gates(self):
        """Silently clear fields the admin has not unlocked for self-service."""
        try:
            settings = frappe.db.get_singles_dict("Faculty Portal Settings")
        except Exception:
            return

        for pref_field, gate_field in _SELF_SERVICE_GATE.items():
            if not int(settings.get(gate_field, 1)):
                field_meta = self.meta.get_field(pref_field)
                default = (field_meta.default if field_meta else None) or ""
                self.set(pref_field, default)


# ── Whitelisted helper for the JS controller ──────────────────────────

@frappe.whitelist()
def get_my_preferences():
    """Return the current user's preferences merged with which gates are open."""
    user = frappe.session.user

    try:
        prefs = frappe.get_doc("Faculty Portal User Preferences", user).as_dict()
    except frappe.DoesNotExistError:
        prefs = {}

    try:
        settings = frappe.db.get_singles_dict("Faculty Portal Settings")
    except Exception:
        settings = {}

    gates = {
        "allow_theme_override":         int(settings.get("allow_theme_override", 1)),
        "allow_font_size_override":      int(settings.get("allow_font_size_override", 1)),
        "allow_density_override":        int(settings.get("allow_density_override", 1)),
        "allow_dashboard_customization": int(settings.get("allow_dashboard_customization", 1)),
        "allow_notification_settings":   int(settings.get("allow_notification_settings", 1)),
        "allow_language_preference":     int(settings.get("allow_language_preference", 0)),
    }

    return {"preferences": prefs, "gates": gates}
