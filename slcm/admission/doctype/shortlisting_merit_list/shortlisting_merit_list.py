import frappe
import re
from frappe.model.document import Document

class ShortlistingMeritList(Document):
    def autoname(self):
        from frappe.model.naming import make_autoname
        if not self.admission_cycle or not self.campus:
            frappe.throw("Admission Cycle and Campus are required for naming.")

        # Use codes instead of names to keep it short
        cycle_code = frappe.db.get_value("Admission Cycle", self.admission_cycle, "cycle_code") or self.admission_cycle
        campus_code = frappe.db.get_value("Campus", self.campus, "campus_code") or self.campus
        
        cycle = cycle_code.replace(" ", "").upper()
        campus = campus_code.replace(" ", "").upper()
        level = (self.program_level or "ALL").upper()

        if self.program:
            program_code = frappe.db.get_value("Programme", self.program, "program_code") or self.program
            # Allow: - . , ( ) along with Alphanumeric
            prog = re.sub(r'[^A-Z0-9\-\.\,\(\)]', '', program_code.replace(" ", "").upper())
            # Use ignore_validate=True to allow parentheses and commas in naming series prefix
            self.name = make_autoname(f"SP-{cycle}-{campus}-{prog}-.####", ignore_validate=True)
        else:
            self.name = make_autoname(f"SP-{cycle}-{campus}-{level}-.####", ignore_validate=True)

    def clear_all_lists(self):
        tables = [
            "shortlist_applicants", "master_rank_list", "general_list", 
            "sc_list", "st_list", "obc_list", "ews_list",
            "karnataka_list", "women_list", "pwd_list"
        ]
        for t in tables:
            self.set(t, [])

    def clear_category_lists(self):
        tables = [
            "general_list", "sc_list", "st_list", "obc_list", "ews_list",
            "karnataka_list", "women_list", "pwd_list"
        ]
        for t in tables:
            self.set(t, [])

    def pull_from_merit_list(self, merit):
        if isinstance(merit, str):
            merit = frappe.get_doc("Merit List", merit)
            
        self.clear_all_lists()
        
        for row in merit.merit_applicants:
            self.append("shortlist_applicants", {
                "applicant_id": row.applicant_id,
                "candidate_name": row.candidate_name,
                "program": row.program,
                "nlsat_part_a_score": row.total_score, # Use total_score from Part A Ranking
                "percentile_score": row.get("percentile_score") or getattr(row, "percentile_score", 0),
                "shortlist_rank": row.overall_rank,
                "category_rank": row.category_rank,
                "actual_category": row.get("actual_category"),
                "date_of_birth": row.get("date_of_birth"),
                "shortlist_status": "Shortlisted"
            })
        self.total_candidates = len(self.shortlist_applicants)
        self.total_shortlisted = len([a for a in self.shortlist_applicants if a.shortlist_status == "Shortlisted"])
        
        # Automatically execute shortlisting logic to fill categories
        from slcm.admission.doctype.merit_generation.merit_service import execute_advanced_allocation_logic, _populate_category_lists
        execute_advanced_allocation_logic(self, is_shortlist_allocation=True)
        _populate_category_lists(self)
        
        # Re-calculate shortlisted count after allocation
        self.total_shortlisted = len([a for a in self.shortlist_applicants if a.shortlist_status == "Shortlisted"])
        
        self.status = "Allocated"
        self.save()

    @frappe.whitelist()
    def execute_shortlisting_logic(self):
        self.clear_category_lists()
        from slcm.admission.doctype.merit_generation.merit_service import execute_advanced_allocation_logic, _populate_category_lists
        execute_advanced_allocation_logic(self, is_shortlist_allocation=True)
        _populate_category_lists(self)
        self.total_shortlisted = len([a for a in self.shortlist_applicants if a.shortlist_status == "Shortlisted"])
        self.status = "Allocated"
        self.save()
        frappe.db.commit()

    @frappe.whitelist()
    def clear_generation_progress(self):
        cache_key = f"merit_generation_{self.admission_cycle}_{self.campus}_{self.program_level}_{self.program or ''}".replace(" ", "_")
        frappe.cache().delete_value(cache_key)
        frappe.cache().set_value(cache_key, {
            "percent": 0,
            "status": "In Progress",
            "description": "Starting Final Merit List generation...",
            "current": 0,
            "total": 100
        }, expires_in_sec=300)

    @frappe.whitelist()
    def generate_final_merit_list(self):
        """
        Triggers the Phase 2 Merit Generation (Entrance + Interview).
        """
        self.clear_generation_progress()

        from slcm.admission.doctype.merit_generation.merit_service import generate_merit_for_level
        merit_list = generate_merit_for_level(
            self.admission_cycle, 
            self.campus, 
            self.program_level, 
            program=self.program,
            processing_stage="Final Allotment Ranking"
        )
        return merit_list.name

    def on_update(self):
        self.sync_shortlisted_status_to_entrance_test_allocations()

    def on_trash(self):
        self.clear_shortlisted_status_in_entrance_test_allocations()

    def on_cancel(self):
        self.clear_shortlisted_status_in_entrance_test_allocations()

    def sync_shortlisted_status_to_entrance_test_allocations(self):
        """
        Synchronizes shortlisted_status field in Entrance Test Seat Allocation
        with candidate shortlist_status from this Shortlisting Merit List.
        """
        shortlisted_map = {}
        if self.shortlist_applicants:
            for row in self.shortlist_applicants:
                if row.applicant_id:
                    shortlisted_map[row.applicant_id] = row.shortlist_status or "Shortlisted"

        filters = {}
        if self.admission_cycle:
            filters["admission_cycle"] = self.admission_cycle
        if self.campus:
            filters["campus"] = self.campus
        if self.program_level:
            filters["program_level"] = self.program_level
        if self.program:
            filters["program"] = self.program

        allocations = frappe.get_all("Entrance Test Seat Allocation", filters=filters, fields=["name", "applicant", "shortlisted_status"])

        for alloc in allocations:
            app_id = alloc.applicant
            new_status = shortlisted_map.get(app_id, "")
            if (alloc.shortlisted_status or "") != new_status:
                frappe.db.set_value("Entrance Test Seat Allocation", alloc.name, "shortlisted_status", new_status, update_modified=False)

    def clear_shortlisted_status_in_entrance_test_allocations(self):
        """
        Clears shortlisted_status to blank ("") in Entrance Test Seat Allocation
        for all applicants associated with this Shortlisting Merit List.
        """
        applicant_ids = [row.applicant_id for row in (self.shortlist_applicants or []) if row.applicant_id]

        filters = {}
        if self.admission_cycle:
            filters["admission_cycle"] = self.admission_cycle
        if self.campus:
            filters["campus"] = self.campus
        if self.program_level:
            filters["program_level"] = self.program_level
        if self.program:
            filters["program"] = self.program

        allocations = frappe.get_all("Entrance Test Seat Allocation", filters=filters, fields=["name", "applicant"])
        alloc_names = set(a.name for a in allocations)

        if applicant_ids:
            by_app = frappe.get_all("Entrance Test Seat Allocation", filters={"applicant": ["in", applicant_ids]}, fields=["name"])
            for a in by_app:
                alloc_names.add(a.name)

        for alloc_name in alloc_names:
            frappe.db.set_value("Entrance Test Seat Allocation", alloc_name, "shortlisted_status", "", update_modified=False)

