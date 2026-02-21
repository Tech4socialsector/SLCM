import frappe
import math
from frappe.model.document import Document
from frappe.utils import now


class SeatAllocation(Document):

    def before_save(self):
        if getattr(frappe.flags, "slcm_waitlist_promotion_in_progress", False):
            return

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

        affected_programs = set()
        for row in (self.selection_applicant or []):
            old_status = before_map.get(row.name)
            new_status = row.selection_status
            if old_status == "Selected" and new_status == "Rejected":
                affected_programs.add(row.program)

                if self.total_selected is not None:
                    self.total_selected = max(0, int(self.total_selected or 0) - 1)
                if self.total_rejected is not None:
                    self.total_rejected = int(self.total_rejected or 0) + 1

        if not affected_programs:
            return

        # Run promotion post-save (in on_update) so DB reflects the newly rejected seat.
        self.flags.slcm_affected_programs_for_waitlist_promotion = sorted(list(affected_programs))

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
                "is_locked": 0,
                "admission_cycle": self.admission_cycle,
                "campus": self.campus,
            },
            pluck="name",
        )

        for rule_name in rule_names:
            frappe.flags.slcm_waitlist_promotion_in_progress = True
            try:
                process_waitlist(frappe.get_doc("Waitlist Rule", rule_name))
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

        # Pull if empty
        if not self.selection_applicant:
            self.pull_from_merit_list()

        admission_year_name = frappe.db.get_value("Admission Cycle", self.admission_cycle, "parent")
        if not admission_year_name or frappe.db.get_value("Admission Cycle", self.admission_cycle, "parenttype") != "Admission Year":
             # Fallback: direct SQL to avoid filter parsing issues with child tables
             res = frappe.db.sql("""
                 SELECT parent FROM `tabAdmission Cycle` 
                 WHERE name = %s AND parenttype = 'Admission Year'
                 LIMIT 1
             """, (self.admission_cycle,))
             if res:
                 admission_year_name = res[0][0]
             
        if not admission_year_name:
            frappe.throw(f"No Admission Year found for cycle {self.admission_cycle}")

        program_offering = frappe.get_doc("Program Offering", {"campus": self.campus, "admission_year": admission_year_name})
        if not program_offering:
            frappe.throw(f"No Program Offering found for Campus {self.campus} and Year {admission_year_name}")

        program_to_rule = {}
        for p in program_offering.programs:
            program_to_rule[p.program_of_study] = p.reservation_rule

        # Helpers
        def get_category_seats(rule_name, cat_name):
            # Resolve all category IDs that match the name or code
            matching_cats = frappe.db.sql("""
                SELECT name FROM `tabAdmission Category`
                WHERE name = %s OR category_code = %s OR category_name = %s
            """, (cat_name, cat_name, cat_name), pluck=True)
            
            for c in matching_cats:
                val = frappe.db.get_value("Reservation Quota", {"parent": rule_name, "category": c}, "seats")
                if val is not None:
                    return int(val), c

            return 0, None

        def get_reserved_categories(rule_name, exclude_cats=None):
            if exclude_cats is None:
                exclude_cats = []
            
            quotas = frappe.get_all("Reservation Quota", filters={"parent": rule_name}, fields=["category"])
            cats = []
            for q in quotas:
                c = q.category
                if c not in ["GEN", "General"] and c not in exclude_cats and c not in cats:
                    cats.append(c)
            return cats

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

            rule_name = program_to_rule.get(program)
            if not rule_name:
                frappe.throw(f"No Reservation Rule found for Program {program} in Program Offering")

            # -----------------------------------
            # Sort by merit
            # -----------------------------------
            applicants.sort(
                key=lambda x: (-(x.total_score or 0), x.overall_rank or 999999)
            )

            # -----------------------------------
            # PHASE 1: OPEN (GEN) SELECTION
            # -----------------------------------
            gen_seats, matched_gen_cat = get_category_seats(rule_name, "GEN")
            if gen_seats == 0:
                gen_seats, matched_gen_cat = get_category_seats(rule_name, "General")

            # Get waitlist percentage from active Waitlist Rule (campus wide)
            waitlist_percent = 50.0
            rules = frappe.get_all("Waitlist Rule", filters={"campus": self.campus, "admission_cycle": self.admission_cycle, "status": "Active"}, fields=["waitlist_percentage"])
            if rules:
                waitlist_percent = rules[0].waitlist_percentage or 50.0
            
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
            processed_cats = []
            if matched_gen_cat:
                processed_cats.append(matched_gen_cat)

            reserved_categories = get_reserved_categories(rule_name, exclude_cats=processed_cats)
            
            # Store waitlist quotas to process later
            category_waitlist_quotas = {}

            for category in reserved_categories:
                category_seats, _ = get_category_seats(rule_name, category)
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
            
            # 1. Waitlist GEN (from highest merit in remaining pool)
            gen_waitlist_pool = remaining_pool[:gen_waitlist_cap]
            remaining_pool = remaining_pool[gen_waitlist_cap:]

            for row in gen_waitlist_pool:
                row.selection_status = "Waitlisted"
                row.allocation_type = "Open"
                total_waitlisted += 1
                
            # 2. Waitlist Reserved (from category specific pools)
            for category in reserved_categories:
                cat_waitlist_cap = category_waitlist_quotas.get(category, 0)
                if cat_waitlist_cap == 0:
                    continue
                    
                cat_doc = frappe.get_cached_value("Admission Category", category, ["name", "category_code", "category_name"], as_dict=1)
                match_strings = [category]
                if cat_doc:
                    if cat_doc.get("category_code"): match_strings.append(cat_doc.get("category_code"))
                    if cat_doc.get("category_name"): match_strings.append(cat_doc.get("category_name"))

                # Re-fetch category pool from the updated remaining pool
                waitlist_pool = [r for r in remaining_pool if r.reservation_category in match_strings]
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
        frappe.db.commit()

        frappe.msgprint("Allocation Published.")
