import frappe
import math
from frappe.model.document import Document
from frappe.utils import now, get_link_to_form, get_datetime, now_datetime

def get_applicant_categories(applicant_id):
    """
    Fetches all categories mapped to the applicant.
    Checks Eligibility Result first, then falls back to the base Applicant record.
    """
    if not applicant_id:
        return []

    # 1. Try from Eligibility Result (primary source of truth for processed apps)
    eligibility = frappe.db.get_value(
        "Eligibility Result",
        {"applicant_id": applicant_id},
        "name"
    )

    categories = []
    if eligibility:
        categories = frappe.db.get_all(
            "Applicant Category",
            filters={"parent": eligibility, "parenttype": "Eligibility Result"},
            pluck="category",
            ignore_permissions=True
        )

    # 2. Try from Applicant (initial source from web form)
    if not categories:
        categories = frappe.db.get_all(
            "Applicant Category",
            filters={"parent": applicant_id, "parenttype": "Applicant"},
            pluck="category",
            ignore_permissions=True
        )

    return list(set(categories))

def get_category_priority(admission_cycle, campus, program):
    program_row = frappe.db.get_value("Admission Cycle Program", {
        "parent": admission_cycle,
        "campus": campus,
        "program": program
    }, ["name", "reservation_policy"], as_dict=True)

    policy_name = None
    if program_row:
        policy_name = program_row.reservation_policy

    if not policy_name:
        policy_name = frappe.db.get_value("Program Reservation Policy", {
            "admission_cycle": admission_cycle,
            "program": program,
            "status": ["!=", "Locked"]
        }, "name")

    priority_map = {}
    if policy_name:
        policy = frappe.get_doc("Program Reservation Policy", policy_name)
        for row in policy.categories:
            priority_map[row.category_name] = int(row.priority or 999)

    return priority_map

