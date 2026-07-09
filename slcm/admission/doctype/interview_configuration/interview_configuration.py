# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import re
import math
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now


class InterviewConfiguration(Document):

    def validate(self):
        pattern = re.compile(r"^[1-9]\d*:[1-9]\d*$")
        
        if self.enter_domestic_ratio:
            if not pattern.match(str(self.enter_domestic_ratio)):
                frappe.throw(_("Enter Domestic Ratio must be in the format 'X:Y' (e.g. '3:1') where both X and Y are positive integers."))

        if self.enter_international_ratio:
            if not pattern.match(str(self.enter_international_ratio)):
                frappe.throw(_("Enter International Ratio must be in the format 'X:Y' (e.g. '3:1') where both X and Y are positive integers."))

    def before_save(self):
        if not self.configuration_code:
            yr = getdate().strftime("%y")
            code = frappe.generate_hash("InterviewConfiguration", 8).upper()[:8]
            self.configuration_code = f"IVC-{yr}-{code}"

        # Update counts on save as well
        if self.academic_year and self.campus and self.admission_cycle and self.program:
            try:
                self.calculate_and_set_counts()
            except Exception:
                pass

    def calculate_and_set_counts(self):
        all_apps = self.get_eligible_applicants()
        domestic_count = 0
        international_count = 0
        for app in all_apps:
            if app.get("foriegn_national") == "Yes":
                international_count += 1
            else:
                domestic_count += 1

        if self.applicant_type == "Domestic Applicants":
            self.domestic_applicants_count = domestic_count
            self.international_applicants_count = 0
        elif self.applicant_type == "International Applicants":
            self.domestic_applicants_count = 0
            self.international_applicants_count = international_count
        else:
            self.domestic_applicants_count = domestic_count
            self.international_applicants_count = international_count

    @frappe.whitelist()
    def fetch_applicant_counts(self):
        self.calculate_and_set_counts()
        self.db_set("domestic_applicants_count", self.domestic_applicants_count)
        self.db_set("international_applicants_count", self.international_applicants_count)
        return {
            "domestic_applicants_count": self.domestic_applicants_count,
            "international_applicants_count": self.international_applicants_count
        }

    def get_total_seats(self, applicant_type=None):
        if not applicant_type:
            applicant_type = self.applicant_type

        program_names = [p.program for p in self.program] if self.program else []
        if not program_names:
            return 0

        if applicant_type == "Both":
            return self.get_total_seats("Domestic Applicants") + self.get_total_seats("International Applicants")

        total_seats = 0
        field_to_fetch = "international_seats" if applicant_type == "International Applicants" else "total_seats"

        for prog in program_names:
            seats = frappe.db.get_value("Program Reservation Policy", {
                "program": prog,
                "admission_cycle": self.admission_cycle,
                "campus": self.campus,
                "status": "Active"
            }, field_to_fetch)
            if not seats:
                # Fallback to any status if no Active policy found
                seats = frappe.db.get_value("Program Reservation Policy", {
                    "program": prog,
                    "admission_cycle": self.admission_cycle,
                    "campus": self.campus
                }, field_to_fetch)
            total_seats += (seats or 0)
        return total_seats

    def get_eligible_applicants(self):
        program_names = [p.program for p in self.program] if self.program else []
        if not program_names:
            return []

        query_args = {
            "academic_year": self.academic_year,
            "campus": self.campus,
            "admission_cycle": self.admission_cycle,
            "programs": program_names
        }

        program_filter = "AND app.program IN %(programs)s"

        # Source 1: National Test (Direct)
        source1_query = f"""
            SELECT
                app.name          AS applicant_id,
                app.candidate_name,
                app.email,
                app.gender,
                app.program,
                app.program_level,
                app.entrance_test,
                app.intereview,
                app.foriegn_national,
                0.0               AS entrance_test_score,
                0.0               AS part_a_score
            FROM `tabApplicant` app
            INNER JOIN `tabEligibility Evaluation` ee
                    ON ee.applicant_name = app.name
            INNER JOIN `tabProgram` p
                    ON p.name = app.program
            WHERE
                app.academic_year    = %(academic_year)s
                AND app.campus       = %(campus)s
                AND app.admission_cycle = %(admission_cycle)s
                {program_filter}
                AND app.status != 'Rejected'
                AND app.name NOT IN (SELECT applicant_id FROM `tabInterview Applicant`)
                AND ee.exempts_entrance_test = 1
                AND (ee.exempts_interview IS NULL OR ee.exempts_interview = 0)
                AND p.intereview = 1
        """

        # Source 2: Entrance Test Passers
        source2_query = f"""
            SELECT
                app.name          AS applicant_id,
                app.candidate_name,
                app.email,
                app.gender,
                app.program,
                app.program_level,
                app.entrance_test,
                app.intereview,
                app.foriegn_national,
                COALESCE(etsa.part_b_total_marks_scored, 0) AS entrance_test_score,
                COALESCE(etsa.part_a_total_marks_scored, 0) AS part_a_score
            FROM `tabEntrance Test Seat Allocation` etsa
            INNER JOIN `tabApplicant` app
                    ON app.name = etsa.applicant
            INNER JOIN `tabProgram` p
                    ON p.name = app.program
            WHERE
                etsa.academic_year    = %(academic_year)s
                AND etsa.campus       = %(campus)s
                AND etsa.admission_cycle = %(admission_cycle)s
                {program_filter}
                AND etsa.result_status   = 'Pass'
                AND app.status != 'Rejected'
                AND app.name NOT IN (SELECT applicant_id FROM `tabInterview Applicant`)
                AND COALESCE(etsa.exempts_interview, 0) = 0
                AND p.intereview = 1
        """

        # Source 3: Academic Eligibility
        source3_query = f"""
            SELECT
                app.name          AS applicant_id,
                app.candidate_name,
                app.email,
                app.gender,
                app.program,
                app.program_level,
                app.entrance_test,
                app.intereview,
                app.foriegn_national,
                0.0               AS entrance_test_score,
                0.0               AS part_a_score
            FROM `tabApplicant` app
            INNER JOIN `tabProgram` p
                    ON p.name = app.program
            WHERE
                app.academic_year    = %(academic_year)s
                AND app.campus       = %(campus)s
                AND app.admission_cycle = %(admission_cycle)s
                {program_filter}
                AND app.status != 'Rejected'
                AND app.name NOT IN (SELECT applicant_id FROM `tabInterview Applicant`)
                AND p.entrance_test = 0
                AND p.intereview = 1
                AND (app.exempts_interview IS NULL OR app.exempts_interview = 0)
        """

        seen = {}

        # Query Source 1
        res1 = frappe.db.sql(source1_query, query_args, as_dict=True)
        for row in res1:
            row.source_type = "National Test (Direct)"
            if not row.get("entrance_test_score"):
                row.entrance_test_score = self.part_b_score or 0.0
            if not row.get("part_a_score"):
                row.part_a_score = 0.0
            seen[row.applicant_id] = row

        # Query Source 3
        res3 = frappe.db.sql(source3_query, query_args, as_dict=True)
        for row in res3:
            row.source_type = "Academic Eligibility"
            if not row.get("entrance_test_score"):
                row.entrance_test_score = self.part_b_score or 0.0
            if not row.get("part_a_score"):
                row.part_a_score = 0.0
            seen[row.applicant_id] = row

        # Query Source 2 (if not fetching exempted only)
        if not self.fetch_exempted_applicant:
            res2 = frappe.db.sql(source2_query, query_args, as_dict=True)
            for row in res2:
                # Overrides direct/academic
                row.source_type = "Entrance Test"
                if not row.get("part_a_score"):
                    row.part_a_score = 0.0
                seen[row.applicant_id] = row

        return list(seen.values())

    @frappe.whitelist()
    def generate_interview_list(self):
        """
        Generates interview list based on applicant type, fetching direct and test passers,
        and optionally applying ratios.
        """
        if self.status not in ["Draft", "In Progress", "Failed"]:
            frappe.throw(
                "Document must be in Draft, In Progress, or Failed to generate interview list"
            )

        # 1. Fetch eligible applicants
        all_applicants = self.get_eligible_applicants()

        # 2. Split into Domestic and International
        domestic_applicants = []
        international_applicants = []

        for app in all_applicants:
            if app.get("foriegn_national") == "Yes":
                international_applicants.append(app)
            else:
                domestic_applicants.append(app)

        # Helper to parse ratio and select top candidates
        def select_applicants(applicants, seats, ratio_str):
            if self.fetch_exempted_applicant or not ratio_str:
                return applicants

            try:
                parts = ratio_str.split(":")
                num1 = float(parts[0])
                num2 = float(parts[1])
                multiplier = max(num1, num2) / min(num1, num2)
            except Exception:
                multiplier = 1.0

            if seats > 0:
                num_to_select = int(math.ceil(seats * multiplier))
            else:
                num_to_select = len(applicants)

            # Rank applicants by entrance_test_score desc, part_a_score desc
            applicants.sort(key=lambda x: (x.get("entrance_test_score", 0), x.get("part_a_score", 0)), reverse=True)
            return applicants[:num_to_select]

        # 3. Filter based on selected applicant_type
        target_applicants = []

        if self.applicant_type == "Domestic Applicants":
            seats = self.get_total_seats("Domestic Applicants")
            target_applicants = select_applicants(domestic_applicants, seats, self.enter_domestic_ratio)
        elif self.applicant_type == "International Applicants":
            seats = self.get_total_seats("International Applicants")
            target_applicants = select_applicants(international_applicants, seats, self.enter_international_ratio)
        elif self.applicant_type == "Both":
            d_seats = self.get_total_seats("Domestic Applicants")
            i_seats = self.get_total_seats("International Applicants")
            selected_domestic = select_applicants(domestic_applicants, d_seats, self.enter_domestic_ratio)
            selected_intl = select_applicants(international_applicants, i_seats, self.enter_international_ratio)
            target_applicants = selected_domestic + selected_intl

        # 4. If no candidates, throw error
        if not target_applicants:
            self.db_set("status", "Failed")

            # Count details for message
            count_total = len(all_applicants)
            count_et_pass = sum(1 for a in all_applicants if a.get("source_type") == "Entrance Test")

            msg = (
                f"<b style='color: #dc3545;'>{_('No Candidates Found')}</b><br>"
                f"{_('Eligibility results')}:<br><br>"
                f"• {_('Total Eligible Applicants Found')}: {count_total}<br>"
                f"• {_('Entrance Test Passers Found')}: {count_et_pass}<br><br>"
                f"<div style='font-size: 12px; color: #666; line-height: 1.6;'>"
                f"<b>{_('Possible reasons for no candidates')}:</b><br>"
                f"• {_('Applicants are already included in an existing Interview List.')}<br>"
                f"• {_('Applicants are exempted from the Interview stage.')}<br>"
                f"• {_('The selected Programs do not offer an Interview stage.')}<br>"
                f"• {_('Applicants have an incomplete application or were rejected.')}<br>"
                f"</div>"
            )
            frappe.throw(msg, title=_("Generation Failed"))

        # Determine level_of_study from first chosen program
        program_levels = {frappe.db.get_value("Program", p.program, "level_of_study") for p in self.program if p.program}
        program_levels = {l for l in program_levels if l}
        program_level = list(program_levels)[0] if program_levels else "Undergraduate"

        # 5. Create Interview List
        interview_list_data = {
            "doctype":              "Interview List",
            "academic_year":        self.academic_year,
            "campus":               self.campus,
            "admission_cycle":      self.admission_cycle,
            "program_level":        program_level,
            "generated_on":         now(),
            "status":               "Generated",
            "interview_applicant":  []
        }
        if self.program:
            interview_list_data["program"] = self.program[0].program

        interview_list = frappe.get_doc(interview_list_data)

        for app in target_applicants:
            interview_list.append("interview_applicant", {
                "applicant_id":         app["applicant_id"],
                "candidate_name":       app["candidate_name"],
                "program":              app["program"],
                "program_level":        app["program_level"],
                "email":                app["email"],
                "gender":               app["gender"],
                "entrance_test":        app["entrance_test"],
                "intereview":           app["intereview"],
                "source_type":          app["source_type"],
                "interview_status":     "Pending"
            })

        interview_list.insert(ignore_permissions=True)

        self.db_set("status", "Completed")
        self.db_set("generated_on", now())
        self.db_set("generated_by", frappe.session.user)

        # Count per source for success message
        cnt_national = sum(1 for a in target_applicants if a["source_type"] == "National Test (Direct)")
        cnt_et       = sum(1 for a in target_applicants if a["source_type"] == "Entrance Test")
        cnt_academic = sum(1 for a in target_applicants if a["source_type"] == "Academic Eligibility")

        msg = (
            f"<div style='text-align: center; padding: 10px;'>"
            f"<h4>{_('Interview List Generated Successfully')}</h4>"
            f"<p>{_('Details Below')}:</p>"
            f"<p style='font-size: 16px;'><b>{_('Eligible Candidates')}: {len(target_applicants)}</b></p>"
            f"<p>{_('National Test')}: {cnt_national} &nbsp;&middot;&nbsp; {_('Entrance Pass')}: {cnt_et} &nbsp;&middot;&nbsp; {_('Academic')}: {cnt_academic}</p>"
            f"<br>"
            f"<a href='/app/interview-list/{interview_list.name}' class='btn btn-primary btn-sm' style='color: #fff !important; text-decoration: none;'>"
            f"{_('View Interview List')}</a>"
            f"</div>"
        )

        frappe.msgprint(msg, indicator="green")

        return interview_list.name
