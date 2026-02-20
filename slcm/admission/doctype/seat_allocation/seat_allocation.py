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
            frappe.throw("Allocation already published. Cannot re-run.")

        # -------------------------
        # 2️⃣ PULL APPLICANTS (if empty)
        # -------------------------
        if not self.selection_applicant:
            self.pull_from_merit_list()
        else:
            # Clear previous status
            for row in self.selection_applicant:
                row.selection_status = "Draft"

        # -------------------------
        # 3️⃣ FIND ADMISSION YEAR & PROGRAM OFFERING
        # -------------------------
        # Admission Year is the parent of Admission Cycle child table rows
        admission_year = frappe.db.get_value("Admission Cycle", self.admission_cycle, "parent")
        if not admission_year:
            frappe.throw(f"No Admission Year found for cycle {self.admission_cycle}")

        program_offering = frappe.get_doc("Program Offering", {"campus": self.campus, "admission_year": admission_year})
        if not program_offering:
            frappe.throw(f"No Program Offering found for Campus {self.campus} and Year {admission_year}")

        # Map Program to Reservation Rule
        program_to_rule = {}
        for p in program_offering.programs:
            program_to_rule[p.program_of_study] = p.reservation_rule

        # -------------------------
        # 4️⃣ GROUP BY PROGRAM + CATEGORY
        # -------------------------
        grouped = {}
        for row in self.selection_applicant:
            key = (row.program, row.reservation_category)
            grouped.setdefault(key, []).append(row)

        total_selected = 0
        total_waitlisted = 0
        total_rejected = 0
        missing_categories = set()

        # -------------------------
        # 5️⃣ PROCESS EACH GROUP
        # -------------------------
        for (program, category), applicants in grouped.items():
            # Sort by Total Score DESC, and Overall Rank ASC as tie-breaker
            # (Note: lower overall_rank is better, so we use -rank with reverse=True)
            applicants.sort(key=lambda x: (x.total_score, -(x.overall_rank or 999999)), reverse=True)

            # Fetch intake capacity for this category
            rule_name = program_to_rule.get(program)
            if not rule_name:
                frappe.throw(f"No Reservation Rule found for Program {program} in Program Offering")

            # Get seats for specific category from Reservation Rule's Reservation Quota table
            # Resolving the category link to a potential match in the quota table
            category_doc = frappe.get_cached_value("Admission Category", category, ["category_code", "category_name"], as_dict=1)
            
            search_categories = [category]
            if category_doc:
                if category_doc.get("category_code"):
                    search_categories.append(category_doc.get("category_code"))
                if category_doc.get("category_name"):
                    search_categories.append(category_doc.get("category_name"))
            
            # Find the first matching category in Reservation Quota
            seat_capacity = None
            for cat_to_search in search_categories:
                # Try 'category' first (new field name)
                seat_capacity = frappe.db.get_value("Reservation Quota", 
                    {"parent": rule_name, "category": cat_to_search}, "seats")
                
                # Fallback to 'quota' (legacy field name) if not found
                if seat_capacity is None:
                    seat_capacity = frappe.db.get_value("Reservation Quota", 
                        {"parent": rule_name, "quota": cat_to_search}, "seats")
                
                if seat_capacity is not None:
                    break
            
            # If not found in rule, assume 0 reserved seats for this category
            if seat_capacity is None:
                S = 0
                missing_categories.add(category)
            else:
                S = int(seat_capacity)

            # Calculate Waitlist (50%)
            W = math.ceil(S * 0.5)

            # -------------------------
            # 6️⃣ ASSIGN STATUS
            # -------------------------
            for index, applicant in enumerate(applicants):
                rank = index + 1
                if rank <= S:
                    applicant.selection_status = "Selected"
                    total_selected += 1
                elif rank <= S + W:
                    applicant.selection_status = "Waitlisted"
                    total_waitlisted += 1
                else:
                    applicant.selection_status = "Rejected"
                    total_rejected += 1

        # -------------------------
        # 7️⃣ UPDATE TOTALS
        # -------------------------
        self.total_selected = total_selected
        self.total_waitlisted = total_waitlisted
        self.total_rejected = total_rejected

        self.status = "Allocated"
        self.save()
        frappe.db.commit()

        msg = "Seat Allocation Completed Successfully."
        if missing_categories:
            cats = ", ".join(missing_categories)
            msg += f"<br><br><b>Note:</b> The following categories were not found in the Reservation Rule and were treated as having 0 seats: {cats}"
        
        frappe.msgprint(msg)

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
