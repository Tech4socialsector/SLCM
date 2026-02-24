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

        from slcm.admission.audit_service import log_seat_allocation_action
        affected_programs = set()
        for row in (self.selection_applicant or []):
            old_status = before_map.get(row.name)
            new_status = row.selection_status
            
            if old_status and old_status != new_status:
                log_seat_allocation_action(
                    reference_doctype="Seat Allocation",
                    reference_name=self.name,
                    applicant=row.applicant,
                    program=row.program,
                    action_type="Manual Status Change",
                    old_value=old_status,
                    new_value=new_status,
                    remarks="Status was manually updated in the Seat Allocation form."
                )

                # Send notification for manual status change only if published
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
                except Exception:
                    ar = None

                if ar and ar.get("email"):
                    applicant_identifier = frappe.db.get_value("Applicant", {"email": ar.get("email")}, "name")
                if not applicant_identifier and ar and ar.get("applicant_name"):
                    applicant_identifier = frappe.db.get_value(
                        "Applicant",
                        {"candidate_name": ar.get("applicant_name")},
                        "name",
                    )
                if not applicant_identifier and ar and ar.get("applicant_name") and frappe.db.exists(
                    "Applicant", ar.get("applicant_name")
                ):
                    applicant_identifier = ar.get("applicant_name")
                if not applicant_identifier:
                    from slcm.admission.doctype.waitlist_rule.waitlist_promotion import (
                        _resolve_applicant_from_admission_result,
                    )
                    applicant_identifier = _resolve_applicant_from_admission_result(row.applicant)

                if applicant_identifier:
                    try:
                        from slcm.api.service.offer_service import OfferService
                        OfferService.update_applicant_status(applicant_identifier, application_status=new_status)
                    except Exception:
                        # Don't block seat allocation save if Applicant sync fails.
                        frappe.log_error(
                            frappe.get_traceback(),
                            "Seat Allocation: Failed to sync Applicant status"
                        )

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

            # Trigger promotion if a Selected/Accepted applicant moves to any rejected status
            if old_status in ["Selected", "Accepted"] and new_status in rejection_statuses:
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

        # Only auto-trigger for Daily / Weekly rules.
        # Rules with upgrade_frequency = "Manual" must be triggered explicitly
        # by the admin via the "Run Promotion" button — never automatically.
        rule_names = frappe.get_all(
            "Waitlist Rule",
            filters={
                "status": "Active",
                "admission_cycle": self.admission_cycle,
                "campus": self.campus,
                "upgrade_frequency": ["!=", "Manual"],
            },
            pluck="name",
        )

        for rule_name in rule_names:
            frappe.flags.slcm_waitlist_promotion_in_progress = True
            try:
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

        # Robust lookup for admission_year
        admission_year_name = frappe.db.get_value("Admission Cycle", self.admission_cycle, "admission_year")
        
        if not admission_year_name:
            # Fallback to parent in case of legacy or custom schema sync issue
            admission_year_name = frappe.db.get_value("Admission Cycle", self.admission_cycle, "parent")
             
        if not admission_year_name:
            frappe.throw(f"No Admission Year found for Admission Cycle {self.admission_cycle}. Please ensure the cycle is correctly linked to an Admission Year.")

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
                # Use explicit None check — `or 50.0` would incorrectly treat 0% as falsy
                # and fall back to 50%, ignoring the admin's intent to have no waitlist.
                wp = rules[0].waitlist_percentage
                waitlist_percent = wp if wp is not None else 50.0

            
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

                # Only remaining candidates NOT selected move forward
                remaining_pool = [r for r in remaining_pool if r not in selected_reserved]

            # -----------------------------------
            # PHASE 3: WAITLISTS (OPEN THEN RESERVED)
            # -----------------------------------

            # Pre-compute ALL reserved category identifiers so GEN waitlist
            # never accidentally absorbs reserved-category applicants.
            all_reserved_match_strings = set()
            for _cat in category_waitlist_quotas.keys():
                all_reserved_match_strings.add(_cat)
                _cat_doc = frappe.get_cached_value(
                    "Admission Category", _cat,
                    ["category_code", "category_name"], as_dict=1
                )
                if _cat_doc:
                    if _cat_doc.get("category_code"):
                        all_reserved_match_strings.add(_cat_doc.get("category_code"))
                    if _cat_doc.get("category_name"):
                        all_reserved_match_strings.add(_cat_doc.get("category_name"))

            # 1. Waitlist GEN — only from applicants NOT in any reserved category
            #    This ensures reserved-category applicants are never consumed here
            #    and remain available for their own reserved waitlist slots.
            gen_waitlist_candidates = [
                r for r in remaining_pool
                if not r.reservation_category or r.reservation_category not in all_reserved_match_strings
            ]
            gen_waitlist_pool = gen_waitlist_candidates[:gen_waitlist_cap]

            for row in gen_waitlist_pool:
                row.selection_status = "Waitlisted"
                row.allocation_type = "Open"
                total_waitlisted += 1

            # Remove GEN-waitlisted applicants from remaining pool
            remaining_pool = [r for r in remaining_pool if r not in gen_waitlist_pool]

            # 2. Waitlist Reserved — only from applicants in that specific category
            for category, cat_waitlist_cap in category_waitlist_quotas.items():
                if cat_waitlist_cap == 0:
                    continue

                cat_doc = frappe.get_cached_value(
                    "Admission Category", category,
                    ["name", "category_code", "category_name"], as_dict=1
                )
                match_strings = [category]
                if cat_doc:
                    if cat_doc.get("category_code"): match_strings.append(cat_doc.get("category_code"))
                    if cat_doc.get("category_name"): match_strings.append(cat_doc.get("category_name"))

                # Only look at remaining applicants in this exact category
                waitlist_pool = [r for r in remaining_pool if r.reservation_category in match_strings]
                waitlist_reserved = waitlist_pool[:cat_waitlist_cap]

                for row in waitlist_reserved:
                    row.selection_status = "Waitlisted"
                    row.allocation_type = "Reserved"
                    total_waitlisted += 1

                # Remove reserved-waitlisted from remaining pool
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
        from slcm.admission.audit_service import log_seat_allocation_action
        for row in self.selection_applicant:
             log_seat_allocation_action(
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

        from slcm.admission.audit_service import log_seat_allocation_action
        log_seat_allocation_action(
            reference_doctype="Seat Allocation",
            reference_name=self.name,
            action_type="Allocation Published",
            remarks=f"Allocation finalized and published by {frappe.session.user}"
        )

        frappe.db.commit()

        # Trigger bulk notifications
        from slcm.admission.notification_service import notify_published_allocation
        notify_published_allocation(self.name)

        frappe.msgprint("Allocation Published and notifications queued.")
