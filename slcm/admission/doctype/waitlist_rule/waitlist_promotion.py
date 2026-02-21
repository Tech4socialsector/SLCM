import frappe
from frappe.utils import now_datetime, getdate


def _get_program_quotas(campus: str, admission_cycle: str, program: str) -> dict:
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
        fields=["category", "seats"],
    )

    def get_category_id(cat_name):
        return frappe.db.sql("""
            SELECT name FROM `tabAdmission Category`
            WHERE name = %s OR category_code = %s OR category_name = %s
            LIMIT 1
        """, (cat_name, cat_name, cat_name), pluck=True)

    gen_cat_name = get_category_id("GEN")
    if not gen_cat_name:
        gen_cat_name = get_category_id("General")

    result = {"GEN": 0, "Reserved": {}}
    for q in quotas:
        if gen_cat_name and q.category == gen_cat_name[0]:
            result["GEN"] = int(q.seats or 0)
        else:
            result["Reserved"][q.category] = int(q.seats or 0)
    
    return result


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

    # Campus-wide rule: Get all programs in this allocation
    programs_to_process = list(set([r.program for r in seat_alloc.selection_applicant if r.program]))

    any_promoted = False
    for program in programs_to_process:
        if _process_single_program_waitlist(seat_alloc, program, rule_doc):
            any_promoted = True

    if any_promoted:
        seat_alloc.save(ignore_permissions=True)

    rule_doc.db_set("last_executed_on", now_datetime(), update_modified=False)
    rule_doc.db_set("execution_log_count", int(rule_doc.execution_log_count or 0) + 1, update_modified=False)

    frappe.db.commit()


def _process_single_program_waitlist(seat_alloc, program: str, rule_doc) -> bool:
    """
    Core promotion logic for a single program within a seat allocation.
    Returns True if any promotion occurred.
    """
    quotas = _get_program_quotas(rule_doc.campus, rule_doc.admission_cycle, program)
    
    selected_rows = [
        r for r in seat_alloc.selection_applicant
        if r.program == program and r.selection_status == "Selected"
    ]
    
    waitlisted_rows = [
        r for r in seat_alloc.selection_applicant
        if r.program == program and r.selection_status == "Waitlisted"
    ]

    if not waitlisted_rows:
        return False

    promoted_total = 0

    # 1. Promote for OPEN seats
    open_selected = [r for r in selected_rows if r.allocation_type == "Open"]
    open_vacancies = max(0, quotas["GEN"] - len(open_selected))
    
    if open_vacancies > 0:
        open_waitlist = [r for r in waitlisted_rows if r.allocation_type == "Open"]
        open_waitlist.sort(key=lambda x: (-(x.total_score or 0), x.overall_rank or 999999))
        
        for row in open_waitlist[:open_vacancies]:
            row.selection_status = "Selected"
            promoted_total += 1

    # 2. Promote for RESERVED seats
    for cat_name, cat_quota in quotas["Reserved"].items():
        # Handle matching by name/code/cat_name for categories
        cat_doc = frappe.get_cached_value("Admission Category", cat_name, ["name", "category_code", "category_name"], as_dict=1)
        match_strings = [cat_name]
        if cat_doc:
            if cat_doc.get("category_code"): match_strings.append(cat_doc.get("category_code"))
            if cat_doc.get("category_name"): match_strings.append(cat_doc.get("category_name"))

        cat_selected = [r for r in selected_rows if r.allocation_type == "Reserved" and r.reservation_category in match_strings]
        cat_vacancies = max(0, cat_quota - len(cat_selected))

        if cat_vacancies > 0:
            cat_waitlist = [r for r in waitlisted_rows if r.allocation_type == "Reserved" and r.reservation_category in match_strings and r.selection_status == "Waitlisted"]
            cat_waitlist.sort(key=lambda x: (-(x.total_score or 0), x.overall_rank or 999999))
            
            for row in cat_waitlist[:cat_vacancies]:
                row.selection_status = "Selected"
                promoted_total += 1

    if promoted_total:
        seat_alloc.total_selected = int(seat_alloc.total_selected or 0) + promoted_total
        seat_alloc.total_waitlisted = max(0, int(seat_alloc.total_waitlisted or 0) - promoted_total)
        return True

    return False


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
