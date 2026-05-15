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
            program_code = frappe.db.get_value("Program", self.program, "program_code") or self.program
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
                "shortlist_rank": row.overall_rank,
                "category_rank": row.category_rank,
                "actual_category": row.get("actual_category"),
                "date_of_birth": row.get("date_of_birth"),
                "shortlist_status": "Shortlisted"
            })
        self.total_candidates = len(self.shortlist_applicants)
        self.total_shortlisted = len([a for a in self.shortlist_applicants if a.shortlist_status == "Shortlisted"])
        
        # Automatically execute shortlisting logic to fill categories
        from slcm.admission.doctype.merit_rule.merit_service import execute_advanced_allocation_logic, _populate_category_lists
        execute_advanced_allocation_logic(self, is_shortlist_allocation=True)
        _populate_category_lists(self)
        
        # Re-calculate shortlisted count after allocation
        self.total_shortlisted = len([a for a in self.shortlist_applicants if a.shortlist_status == "Shortlisted"])
        
        self.status = "Allocated"
        self.save()

    @frappe.whitelist()
    def execute_shortlisting_logic(self):
        from slcm.admission.doctype.merit_rule.merit_service import execute_advanced_allocation_logic, _populate_category_lists
        execute_advanced_allocation_logic(self, is_shortlist_allocation=True)
        _populate_category_lists(self)
        self.total_shortlisted = len([a for a in self.shortlist_applicants if a.shortlist_status == "Shortlisted"])
        self.status = "Allocated"
        self.save()
        frappe.db.commit()

    @frappe.whitelist()
    def generate_final_merit_list(self):
        """
        Triggers the Phase 2 Merit Generation (Entrance + Interview).
        """
        from slcm.admission.doctype.merit_rule.merit_service import generate_merit_for_level
        merit_list = generate_merit_for_level(
            self.admission_cycle, 
            self.campus, 
            self.program_level, 
            program=self.program,
            processing_stage="Final Allotment Ranking"
        )
        return merit_list.name

@frappe.whitelist()
def download_merit_list(name, download_type, category=None):
    doc = frappe.get_doc("Shortlisting Merit List", name)
    
    columns = [
        "Rank", "Applicant ID", "Candidate Name", "Category Rank", 
        "Actual Category", "Part A Score", "Vertical Category", 
        "Compartmentalized Category", "Horizontal Categories", 
        "Allocation Type", "Shortlisted Category"
    ]
    
    def get_row(candidate):
        return [
            candidate.shortlist_rank,
            candidate.applicant_id,
            candidate.candidate_name,
            candidate.category_rank,
            candidate.actual_category,
            candidate.nlsat_part_a_score,
            candidate.vertical_category,
            candidate.compartmentalized_category,
            candidate.horizontal_categories,
            candidate.allocation_type,
            candidate.shortlist_category
        ]

    xlsx_data = {}

    if download_type == "Overall":
        sheet_name = "Overall Master List"
        rows = [columns]
        for cand in doc.shortlist_applicants:
            rows.append(get_row(cand))
        xlsx_data[sheet_name] = rows
    
    elif download_type == "Category Wise":
        category_map = {
            "General": ("General List", "general_list"),
            "SC": ("SC List", "sc_list"),
            "ST": ("ST List", "st_list"),
            "OBC": ("OBC List", "obc_list"),
            "EWS": ("EWS List", "ews_list"),
            "Karnataka": ("Karnataka Students", "karnataka_list"),
            "Women": ("Women Merit List", "women_list"),
            "PWD": ("PWD Merit List", "pwd_list")
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
    
    frappe.response['filename'] = f"{doc.name}_{download_type}.xlsx"
    frappe.response['filecontent'] = output.getvalue()
    frappe.response['type'] = 'binary'
