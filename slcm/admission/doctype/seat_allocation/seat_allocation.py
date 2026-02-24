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
            if row.selection_status in ["Selected", "Accepted"]:
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

        from slcm.admission.doctype.admission_audit_log.audit_service import log_admission_action
        affected_programs = set()
        for row in (self.selection_applicant or []):
            old_status = before_map.get(row.name)
            new_status = row.selection_status

            if old_status and old_status != new_status:
                log_admission_action(
                    reference_doctype="Seat Allocation",
                    reference_name=self.name,
                    applicant=row.applicant,
                    program=row.program,
                    action_type="Manual Status Change",
                    old_value=old_status,
                    new_value=new_status,
                    remarks="Status was manually updated in the Seat Allocation form."
                )

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

            if old_status in ["Selected", "Accepted"] and new_status in rejection_statuses:
                affected_programs.add(row.program)

        if not affected_programs:
            return

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

        # ✅ Enqueue into background — never modify same document inside on_update.
        # This prevents nested saves and version conflicts on multi-worker hosted environments.
        frappe.enqueue(
            "slcm.admission.doctype.waitlist_rule.waitlist_promotion.process_waitlist_background",
            seat_allocation_name=self.name,
            campus=self.campus,
            admission_cycle=self.admission_cycle,
            queue="long",
            now=False,
            is_async=True,
            enqueue_after_commit=True
        )

    @frappe.whitelist()
    def pull_from_merit_list(self):
        """
        Copies all applicants from the linked Merit List into the
        Selection Applicant child table, preserving ranking data.
        """
        # 1. Reload hits the DB for the latest 'modified' timestamp.
        # This wins over background jobs that might have bumped the version.
        self.reload()

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

        # Clear existing rows and repopulate
        self.selection_applicant = []

        for row in merit.merit_applicants:
            self.append("selection_applicant", {
                "applicant": row.applicant,
                "applicant_id": row.applicant_id,
                "program": row.program,
                "reservation_category": row.reservation_category,
                "total_score": row.total_score,
                "category_rank": row.category_rank,
                "overall_rank": row.overall_rank,
                "selection_status": "Draft"
            })

        # 2. Persist immediately on server. 
        # ignore_version ensures we bypass any collision with the browser's stale timestamp.
        self.flags.ignore_version = True
        self.save(ignore_permissions=True)
        
        frappe.msgprint("Applicants pulled successfully.")

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

        if not frappe.db.exists("Waitlist Rule", {
            "campus": self.campus,
            "admission_cycle": self.admission_cycle,
            "status": "Active"
        }):
            frappe.throw(
                f"No active Waitlist Rule found for Campus '{self.campus}' and "
                f"Admission Cycle '{self.admission_cycle}'. "
                "Please create an active Waitlist Rule before running allocation.",
                title="Missing Waitlist Rule"
            )

        # ✅ Sync with DB version before heavy processing
        self.reload()

        # Pull applicants if table is empty (inline — no internal save)
        if not self.selection_applicant:
            self._pull_applicants_in_memory()

        admission_year_name = frappe.db.get_value("Admission Cycle", self.admission_cycle, "admission_year")
        if not admission_year_name:
            # Fallback for legacy data if any
            res = frappe.db.sql("""
                SELECT parent FROM `tabAdmission Cycle`
                WHERE name = %s AND parenttype = 'Admission Year'
                LIMIT 1
            """, (self.admission_cycle,))
            if res:
                admission_year_name = res[0][0]

        if not admission_year_name:
            frappe.throw(f"No Admission Year linked to cycle {self.admission_cycle}. Please update the Admission Cycle record.")

        from slcm.admission.doctype.waitlist_rule.waitlist_promotion import _get_program_quotas

        total_selected = 0
        total_waitlisted = 0
        total_rejected = 0

        # -------------------------
        # 2️⃣ GROUP BY PROGRAM
        # -------------------------
        grouped_by_program = {}
        for row in self.selection_applicant:
            grouped_by_program.setdefault(row.program, []).append(row)

        # Get waitlist percentage once
        waitlist_percent = 50.0
        rules = frappe.get_all(
            "Waitlist Rule",
            filters={"campus": self.campus, "admission_cycle": self.admission_cycle, "status": "Active"},
            fields=["waitlist_percentage"]
        )
        if rules:
            waitlist_percent = rules[0].waitlist_percentage or 50.0
        waitlist_factor = waitlist_percent / 100.0

        for program, applicants in grouped_by_program.items():
            quotas = _get_program_quotas(self.campus, self.admission_cycle, program)
            applicants.sort(key=lambda x: (-(x.total_score or 0), x.overall_rank or 999999))

            # PHASE 1: OPEN
            gen_seats = quotas.get("GEN", 0)
            gen_waitlist_cap = math.ceil(gen_seats * waitlist_factor)
            selected_open = applicants[:gen_seats]
            remaining_pool = applicants[gen_seats:]

            for row in selected_open:
                row.selection_status = "Selected"
                row.allocation_type = "Open"
                total_selected += 1

            # PHASE 2: RESERVED
            reserved_quotas = quotas.get("Reserved", {})
            category_waitlist_quotas = {}

            for category, category_seats in reserved_quotas.items():
                category_waitlist_quotas[category] = math.ceil(category_seats * waitlist_factor)
                cat_doc = frappe.get_cached_value("Admission Category", category, ["name", "category_code", "category_name"], as_dict=1)
                match_strings = [category]
                if cat_doc:
                    if cat_doc.get("category_code"): match_strings.append(cat_doc.get("category_code"))
                    if cat_doc.get("category_name"): match_strings.append(cat_doc.get("category_name"))

                category_pool = [r for r in remaining_pool if r.reservation_category in match_strings]
                selected_reserved = category_pool[:category_seats]
                for row in selected_reserved:
                    row.selection_status = "Selected"
                    row.allocation_type = "Reserved"
                    total_selected += 1
                remaining_pool = [r for r in remaining_pool if r not in selected_reserved]

            # PHASE 3: WAITLISTS
            gen_waitlist_pool = remaining_pool[:gen_waitlist_cap]
            remaining_pool = remaining_pool[gen_waitlist_cap:]
            for row in gen_waitlist_pool:
                row.selection_status = "Waitlisted"
                row.allocation_type = "Open"
                total_waitlisted += 1

            for category, cat_waitlist_cap in category_waitlist_quotas.items():
                if cat_waitlist_cap == 0: continue
                cat_doc = frappe.get_cached_value("Admission Category", category, ["name", "category_code", "category_name"], as_dict=1)
                match_strings = [category]
                if cat_doc:
                    if cat_doc.get("category_code"): match_strings.append(cat_doc.get("category_code"))
                    if cat_doc.get("category_name"): match_strings.append(cat_doc.get("category_name"))

                waitlist_pool = [r for r in remaining_pool if r.reservation_category in match_strings]
                waitlist_reserved = waitlist_pool[:cat_waitlist_cap]
                for row in waitlist_reserved:
                    row.selection_status = "Waitlisted"
                    row.allocation_type = "Reserved"
                    total_waitlisted += 1
                remaining_pool = [r for r in remaining_pool if r not in waitlist_reserved]

            # PHASE 4: REJECT
            for row in remaining_pool:
                row.selection_status = "Rejected"
                row.allocation_type = ""
                total_rejected += 1

        # -------------------------
        # 3️⃣ SAVE
        # -------------------------
        from slcm.admission.doctype.admission_audit_log.audit_service import log_admission_action
        for row in self.selection_applicant:
            log_admission_action(
                reference_doctype="Seat Allocation",
                reference_name=self.name,
                applicant=row.applicant,
                program=row.program,
                action_type="Outcome Assigned",
                old_value="Draft",
                new_value=row.selection_status,
                remarks=f"Automatic allocation as {row.allocation_type or 'N/A'}"
            )

        self.total_selected = total_selected
        self.total_waitlisted = total_waitlisted
        self.total_rejected = total_rejected
        self.status = "Allocated"

        # Sync save to prevent data loss
        self.flags.ignore_version = True
        self.save(ignore_permissions=True)

        frappe.msgprint("Seat Allocation phase completed successfully.")

    def _pull_applicants_in_memory(self):
        if not self.merit_list: return
        merit = frappe.get_doc("Merit List", self.merit_list)
        self.selection_applicant = []
        for row in merit.merit_applicants:
            self.append("selection_applicant", {
                "applicant": row.applicant,
                "applicant_id": row.applicant_id,
                "program": row.program,
                "reservation_category": row.reservation_category,
                "total_score": row.total_score,
                "category_rank": row.category_rank,
                "overall_rank": row.overall_rank,
                "selection_status": "Draft"
            })

    @frappe.whitelist()
    def publish_allocation(self):
        self.reload()

        if self.status != "Allocated":
            frappe.throw("Run allocation first.")

        self.status = "Published"
        self.published_on = now()
        self.published_by = frappe.session.user

        self.flags.ignore_version = True
        self.save(ignore_permissions=True)

        from slcm.admission.doctype.admission_audit_log.audit_service import log_admission_action
        log_admission_action(
            reference_doctype="Seat Allocation",
            reference_name=self.name,
            action_type="Allocation Published",
            remarks=f"Allocation finalized and published by {frappe.session.user}"
        )

        frappe.enqueue(
            "slcm.admission.notification_service.notify_published_allocation",
            allocation_name=self.name,
            queue="long",
            now=False,
            is_async=True,
            enqueue_after_commit=True
        )

        frappe.msgprint("Allocation Published.")
