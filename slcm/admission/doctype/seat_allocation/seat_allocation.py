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
        When a Seat Allocation is deleted, reset the filled counts in the linked PRP
        and clear the Audit Logs to prevent link errors.
        """
        self.sync_filled_seats(reset_only=True)
        
        # Clear Audit Logs
        frappe.db.delete("Seat Allocation Audit Log", {"seat_allocation": self.name})

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
        from slcm.admission.doctype.merit_rule.merit_service import clear_category_cache
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

        self._execute_nlsat_allocation()
        self._finish_allocation()

    def _execute_nlsat_allocation(self):
        from slcm.admission.doctype.merit_rule.merit_service import _assign_seat_to_applicant, _execute_recursive_displacement, get_applicant_categories, _get_categorized_traits, clear_category_cache, _rank_applicants, _check_percentile_eligibility, _has_trait
        import math
        clear_category_cache()
        """
        NLSAT specific seat allocation logic based on document rules.
        Phases:
        1. Vertical Allocation (General, then Reserved)
        2. Karnataka Sub-quota Adjustments (with recursive displacement)
        3. Horizontal Reservation (PWD, then Women)
        """

        child_table = None
        status_field = "status"
        if hasattr(self, "shortlist_applicants"):
            child_table = "shortlist_applicants"
            status_field = "shortlist_status"
        elif hasattr(self, "selection_applicant"):
            child_table = "selection_applicant"
            status_field = "selection_status"
        elif hasattr(self, "merit_applicants"):
            child_table = "merit_applicants"
            status_field = "status"

        if not child_table:
            return False

        applicants_list = getattr(self, child_table)

        # Initial Rank
        processing_stage = "Final Allotment Ranking"
        _rank_applicants(applicants_list, use_advanced_ranking=True, processing_stage=processing_stage)

        grouped_by_program = {}
        for row in applicants_list:
            # Ignore already rejected candidates if they were explicitly rejected (e.g. by a previous manual step)
            if getattr(row, status_field, "") == "Rejected" and not ignore_seat_limits:
                continue
            grouped_by_program.setdefault(row.program, []).append(row)

        for program, applicants in grouped_by_program.items():
            policy_name = frappe.db.get_value("Program Reservation Policy", {
                "admission_cycle": self.admission_cycle,
                "program": program
            }, "name")

            if not policy_name: continue
            policy = frappe.get_doc("Program Reservation Policy", policy_name)
            if not policy.enable_advanced_shortlisting: 
                continue


            # 1. Setup Targets from Policy
            vertical_targets = {}
            for v in policy.categories:
                v_cat_name = v.category_name or "General"
                seats = v.seats or 0

                vertical_targets[v_cat_name] = {
                    "seats": seats or 0,
                    "original_seats": v.seats or 0,
                    "filled": 0,
                    "min_percentile": v.min_percentile,
                    "priority": v.priority or 0
                }

            ka_targets = {}
            ka_percentage = 25.0 # Default NLSAT requirement
            common_ka_row = next((c for c in policy.compartmental_reservations if c.category_name == "Karnataka"), None)
            if common_ka_row:
                ka_percentage = common_ka_row.percentage or 25.0

            for v_cat, v_info in vertical_targets.items():
                ka_targets[v_cat] = {
                    "seats": int((v_info["seats"] * ka_percentage) / 100.0),
                    "original_seats": int((v_info["original_seats"] * ka_percentage) / 100.0),
                    "filled": 0
                }

            horizontal_targets = {}
            for h in policy.horizontal_reservations:
                horizontal_targets[h.category_name] = {
                    "seats": h.seats or 0,
                    "original_seats": h.seats or 0,
                    "filled": 0
                }

            # 2. Filter by Percentile Eligibility (Requirement I.6)
            eligible_applicants = []
            for app in applicants:
                if _check_percentile_eligibility(app, vertical_targets):
                    eligible_applicants.append(app)
                else:
                    setattr(app, status_field, "Rejected")
                    app.allocation_type = "Not Allocated"
                    app.remarks = "Did not meet minimum percentile threshold"

            unallocated = eligible_applicants[:]
            allocated_list = []

            # --- PHASE 1: INITIAL VERTICAL ALLOTMENT ---
            # Requirement: General first, then reserved.
            ordered_cats = ["General"] + sorted([c for c in vertical_targets.keys() if c != "General"], 
                                              key=lambda x: vertical_targets[x]["priority"])

            for v_cat in ordered_cats:
                v_info = vertical_targets[v_cat]
                for app in unallocated[:]:
                    v_traits, _, _ = _get_categorized_traits(app.applicant_id)
                    actual_v = v_traits[0] if v_traits else "General"

                    # Rule: Top merit get General seats regardless of their category (Merit Migration)
                    can_take_seat = (v_cat == "General") or (actual_v == v_cat)

                    if can_take_seat and v_info["filled"] < v_info["seats"]:
                        alloc_type = "Open" if v_cat == "General" else "Reserved"
                        _assign_seat_to_applicant(app, v_cat, alloc_type, allocated_list, unallocated, v_info, status_field)

            # --- PHASE 2: KARNATAKA SUB-QUOTA ADJUSTMENT ---
            # Requirement: Displace lowest AI in the pool with next highest Karnataka student.
            for v_cat in ordered_cats:
                v_info = vertical_targets[v_cat]
                ka_info = ka_targets.get(v_cat)
                if not ka_info or ka_info["seats"] <= 0: continue

                # Count current Karnataka coverage in this pool
                ka_in_v = [a for a in allocated_list if a.vertical_category == v_cat and _has_trait(a.applicant_id, "Karnataka")]
                deficit = ka_info["seats"] - len(ka_in_v)

                if deficit > 0:
                    potential_ka = [u for u in unallocated if _has_trait(u.applicant_id, "Karnataka")]
                    # Filter potential Karnataka by category if not General
                    if v_cat != "General":
                        potential_ka = [u for u in potential_ka if v_cat in get_applicant_categories(u.applicant_id)]

                    for in_cand in potential_ka:
                        if deficit <= 0: break

                        eligible_out = [a for a in allocated_list if a.vertical_category == v_cat and not _has_trait(a.applicant_id, "Karnataka")]
                        if eligible_out:
                            # Sort by lowest merit rank for displacement (highest rank number)
                            eligible_out.sort(key=lambda x: -(x.overall_rank or 999999))
                            out_cand = eligible_out[0]

                            # Recursive Displacement: Save out_cand in their reserved category if possible
                            _execute_recursive_displacement(out_cand, allocated_list, unallocated, vertical_targets, status_field)
                            _assign_seat_to_applicant(in_cand, v_cat, "Open" if v_cat == "General" else "Reserved", allocated_list, unallocated, v_info, status_field)
                            deficit -= 1

            # --- PHASE 3: HORIZONTAL RESERVATION (PWD & Women) ---
            h_order = ["PWD", "Women"]
            for h_cat in h_order:
                h_info = horizontal_targets.get(h_cat)
                if not h_info or h_info["seats"] <= 0: continue

                h_count = len([a for a in allocated_list if _has_trait(a.applicant_id, h_cat)])
                deficit = h_info["seats"] - h_count

                if deficit > 0:
                    potential = [u for u in unallocated if _has_trait(u.applicant_id, h_cat)]
                    for in_cand in potential:
                        if deficit <= 0: break

                        v_traits, _, _ = _get_categorized_traits(in_cand.applicant_id)
                        v_belong = v_traits[0] if v_traits else "General"

                        # Try to displace lowest AI candidate in the same vertical category
                        eligible_out = [a for a in allocated_list if a.vertical_category == v_belong 
                                        and not _has_trait(a.applicant_id, "Karnataka")
                                        and not _has_trait(a.applicant_id, h_cat)]

                        if eligible_out:
                            eligible_out.sort(key=lambda x: -(x.overall_rank or 999999))
                            out_cand = eligible_out[0]

                            _execute_recursive_displacement(out_cand, allocated_list, unallocated, vertical_targets, status_field)
                            _assign_seat_to_applicant(in_cand, v_belong, "Open" if v_belong == "General" else "Reserved", allocated_list, unallocated, vertical_targets[v_belong], status_field)
                            deficit -= 1

            # (Phase 4 Waitlist Allocation removed - now handled natively in seat_allocation.py)

        # --- POPULATE SUMMARY ---
        if hasattr(self, "category_summary"):
            self.set("category_summary", [])

            # 1. Main Vertical Categories
            for v_cat in ordered_cats:
                v_info = vertical_targets[v_cat]
                self.append("category_summary", {
                    "category": v_cat,
                    "seats": v_info.get("original_seats", 0),
                "multiplier": 1.0,
                    "required": v_info["seats"],
                    "actually_allocated": v_info["filled"],
                    # Backward compatibility for old UI
                    "total_seats": v_info.get("original_seats", 0),
                    "allocated_seats": v_info["filled"],
                    "vacant_seats": max(0, v_info["seats"] - v_info["filled"])
                })

            # 2. Horizontal (PWD, Women)
            for h_cat in ["PWD", "Women"]:
                h_info = horizontal_targets.get(h_cat)
                if h_info:
                    h_filled = len([a for a in allocated_list if _has_trait(a.applicant_id, h_cat)])
                    self.append("category_summary", {
                        "category": h_cat,
                        "seats": h_info.get("original_seats", 0),
                "multiplier": 1.0,
                        "required": h_info["seats"],
                        "actually_allocated": h_filled,
                        # Backward compatibility
                        "total_seats": h_info.get("original_seats", 0),
                        "allocated_seats": h_filled,
                        "vacant_seats": max(0, h_info["seats"] - h_filled)
                    })
            
            # 3. Karnataka Breakdown
            for v_cat in ordered_cats:
                ka_info = ka_targets.get(v_cat)
                if ka_info:
                    ka_in_v = len([a for a in allocated_list if a.vertical_category == v_cat and _has_trait(a.applicant_id, "Karnataka")])
                    self.append("category_summary", {
                        "category": f"Karnataka ({v_cat})",
                        "seats": ka_info.get("original_seats", 0),
                        "multiplier": 1.0,
                        "required": ka_info["seats"],
                        "actually_allocated": ka_in_v,
                        "total_seats": ka_info.get("original_seats", 0),
                        "allocated_seats": ka_in_v,
                        "vacant_seats": max(0, ka_info["seats"] - ka_in_v)
                    })
            
            # 4. Karnataka (Common)
            ka_total_orig = sum(k.get("original_seats", 0) for k in ka_targets.values())
            ka_total_req = sum(k.get("seats", 0) for k in ka_targets.values())
            ka_total_filled = len([a for a in allocated_list if _has_trait(a.applicant_id, "Karnataka")])
            if ka_total_req > 0:
                self.append("category_summary", {
                    "category": "Karnataka (Common)",
                    "seats": ka_total_orig,
                    "multiplier": 1.0,
                    "required": ka_total_req,
                    "actually_allocated": ka_total_filled,
                    "total_seats": ka_total_orig,
                    "allocated_seats": ka_total_filled,
                    "vacant_seats": max(0, ka_total_req - ka_total_filled)
                })
            # Explicitly Reject unallocated before Waitlist Phase
            for u in unallocated:
                setattr(u, status_field, "Rejected")
                u.allocation_type = "Not Allocated"
                u.remarks = "Not enough merit to secure a seat"
                u.vertical_category = ""

            # --- PHASE 4: WAITLIST ALLOCATION ---
            for v_cat in ordered_cats:
                v_info = vertical_targets[v_cat]
                w_limit = v_info.get("waitlist_seats", 0)
                if w_limit <= 0: continue
                
                # Find remaining unallocated who are eligible for this category
                potential_w = [u for u in unallocated if getattr(u, status_field) == "Rejected"]
                if v_cat != "General":
                    potential_w = [u for u in potential_w if v_cat in get_applicant_categories(u.applicant_id)]
                
                # Merit sort
                potential_w.sort(key=lambda x: (-(float(getattr(x, "total_score", 0) or 0)), (x.overall_rank or 999999)))
                
                for w_cand in potential_w:
                    if v_info["waitlist_filled"] < w_limit:
                        setattr(w_cand, status_field, "Waitlisted")
                        w_cand.allocation_type = "Reserved" if v_cat != "General" else "Open"
                        w_cand.vertical_category = v_cat
                        w_cand.remarks = f"Waitlisted under {v_cat} quota"
                        
                        # Sync combined category string
                        _assign_seat_to_applicant(w_cand, v_cat, w_cand.allocation_type, [], [], {"filled": 0}, status_field)
                        # Reset the status back to Waitlisted since _assign sets it to Selected/Shortlisted
                        setattr(w_cand, status_field, "Waitlisted")
                        
                        v_info["waitlist_filled"] += 1
