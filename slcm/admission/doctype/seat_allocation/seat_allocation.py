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
    Checks base Entrance Test Seat Allocation record category child table as the absolute source of truth.
    """
    if not applicant_id:    
        return []
        
    global _CATEGORY_CACHE
    if applicant_id in _CATEGORY_CACHE:
        return _CATEGORY_CACHE[applicant_id]

    cats = frappe.get_all("Applicant Category", filters={"parent": applicant_id, "parenttype": "Entrance Test Seat Allocation"}, fields=["category"])
    categories = [c.category for c in cats]
    
    # Check gender as fallback for Women category
    gender = frappe.db.get_value("Entrance Test Seat Allocation", applicant_id, "gender")
    if gender == "Female" and "Women" not in categories:
        categories.append("Women")
    
    # Normalize / Alias Layer
    normalized = []
    for c in categories:
        if not c: continue
        c_str = str(c).strip()
        if "Karnataka" in c_str: normalized.append("Karnataka")
        elif "Women" in c_str or "Female" in c_str: normalized.append("Women")
        elif "PWD" in c_str or "Person with Disability" in c_str: normalized.append("PWD")
        elif "OBC" in c_str or "BC" in c_str: normalized.append("OBC-NCL")
        elif "EWS" in c_str: normalized.append("EWS")
        elif "ST" in c_str: normalized.append("ST")
        elif "SC" in c_str: normalized.append("SC")
        else: normalized.append(c_str)

    final_categories = list(set(normalized))
    
    # If no vertical category was set, default to General
    vertical_set = {"SC", "ST", "OBC-NCL", "EWS"}
    if not any(v in final_categories for v in vertical_set):
        final_categories.append("General")

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
        policy_name = frappe.db.get_value("Programme Reservation Policy", {
            "admission_cycle": admission_cycle,
            "program": program,
            "status": ["!=", "Locked"]
        }, "name")

    priority_map = {}
    if policy_name:
        policy = frappe.get_doc("Programme Reservation Policy", policy_name)
        for row in policy.categories:
            priority_map[row.category_name] = int(row.priority or 999)

    return priority_map

class SeatAllocation(Document):
    def validate(self):
        if self.published_on and get_datetime(self.published_on) > get_datetime(now_datetime()):
            frappe.throw("Published On date cannot be in the future.")

    def autoname(self):
        from frappe.model.naming import make_autoname
        import re

        if not self.admission_cycle or not self.campus:
            frappe.throw("Admission Cycle and Campus are required for naming.")

        # Helper to strip non-allowed special characters. 
        # Allowed: Alphanumeric and '-', '#', '.', '/', '{', '}'
        def sanitize(val):
            if not val: return ""
            # 1. Replace spaces with nothing and convert to upper
            val = str(val).replace(" ", "").upper()
            # 2. Remove any character that is NOT A-Z, 0-9, -, #, ., /, {, }
            return re.sub(r'[^A-Z0-9\-#./{}]', '', val)

        cycle_code = frappe.db.get_value("Admission Cycle", self.admission_cycle, "cycle_code") or self.admission_cycle
        campus_code = frappe.db.get_value("Campus", self.campus, "campus_code") or self.campus
        
        cycle = sanitize(cycle_code)
        campus = sanitize(campus_code)
        level = sanitize(self.program_level or "ALL")

        if self.program:
            program_code = frappe.db.get_value("Programme", self.program, "program_code") or self.program
            prog = sanitize(program_code)
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
        selection_statuses = ["Selected", "Offer Issued", "Offer Accepted", "Accepted", "Fee Paid", "Payment Completed", "Enrolled", "Seat Selected"]
        
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
            app_ids = [getattr(row, "applicant_id", None) or getattr(row, "applicant", None) for row in self.selection_applicant]
            app_ids = [aid for aid in app_ids if aid]
            dob_map = {}
            if app_ids:
                dob_map = {r.name: r.date_of_birth for r in frappe.db.get_all("Applicant", filters={"name": ["in", app_ids]}, fields=["name", "date_of_birth"])}

            def get_save_sort_key(x):
                overall_rnk = flt(getattr(x, "overall_rank", None) or x.get("overall_rank") or 999999)
                part_b = flt(getattr(x, "nlsat_part_b_score", None) or x.get("nlsat_part_b_score") or 0)
                app_id = getattr(x, "applicant_id", None) or getattr(x, "applicant", None) or getattr(x, "name", "")
                dob_val = getattr(x, "date_of_birth", None) or x.get("date_of_birth") or dob_map.get(app_id)
                dob = str(dob_val) if dob_val else "9999-12-31"
                return (
                    overall_rnk,
                    -part_b,
                    dob,
                    app_id
                )

            self.selection_applicant.sort(key=get_save_sort_key)
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
            c_cat = row.get("compartmentalized_category")
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

        affected_programs = set()
        for row in (self.selection_applicant or []):
            old_status = before_map.get(row.name)
            new_status = row.selection_status
            
            if old_status and old_status != new_status:


                # Sync status to Applicant
                if row.applicant_id:
                    from slcm.api.service.offer_service import OfferService
                    OfferService.update_applicant_status(row.applicant_id, status=new_status)

                # Send notification for manual status change
                if self.status == "Published":
                    from slcm.admission.notification_service import notify_status_change
                    notify_status_change(
                        applicant=row.applicant_id,
                        program=row.program,
                        old_status=old_status,
                        new_status=new_status,
                        allocation_name=self.name,
                        admission_cycle=self.admission_cycle,
                        row=row
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
        When a Seat Allocation is deleted, reset the filled counts in the linked PRP
        and clear the Audit Logs to prevent link errors.
        """
        self.sync_filled_seats(reset_only=True)
        
        # Clear Audit Logs
        frappe.db.delete("Seat Allocation Audit Log", {"seat_allocation": self.name})

    def sync_filled_seats(self, reset_only=False):
        """
        Updates the linked Programme Reservation Policy for each program in this allocation
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
        policies = frappe.get_all("Programme Reservation Policy", filters={
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
            policy = frappe.get_doc("Programme Reservation Policy", policy_name)
            
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
                    fields_to_fetch.extend(["vertical_category", "horizontal_categories", "compartmentalized_category"])

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
                    c_cat = app.get("compartmentalized_category")
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
                "actual_category": row.get("actual_category"),
                "vertical_category": row.get("vertical_category"),
                "selection_status": "Draft"
            })

        self.save()
        frappe.db.commit()

    def _finish_allocation(self):
        """
        Handles final tallying, logging, sorting and saving after allocation logic.
        """
        # Calculate counters
        self.total_selected = 0
        self.total_waitlisted = 0
        self.total_rejected = 0
        
        selection_statuses = ["Selected", "Offer Issued", "Offer Accepted", "Accepted", "Fee Paid", "Payment Completed", "Enrolled", "Seat Selected"]
        
        for row in self.selection_applicant:
            if row.selection_status in selection_statuses:
                self.total_selected += 1
            elif row.selection_status == "Waitlisted":
                self.total_waitlisted += 1
            elif row.selection_status in ["Rejected", "Offer Declined", "Offer Expired", "Withdrawn"]:
                self.total_rejected += 1

        # Sort selection_applicant table
        status_priority = {"Selected": 1, "Waitlisted": 2, "Rejected": 3, "Draft": 4}
        
        app_ids = [getattr(row, "applicant_id", None) or getattr(row, "applicant", None) for row in self.selection_applicant]
        app_ids = [aid for aid in app_ids if aid]
        dob_map = {}
        if app_ids:
            dob_map = {r.name: r.date_of_birth for r in frappe.db.get_all("Applicant", filters={"name": ["in", app_ids]}, fields=["name", "date_of_birth"])}

        def get_allocation_sort_key(x):
            from frappe.utils import flt
            status_pri = status_priority.get(x.selection_status, 99)
            overall_rnk = flt(getattr(x, "overall_rank", None) or x.get("overall_rank") or 999999)
            part_b = flt(getattr(x, "nlsat_part_b_score", None) or x.get("nlsat_part_b_score") or 0)
            app_id = getattr(x, "applicant_id", None) or getattr(x, "applicant", None) or getattr(x, "name", "")
            dob_val = getattr(x, "date_of_birth", None) or x.get("date_of_birth") or dob_map.get(app_id)
            dob = str(dob_val) if dob_val else "9999-12-31"
            return (
                status_pri,
                overall_rnk,
                -part_b,
                dob,
                app_id
            )

        sorted_rows = sorted(self.selection_applicant, key=get_allocation_sort_key)
        
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
        from slcm.admission.doctype.merit_generation.merit_service import execute_advanced_allocation_logic, clear_category_cache
        clear_category_cache()
        if not self.admission_cycle:
            frappe.throw("Admission Cycle is required.")
        if not self.campus:
            frappe.throw("Campus is required.")
        if not self.merit_list:
            frappe.throw("Merit List is required.")
        if self.status == "Published":
            frappe.throw("Cannot re-run allocation after publish.")

        if not self.selection_applicant:
            self.pull_from_merit_list()

        # Execute dynamic consolidated logic from merit_service
        execute_advanced_allocation_logic(self, is_shortlist_allocation=False)
        self._finish_allocation()

    @frappe.whitelist()
    def get_waitlist_promotion_preview(self):
        """
        Simulates waitlist promotion and returns a mapping of:
        - Vacant seats (Expired/Rejected candidates)
        - Candidates to be promoted
        """
        from slcm.admission.doctype.waitlist_rule.waitlist_promotion import _get_program_quotas
        
        # 1. Identify all programs in this allocation
        programs = list(set([r.program for r in self.selection_applicant if r.program]))
        
        vacancies_data = []
        preview_data = []
        
        # Define statuses
        vacant_statuses = ["Offer Declined", "Offer Expired", "Withdrawn"]
        selection_statuses = ["Selected", "Offer Issued", "Offer Accepted", "Fee Paid", "Accepted", "Payment Completed", "Enrolled", "Seat Selected"]
        waitlist_statuses = ["Waitlisted"]
        
        for program in programs:
            quotas = _get_program_quotas(self.campus, self.admission_cycle, program)
            priority_map = get_category_priority(self.admission_cycle, self.campus, program)
            
            # Active pool = ONLY Waitlisted candidates
            active_pool = [
                r for r in self.selection_applicant
                if r.program == program and r.selection_status in waitlist_statuses
            ]
            
            # We also need to know who recently became vacant to show "against whom"
            recent_vacancies = [
                r for r in self.selection_applicant
                if r.program == program and r.selection_status in vacant_statuses
            ]
            
            if not active_pool and not recent_vacancies:
                continue

            # Calculate current active selected counts to compute net unfilled vacancies
            active_selected = [
                r for r in self.selection_applicant
                if r.program == program and r.selection_status in selection_statuses
            ]
            active_gen = len([r for r in active_selected if (r.vertical_category or "General") == "General"])
            active_reserved = {
                cat: len([r for r in active_selected if r.vertical_category == cat])
                for cat in quotas["Reserved"].keys()
            }
            net_vacancies = {
                "GEN": max(0, quotas["GEN"] - active_gen),
                "Reserved": {cat: max(0, quotas["Reserved"][cat] - active_reserved[cat]) for cat in quotas["Reserved"].keys()}
            }

            # Sort by Merit
            active_pool.sort(key=lambda x: (-(x.total_score or 0), x.overall_rank or 999999))
            
            # Record vacancies
            recent_vacancies.sort(key=lambda x: (-(x.total_score or 0), x.overall_rank or 999999))
            
            vacancies = {
                "GEN": 0,
                "Reserved": {k: 0 for k in quotas["Reserved"].keys()},
                "Compartmentalized": {}
            }
            
            for v in recent_vacancies:
                v_cat = v.get("vertical_category") or "General"
                comp_cat = v.get("compartmentalized_category")
                
                # Verify if there is an unfilled vacancy in this vertical category
                has_unfilled = False
                if v_cat == "General" and net_vacancies["GEN"] > 0:
                    has_unfilled = True
                    net_vacancies["GEN"] -= 1
                elif v_cat in net_vacancies["Reserved"] and net_vacancies["Reserved"][v_cat] > 0:
                    has_unfilled = True
                    net_vacancies["Reserved"][v_cat] -= 1
                    
                if not has_unfilled:
                    continue

                vacancies_data.append({
                    "applicant_id": v.applicant_id,
                    "candidate_name": v.candidate_name,
                    "program": v.program,
                    "selection_status": v.selection_status,
                    "allocated_category": v.allocated_category,
                    "total_score": v.total_score
                })
                # Tally up available seats from these specific vacancies
                if comp_cat:
                    key = (v_cat, comp_cat)
                    vacancies["Compartmentalized"][key] = vacancies["Compartmentalized"].get(key, 0) + 1
                else:
                    if v_cat == "General":
                        vacancies["GEN"] += 1
                    elif v_cat in vacancies["Reserved"]:
                        vacancies["Reserved"][v_cat] += 1

            # Simulate allocation to find who GETS a seat now
            promoted_this_prog = []
            for row in active_pool:
                assigned = False
                new_cat = None
                
                # Check if this waitlisted candidate matches a compartmentalized vacancy
                comp_cat = row.get("compartmentalized_category")
                v_cat = row.get("vertical_category") or "General"
                
                if comp_cat and vacancies["Compartmentalized"].get((v_cat, comp_cat), 0) > 0:
                    assigned = True
                    new_cat = v_cat
                    vacancies["Compartmentalized"][(v_cat, comp_cat)] -= 1
                elif vacancies["GEN"] > 0:
                    assigned = True
                    new_cat = "General"
                    vacancies["GEN"] -= 1
                else:
                    app_cats = get_applicant_categories(row.applicant_id)
                    valid_cats = sorted(
                        [c for c in app_cats if c in vacancies["Reserved"]],
                        key=lambda c: priority_map.get(c, 999)
                    )
                    for cat in valid_cats:
                        if vacancies["Reserved"][cat] > 0:
                            assigned = True
                            new_cat = cat
                            vacancies["Reserved"][cat] -= 1
                            break
                
                if assigned:
                    # Construct display category for preview
                    # Use their compartmentalized and horizontal categories if present
                    c_trait = row.get("compartmentalized_category")
                    h_traits_str = row.get("horizontal_categories")
                    
                    parts = [new_cat]
                    if c_trait:
                        parts.append(c_trait)
                    if h_traits_str:
                        h_traits = sorted([c.strip() for c in h_traits_str.split(",") if c.strip()])
                        parts.extend(h_traits)
                    
                    display_cat = " + ".join(parts)
                    
                    promoted_this_prog.append({
                        "applicant_id": row.applicant_id,
                        "candidate_name": row.candidate_name,
                        "program": program,
                        "new_status": "Selected",
                        "allocated_category": display_cat,
                        "overall_rank": row.overall_rank,
                        "total_score": row.total_score
                    })
            
            for i, promoted in enumerate(promoted_this_prog):
                vacant_info = "Available Seat"
                v = None
                if i < len(recent_vacancies):
                    v = recent_vacancies[i]
                    vacant_info = f"{v.candidate_name} ({v.selection_status})"
                
                promoted["vacant_seat_info"] = vacant_info
                
                # Find all eligible candidates for this specific vacancy slot
                eligible_candidates = []
                if v:
                    v_cat = v.get("vertical_category") or "General"
                    v_comp = v.get("compartmentalized_category")
                    
                    for candidate in active_pool:
                        c_cat = candidate.get("vertical_category") or "General"
                        c_comp = candidate.get("compartmentalized_category")
                        
                        # Check vertical match
                        vertical_match = False
                        if v_cat == "General":
                            vertical_match = True
                        else:
                            cand_cats = get_applicant_categories(candidate.applicant_id)
                            if v_cat in cand_cats:
                                vertical_match = True
                                
                        # Check compartmentalized match
                        comp_match = False
                        if not v_comp:
                            comp_match = True
                        else:
                            if c_comp == v_comp:
                                comp_match = True
                                
                        if vertical_match and comp_match:
                            eligible_candidates.append({
                                "applicant_id": candidate.applicant_id,
                                "candidate_name": candidate.candidate_name,
                                "overall_rank": candidate.overall_rank,
                                "total_score": candidate.total_score
                            })
                
                # Ensure the auto-selected candidate is always in the list of eligible candidates
                if not any(ec["applicant_id"] == promoted["applicant_id"] for ec in eligible_candidates):
                    eligible_candidates.append({
                        "applicant_id": promoted["applicant_id"],
                        "candidate_name": promoted["candidate_name"],
                        "overall_rank": promoted["overall_rank"],
                        "total_score": promoted["total_score"]
                    })
                
                # Sort eligible candidates by merit (highest score first, then lowest rank)
                eligible_candidates.sort(key=lambda x: (-(x["total_score"] or 0), x["overall_rank"] or 999999))
                promoted["eligible_candidates"] = eligible_candidates
                
                preview_data.append(promoted)

        return {
            "vacancies": vacancies_data,
            "promotions": preview_data
        }

    @frappe.whitelist()
    def run_promotion(self, promoted_applicants=None):
        """
        Executes the promotion for selected applicants.
        """
        if promoted_applicants and isinstance(promoted_applicants, str):
            import json
            promoted_applicants = json.loads(promoted_applicants)

        if promoted_applicants:
            from slcm.admission.doctype.admission_audit_log.audit_service import log_seat_allocation_action
            from slcm.admission.notification_service import notify_status_change
            from slcm.api.service.offer_service import OfferService
            
            promoted_ids = [p.get("applicant_id") for p in promoted_applicants]
            affected = False
            promoted_rows = []
            
            for row in self.selection_applicant:
                if row.applicant_id in promoted_ids and row.selection_status == "Waitlisted":
                    intended = next((p for p in promoted_applicants if p["applicant_id"] == row.applicant_id), {})
                    
                    old_status = row.selection_status
                    row.selection_status = "Selected"
                    if intended.get("allocated_category"):
                        row.vertical_category = intended["allocated_category"].split("+")[0].strip()
                        row.allocated_category = intended["allocated_category"]
                    
                    affected = True
                    promoted_rows.append((row, old_status))

            if affected:
                # Save the new status to the database so that generate_offer pre-flight checks pass
                self.save(ignore_permissions=True)
                
                for row, old_status in promoted_rows:
                    log_seat_allocation_action(
                        seat_allocation=self.name,
                        admission_cycle=self.admission_cycle,
                        applicant=row.applicant_id,
                        program=row.program,
                        action_type="Waitlist Promoted",
                        old_value=old_status,
                        new_value="Selected",
                        remarks="Promoted via Interactive Waitlist Manager."
                    )
                    
                    OfferService.update_applicant_status(row.applicant_id, status="Selected")
                    notify_status_change(row.applicant_id, row.program, old_status, "Selected", self.name, self.admission_cycle)
                    
                    try:
                        OfferService.generate_offer(
                            applicant=row.applicant_id,
                            campus=self.campus,
                            program=row.program,
                            cycle=self.admission_cycle
                        )
                    except Exception as e:
                        frappe.log_error(f"Manual Promotion Offer Generation Failed: {str(e)}", "Waitlist Promotion")
                
                self.save(ignore_permissions=True)
                frappe.db.commit()
                return True
        else:
            from slcm.admission.doctype.waitlist_rule.waitlist_promotion import promote_waitlist_without_rule
            return promote_waitlist_without_rule(self.campus, self.admission_cycle, self.program_level)

    @frappe.whitelist()
    def publish_allocation(self):
        """
        Marks the allocation as Published, records the timestamp,
        advances candidate application statuses, and sends notifications.
        """
        from frappe.utils import now
        self.status = "Published"
        self.published_on = now()
        self.published_by = frappe.session.user
        self.save()

        # Update Applicant status and send notifications
        for i, row in enumerate(self.selection_applicant):
            if not row.applicant_id:
                continue

            # Determine and update Applicant status
            new_status = "Seat Selected"
            if row.selection_status == "Selected":
                new_status = "Seat Selected"
            elif row.selection_status == "Waitlisted":
                new_status = "Seat Waitlisted"
            elif row.selection_status == "Rejected":
                new_status = "Seat Rejected"

            frappe.db.set_value("Applicant", row.applicant_id, "status", new_status)

            # Retrieve candidate email
            applicant_email = frappe.db.get_value("Applicant", row.applicant_id, "email")
            if applicant_email:
                try:
                    self._send_allocation_notification(row, applicant_email)
                except Exception:
                    frappe.log_error(frappe.get_traceback(), f"Seat Allocation Notification Failed for {row.applicant_id}")

            # Periodically commit to manage resources
            if i % 10 == 0:
                frappe.db.commit()

        frappe.db.commit()
        frappe.msgprint(frappe._("Seat Allocation has been published successfully, and notification emails have been queued."), indicator="green")

    def _send_allocation_notification(self, row, email):
        """
        Queues email using 'Seat Allocation Result Notification' template and creates a system notification alert.
        """
        # 1. Email Notification
        template_name = "Seat Allocation Result Notification"
        if frappe.db.exists("Email Template", template_name):
            template = frappe.get_doc("Email Template", template_name)
            
            # Inject campus and cycle into the row context for template interpolation
            row.campus = self.campus
            row.admission_cycle = self.admission_cycle

            args = {"doc": row}
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
                sender = None
                if template.get("email_account"):
                    sender = frappe.db.get_value("Email Account", template.get("email_account"), "email_id") or template.get("email_account")

                frappe.sendmail(
                    recipients=[email],
                    sender=sender,
                    cc=cc_list,
                    subject=subject,
                    message=message,
                    reference_doctype="Seat Allocation",
                    reference_name=self.name,
                    now=False
                )

        # 2. System Notification Log
        if frappe.db.exists("User", email):
            message_body = f"""
                <p>The Seat Allocation for <strong>"{self.name}"</strong> has been published.</p>
                <p>Your status: <strong>{row.selection_status}</strong></p>
                <p><a href="/my-applications?app={row.applicant_id}" style="color: #1a3c6e; font-weight: bold;">Click here to view your seat allocation details.</a></p>
            """
            
            frappe.get_doc({
                "doctype": "Notification Log",
                "subject": "Seat Allocation Published",
                "for_user": email,
                "type": "Alert",
                "email_content": message_body,
                "document_type": "Seat Allocation",
                "document_name": self.name,
                "from_user": frappe.session.user,
                "link": f"/my-applications?app={row.applicant_id}"
            }).insert(ignore_permissions=True)

    @frappe.whitelist()
    def unpublish_allocation(self):
        """
        Reverts the allocation status to Allocated and reverts applicant status.
        """
        self.status = "Allocated"
        self.save()

        # Revert Applicant status back to their merit statuses
        for row in self.selection_applicant:
            if not row.applicant_id:
                continue

            new_status = "Merit Published"
            if self.merit_list:
                merit_status = frappe.db.get_value("Merit List Applicant", 
                    {"parent": self.merit_list, "applicant_id": row.applicant_id}, 
                    "status"
                )
                if merit_status == "Selected":
                    new_status = "Merit Selected"
                elif merit_status == "Waitlisted":
                    new_status = "Merit Waitlisted"
                elif merit_status == "Rejected":
                    new_status = "Merit Rejected"
            else:
                if row.selection_status == "Selected":
                    new_status = "Merit Selected"
                elif row.selection_status == "Waitlisted":
                    new_status = "Merit Waitlisted"
                elif row.selection_status == "Rejected":
                    new_status = "Merit Rejected"

            frappe.db.set_value("Applicant", row.applicant_id, "status", new_status)

        frappe.db.commit()
        frappe.msgprint(frappe._("Seat Allocation has been unpublished and candidate statuses reverted."), indicator="orange")


@frappe.whitelist()
def download_allocation(name):
    doc = frappe.get_doc("Seat Allocation", name)
    
    columns = [
        "Applicant ID", "Candidate Name", "Rank", "Category", 
        "Selection Status", "Total Score", "Allocated Category", "Vertical Category",
        "Horizontal Categories", "Compartmentalized Category", "Allocation Type"
    ]
    
    def get_row(candidate):
        return [
            candidate.applicant_id,
            candidate.candidate_name,
            candidate.overall_rank,
            candidate.actual_category,
            candidate.selection_status,
            candidate.total_score,
            candidate.allocated_category,
            candidate.vertical_category,
            candidate.horizontal_categories,
            candidate.compartmentalized_category,
            candidate.allocation_type
        ]

    rows = [columns]
    for cand in doc.selection_applicant:
        rows.append(get_row(cand))

    if len(rows) <= 1:
        frappe.throw("No candidate records found in this allocation.")

    from frappe.utils.xlsxutils import make_xlsx
    from io import BytesIO
    import xlsxwriter

    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {"constant_memory": True})
    make_xlsx(rows, "Seat Allocation", wb=workbook)
    workbook.close()
    
    prog = doc.program or "Programme"
    year = frappe.db.get_value("Admission Cycle", doc.admission_cycle, "academic_year") or "Year"
    frappe.response['filename'] = f"seat allocation report - {prog} - {year}.xlsx"
    frappe.response['filecontent'] = output.getvalue()
    frappe.response['type'] = 'binary'
