import frappe
import math
from frappe.model.document import Document
from frappe.utils import now, get_link_to_form, get_datetime, now_datetime

_CATEGORY_CACHE = {}

def clear_category_cache():
    global _CATEGORY_CACHE
    _CATEGORY_CACHE = {}

def get_applicant_categories(applicant_id):
    """
    Fetches all categories mapped to the applicant.
    Checks Eligibility Result first, then falls back to the base Applicant record.
    """
    if not applicant_id:
        return []
        
    global _CATEGORY_CACHE
    if applicant_id in _CATEGORY_CACHE:
        return _CATEGORY_CACHE[applicant_id]

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
            pluck="category"
        )

    # 2. Try from Applicant (initial source from web form)
    if not categories:
        categories = frappe.db.get_all(
            "Applicant Category",
            filters={"parent": applicant_id, "parenttype": "Applicant"},
            pluck="category"
        )
        
    categories = list(set(categories))

    # 3. Auto-inject Gender-based categories for Horizontal Reservation
    if applicant_id:
        gender = frappe.db.get_value("Applicant", applicant_id, "gender")
        if gender == "Female":
            categories.extend(["Women", "Female"])

    final_categories = list(set(categories))
    _CATEGORY_CACHE[applicant_id] = final_categories
    return final_categories

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

        if self.program:
            program_code = frappe.db.get_value("Program", self.program, "program_code") or self.program
            prog = program_code.replace(" ", "").upper()
            self.name = make_autoname(f"SA-{cycle}-{campus}-{prog}-.#####")
        else:
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
        
        # Update display name for combined categories (e.g., "SC + Women")
        # This handles initial allocation, waitlist promotion, and manual saves.
        h_categories = frappe.db.get_all("Admission Category", 
            filters={"reservation_type": ["in", ["Horizontal", "Compartmentalised Horizontal"]]}, 
            pluck="name"
        )
        
        for row in (self.selection_applicant or []):
            v_cat = row.get("vertical_category")
            c_cat = row.get("compartment_category")
            h_cats_str = row.get("horizontal_categories")

            if row.selection_status in selection_statuses and v_cat:
                parts = [v_cat]
                
                if c_cat:
                    parts.append(c_cat)
                
                if h_cats_str:
                    h_cats = sorted([c.strip() for c in h_cats_str.split(",") if c.strip()])
                    parts.extend(h_cats)
                
                row.allocated_category = " + ".join(parts)
            elif row.selection_status in selection_statuses and not v_cat and row.allocated_category:
                # Backwards compatibility for manually set categories
                pass
            elif row.selection_status in selection_statuses and not v_cat:
                row.vertical_category = "General"
                row.allocated_category = "General"

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
        
        if self.program:
            filters["program"] = self.program
        
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
            program_level=self.program_level,
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
        to reflect Filled and Available seats across all tables.
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

        # 2. Map programs to their specific policies (Campus-aware)
        policies = frappe.get_all("Program Reservation Policy", filters={
            "admission_cycle": self.admission_cycle,
            "program": ["in", list(affected_programs)],
            "campus": ["in", [self.campus, None, ""]], # Match current campus or legacy policies
            "docstatus": ["!=", 2]
        }, fields=["name", "program", "campus"])

        # Prioritize campus-specific policies over generic/legacy ones
        policy_map = {}
        for p in policies:
            if p.program not in policy_map or p.campus == self.campus:
                policy_map[p.program] = p.name
        
        filled_statuses = ["Selected", "Offer Issued", "Offer Accepted", "Fee Paid", "Accepted"]

        # 3. Process each policy found
        for prog, policy_name in policy_map.items():
            policy = frappe.get_doc("Program Reservation Policy", policy_name)
            
            # Reset counts in all tables
            for table in ["categories", "horizontal_reservations", "compartmental_reservations"]:
                for p_row in getattr(policy, table, []):
                    p_row.filled_seats = 0
            
            # Tally counts from ALL relevant allocations in this cycle/program
            if not reset_only:
                # Find all active allocations for this cycle/program
                sa_names = frappe.get_all("Seat Allocation", filters={
                    "admission_cycle": self.admission_cycle,
                    "status": ["in", ["Published", "Allocated"]],
                    "docstatus": ["<", 2]
                }, pluck="name")
                
                if not sa_names: continue

                # Check for field existence before querying
                meta = frappe.get_meta("Seat Selection Applicant")
                has_new_fields = meta.has_field("vertical_category")
                fields_to_fetch = ["applicant_id", "allocated_category"]
                if has_new_fields:
                    fields_to_fetch.extend(["vertical_category", "horizontal_categories", "compartment_category"])

                # Get all allocated/selected students
                applicants = frappe.get_all("Seat Selection Applicant", 
                    filters={
                        "parent": ["in", sa_names],
                        "program": prog,
                        "selection_status": ["in", filled_statuses]
                    },
                    fields=fields_to_fetch
                )
                
                # Fetch category types
                cat_types = {c.name: c.reservation_type for c in frappe.get_all("Admission Category", fields=["name", "reservation_type"])}

                for app in applicants:
                    # A. Vertical Consumption (Real Seats)
                    v_cat = app.get("vertical_category")
                    all_cat = app.get("allocated_category")
                    
                    if has_new_fields and v_cat:
                        # NEW LOGIC: Use separate fields
                        for p_row in (policy.categories or []):
                            is_gen = v_cat == "General" and (p_row.reservation_quota == "General" or not p_row.category_name)
                            if p_row.category_name == v_cat or is_gen:
                                p_row.filled_seats = int(p_row.filled_seats or 0) + 1
                                break
                    else:
                        # FALLBACK: Use string parsing
                        cats = [c.strip() for c in (all_cat or "").split("+")]
                        if not cats or (len(cats) == 1 and cats[0] == ""):
                            cats = ["General"]
                        
                        base_cat = cats[0]
                        if cat_types.get(base_cat, "Vertical") == "Vertical" or base_cat == "General":
                            for p_row in (policy.categories or []):
                                is_gen = base_cat == "General" and (p_row.reservation_quota == "General" or not p_row.category_name)
                                if p_row.category_name == base_cat or is_gen:
                                    p_row.filled_seats = int(p_row.filled_seats or 0) + 1
                                    break
                    
                    # B. Horizontal Coverage (Statistics)
                    h_cats_val = app.get("horizontal_categories")
                    if has_new_fields and h_cats_val:
                        traits = [t.strip() for t in h_cats_val.split(",") if t.strip()]
                        for trait in traits:
                            for p_row in (policy.horizontal_reservations or []):
                                if p_row.category_name == trait:
                                    p_row.filled_seats = int(p_row.filled_seats or 0) + 1
                    else:
                        # Fallback to traits from DB
                        traits = [c for c in get_applicant_categories(app.applicant_id) if cat_types.get(c) == "Horizontal"]
                        for trait in traits:
                            for p_row in (policy.horizontal_reservations or []):
                                if p_row.category_name == trait:
                                    p_row.filled_seats = int(p_row.filled_seats or 0) + 1

                    # C. Compartmentalised Consumption
                    c_cat = app.get("compartment_category")
                    if has_new_fields and c_cat:
                        for p_row in (policy.compartmental_reservations or []):
                            if p_row.category_name == c_cat:
                                p_row.filled_seats = int(p_row.filled_seats or 0) + 1
                                break
                    else:
                        # Fallback: find it in the split string if it's compartmental type
                        cats = [c.strip() for c in (all_cat or "").split("+")]
                        for c_name in cats:
                            if cat_types.get(c_name) == "Compartmentalised Horizontal":
                                for p_row in (policy.compartmental_reservations or []):
                                    if p_row.category_name == c_name:
                                        p_row.filled_seats = int(p_row.filled_seats or 0) + 1

            # 4. Finalize totals and save
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

        # Auto-populate header fields from Merit List if empty
        if not self.admission_cycle: self.admission_cycle = merit.admission_cycle
        if not self.campus: self.campus = merit.campus
        if not self.program_level: self.program_level = merit.program_level
        if not self.program: self.program = merit.program

        # Clear existing rows
        self.set("selection_applicant", [])

        for row in merit.merit_applicants:
            self.append("selection_applicant", {
                "applicant_id": row.applicant_id,
                "candidate_name": row.candidate_name,
                "program": row.program,
                "total_score": row.total_score,
                "overall_rank": row.overall_rank,
                "entrance_score": row.entrance_score,
                "interview_score": row.interview_score,
                "nlsat_part_a_score": row.entrance_score,
                "nlsat_part_b_score": row.interview_score,
                "shortlist_rank": row.overall_rank if getattr(merit, "merit_processing_stage", "") == "Part A Ranking" else None,
                "admission_rank": row.overall_rank if getattr(merit, "merit_processing_stage", "") == "Final Allotment Ranking" else None,
                "percentile_score": row.get("percentile_score"),
                "selection_status": "Draft"
            })

        self.save()
        frappe.db.commit()

    def _finish_allocation(self):
        """
        Handles final tallying, logging, sorting and saving after allocation logic.
        """
        from slcm.admission.doctype.admission_audit_log.audit_service import bulk_log_seat_allocation_actions
        
        # Calculate counters
        self.total_selected = 0
        self.total_waitlisted = 0
        self.total_rejected = 0
        
        selection_statuses = ["Selected", "Offer Issued", "Offer Accepted", "Accepted", "Fee Paid"]
        
        for row in self.selection_applicant:
            if row.selection_status in selection_statuses:
                self.total_selected += 1
            elif row.selection_status == "Waitlisted":
                self.total_waitlisted += 1
            elif row.selection_status in ["Rejected", "Offer Declined", "Offer Expired", "Withdrawn"]:
                self.total_rejected += 1

        audit_logs = []
        for row in self.selection_applicant:
             category_used_str = f" Category Used: {row.allocated_category}" if row.allocated_category else ""
             audit_logs.append({
                "seat_allocation": self.name,
                "admission_cycle": self.admission_cycle,
                "applicant": row.applicant_id,
                "program": row.program,
                "action_type": "Seat Allocated",
                "old_value": "Draft",
                "new_value": row.selection_status,
                "remarks": f"Initial automatic allocation as {row.allocation_type or 'N/A'}.{category_used_str}"
            })
        
        bulk_log_seat_allocation_actions(audit_logs)

        # Sort selection_applicant table
        status_priority = {"Selected": 1, "Waitlisted": 2, "Rejected": 3, "Draft": 4}
        sorted_rows = sorted(self.selection_applicant, key=lambda x: (
            status_priority.get(x.selection_status, 99),
            -(x.total_score or 0),
            (x.overall_rank or 999999)
        ))
        
        self.set("selection_applicant", [])
        for i, row in enumerate(sorted_rows):
            row.idx = i + 1
            self.append("selection_applicant", row)
            
        self.status = "Allocated"
        self.save()
        self.sync_filled_seats()
        frappe.db.commit()

        if not getattr(self.flags, "is_background", False):
            frappe.msgprint("Seat Allocation phase completed successfully.")

    @frappe.whitelist()
    def allocate_seats(self):
        clear_category_cache()
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

        # Waitlist Rule is no longer required for NLSAT

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

        import math
        cat_types = {c.name: c.reservation_type for c in frappe.get_all("Admission Category", fields=["name", "reservation_type"])}

        # 2.5 Advanced Allocation Check
        # Check if any program in this allocation uses the advanced shortlisting process
        has_advanced_program = False
        for program in grouped_by_program.keys():
            if frappe.db.get_value("Program Reservation Policy", {"program": program, "admission_cycle": self.admission_cycle}, "enable_advanced_shortlisting"):
                has_advanced_program = True
                break
        
        if has_advanced_program:
            from slcm.admission.doctype.merit_rule.merit_service import execute_advanced_allocation_logic
            execute_advanced_allocation_logic(self)
            # Log results and finish
            self._finish_allocation()
            return

        for program, applicants in grouped_by_program.items():
            
            # Fetch PRP to get matrices
            policy_name = frappe.db.get_value("Program Reservation Policy", {
                "admission_cycle": self.admission_cycle,
                "program": program,
                "status": "Active"
            }, "name")
            
            if not policy_name:
                policy_name = frappe.db.get_value("Program Reservation Policy", {
                    "admission_cycle": self.admission_cycle,
                    "program": program
                }, "name")
                
            if not policy_name:
                frappe.throw(f"No Program Reservation Policy found for Program {program}.")
                
            policy = frappe.get_doc("Program Reservation Policy", policy_name)
            
            # Sort applicants strictly by merit
            applicants.sort(key=lambda x: (-(x.total_score or 0), x.overall_rank or 999999))
            
            # Setup State
            # Setup State dynamically from policy
            v_matrix = {}
            for v in getattr(policy, "categories", []):
                v_total = math.floor((policy.total_seats or 0) * ((v.percentage or 0) / 100.0))
                v_matrix[v.category_name] = {"total": v_total, "filled": 0, "priority": v.priority}
                
            c_matrix = {}
            for c in getattr(policy, "compartmental_reservations", []):
                for v_cat, v_info in v_matrix.items():
                    c_total = math.floor(v_info["total"] * ((c.percentage or 0) / 100.0))
                    if c_total > 0:
                        if v_cat not in c_matrix:
                            c_matrix[v_cat] = {}
                        c_matrix[v_cat][c.category_name] = {"total": c_total, "filled": 0, "priority": c.priority}
                
            h_matrix = {}
            for h in getattr(policy, "horizontal_reservations", []):
                for v_cat, v_info in v_matrix.items():
                    h_total = math.floor(v_info["total"] * ((h.percentage or 0) / 100.0))
                    if h_total > 0:
                        if v_cat not in h_matrix:
                            h_matrix[v_cat] = {}
                        h_matrix[v_cat][h.category_name] = {"total": h_total, "filled": 0, "priority": h.priority}
            
            total_intake = policy.total_seats or 0
            reserved_intake = sum(v_info["total"] for v_info in v_matrix.values())
            gen_seats = total_intake - reserved_intake
            gen_filled = 0
            
            waitlist_percent = 50.0
            rules = frappe.get_all("Waitlist Rule", filters={"campus": self.campus, "admission_cycle": self.admission_cycle, "program_level": self.program_level, "status": "Active"}, fields=["waitlist_percentage"])
            if rules and rules[0].waitlist_percentage is not None:
                waitlist_percent = rules[0].waitlist_percentage
            waitlist_factor = waitlist_percent / 100.0

            unallocated = applicants[:]
            allocated_list = []
            
            # Phase 1: General (Open) Merit Allocation
            gen_state = v_matrix.get("General")
            if gen_state:
                for applicant in unallocated[:]:
                    if gen_state["filled"] < gen_state["total"]:
                        applicant.selection_status = "Selected"
                        applicant.allocation_type = "Open"
                        applicant.vertical_category = "General"
                        applicant.allocated_category = "General"
                        applicant.horizontal_categories = "" # Keep it clean for Open seats
                        
                        gen_state["filled"] += 1
                        total_selected += 1
                        allocated_list.append(applicant)
                        unallocated.remove(applicant)

            # PHASE 2 & 3: Vertical & Compartmentalised
            for applicant in unallocated[:]:
                app_categories = get_applicant_categories(applicant.applicant_id)
                v_cat = None
                valid_vs = [c for c in app_categories if c in v_matrix]
                if valid_vs:
                    valid_vs.sort(key=lambda c: v_matrix[c]["priority"] or 999)
                    v_cat = valid_vs[0]
                
                if not v_cat:
                    continue
                
                v_state = v_matrix[v_cat]
                if v_state["filled"] >= v_state["total"]:
                    continue
                    
                c_cat_allocated = None
                if v_cat in c_matrix:
                    valid_cs = [c for c in app_categories if c in c_matrix[v_cat]]
                    if valid_cs:
                        valid_cs.sort(key=lambda c: c_matrix[v_cat][c]["priority"] or 999)
                        for c_cat in valid_cs:
                            c_state = c_matrix[v_cat][c_cat]
                            if c_state["filled"] < c_state["total"]:
                                c_cat_allocated = c_cat
                                c_state["filled"] += 1
                                break
                                
                if c_cat_allocated:
                    applicant.selection_status = "Selected"
                    applicant.allocation_type = "Reserved"
                    applicant.vertical_category = v_cat
                    applicant.compartment_category = c_cat_allocated
                    
                    # Capture horizontal traits for coverage
                    traits = [c for c in get_applicant_categories(applicant.applicant_id) if cat_types.get(c) == "Horizontal"]
                    if traits:
                        applicant.horizontal_categories = ", ".join(sorted(traits))

                    v_state["filled"] += 1
                    total_selected += 1
                    allocated_list.append(applicant)
                    unallocated.remove(applicant)
                else:
                    generic_cap = v_state["total"] - sum(c_info["total"] for c_info in c_matrix.get(v_cat, {}).values())
                    generic_filled = v_state["filled"] - sum(c_info["filled"] for c_info in c_matrix.get(v_cat, {}).values())
                    
                    if generic_filled < generic_cap:
                        applicant.selection_status = "Selected"
                        applicant.allocation_type = "Reserved"
                        applicant.vertical_category = v_cat
                        
                        # Capture horizontal traits for coverage
                        traits = [c for c in get_applicant_categories(applicant.applicant_id) if cat_types.get(c) == "Horizontal"]
                        if traits:
                            applicant.horizontal_categories = ", ".join(sorted(traits))

                        v_state["filled"] += 1
                        total_selected += 1
                        allocated_list.append(applicant)
                        unallocated.remove(applicant)

            # Conversion Pass: Unused Compartmentalised become Generic Vertical
            for applicant in unallocated[:]:
                app_categories = get_applicant_categories(applicant.applicant_id)
                valid_vs = [c for c in app_categories if c in v_matrix]
                if valid_vs:
                    valid_vs.sort(key=lambda c: v_matrix[c]["priority"] or 999)
                    v_cat = valid_vs[0]
                    v_state = v_matrix[v_cat]
                    if v_state["filled"] < v_state["total"]:
                        applicant.selection_status = "Selected"
                        applicant.allocation_type = "Reserved"
                        applicant.vertical_category = v_cat

                        # Capture horizontal traits for coverage
                        traits = [c for c in get_applicant_categories(applicant.applicant_id) if cat_types.get(c) == "Horizontal"]
                        if traits:
                            applicant.horizontal_categories = ", ".join(sorted(traits))

                        v_state["filled"] += 1
                        total_selected += 1
                        allocated_list.append(applicant)
                        unallocated.remove(applicant)

            # PHASE 4: Horizontal Reservation Adjustment (GLOBAL)
            h_targets = {}
            for h in getattr(policy, "horizontal_reservations", []):
                h_targets[h.category_name] = math.floor(total_intake * ((h.percentage or 0) / 100.0))
                
            for h_cat, required_total in h_targets.items():
                h_selected = 0
                for a in allocated_list:
                    if h_cat in get_applicant_categories(a.applicant_id):
                        h_selected += 1
                        
                deficit = required_total - h_selected
                
                if deficit > 0:
                    unallocated_h_candidates = [u for u in unallocated if h_cat in get_applicant_categories(u.applicant_id)]
                    unallocated_h_candidates.sort(key=lambda x: (-(x.total_score or 0), x.overall_rank or 999999))
                    
                    for in_cand in unallocated_h_candidates:
                        if deficit <= 0:
                            break
                            
                        in_cats = get_applicant_categories(in_cand.applicant_id)
                        
                        # Find the lowest scoring allocated candidate that in_cand can legally replace
                        # Legal replacement: The allocated candidate does NOT have h_cat, AND
                        # either occupies a "General" seat OR occupies a vertical seat that in_cand also belongs to.
                        eligible_out_candidates = []
                        for out_cand in allocated_list:
                            if h_cat not in get_applicant_categories(out_cand.applicant_id):
                                if out_cand.allocated_category == "General" or out_cand.allocated_category in in_cats:
                                    eligible_out_candidates.append(out_cand)
                                    
                        if eligible_out_candidates:
                            # Sort by lowest score
                            eligible_out_candidates.sort(key=lambda x: (x.total_score or 0, -(x.overall_rank or 999999)))
                            out_cand = eligible_out_candidates[0]
                            
                            # Perform Swap
                            target_vertical = out_cand.vertical_category
                            target_compartment = out_cand.compartment_category
                            target_type = out_cand.allocation_type
                            
                            out_cand.selection_status = "Rejected"
                            out_cand.allocation_type = ""
                            out_cand.vertical_category = ""
                            out_cand.compartment_category = ""
                            out_cand.horizontal_categories = ""
                            out_cand.allocated_category = ""
                            allocated_list.remove(out_cand)
                            unallocated.append(out_cand)
                            
                            in_cand.selection_status = "Selected"
                            in_cand.allocation_type = target_type
                            in_cand.vertical_category = target_vertical
                            in_cand.compartment_category = target_compartment
                            
                            # Recapture horizontal traits for in_cand
                            traits = [c for c in get_applicant_categories(in_cand.applicant_id) if cat_types.get(c) == "Horizontal"]
                            if traits:
                                in_cand.horizontal_categories = ", ".join(sorted(traits))

                            unallocated.remove(in_cand)
                            allocated_list.append(in_cand)
                            
                            deficit -= 1
                            
            # Resort unallocated for Waitlist
            unallocated.sort(key=lambda x: (-(x.total_score or 0), x.overall_rank or 999999))
            
            # PHASE 5: Waitlists
            gen_waitlist_cap = math.ceil(gen_seats * waitlist_factor)
            
            for row in unallocated[:gen_waitlist_cap]:
                row.selection_status = "Waitlisted"
                row.allocation_type = "Open"
                row.vertical_category = "General"
                row.allocated_category = "General"
                total_waitlisted += 1
            unallocated = unallocated[gen_waitlist_cap:]
            
            v_waitlist_caps = {}
            for v_cat, v_state in v_matrix.items():
                v_waitlist_caps[v_cat] = math.ceil(v_state["total"] * waitlist_factor)
                
            for row in unallocated[:]:
                app_cats = get_applicant_categories(row.applicant_id)
                valid_vs = [c for c in app_cats if c in v_waitlist_caps]
                if valid_vs:
                    valid_vs.sort(key=lambda c: v_matrix[c]["priority"] or 999)
                    for v in valid_vs:
                        if v_waitlist_caps[v] > 0:
                            row.selection_status = "Waitlisted"
                            row.allocation_type = "Reserved"
                            row.vertical_category = v
                            row.allocated_category = v
                            total_waitlisted += 1
                            v_waitlist_caps[v] -= 1
                            unallocated.remove(row)
                            break
                            
            # PHASE 6: Reject remaining
            for row in unallocated:
                row.selection_status = "Rejected"
                row.allocation_type = ""
                total_rejected += 1

        self._finish_allocation()

    @frappe.whitelist()
    def allocate_seats_trigger(self):
        """
        Whitelisted entry point that decides whether to run immediately or in background.
        """
        if not self.selection_applicant:
            self.pull_from_merit_list()
            
        count = len(self.selection_applicant)
        if count > 500:
            frappe.enqueue(
                method="slcm.admission.doctype.seat_allocation.seat_allocation.run_allocation_background",
                queue="long",
                name=self.name,
                user=frappe.session.user
            )
            return {
                "queued": True,
                "message": f"Large allocation detected ({count} applicants). Processing started in the background. You will be notified when finished."
            }
        
        self.allocate_seats()
        return {"queued": False}

    @frappe.whitelist()
    def publish_allocation(self):
        if self.status != "Allocated":
            frappe.throw("Run allocation first.")
 
        self._publish_logic()
        return {"queued": False}

    def _publish_logic(self):
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

        # Trigger notifications directly (uses now=False internally)
        # Following the 'Interview Seat Allocation' method (Direct Loop + Periodic Commits)
        self._trigger_allocation_notifications_local()

        if not getattr(self.flags, "is_background", False):
            frappe.msgprint("Allocation Published and notifications queued.")

    def _trigger_allocation_notifications_local(self):
        """
        Directly loops through applicants and sends notifications.
        Matches the pattern used in Interview Seat Allocation.
        """
        total = len(self.selection_applicant)
        for i, row in enumerate(self.selection_applicant):
            if row.selection_status not in ["Selected", "Waitlisted", "Rejected"]:
                continue
                
            email = frappe.db.get_value("Applicant", row.applicant_id, "email")
            if not email:
                continue
                
            try:
                self._send_allocation_email_local(row, email)
                self._send_allocation_system_notification_local(row, email)
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"Allocation Notification Failed for {row.applicant_id}")

            # Commit every 10 records to match the Interview method
            if i % 10 == 0:
                frappe.db.commit()

    def _send_allocation_email_local(self, row, email):
        """
        Sends email using 'Seat Allocation Result Notification' following the Interview style.
        """
        template_name = "Seat Allocation Result Notification"
        if not frappe.db.exists("Email Template", template_name):
            return

        template = frappe.get_doc("Email Template", template_name)
        
        # Prepare context
        safe_name = str(row.candidate_name or "Applicant")
        
        doc_context = row.as_dict()
        doc_context["admission_cycle"] = self.admission_cycle
        doc_context["campus"] = self.campus
        
        args = {
            "doc": doc_context,
            "candidate_name": safe_name,
            "status": row.selection_status,
            "allocation_name": self.name,
            "portal_url": frappe.utils.get_url(f"/my-applications?app={row.applicant_id}")
        }

        subject = frappe.render_template(template.subject, args)
        
        if template.get("use_html"):
            message = frappe.render_template(template.response_html, args)
        else:
            message = frappe.render_template(template.response, args)

        if not message:
            message = frappe.render_template(template.get("message") or "", args)

        cc_list = []
        cc_field_value = template.get("cc")
        if cc_field_value:
            cc_list = [c.strip() for c in cc_field_value.replace(";", ",").split(",") if c.strip()]

        if message:
            frappe.sendmail(
                recipients=[email],
                cc=cc_list,
                subject=subject,
                message=message,
                reference_doctype="Seat Allocation",
                reference_name=self.name,
                now=False
            )

    def _send_allocation_system_notification_local(self, row, email):
        """
        Creates Notification Log following the Interview style.
        """
        if frappe.db.exists("User", email):
            frappe.get_doc({
                "doctype": "Notification Log",
                "subject": f"Seat Allocation Status: {row.selection_status}",
                "for_user": email,
                "type": "Alert",
                "email_content": f"Your status for Seat Allocation {self.name} has been updated to <strong>{row.selection_status}</strong>.",
                "document_type": "Seat Allocation",
                "document_name": self.name,
                "from_user": frappe.session.user,
                "link": f"/my-applications?app={row.applicant_id}"
            }).insert(ignore_permissions=True)

    @frappe.whitelist()
    def unpublish_allocation(self):
        """
        Reverts the Seat Allocation status to 'Allocated', hiding results from students.
        Also reverts the Application Status of all applicants in the list to 'Merit Published'.
        """
        if self.status != "Published":
            frappe.throw("Seat Allocation is not currently published.")

        self.db_set("status", "Allocated")
        self.db_set("published_on", None)
        self.db_set("published_by", None)

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

    @frappe.whitelist()
    def run_promotion(self):
        """
        NLSAT Promotion Trigger: Promotes waitlisted candidates to available seats.
        """
        from slcm.admission.doctype.waitlist_rule.waitlist_promotion import promote_waitlist_without_rule
        any_promoted = promote_waitlist_without_rule(self.campus, self.admission_cycle, self.program_level)
        
        if any_promoted:
            frappe.msgprint("Waitlist promotion completed. Candidates have been promoted and offers generated.")
        else:
            frappe.msgprint("No vacancies found for promotion.")
        
        return {"any_promoted": any_promoted}

def run_allocation_background(name, user=None):
    """Background worker for large-scale seat allocation."""
    if user:
        frappe.set_user(user)
    
    doc = frappe.get_doc("Seat Allocation", name)
    doc.flags.is_background = True
    doc.allocate_seats()
    
    # Notify user on completion
    frappe.publish_realtime("msgprint", {
        "message": f"Seat Allocation {name} has been processed successfully in the background.",
        "title": "Allocation Complete",
        "indicator": "green"
    }, user=user)

def publish_allocation_background(name, user=None):
    """Background worker for large-scale result publication."""
    if user:
        frappe.set_user(user)
    
    doc = frappe.get_doc("Seat Allocation", name)
    doc.flags.is_background = True
    doc._publish_logic()
    
    # Notify user on completion
    frappe.publish_realtime("msgprint", {
        "message": f"Results for Seat Allocation {name} have been published and notifications are being sent.",
        "title": "Publication Complete",
        "indicator": "green"
    }, user=user)
