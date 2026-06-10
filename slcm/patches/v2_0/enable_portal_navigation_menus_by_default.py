import frappe


_MENU_FIELDS = [
    "menu_dashboard", "menu_courses", "menu_attendance", "menu_timetable",
    "menu_exam_schedule", "menu_fees", "menu_results", "menu_announcements",
    "menu_enrollment", "menu_venue_booking",
    "menu_profile", "menu_documents", "menu_grade_appeal",
    "menu_transcript_request", "menu_placement", "menu_helpdesk",
]


def execute():
    """Enable all portal navigation menu fields that have never been explicitly saved.

    When new Check fields are added to an existing Single doctype, Frappe's migrate
    may write value='0' into tabSingles (the DB default) before the field's JSON
    default of '1' is applied.  This patch sets every menu field to 1 unless the
    admin has already explicitly changed it away from the factory default.  Since
    these fields are brand-new, any '0' row was written by the migrate process, not
    by a deliberate admin choice, so it is safe to overwrite.
    """
    for field in _MENU_FIELDS:
        frappe.db.set_single_value("Student Portal Settings", field, 1)
    frappe.db.commit()
