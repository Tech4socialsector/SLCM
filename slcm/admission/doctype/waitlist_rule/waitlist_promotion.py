import frappe
from frappe.utils import now_datetime, getdate


def _get_program_quotas(campus: str, admission_cycle: str, program: str) -> dict:
    # 1. Try to find the program row from Admission Cycle for campus-specific linking
    program_row = frappe.db.get_value("Admission Cycle Program", {
        "parent": admission_cycle,
        "campus": campus,
        "program": program
    }, ["name", "seats", "reservation_policy"], as_dict=True)

    result = {"GEN": 0, "Reserved": {}}
    policy_name = None
    fallback_seats = 0

    if program_row:
        policy_name = program_row.reservation_policy
        fallback_seats = int(program_row.seats or 0)
    
    # 2. If no policy found via child table, try direct lookup by cycle and program
    if not policy_name:
        policy_name = frappe.db.get_value("Program Reservation Policy", {
            "admission_cycle": admission_cycle,
            "program": program,
            "status": ["!=", "Locked"] # Fetch any active or draft policy if not locked
        }, "name")

    if not policy_name and not fallback_seats:
        frappe.throw(f"No active Program Reservation Policy or Seats found in cycle '{admission_cycle}' for Campus '{campus}' and Program '{program}'")

    if policy_name:
        # 2. Fetch quotas from Program Reservation Policy
        policy = frappe.get_doc("Program Reservation Policy", policy_name)
        
        for q in (policy.categories or []):
            seats = int(q.seats or 0)
            
            # Map to GEN pool if quota type is General
            if q.reservation_quota == "General":
                result["GEN"] += seats
            else:
                # Use category_name for Reserved mapping
                category = q.category_name
                if not category:
                    result["GEN"] += seats
                    continue
                result["Reserved"][category] = result["Reserved"].get(category, 0) + seats
    else:
        # Fallback to total seats if no policy defined
        result["GEN"] = int(fallback_seats or 0)

    # Safety fallback: if computed seats is 0, fallback to total seats
    if int(result.get("GEN") or 0) + sum(int(v or 0) for v in (result.get("Reserved") or {}).values()) <= 0:
        result["GEN"] = int(fallback_seats or 0)
    
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




def process_waitlist(rule_doc, ignore_cutoff=False):
    if not rule_doc or rule_doc.doctype != "Waitlist Rule":
        frappe.throw("Invalid Waitlist Rule")


    if (rule_doc.status or "").lower() != "active":
        return

    if not ignore_cutoff and rule_doc.upgrade_cutoff_date and getdate(now_datetime()) > getdate(rule_doc.upgrade_cutoff_date):
        return

    seat_alloc = _get_latest_seat_allocation(rule_doc.admission_cycle, rule_doc.campus)
    if not seat_alloc:
        return

    _lock_seat_allocation(seat_alloc.name)

    # Campus-wide rule: Get all programs in this allocation
    programs_to_process = list(set([r.program for r in seat_alloc.selection_applicant if r.program]))

    any_promoted = False
    promoted_applicants = []
    for program in programs_to_process:
        promoted = _process_single_program_waitlist(seat_alloc, program, rule_doc)
        if promoted:
            any_promoted = True
            promoted_applicants.extend(promoted)

    if any_promoted:
        seat_alloc.save(ignore_permissions=True)
        # Commit to ensure OfferService sees the "Selected" status in the database
        frappe.db.commit()

        from slcm.api.service.offer_service import OfferService
        for app_id, prog in promoted_applicants:
            try:
                OfferService.generate_offer(
                    applicant=app_id,
                    campus=seat_alloc.campus,
                    program=prog,
                    cycle=seat_alloc.admission_cycle
                )
            except Exception as e:
                frappe.log_error(f"Auto Offer Generation Failed for {app_id} (Post-Promotion): {str(e)}", "Waitlist Promotion")

    rule_doc.db_set("last_executed_on", now_datetime(), update_modified=False)
    rule_doc.db_set("execution_log_count", int(rule_doc.execution_log_count or 0) + 1, update_modified=False)

    # Commit is now handled by the caller (scheduled job or manual trigger)
    # to avoid breaking transactions when called from Seat Allocation hooks.