class SeatAllocation(Document):
    def validate(self):
        if self.published_on and get_datetime(self.published_on) > get_datetime(now_datetime()):
            frappe.throw("Published On date cannot be in the future.")

    def autoname(self):
        from frappe.model.naming import make_autoname
        if not self.admission_cycle or not self.campus:
            frappe.throw("Admission Cycle and Campus are required for naming.")

        # Use codes instead of names to keep it short
        cycle_code = frappe.db.get_value("Admission Cycle", self.admission_cycle, "cycle_code") or self.admission_cycle
        campus_code = frappe.db.get_value("Campus", self.campus, "campus_code") or self.campus
        
        cycle = cycle_code.replace(" ", "").upper()
        campus = campus_code.replace(" ", "").upper()
        level = (self.program_level or "ALL").replace(" ", "").upper()

        self.name = make_autoname(f"SA-{cycle}-{campus}-{level}-.#####")

    def before_save(self):
        if getattr(frappe.flags, "slcm_waitlist_promotion_in_progress", False):
            return

        # Recalculate counters for accuracy
        self.total_selected = 0
        self.total_waitlisted = 0
        self.total_rejected = 0
        
        rejection_statuses = ["Rejected", "Offer Declined", "Offer Expired", "Withdrawn"]
        selection_statuses = ["Selected", "Offer Issued", "Offer Accepted", "Accepted", "Fee Paid"]
        
        for row in (self.selection_applicant or []):
            if row.selection_status in selection_statuses:
                self.total_selected += 1
            elif row.selection_status == "Waitlisted":
                self.total_waitlisted += 1
            elif row.selection_status in rejection_statuses:
                self.total_rejected += 1

        # Always enforce ascending sort by overall rank before saving
        if self.selection_applicant:
            from frappe.utils import flt
            self.selection_applicant.sort(key=lambda x: flt(x.overall_rank or 999999))
            for i, row in enumerate(self.selection_applicant):
                row.idx = i + 1

        self.validate_uniqueness()

        before = None
        try:
            before = self.get_doc_before_save()
        except Exception:
            before = None

        if not before:
            return

        before_map = {}
        for row in (before.selection_applicant or []):
            before_map[row.name] = row.selection_status

        from slcm.admission.doctype.admission_audit_log.audit_service import log_seat_allocation_action
        affected_programs = set()
        for row in (self.selection_applicant or []):
            old_status = before_map.get(row.name)
            new_status = row.selection_status
            
            if old_status and old_status != new_status:
                log_seat_allocation_action(
                    seat_allocation=self.name,
                    admission_cycle=self.admission_cycle,
                    applicant=row.applicant_id,
                    program=row.program,
                    action_type="Manual Status Change",
                    old_value=old_status,
                    new_value=new_status,
                    remarks="Status was manually updated in the Seat Allocation form."
                )

                # Sync status to Applicant
                if row.applicant_id:
                    from slcm.api.service.offer_service import OfferService
                    OfferService.update_applicant_status(row.applicant_id, application_status=new_status)

                # Send notification for manual status change
                if self.status == "Published":
                    from slcm.admission.notification_service import notify_status_change
                    notify_status_change(
                        applicant=row.applicant_id,
                        program=row.program,
                        old_status=old_status,
                        new_status=new_status,
                        allocation_name=self.name,
                        admission_cycle=self.admission_cycle
                    )

            # Trigger promotion if a seat-occupying applicant moves to any released status
            if old_status in selection_statuses and new_status in rejection_statuses:
                affected_programs.add(row.program)

        if not affected_programs:
            return

        # Run promotion post-save (in on_update) so DB reflects the newly rejected seat.
        self.flags.slcm_affected_programs_for_waitlist_promotion = sorted(list(affected_programs))

    def validate_uniqueness(self):
        """
        Ensures only one PUBLISHED Seat Allocation exists per Campus, Admission Cycle, and Program Level.
        """
        if self.status != "Published":
            return

        filters = {
            "campus": self.campus,
            "admission_cycle": self.admission_cycle,
            "program_level": self.program_level,
            "status": "Published",
            "name": ["!=", self.name]
        }
        
        existing = frappe.db.exists("Seat Allocation", filters)
        if existing:
            link = get_link_to_form("Seat Allocation", existing)
            frappe.throw(
                f"A Seat Allocation is already PUBLISHED for Campus '{self.campus}', "
                f"Admission Cycle '{self.admission_cycle}' and Program Level '{self.program_level or 'All'}'. "
                f"Unpublish it first if you need to publish this one. "
                f"<br><br>Existing Published Allocation: {link}",
                title="Duplicate Published Allocation"
            )

    def on_update(self):
        self.sync_filled_seats()

        if getattr(frappe.flags, "slcm_waitlist_promotion_in_progress", False):
            return

        programs = getattr(self.flags, "slcm_affected_programs_for_waitlist_promotion", None)
        if not programs:
            return

        # Background the promotion to prevent UI lag
        frappe.enqueue(
            "slcm.admission.doctype.waitlist_rule.waitlist_promotion.process_waitlist_background",
            admission_cycle=self.admission_cycle,
            campus=self.campus,
            now=frappe.flags.in_test,
            enqueue_after_commit=True
        )

    def on_trash(self):
        """
        When a Seat Allocation is deleted, reset the filled counts in the linked PRP.
        """
        self.sync_filled_seats(reset_only=True)

    def sync_filled_seats(self, reset_only=False):
        """
        Updates the linked Program Reservation Policy for each program in this allocation
        to reflect Filled and Available seats.
        """
        # 1. Identify programs in this allocation
        affected_programs = set()
        grouped_by_program = {}
        for row in self.selection_applicant:
            if row.program:
                affected_programs.add(row.program)
                if not reset_only:
                    grouped_by_program.setdefault(row.program, []).append(row)

        if not affected_programs:
            return

        # 2. Map programs to their specific policies
        policies = frappe.get_all("Program Reservation Policy", filters={
            "admission_cycle": self.admission_cycle,
            "program": ["in", list(affected_programs)],
            "docstatus": ["!=", 2]
        }, fields=["name", "program"])

        policy_map = {p.program: p.name for p in policies}
        
        filled_statuses = ["Selected", "Offer Issued", "Offer Accepted", "Fee Paid", "Accepted"]

        # 3. Process each policy found for this campus/cycle
        for prog, policy_name in policy_map.items():
            policy = frappe.get_doc("Program Reservation Policy", policy_name)
            
            # Reset counts
            for p_row in policy.categories:
                p_row.filled_seats = 0
            
            # Tally
            if not reset_only and prog in grouped_by_program:
                applicants = grouped_by_program[prog]
                for app in applicants:
                    if app.selection_status in filled_statuses:
                        category_found = False
                        
                        if app.allocation_type == "Open":
                            for p_row in policy.categories:
                                if p_row.reservation_quota == "General" or not p_row.category_name:
                                    p_row.filled_seats = int(p_row.filled_seats or 0) + 1
                                    category_found = True
                                    break
                        else:
                            for p_row in policy.categories:
                                if p_row.category_name == app.allocated_category:
                                    p_row.filled_seats = int(p_row.filled_seats or 0) + 1
                                    category_found = True
                                    break
                        
                        if not category_found:
                             for p_row in policy.categories:
                                if p_row.reservation_quota == "General":
                                    p_row.filled_seats = int(p_row.filled_seats or 0) + 1
                                    break

            # 4. Finalize totals
            policy.total_filled = sum(int(pr.filled_seats or 0) for pr in policy.categories)
            for p_row in policy.categories:
                p_row.available_seats = max(0, int(p_row.seats or 0) - int(p_row.filled_seats or 0))
            
            policy.total_available = max(0, int(policy.total_allocated or 0) - policy.total_filled)
            policy.save(ignore_permissions=True)

    @frappe.whitelist()
    def pull_from_merit_list(self):
        """
        Copies all applicants from the linked Merit List into the
        Selection Applicant child table, preserving ranking data.
        """
        if not self.merit_list:
            frappe.throw(
                "Please select a Merit List before pulling data.",
                title="Missing Merit List"
            )

        merit = frappe.get_doc("Merit List", self.merit_list)

        if not merit.merit_applicants:
            frappe.throw(
                f"The Merit List '{self.merit_list}' has no applicants.",
                title="Empty Merit List"
            )

        # Clear existing rows
        self.selection_applicant = []

        for row in merit.merit_applicants:
            self.append("selection_applicant", {
                "applicant_id": row.applicant_id,
                "candidate_name": row.candidate_name,
                "program": row.program,
                "total_score": row.total_score,
                "overall_rank": row.overall_rank,
                "selection_status": "Draft"
            })

        self.save()
        frappe.db.commit()

    @frappe.whitelist()
    def allocate_seats(self):
        # -------------------------
        # 1️⃣ VALIDATIONS
        # -------------------------
        if not self.admission_cycle:
            frappe.throw("Admission Cycle is required.")
        if not self.campus:
            frappe.throw("Campus is required.")
        if not self.merit_list:
            frappe.throw("Merit List is required.")
        if self.status == "Published":
            frappe.throw("Cannot re-run allocation after publish.")

        # Check for active Waitlist Rule
        if not frappe.db.exists("Waitlist Rule", {
            "campus": self.campus,
            "admission_cycle": self.admission_cycle,
            "status": "Active"
        }):
            frappe.throw(
                f"No active Waitlist Rule found for Campus '{self.campus}' and Admission Cycle '{self.admission_cycle}'. "
                "Please create an active Waitlist Rule before running allocation.",
                title="Missing Waitlist Rule"
            )

        # Pull if empty
        if not self.selection_applicant:
            self.pull_from_merit_list()


        from slcm.admission.doctype.waitlist_rule.waitlist_promotion import _get_program_quotas

        total_selected = 0
        total_waitlisted = 0
        total_rejected = 0

        # -------------------------
        # 2️⃣ GROUP BY PROGRAM ONLY
        # -------------------------
        grouped_by_program = {}
        for row in self.selection_applicant:
            grouped_by_program.setdefault(row.program, []).append(row)

        for program, applicants in grouped_by_program.items():

            quotas = _get_program_quotas(self.campus, self.admission_cycle, program)

            # -----------------------------------
            # Sort by merit
            # -----------------------------------
            applicants.sort(
                key=lambda x: (-(x.total_score or 0), x.overall_rank or 999999)
            )

            # -----------------------------------
            # PHASE 1: OPEN (GEN) SELECTION
            # -----------------------------------
            gen_seats = quotas.get("GEN", 0)

            # Get waitlist percentage from active Waitlist Rule (campus wide)
            waitlist_percent = 50.0
            rules = frappe.get_all("Waitlist Rule", filters={"campus": self.campus, "admission_cycle": self.admission_cycle, "status": "Active"}, fields=["waitlist_percentage"])
            if rules:
                val = rules[0].waitlist_percentage
                waitlist_percent = val if val is not None else 50.0
            
            waitlist_factor = waitlist_percent / 100.0
            gen_waitlist_cap = math.ceil(gen_seats * waitlist_factor)

            selected_open = applicants[:gen_seats]
            remaining_pool = applicants[gen_seats:]

            for row in selected_open:
                row.selection_status = "Selected"
                row.allocation_type = "Open"
                row.allocated_category = "General"
                total_selected += 1

            # -----------------------------------
            # PHASE 2: RESERVED SELECTION
            # -----------------------------------
            reserved_quotas = quotas.get("Reserved", {})
            priority_map = get_category_priority(self.admission_cycle, self.campus, program)
            
            # Store waitlist quotas to process later
            category_waitlist_quotas = {}
            for category, category_seats in reserved_quotas.items():
                category_waitlist_quotas[category] = math.ceil(category_seats * waitlist_factor)

            # Allocate reserved seats
            for applicant in remaining_pool[:]:
                applicant_categories = get_applicant_categories(applicant.applicant_id)
                
                # Filter categories that have quotas
                valid_categories = [c for c in applicant_categories if c in reserved_quotas]

                # Sort by category priority (lowest number = highest priority)
                valid_categories = sorted(
                    valid_categories,
                    key=lambda c: priority_map.get(c, 999)
                )

                for category in valid_categories:
                    if reserved_quotas[category] > 0:
                        applicant.selection_status = "Selected"
                        applicant.allocation_type = "Reserved"
                        applicant.allocated_category = category
                        
                        reserved_quotas[category] -= 1
                        total_selected += 1
                        
                        remaining_pool.remove(applicant)
                        break

            # -----------------------------------
            # PHASE 3: WAITLISTS (OPEN THEN RESERVED)
            # -----------------------------------
            
            # 1. Waitlist GEN (from highest merit in remaining pool)
            gen_waitlist_pool = remaining_pool[:gen_waitlist_cap]
            remaining_pool = remaining_pool[gen_waitlist_cap:]

            for row in gen_waitlist_pool:
                row.selection_status = "Waitlisted"
                row.allocation_type = "Open"
                row.allocated_category = "General"
                total_waitlisted += 1
                
            # 2. Waitlist Reserved (from category specific pools)
            for applicant in remaining_pool[:]:
                applicant_categories = get_applicant_categories(applicant.applicant_id)

                valid_categories = [c for c in applicant_categories if c in category_waitlist_quotas]

                valid_categories = sorted(
                    valid_categories,
                    key=lambda c: priority_map.get(c, 999)
                )

                for category in valid_categories:
                    if category_waitlist_quotas[category] > 0:
                        applicant.selection_status = "Waitlisted"
                        applicant.allocation_type = "Reserved"
                        applicant.allocated_category = category
                        
                        category_waitlist_quotas[category] -= 1
                        total_waitlisted += 1
                        
                        remaining_pool.remove(applicant)
                        break

            # -----------------------------------
            # PHASE 4: REJECT REMAINING
            # -----------------------------------
            for row in remaining_pool:
                row.selection_status = "Rejected"
                row.allocation_type = ""
                total_rejected += 1

        # -------------------------
        # 5️⃣ LOGGING & COMMIT
        # -------------------------
        from slcm.admission.doctype.admission_audit_log.audit_service import log_seat_allocation_action
        for row in self.selection_applicant:
             category_used_str = f" Category Used: {row.allocated_category}" if row.allocated_category else ""
             log_seat_allocation_action(
                seat_allocation=self.name,
                admission_cycle=self.admission_cycle,
                applicant=row.applicant_id,
                program=row.program,
                action_type="Seat Allocated",
                old_value="Draft",
                new_value=row.selection_status,
                remarks=f"Initial automatic allocation as {row.allocation_type or 'N/A'}.{category_used_str}"
            )

        self.total_selected = total_selected
        self.total_waitlisted = total_waitlisted
        self.total_rejected = total_rejected
        self.status = "Allocated"
        
        self.save()
        self.sync_filled_seats()
        frappe.db.commit()

        frappe.msgprint("Seat Allocation phase completed successfully.")

    @frappe.whitelist()
    def publish_allocation(self):
        if self.status != "Allocated":
            frappe.throw("Run allocation first.")
 
        self.status = "Published"
        self.published_on = now()
        self.published_by = frappe.session.user
        self.save()

        from slcm.admission.doctype.admission_audit_log.audit_service import log_seat_allocation_action
        log_seat_allocation_action(
            seat_allocation=self.name,
            admission_cycle=self.admission_cycle,
            action_type="Allocation Published",
            remarks=f"Allocation finalized and published by {frappe.session.user}"
        )

        frappe.db.commit()

        # Trigger bulk notifications
        from slcm.admission.notification_service import notify_published_allocation
        notify_published_allocation(self.name)

        frappe.msgprint("Allocation Published and notifications queued.")

    @frappe.whitelist()
    def unpublish_allocation(self):
        """
        Reverts the Seat Allocation status to 'Allocated', hiding results from students.
        Also reverts the Application Status of all applicants in the list to 'Merit Published'.
        """
        if self.status != "Published":
            frappe.throw("Seat Allocation is not currently published.")

        self.status = "Allocated"
        self.published_on = None
        self.published_by = None
        self.save()

        # Revert Applicant status
        selection_statuses = ["Selected", "Waitlisted", "Rejected", "Offer Issued", "Offer Accepted", "Accepted", "Fee Paid"]
        for row in self.selection_applicant:
            if row.applicant_id:
                current_status = frappe.db.get_value("Applicant", row.applicant_id, "application_status")
                if current_status in selection_statuses:
                    from slcm.api.service.offer_service import OfferService
                    OfferService.update_applicant_status(row.applicant_id, application_status="Merit Published")

        # Audit log
        from slcm.admission.doctype.admission_audit_log.audit_service import log_seat_allocation_action
        log_seat_allocation_action(
            seat_allocation=self.name,
            admission_cycle=self.admission_cycle,
            action_type="Unpublished",
            remarks=f"Seat Allocation {self.name} unpublished by {frappe.session.user}. It is now hidden from applicants."
        )

        frappe.db.commit()
        return {"status": "Allocated"}
