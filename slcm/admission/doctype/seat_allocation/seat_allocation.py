import frappe
import math
from frappe.model.document import Document
from frappe.utils import now, get_link_to_form


class SeatAllocation(Document):

    def before_save(self):
        if getattr(frappe.flags, "slcm_waitlist_promotion_in_progress", False):
            return

        # Recalculate counters for accuracy
        self.total_selected = 0
        self.total_waitlisted = 0
        self.total_rejected = 0
        
        rejection_statuses = ["Rejected", "Offer Declined", "Offer Expired"]
        
        for row in (self.selection_applicant or []):
            if row.selection_status in ["Selected", "Offer Accepted"]:
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
                    applicant=row.applicant,
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
                        applicant=row.applicant,
                        program=row.program,
                        old_status=old_status,
                        new_status=new_status,
                        allocation_name=self.name,
                        admission_cycle=self.admission_cycle
                    )

            # Trigger promotion if a Selected/Offer Accepted/Offer Issued applicant moves to any rejected status
            if old_status in ["Selected", "Offer Accepted", "Offer Issued"] and new_status in rejection_statuses:
                affected_programs.add(row.program)

        if not affected_programs:
            return

        # Run promotion post-save (in on_update) so DB reflects the newly rejected seat.
        self.flags.slcm_affected_programs_for_waitlist_promotion = sorted(list(affected_programs))

    def validate_uniqueness(self):
        """
        Ensures only one Seat Allocation exists per Campus, Admission Cycle, and Program Level.
        """
        filters = {
            "campus": self.campus,
            "admission_cycle": self.admission_cycle,
            "program_level": self.program_level,
            "name": ["!=", self.name]
        }
        
        existing = frappe.db.exists("Seat Allocation", filters)
        if existing:
            link = get_link_to_form("Seat Allocation", existing)
            frappe.throw(
                f"A Seat Allocation already exists for Campus '{self.campus}', "
                f"Admission Cycle '{self.admission_cycle}' and Program Level '{self.program_level or 'All'}'. "
                f"<br><br>Existing Allocation: {link}",
                title="Duplicate Seat Allocation"
            )

    def on_update(self):
        if getattr(frappe.flags, "slcm_waitlist_promotion_in_progress", False):
            return

        programs = getattr(self.flags, "slcm_affected_programs_for_waitlist_promotion", None)
        if not programs:
            return

        from slcm.admission.doctype.waitlist_rule.waitlist_promotion import process_waitlist

        # Find the active automatic rule for this campus/cycle
        rule_names = frappe.get_all(
            "Waitlist Rule",
            filters={
                "status": "Active",
                "admission_cycle": self.admission_cycle,
                "campus": self.campus,
                "upgrade_frequency": "Automatic"
            },
            pluck="name",
        )

        for rule_name in rule_names:
            frappe.flags.slcm_waitlist_promotion_in_progress = True
            try:
                # Manual triggers (from on_update) should ignore the cutoff date
                process_waitlist(frappe.get_doc("Waitlist Rule", rule_name), ignore_cutoff=True)
            finally:
                frappe.flags.slcm_waitlist_promotion_in_progress = False

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
            app_id = row.applicant_id or row.applicant
            self.append("selection_applicant", {
                "applicant": row.applicant,
                "applicant_id": row.applicant_id,
                "candidate_name": row.candidate_name,
                "program": row.program,
                "reservation_category": row.reservation_category,
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
                total_selected += 1

            # -----------------------------------
            # PHASE 2: RESERVED SELECTION
            # -----------------------------------
            reserved_quotas = quotas.get("Reserved", {})
            
            # Store waitlist quotas to process later
            category_waitlist_quotas = {}

            for category, category_seats in reserved_quotas.items():
                category_waitlist_quotas[category] = math.ceil(category_seats * waitlist_factor)

                cat_doc = frappe.get_cached_value("Admission Category", category, ["name", "category_code", "category_name"], as_dict=1)
                if not cat_doc:
                    cat_name = frappe.db.get_value("Admission Category", {"category_name": category}, "name") or \
                               frappe.db.get_value("Admission Category", {"category_code": category}, "name")
                    if cat_name:
                        cat_doc = frappe.get_cached_value("Admission Category", cat_name, ["name", "category_code", "category_name"], as_dict=1)

                match_strings = [category]
                if cat_doc:
                    match_strings.extend([cat_doc.name, cat_doc.category_code, cat_doc.category_name])
                
                match_strings = list(set([s for s in match_strings if s]))

                category_pool = [r for r in remaining_pool if (r.reservation_category or "General") in match_strings]

                selected_reserved = category_pool[:category_seats]

                for row in selected_reserved:
                    row.selection_status = "Selected"
                    row.allocation_type = "Reserved"
                    total_selected += 1

                # Only remaining candidates NOT selected move forward
                remaining_pool = [r for r in remaining_pool if r not in selected_reserved]

            # -----------------------------------
            # PHASE 3: WAITLISTS (OPEN THEN RESERVED)
            # -----------------------------------
            
            # 1. Waitlist GEN (from highest merit in remaining pool)
            gen_waitlist_pool = remaining_pool[:gen_waitlist_cap]
            remaining_pool = remaining_pool[gen_waitlist_cap:]

            for row in gen_waitlist_pool:
                row.selection_status = "Waitlisted"
                row.allocation_type = "Open"
                total_waitlisted += 1
                
            # 2. Waitlist Reserved (from category specific pools)
            for category, cat_waitlist_cap in category_waitlist_quotas.items():
                if cat_waitlist_cap == 0:
                    continue
                    
                cat_doc = frappe.get_cached_value("Admission Category", category, ["name", "category_code", "category_name"], as_dict=1)
                if not cat_doc:
                    cat_name = frappe.db.get_value("Admission Category", {"category_name": category}, "name") or \
                               frappe.db.get_value("Admission Category", {"category_code": category}, "name")
                    if cat_name:
                        cat_doc = frappe.get_cached_value("Admission Category", cat_name, ["name", "category_code", "category_name"], as_dict=1)

                match_strings = [category]
                if cat_doc:
                    match_strings.extend([cat_doc.name, cat_doc.category_code, cat_doc.category_name])
                
                match_strings = list(set([s for s in match_strings if s]))

                # Re-fetch category pool from the updated remaining pool
                waitlist_pool = [r for r in remaining_pool if (r.reservation_category or "General") in match_strings]
                waitlist_reserved = waitlist_pool[:cat_waitlist_cap]

                for row in waitlist_reserved:
                    row.selection_status = "Waitlisted"
                    row.allocation_type = "Reserved"
                    total_waitlisted += 1

                # Only candidates NOT waitlisted move to rejections
                remaining_pool = [r for r in remaining_pool if r not in waitlist_reserved]

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
             log_seat_allocation_action(
                seat_allocation=self.name,
                admission_cycle=self.admission_cycle,
                applicant=row.applicant,
                program=row.program,
                action_type="Seat Allocated",
                old_value="Draft",
                new_value=row.selection_status,
                remarks=f"Initial automatic allocation as {row.allocation_type or 'N/A'}"
            )

        self.total_selected = total_selected
        self.total_waitlisted = total_waitlisted
        self.total_rejected = total_rejected
        self.status = "Allocated"
        
        self.save()
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