def _process_single_program_waitlist(seat_alloc, program: str, rule_doc) -> list:
    """
    Core promotion logic for a single program within a seat allocation.
    Returns a list of (applicant_id, program) tuples for newly promoted candidates.
    """
    quotas = _get_program_quotas(rule_doc.campus, rule_doc.admission_cycle, program)
    
    selected_rows = [
        r for r in seat_alloc.selection_applicant
        if r.program == program and r.selection_status in ["Selected", "Accepted"]
    ]
    
    waitlisted_rows = [
        r for r in seat_alloc.selection_applicant
        if r.program == program and r.selection_status == "Waitlisted"
    ]

    if not waitlisted_rows:
        return False

    from slcm.admission.doctype.admission_audit_log.audit_service import log_seat_allocation_action
    promoted_total = 0
    promoted_list = []

    # 1. Promote for OPEN seats
    open_selected = [r for r in selected_rows if r.allocation_type == "Open"]
    open_vacancies = max(0, quotas["GEN"] - len(open_selected))
    
    if open_vacancies > 0:
        open_waitlist = [r for r in waitlisted_rows if r.allocation_type == "Open"]
        open_waitlist.sort(key=lambda x: (-(x.total_score or 0), x.overall_rank or 999999))
        
        # Log that vacancies were identified
        log_seat_allocation_action(
            seat_allocation=seat_alloc.name,
            admission_cycle=seat_alloc.admission_cycle,
            program=program,
            action_type="Waitlist Vacated",
            remarks=f"Automatic promotion engine ({rule_doc.name}) identified {open_vacancies} vacant OPEN seat(s)."
        )

        for row in open_waitlist[:open_vacancies]:
            row.selection_status = "Selected"
            promoted_total += 1
            promoted_list.append((row.applicant_id, program))
            log_seat_allocation_action(
                seat_allocation=seat_alloc.name,
                admission_cycle=seat_alloc.admission_cycle,
                applicant=row.applicant,
                program=program,
                action_type="Waitlist Promoted",
                old_value="Waitlisted",
                new_value="Selected",
                remarks=f"Automatically promoted to OPEN seat via rule {rule_doc.name}."
            )

            # Send notification for automatic promotion
            from slcm.admission.notification_service import notify_status_change
            notify_status_change(
                applicant=row.applicant,
                program=program,
                old_status="Waitlisted",
                new_status="Selected",
                allocation_name=seat_alloc.name,
                admission_cycle=seat_alloc.admission_cycle
            )

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
            
            # Log that vacancies were identified for this category
            log_seat_allocation_action(
                seat_allocation=seat_alloc.name,
                admission_cycle=seat_alloc.admission_cycle,
                program=program,
                action_type="Waitlist Vacated",
                remarks=f"Automatic promotion engine ({rule_doc.name}) identified {cat_vacancies} vacant RESERVED seat(s) for {cat_name}."
            )

            for row in cat_waitlist[:cat_vacancies]:
                row.selection_status = "Selected"
                promoted_total += 1
                promoted_list.append((row.applicant_id, program))
                log_seat_allocation_action(
                    seat_allocation=seat_alloc.name,
                    admission_cycle=seat_alloc.admission_cycle,
                    applicant=row.applicant,
                    program=program,
                    action_type="Waitlist Promoted",
                    old_value="Waitlisted",
                    new_value="Selected",
                    remarks=f"Automatically promoted to RESERVED ({cat_name}) seat via rule {rule_doc.name}."
                )

                # Send notification for automatic promotion
                from slcm.admission.notification_service import notify_status_change
                notify_status_change(
                    applicant=row.applicant,
                    program=program,
                    old_status="Waitlisted",
                    new_status="Selected",
                    allocation_name=seat_alloc.name,
                    admission_cycle=seat_alloc.admission_cycle
                )

    if promoted_total:
        seat_alloc.total_selected = int(seat_alloc.total_selected or 0) + promoted_total
        seat_alloc.total_waitlisted = max(0, int(seat_alloc.total_waitlisted or 0) - promoted_total)
        return promoted_list

    return []


@frappe.whitelist()
def run_manual_waitlist(rule: str):
    rule_doc = frappe.get_doc("Waitlist Rule", rule)
    process_waitlist(rule_doc, ignore_cutoff=True)
    frappe.db.commit()


def run_scheduled_waitlist():
    """
    Scheduled job: runs waitlist promotion based on the 'Upgrade Frequency' setting.
    - 'Automatic': runs every time the scheduler triggers this method (every 10 min).
    - 'Manual': skipped.
    """
    rules = frappe.get_all(
        "Waitlist Rule",
        filters={"status": "Active", "upgrade_frequency": "Automatic"},
        fields=["name"],
    )

    for r in rules:
        try:
            process_waitlist(frappe.get_doc("Waitlist Rule", r.name))
            frappe.db.commit()
        except Exception as e:
            frappe.db.rollback()
            frappe.log_error(f"Scheduled Waitlist Promotion Failed for {r.name}: {str(e)}", "Waitlist Promotion")
