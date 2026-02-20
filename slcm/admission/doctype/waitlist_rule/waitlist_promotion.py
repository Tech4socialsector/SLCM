import frappe
from frappe.utils import now_datetime, getdate


def _get_total_program_seats(campus: str, admission_cycle: str, program: str) -> int:
    admission_year = frappe.db.get_value("Admission Cycle", admission_cycle, "parent")
    if not admission_year:
        frappe.throw(f"No Admission Year found for cycle {admission_cycle}")

    program_offering = frappe.get_doc(
        "Program Offering",
        {"campus": campus, "admission_year": admission_year},
    )

    rule_name = None
    for p in program_offering.programs:
        if p.program_of_study == program:
            rule_name = p.reservation_rule
            break

    if not rule_name:
        frappe.throw(f"No Reservation Rule found for Program {program} in Program Offering")

    quotas = frappe.get_all(
        "Reservation Quota",
        filters={"parent": rule_name},
        fields=["seats"],
    )

    total = 0
    for q in quotas:
        try:
            total += int(q.seats or 0)
        except Exception:
            total += 0

    return int(total)


def _get_latest_seat_allocation(admission_cycle: str, campus: str):
    name = frappe.db.get_value(
        "Seat Allocation",
        {"admission_cycle": admission_cycle, "campus": campus, "docstatus": ["<", 2]},
        "name",
        order_by="modified desc",
    )
    if not name:
        return None
    return frappe.get_doc("Seat Allocation", name)


def _lock_seat_allocation(seat_allocation_name: str) -> None:
    # Prevent race conditions if manual + scheduler are run at the same time.
    frappe.db.sql(
        """
        SELECT name
        FROM `tabSeat Allocation`
        WHERE name=%s
        FOR UPDATE
        """,
        (seat_allocation_name,),
    )


def _resolve_applicant_from_admission_result(admission_result_name: str):
    # Seat Selection Applicant currently links to Admission Result.
    # Offer Letter links to Applicant. Try best-effort mapping.
    if frappe.db.exists("Applicant", admission_result_name):
        return admission_result_name

    ar = frappe.db.get_value(
        "Admission Result",
        admission_result_name,
        ["applicant_name"],
        as_dict=True,
    )
    if ar and ar.get("applicant_name") and frappe.db.exists("Applicant", ar.get("applicant_name")):
        return ar.get("applicant_name")

    return None


def _create_offer_letter_if_possible(admission_result_name: str, rule_doc) -> None:
    applicant = _resolve_applicant_from_admission_result(admission_result_name)
    if not applicant:
        return

    exists = frappe.db.exists(
        "Offer Letter",
        {"applicant": applicant, "admission_cycle": rule_doc.admission_cycle, "program": rule_doc.program},
    )
    if exists:
        return

    offer = frappe.new_doc("Offer Letter")
    offer.applicant = applicant
    offer.admission_cycle = rule_doc.admission_cycle
    offer.campus = rule_doc.campus
    offer.program = rule_doc.program
    offer.offer_status = "Draft"
    offer.insert(ignore_permissions=True)


def process_waitlist(rule_doc):
    if not rule_doc or rule_doc.doctype != "Waitlist Rule":
        frappe.throw("Invalid Waitlist Rule")

    if rule_doc.is_locked:
        return

    if (rule_doc.status or "").lower() != "active":
        return

    if rule_doc.upgrade_cutoff_date and getdate(now_datetime()) > getdate(rule_doc.upgrade_cutoff_date):
        return

    seat_alloc = _get_latest_seat_allocation(rule_doc.admission_cycle, rule_doc.campus)
    if not seat_alloc:
        return

    _lock_seat_allocation(seat_alloc.name)

    total_seats = _get_total_program_seats(rule_doc.campus, rule_doc.admission_cycle, rule_doc.program)

    selected_rows = [
        r
        for r in seat_alloc.selection_applicant
        if r.program == rule_doc.program and r.selection_status == "Selected"
    ]
    allocated = len(selected_rows)
    available = int(total_seats) - int(allocated)

    if available <= 0:
        return

    waitlisted = [
        r
        for r in seat_alloc.selection_applicant
        if r.program == rule_doc.program and r.selection_status == "Waitlisted"
    ]

    # Highest merit first
    waitlisted.sort(key=lambda x: (-(x.total_score or 0), x.overall_rank or 999999))

    promoted = 0
    for row in waitlisted[:available]:
        row.selection_status = "Selected"
        promoted += 1
        _create_offer_letter_if_possible(row.applicant, rule_doc)

    if promoted:
        seat_alloc.total_selected = int(seat_alloc.total_selected or 0) + promoted
        seat_alloc.total_waitlisted = max(0, int(seat_alloc.total_waitlisted or 0) - promoted)
        seat_alloc.save(ignore_permissions=True)

    rule_doc.db_set("last_executed_on", now_datetime(), update_modified=False)
    rule_doc.db_set("execution_log_count", int(rule_doc.execution_log_count or 0) + 1, update_modified=False)

    frappe.db.commit()


@frappe.whitelist()
def run_manual_waitlist(rule: str):
    rule_doc = frappe.get_doc("Waitlist Rule", rule)
    process_waitlist(rule_doc)


def run_scheduled_waitlist():
    rules = frappe.get_all(
        "Waitlist Rule",
        filters={"status": "Active", "is_locked": 0},
        fields=["name", "upgrade_frequency"],
    )

    weekday = now_datetime().weekday()  # Monday=0

    for r in rules:
        freq = (r.upgrade_frequency or "Manual")
        if freq == "Daily":
            process_waitlist(frappe.get_doc("Waitlist Rule", r.name))
        elif freq == "Weekly":
            if weekday == 0:
                process_waitlist(frappe.get_doc("Waitlist Rule", r.name))
