import frappe
import math
from frappe.model.document import Document
from frappe.utils import now


class SeatAllocation(Document):

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

        admission_year = frappe.db.get_value("Admission Cycle", self.admission_cycle, "parent")
        if not admission_year:
            frappe.throw(f"No Admission Year found for cycle {self.admission_cycle}")

        program_offering = frappe.get_doc("Program Offering", {"campus": self.campus, "admission_year": admission_year})
        if not program_offering:
            frappe.throw(f"No Program Offering found for Campus {self.campus} and Year {admission_year}")

        program_to_rule = {}
        for p in program_offering.programs:
            program_to_rule[p.program_of_study] = p.reservation_rule

        # Helpers
        def get_category_seats(rule_name, cat_name):
            cat_doc = frappe.get_cached_value("Admission Category", cat_name, ["name", "category_code", "category_name"], as_dict=1)
            search_cats = [cat_name]
            if cat_doc:
                if cat_doc.get("category_code"): search_cats.append(cat_doc.get("category_code"))
                if cat_doc.get("category_name"): search_cats.append(cat_doc.get("category_name"))
            
            for c in search_cats:
                for field in ["category", "quota"]:
                    val = frappe.db.get_value("Reservation Quota", {"parent": rule_name, field: c}, "seats")
                    if val is not None:
                        return int(val)
            return 0

        def get_reserved_categories(rule_name):
            quotas = frappe.get_all("Reservation Quota", filters={"parent": rule_name}, fields=["category", "quota"])
            cats = []
            for q in quotas:
                c = q.category or q.quota
                if c not in ["GEN", "General"] and c not in cats:
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
            gen_seats = get_category_seats(rule_name, "GEN")
            if gen_seats == 0:
                gen_seats = get_category_seats(rule_name, "General")

            gen_waitlist = math.ceil(gen_seats * 0.5)

            selected_open = applicants[:gen_seats]
            remaining_pool = applicants[gen_seats:]

            for row in selected_open:
                row.selection_status = "Selected"
                row.allocation_type = "Open"
                total_selected += 1

            # -----------------------------------
            # PHASE 2: RESERVED SELECTION
            # -----------------------------------
            reserved_categories = get_reserved_categories(rule_name)
            
            # Store waitlist quotas to process later
            category_waitlist_quotas = {}

            for category in reserved_categories:
                category_seats = get_category_seats(rule_name, category)
                category_waitlist_quotas[category] = math.ceil(category_seats * 0.5)

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
            gen_waitlist_pool = remaining_pool[:gen_waitlist]
            remaining_pool = remaining_pool[gen_waitlist:]

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
    def promote_waitlist(self, rejected_applicant):
        """
        Triggered when a Selected candidate's status becomes 'Rejected'.
        Finds the highest-merit waitlisted candidate matching the exact 
        Program and Allocation Type (Open or Reserved category) and 
        promotes them to 'Selected'.
        """
        # Find the rejected candidate's original allocation details
        rejected_row = None
        for row in self.selection_applicant:
            if row.applicant == rejected_applicant and row.selection_status == "Rejected":
                rejected_row = row
                break
                
        if not rejected_row:
            frappe.throw(f"Applicant {rejected_applicant} is not found or not marked as Rejected in this allocation.")
            
        program = rejected_row.program
        allocation_type = rejected_row.allocation_type
        category = rejected_row.reservation_category
        
        # We need to find the highest merit (highest total_score, lowest overall_rank)
        # candidate who is currently "Waitlisted" for the exact same seat constraints.
        
        candidates = []
        for row in self.selection_applicant:
            if row.selection_status == "Waitlisted" and row.program == program:
                if allocation_type == "Open":
                    # For Open seats, ANY waitlisted candidate in the Open waitlist pool is eligible
                    if row.allocation_type == "Open":
                        candidates.append(row)
                elif allocation_type == "Reserved":
                    # For Reserved seats, they MUST perfectly match the specific reserved category
                    if row.allocation_type == "Reserved" and row.reservation_category == category:
                        candidates.append(row)
                        
        if not candidates:
            frappe.msgprint(f"No eligible waitlisted candidates found to promote for {program} ({allocation_type}).")
            return
            
        # Sort to find the absolute best candidate (same logic as allocation)
        candidates.sort(key=lambda x: (-(x.total_score or 0), x.overall_rank or 999999))
        
        top_candidate = candidates[0]
        
        # Promote them
        top_candidate.selection_status = "Selected"
        self.total_selected += 1
        self.total_waitlisted -= 1
        
        # We don't change the rejected candidate's counts because they were already excluded 
        # from total_selected when their status changed to Rejected prior to calling this.
        
        self.save()
        frappe.db.commit()
        
        frappe.msgprint(f"Successfully promoted Applicant {top_candidate.applicant} from Waitlist to Selected for {program}.")

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