@frappe.whitelist()
def get_generation_progress(docname):
    """
    Returns cached progress for Final Merit List generation.
    """
    doc = frappe.get_doc("Shortlisting Merit List", docname)
    cache_key = f"merit_generation_{doc.admission_cycle}_{doc.campus}_{doc.program_level}_{doc.program or ''}".replace(" ", "_")
    progress = frappe.cache().get_value(cache_key) or {}
    
    if "status" not in progress:
        progress["status"] = "In Progress"
    if "percent" not in progress:
        progress["percent"] = 0
    if "description" not in progress:
        progress["description"] = "Starting Final Merit List generation..."

    return progress

@frappe.whitelist()
def download_merit_list(name, download_type, category=None):
    doc = frappe.get_doc("Shortlisting Merit List", name)
    
    columns = [
        "Applicant ID", "Candidate Name", "Rank", "Candidate Category", 
        "Category Rank", "Part A Score", "Part A Percentile", "Vertical Category", 
        "Compartmentalized Category", "Horizontal Categories", 
        "Allocation Type", "Shortlisted Category"
    ]
    
    def get_row(candidate):
        return [
            candidate.applicant_id,
            candidate.candidate_name,
            candidate.shortlist_rank,
            candidate.actual_category,
            candidate.category_rank,
            candidate.nlsat_part_a_score,
            candidate.get("percentile_score") or 0,
            candidate.vertical_category,
            candidate.compartmentalized_category,
            candidate.horizontal_categories,
            candidate.allocation_type,
            candidate.shortlist_category
        ]

    xlsx_data = {}

    if download_type == "Overall":
        sheet_name = "Overall Shortlisting Merit Rank List"
        rows = [columns]
        for cand in doc.shortlist_applicants:
            rows.append(get_row(cand))
        xlsx_data[sheet_name] = rows
    
    elif download_type == "Category Wise":
        category_map = {
            "General": ("Vertical Shortlisting Merit Rank List", "general_list"),
            "SC": ("SC Shortlisting Merit Rank List", "sc_list"),
            "ST": ("ST Shortlisting Merit Rank List", "st_list"),
            "OBC": ("OBC Shortlisting Merit Rank List", "obc_list"),
            "EWS": ("EWS Shortlisting Merit Rank List", "ews_list"),
            "Karnataka": ("Karnataka Shortlisting Merit Rank List", "karnataka_list"),
            "Women": ("Women Shortlisting Merit Rank List", "women_list"),
            "PWD": ("PWD Shortlisting Merit Rank List", "pwd_list")
        }
        
        if category and category != "All":
            if category in category_map:
                label, fieldname = category_map.get(category)
                rows = [columns]
                for cand in doc.get(fieldname):
                    rows.append(get_row(cand))
                xlsx_data[label] = rows
        else:
            # All categories in separate sheets
            for label, fieldname in category_map.values():
                table_data = doc.get(fieldname)
                if table_data:
                    rows = [columns]
                    for cand in table_data:
                        rows.append(get_row(cand))
                    xlsx_data[label] = rows

    if not xlsx_data or not any(len(rows) > 1 for rows in xlsx_data.values()):
        frappe.throw("No candidate records found for the selected criteria. Please ensure the shortlisting logic has been run.")

    from frappe.utils.xlsxutils import make_xlsx
    from io import BytesIO
    import xlsxwriter

    output = BytesIO()
    # Using the same options as Frappe's make_xlsx
    workbook = xlsxwriter.Workbook(output, {"constant_memory": True})
    
    for sheet_name, rows in xlsx_data.items():
        # make_xlsx adds a worksheet to the workbook
        make_xlsx(rows, sheet_name, wb=workbook)
    
    workbook.close()
    
    prog = doc.program or "Programme"
    year = frappe.db.get_value("Admission Cycle", doc.admission_cycle, "academic_year") or "Year"
    if download_type == "Overall":
        fname = f"overall shortlisting rank report - {prog} - {year}.xlsx"
    else:
        cat_label = category if category and category != "All" else "Category Wise"
        fname = f"{cat_label} shortlisting rank list - {prog} - {year}.xlsx"
    
    frappe.response['filename'] = fname
    frappe.response['filecontent'] = output.getvalue()
    frappe.response['type'] = 'binary'
