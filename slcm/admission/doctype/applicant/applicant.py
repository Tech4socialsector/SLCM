import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import validate_email_address, getdate, date_diff, today, now, flt, nowdate
from slcm.admission.utils.regulatory import log_audit_trail

class Applicant(Document):

    # ──────────────────────────────────────────────
    # VALIDATE
    # ──────────────────────────────────────────────

    def validate(self):
        """
        FIX — Duplicate Record Issue:
        ─────────────────────────────
        Previously, create_or_update_evaluation() was called:
          1. Inside validate_eligibility() (before throw, for ineligible path)
          2. Again here in validate() as a "safety net" for the eligible path

        This caused duplicate/double-save calls for both paths when no throw occurred.

        CORRECTED FLOW:
          - validate_eligibility() handles ALL saves internally:
              • Ineligible: saves BEFORE throw (required — throw exits the stack)
              • Eligible:   saves at the END of validate_eligibility()
          - validate() no longer calls create_or_update_evaluation() at all.
        """
        set_intake_type(self)
        self.validate_eligibility()
        # NOTE: create_or_update_evaluation() is now called exclusively inside
        # validate_eligibility() for BOTH eligible and ineligible outcomes.
        # Do NOT add another call here — it would cause duplicate records.

    def validate_email(self):
        if not validate_email_address(self.email):
            frappe.throw(
                f"Invalid email address: {self.email}",
                title="Invalid Email"
            )

    def validate_age(self):
        if self.date_of_birth:
            age = date_diff(today(), self.date_of_birth) / 365
            if age < 17:
                frappe.throw(
                    "Applicant must be at least 17 years old.",
                    title="Age Restriction"
                )

    # def validate_percentages(self):
    #     if self.class_x_percentage:
    #         if not 0 <= self.class_x_percentage <= 100:
    #             frappe.throw(
    #                 "Class X Percentage must be between 0 and 100.",
    #                 title="Invalid Percentage"
    #             )
    #     if self.class_xii_percentage:
    #         if not 0 <= self.class_xii_percentage <= 100:
    #             frappe.throw(
    #                 "Class XII Percentage must be between 0 and 100.",
    #                 title="Invalid Percentage"
    #             )

    def validate_reservation_documents(self):
        if self.ews == "Yes" and not self.ews_certificate:
            frappe.throw(
                "EWS Certificate is mandatory for EWS category.",
                title="Missing Document"
            )

        # Derive caste categories from the whether_scstobc_ncl field
        caste_categories = {"SC", "ST", "OBC-NCL"}
        applicant_cats = self._get_applicant_categories()
        matched_caste = applicant_cats & caste_categories

        if matched_caste and not self.caste_certificate:
            frappe.throw(
                f"Caste Certificate is mandatory for {', '.join(sorted(matched_caste))} category.",
                title="Missing Document"
            )

        if self.pwd == "Yes" and not self.pwd_certificate:
            frappe.throw(
                "PwD Certificate is mandatory for PwD category.",
                title="Missing Document"
            )

    def validate_preferences(self):
        if not self.first_preference:
            frappe.throw(
                "First Campus Preference is mandatory.",
                title="Missing Preference"
            )
        preferences = [
            self.first_preference,
            self.second_preference,
            self.third_preference
        ]
        filled = [p for p in preferences if p]
        if len(filled) != len(set(filled)):
            frappe.throw(
                "Duplicate campus preferences are not allowed.",
                title="Duplicate Preference"
            )

    def validate_declaration(self):
        if self.docstatus == 1 and not self.declaration_undertaking:
            frappe.throw(
                "Declaration Undertaking must be accepted before submission.",
                title="Declaration Required"
            )

    def before_save(self):
        if not self.applicant_id:
            self.applicant_id = frappe.generate_hash(length=8).upper()

    def on_submit(self):
        self.db_set("application_status", "Submitted")
        self.db_set("submitted_on", now())
        log_audit_trail(
            self.doctype, self.name,
            "Submitted", "application_status",
            "Draft", "Submitted", "General"
        )
        frappe.sendmail(
            recipients=[self.email],
            subject=f"NLSIU Application Submitted - {self.applicant_id}",
            message=f"""
            Dear {self.candidate_name},<br><br>
            Your application <b>{self.applicant_id}</b> has been
            successfully submitted.<br>
            Application Type: {self.application_type}<br>
            Program: {self.program}<br><br>
            You will be notified of further updates.<br><br>
            NLSIU Admissions Team
            """
        )

        from slcm.admission.utils.notifications import log_communication
        log_communication(
            applicant=self.name,
            communication_type="Email",
            category="Admission",
            subject=f"NLSIU Application Submitted - {self.applicant_id}",
            content=f"Confirmation email sent for application {self.applicant_id}. Program: {self.program}",
            reference_doctype="Applicant",
            reference_name=self.name
        )

    def before_submit(self):
        if self.evaluation_status == "Ineligible":
            frappe.throw(
                _("Submission Not Allowed: Applicant is not eligible."),
                title=_("Submission Not Allowed")
            )

    def on_update(self):
        # If current_stage changed, notify applicant
        if self.is_new() or self.has_value_changed("current_stage"):
            if self.current_stage and self.admission_cycle:
                try:
                    from slcm.admission.utils.stage_control import get_cycle_stages
                    stages = get_cycle_stages(self.admission_cycle, self.intake_type or "All")
                    for s in stages:
                        if s.stage_name == self.current_stage:
                            notify_stage_entry(self, s)
                            break
                except Exception:
                    pass

    # ──────────────────────────────────────────────
    # APPLICANT CATEGORY HELPER
    # ──────────────────────────────────────────────

    def _get_applicant_categories(self):
        """
        Derive the applicant's Admission Category set from the existing
        reservation fields in the eligibility_for_reservation_tab.

        Field → Admission Category mapping (static, matches DB records):
          whether_scstobc_ncl  (not "NA")  →  OBC-NCL / ST / SC
          pwd == "Yes"                     →  PWD
          karnataka_category == "Yes"      →  Karnataka category

        Returns a set of category name strings.
        """
        cats = set()

        if (getattr(self, "ews", None) or "").strip() == "Yes":
            cats.add("EWS")

        sc_st_obc = (getattr(self, "whether_scstobc_ncl", None) or "").strip()
        if sc_st_obc and sc_st_obc.lower() != "na":
            cats.add(sc_st_obc)  # Only include real categories like "OBC-NCL", "ST", or "SC"

        if (getattr(self, "pwd", None) or "").strip() == "Yes":
            cats.add("PWD")

        if (getattr(self, "karnataka_category", None) or "").strip() == "Yes":
            cats.add("Karnataka category")

        return cats

    # ──────────────────────────────────────────────
    # CHILD TABLE VALUE HELPERS
    # ──────────────────────────────────────────────

    def _get_ug_cgpa_values(self):
        """Return a list of all UG CGPA values from the ug_degree_details child table."""
        rows = getattr(self, "ug_degree_details", None) or []
        return [flt(row.ug_cgpa) for row in rows if row.ug_cgpa not in (None, "")]

    @frappe.whitelist()
    def waive_fee(self):
        """Admin marks fee as waived — records who waived and when."""
        self.application_fee_status = "Waived"
        self.fee_waived_by = frappe.session.user
        self.fee_waived_on = frappe.utils.now()
        self.save(ignore_permissions=True)
        frappe.get_doc({
            "doctype": "Admission Audit Log",
            "action": "Fee Waived",
            "reference_doctype": "Applicant",
            "reference_name": self.name,
            "performed_by": frappe.session.user,
            "reason": "Application fee waived by admin"
        }).insert(ignore_permissions=True)

    def _get_ug_programs(self):
        """Return a list of all UG programs from the ug_degree_details child table."""
        rows = getattr(self, "ug_degree_details", None) or []
        return [row.ug_program for row in rows if row.ug_program]

    def _get_pg_programs(self):
        """Return a list of all PG programs from the pg_degree_details child table."""
        rows = getattr(self, "pg_degree_details", None) or []
        return [row.pg_program for row in rows if row.pg_program]

    def _get_applicant_hsc_groups(self):
        """
        Return the applicant's HSC group as a set (single value from hsc_group field).
        """
        hsc_group = getattr(self, "hsc_group", None)
        if hsc_group:
            return {hsc_group.strip()}
        return set()

    # ──────────────────────────────────────────────
    # PROGRAM LEVEL HELPER
    # ──────────────────────────────────────────────

    def _get_selected_program_level(self):
        """
        Returns the program_level ('UG', 'PG', 'Research Course') of the
        currently selected program by querying the Program doctype.

        Returns None if not found.
        """
        if not self.program:
            return None
        return frappe.db.get_value("Program", self.program, "program_level")

    def _get_all_programs_for_level(self, program_level):
        """
        Returns ALL programs from the Program doctype that match the given
        program_level (e.g., 'UG', 'PG', 'Research Course').

        This ensures the eligibility table shows EVERY program of the same
        level — not just those with eligibility rules configured.
        """
        if not program_level:
            return []

        programs = frappe.db.sql("""
            SELECT name AS program
            FROM `tabProgram`
            WHERE program_level = %(program_level)s
            ORDER BY name ASC
        """, {"program_level": program_level}, as_dict=True)

        return [row.program for row in programs if row.program]

    # ──────────────────────────────────────────────
    # CORE ELIGIBILITY LOGIC
    # ──────────────────────────────────────────────

    def validate_eligibility(self):
        """
        Main eligibility entry point.

        Flow:
        ─────
        STEP 0 — National Test Exemption check.
        STEP 1 — Academic Eligibility Rule Mapping checks.

        KEY BEHAVIOUR:
        ─────────────
        On ineligibility:
          1. Sets self.evaluation_status = "Ineligible" and self.rejected_reason.
          2. Calls create_or_update_evaluation() IMMEDIATELY — so the Ineligible
             record is persisted to the Eligibility Evaluation doctype BEFORE the
             throw. Without this, frappe.throw() exits the call stack and the
             save in validate() never runs, meaning ineligible records are lost.
          3. Raises a single frappe.throw() containing:
               • Red reason box  (the specific failure message)
               • Full program table  (all same-level programs + full eligibility check)

        On eligibility:
          1. Sets self.evaluation_status = "Eligible".
          2. Calls create_or_update_evaluation() here (NOT in validate()).
             This prevents the double-save duplicate record bug.
        """

        if not all([self.program, self.campus, self.admission_cycle, self.academic_year]):
            self.evaluation_status = ""
            self.rejected_reason = ""
            self._clear_national_test_flags()
            return

        try:
            # ── STEP 0: National Test Exemption ─────────────────────────────
            national_test_result = self._evaluate_national_test_exemption()

            if national_test_result.get("passed") and national_test_result.get("overrides_academic_rule"):
                # Passed national test AND rule overrides academic checks → Eligible immediately
                self.evaluation_status = "Eligible"
                self.rejected_reason   = ""
                self._apply_national_test_flags(national_test_result)

                # Save the eligible record here (not in validate())
                program_table_html = self._build_program_eligibility_html()
                self.create_or_update_evaluation(program_details_html=program_table_html)

                frappe.msgprint(
                    _("Eligible via National Test ({0}). Academic rule check bypassed.").format(
                        self.national_test_name or ""
                    ),
                    title=_("National Test Exemption Applied"),
                    indicator="green"
                )
                return

            # National test passed but does NOT override → store flags, continue
            if national_test_result.get("passed"):
                self._apply_national_test_flags(national_test_result)
            else:
                self._clear_national_test_flags()

            # ── STEP 1: Academic Eligibility Rule Mapping checks ─────────────
            rule_mappings = self._get_rule_mappings_for_applicant()

            if not rule_mappings:
                # No mapping found → no restriction → eligible
                self.evaluation_status = "Eligible"
                self.rejected_reason   = ""
                # Save eligible record here (not in validate())
                program_table_html = self._build_program_eligibility_html()
                self.create_or_update_evaluation(program_details_html=program_table_html)
                return

            for mapping in rule_mappings:
                is_eligible, failure_message = self._evaluate_mapping_with_category_priority(mapping)

                if not is_eligible:
                    self.evaluation_status  = "Ineligible"
                    self.application_status = "Rejected"
                    self.rejected_reason    = failure_message

                    # ── Build combined HTML: reason box + program table ────────
                    program_table_html = self._build_program_eligibility_html()

                    # ── CRITICAL: Save the Ineligible record NOW, before throw ──
                    # frappe.throw() raises ValidationError which unwinds the stack,
                    # so create_or_update_evaluation() would never execute after throw.
                    # We must save here explicitly before throwing.
                    self.create_or_update_evaluation(program_details_html=program_table_html)

                    full_message = self._build_ineligibility_message(failure_message, program_table_html)

                    # ONE single frappe.throw() — contains reason box + program table
                    # NOTE: allow_dangerous_html=True is required for modern Frappe versions (v15+)
                    # to render styles correctly. We check dynamically to avoid TypeError on older versions.
                    throw_kwargs = {
                        "msg": full_message,
                        "title": _("Eligibility Evaluation Results"),
                        "wide": True,
                    }

                    import inspect
                    if "allow_dangerous_html" in inspect.signature(frappe.throw).parameters:
                        throw_kwargs["allow_dangerous_html"] = True

                    frappe.throw(**throw_kwargs)
                    return

            # Passed all mappings → Eligible
            self.evaluation_status = "Eligible"
            self.rejected_reason   = ""
            program_table_html = self._build_program_eligibility_html()
            self.create_or_update_evaluation(program_details_html=program_table_html)

        except frappe.ValidationError:
            # Standard validation failure — let it raise naturally for the frontend
            raise
        except Exception:
            # Unexpected system error — log it to Error Log then raise
            frappe.log_error(frappe.get_traceback(), "Applicant Eligibility Validation Error")
            raise

    # ──────────────────────────────────────────────
    # INELIGIBILITY MESSAGE BUILDER  (Frappe-native)
    # ──────────────────────────────────────────────

    def _build_ineligibility_message(self, failure_message, program_table_html):
        """
        Builds the full ineligibility HTML message using explicit inline styles
        for consistent rendering across local and production Frappe environments.
        """
        escaped_reason = frappe.utils.escape_html(failure_message)

        return (
            '<div style="font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif;">'
            '<!-- ── Ineligibility Alert ───────────────────────────────── -->'
            '<div style="display: flex; align-items: flex-start; gap: 10px; margin-bottom: 16px; padding: 12px 16px; '
            'background-color: #fff2f2; border: 1px solid #f5c6cb; border-left: 4px solid #e74c3c; border-radius: 6px;">'
            '<span style="display: inline-block; width: 10px; height: 10px; background-color: #e74c3c; border-radius: 50%; '
            'margin-top: 4px; flex-shrink: 0;"></span>'
            '<div>'
            '<div style="font-weight: 600; font-size: 14px; color: #c0392b;">{reason}</div>'
            '<div style="font-size: 12px; color: #666; margin-top: 3px;">{note}</div>'
            '</div>'
            '</div>'
            '<!-- ── Program Options ───────────────────────────────────── -->'
            '{table}'
            '</div>'
        ).format(
            reason=escaped_reason,
            note=_("The applicant does not meet the eligibility criteria for the selected program."),
            table=program_table_html,
        )

    # ──────────────────────────────────────────────
    # PROGRAM ELIGIBILITY TABLE (rendered inside throw)
    # ──────────────────────────────────────────────

    def _build_program_eligibility_html(self):
        """
        Returns styled HTML listing EVERY program of the SAME LEVEL as the
        applicant's selected program (UG / PG / Research Course).

        FIX — Previously only showed programs that had eligibility rules configured.
        Now shows ALL programs from the Program doctype with matching program_level:
          • Programs WITH eligibility rules → full eligibility check (pass/fail + reason)
          • Programs WITHOUT eligibility rules → shown as "Eligible" (no restriction)
          • Programs of a DIFFERENT level (e.g., PG when applicant applied for UG)
            are completely excluded — they are irrelevant to the applicant.

        The currently selected program is marked with a "Selected" badge.
        """

        # Get the level of the selected program (UG / PG / Research Course)
        selected_program_level = self._get_selected_program_level()

        if not selected_program_level:
            return (
                "<p style='color:#888;font-size:12px;'>{0}</p>".format(
                    _("Could not determine program level for the selected program.")
                )
            )

        # Get ALL programs of the same level from Program doctype
        all_programs = self._get_all_programs_for_level(selected_program_level)

        if not all_programs:
            return (
                "<p style='color:#888;font-size:12px;'>{0}</p>".format(
                    _("No programs found for program level: {0}").format(selected_program_level)
                )
            )

        rows_html        = ""
        eligible_count   = 0
        ineligible_count = 0

        for prog_name in all_programs:
            is_prog_eligible, reason = self._check_eligibility_for_program(prog_name)
            is_selected = (prog_name == self.program)

            if not is_prog_eligible:
                ineligible_count += 1
                continue

            eligible_count += 1
            dot_color    = "#27ae60"
            status_label = _("Eligible")
            status_color = "#27ae60"
            row_bg       = "#fff"

            # Program name cell — bold + "Selected" badge for the active program
            if is_selected:
                prog_display = """
                    <strong style="color:#2c3e50;">{name}</strong>
                    &nbsp;<span style="
                        font-size: 10px;
                        padding: 2px 8px;
                        background-color: #3498db;
                        color: #fff;
                        border-radius: 10px;
                        font-weight: 600;
                        vertical-align: middle;
                    ">{label}</span>
                """.format(
                    name  = frappe.utils.escape_html(prog_name),
                    label = _("Selected"),
                )
            else:
                prog_display = "<span style='color:#2c3e50;'>{0}</span>".format(
                    frappe.utils.escape_html(prog_name)
                )

            rows_html += """
                <tr style="background-color:{row_bg};">
                    <td style="padding:10px 12px;vertical-align:middle;border-bottom:1px solid #eee;">
                        {prog}
                    </td>
                    <td style="padding:10px 12px;vertical-align:middle;text-align:center;white-space:nowrap;border-bottom:1px solid #eee;">
                        <span style="
                            display: inline-block;
                            width: 8px;
                            height: 8px;
                            background-color: {dot};
                            border-radius: 50%;
                            vertical-align: middle;
                            margin-right: 4px;
                        "></span>
                        <span style="font-size:13px;font-weight:500;color:{status_color};">{status}</span>
                    </td>
                </tr>
            """.format(
                row_bg       = row_bg,
                prog         = prog_display,
                dot          = dot_color,
                status_color = status_color,
                status       = status_label,
            )

        # ── Summary counts ───────────────────────────────────────────────────
        summary_html = (
            '<div style="display:flex;align-items:center;gap:16px;margin-bottom:12px;flex-wrap:wrap;">'
            '<span style="display:inline-flex;align-items:center;gap:6px;">'
            '<span style="display:inline-block;width:8px;height:8px;background:#27ae60;border-radius:50%;"></span>'
            '<strong style="color:#2c3e50;">{ec}</strong>'
            '<span style="font-size:12px;color:#888;">{el}</span>'
            '</span>'
            '<span style="font-size:12px;color:#aaa;">({total}&nbsp;{tl})</span>'
            '</div>'
        ).format(
            ec    = eligible_count,
            el    = _("eligible programs found"),
            total = eligible_count + ineligible_count,
            tl    = _("total same-level programs"),
        )

        # ── Section heading ──────────────────────────────────────────────────
        heading_html = (
            '<div style="display:flex;align-items:baseline;gap:8px;margin-bottom:6px;">'
            '<span style="font-weight:700;font-size:14px;color:#2c3e50;">{heading}</span>'
            '<span style="font-size:12px;color:#888;">&mdash;&nbsp;{campus}&nbsp;&middot;&nbsp;{cycle}&nbsp;&middot;&nbsp;{level}</span>'
            '</div>'
        ).format(
            heading = _("Suggested Eligible Programs"),
            campus  = frappe.utils.escape_html(self.campus or ""),
            cycle   = frappe.utils.escape_html(self.admission_cycle or ""),
            level   = frappe.utils.escape_html(selected_program_level or ""),
        )

        # ── Full table ───────────────────────────────────────────────────────
        table_html = (
            '<div style="margin-top:8px;">'
            '{heading}'
            '<hr style="margin:6px 0 12px 0;border:none;border-top:1px solid #eee;">'
            '{summary}'
            '<div style="overflow-x:auto;">'
            '<table style="width: 100%; border-collapse: collapse; border: 1px solid #e0e0e0; border-radius: 6px; overflow: hidden; font-size: 13px;">'
            '<thead>'
            '<tr style="background-color:#f8f9fa;">'
            '<th style="padding:10px 12px;text-align:left;font-weight:600;color:#555;width:70%;border-bottom:2px solid #e0e0e0;">{col1}</th>'
            '<th style="padding:10px 12px;text-align:center;font-weight:600;color:#555;border-bottom:2px solid #e0e0e0;">{col2}</th>'
            '</tr>'
            '</thead>'
            '<tbody>'
            '{rows}'
            '</tbody>'
            '</table>'
            '</div>'
            '</div>'
        ).format(
            heading = heading_html,
            summary = summary_html,
            col1    = _("Program"),
            col2    = _("Status"),
            rows    = rows_html,
        )

        return table_html

    def _check_eligibility_for_program(self, program_name):
        """
        Runs the full eligibility engine for a given program using the current
        applicant's scores, categories, campus, admission_cycle, and academic_year —
        WITHOUT permanently modifying self.

        Temporarily swaps self.program → runs check → restores original in finally.

        KEY BEHAVIOUR for programs WITHOUT eligibility rules:
          If no rule mappings exist for a program, it is treated as Eligible
          (no restriction configured = open to all applicants of that level).

        Returns (is_eligible: bool, failure_message: str)
        """
        original_program = self.program
        try:
            self.program = program_name

            # National test exemption for this program
            national_test_result = self._evaluate_national_test_exemption()
            if (national_test_result.get("passed")
                    and national_test_result.get("overrides_academic_rule")):
                return True, ""

            # Rule mappings for this program (direct link now)
            rule_mappings = frappe.db.sql("""
                SELECT erm.name, erm.failure_message
                FROM `tabEligibility Rule Mapping` erm
                WHERE erm.is_active       = 1
                  AND erm.campus          = %(campus)s
                  AND erm.admission_cycle = %(admission_cycle)s
                  AND erm.program         = %(program)s
            """, {
                "campus":          self.campus,
                "admission_cycle": self.admission_cycle,
                "program":         program_name,
            }, as_dict=True)

            # No rule mapping → no restriction → eligible
            if not rule_mappings:
                return True, ""

            for mapping in rule_mappings:
                is_eligible, failure_message = self._evaluate_mapping_with_category_priority(mapping)
                if not is_eligible:
                    return False, failure_message

            return True, ""

        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                "Program Eligibility Check Error — {0}".format(program_name)
            )
            return False, _("Error during eligibility check")

        finally:
            # Always restore original — even if exception occurs
            self.program = original_program

    # ──────────────────────────────────────────────
    # NATIONAL TEST EXEMPTION
    # ──────────────────────────────────────────────

    def _evaluate_national_test_exemption(self):
        """
        Check if the applicant qualifies under a National Test Exemption Rule.

        Returns a dict:
        {
            "passed":                  bool,
            "overrides_academic_rule": bool,
            "exempts_entrance_test":   bool,
            "exempts_interview":       bool,
            "rule_name":               str,
        }
        """
        empty = {
            "passed":                  False,
            "overrides_academic_rule": False,
            "exempts_entrance_test":   False,
            "exempts_interview":       False,
            "rule_name":               "",
        }

        national_test = getattr(self, "national_test_name", None)
        applicant_pct = flt(getattr(self, "percentage", None) or 0)

        if not national_test:
            return empty

        exemption_rules = frappe.db.sql("""
            SELECT
                nter.name,
                nter.mark_percentage,
                nter.operator,
                nter.overrides_academic_rule,
                nter.exempts_entrance_test,
                nter.exempts_interview
            FROM `tabNational Test Exemption Rule` nter
            INNER JOIN `tabEligibility Allowed Degree` ead
                ON ead.parent      = nter.name
               AND ead.degree_name = %(program)s
            WHERE nter.is_active        = 1
              AND nter.campus           = %(campus)s
              AND nter.admission_cycle  = %(admission_cycle)s
              AND nter.academic_year    = %(academic_year)s
              AND nter.national_test    = %(national_test)s
              AND %(today)s BETWEEN nter.valid_from AND nter.valid_until
            ORDER BY nter.mark_percentage DESC
            LIMIT 1
        """, {
            "program":         self.program,
            "campus":          self.campus,
            "admission_cycle": self.admission_cycle,
            "academic_year":   self.academic_year,
            "national_test":   national_test,
            "today":           nowdate(),
        }, as_dict=True)

        if not exemption_rules:
            return empty

        rule         = exemption_rules[0]
        required_pct = flt(rule.get("mark_percentage") or 0)
        operator     = rule.get("operator") or ">="
        passed       = self._compare(applicant_pct, required_pct, operator)

        return {
            "passed":                  passed,
            "overrides_academic_rule": bool(rule.get("overrides_academic_rule")),
            "exempts_entrance_test":   bool(rule.get("exempts_entrance_test")),
            "exempts_interview":       bool(rule.get("exempts_interview")),
            "rule_name":               rule.get("name", ""),
        }

    def _apply_national_test_flags(self, result):
        self.exempts_entrance_test   = 1 if result.get("exempts_entrance_test")   else 0
        self.exempts_interview       = 1 if result.get("exempts_interview")        else 0
        self.national_test_rule_used = result.get("rule_name", "")

    def _clear_national_test_flags(self):
        self.exempts_entrance_test   = 0
        self.exempts_interview       = 0
        self.national_test_rule_used = ""

    # ──────────────────────────────────────────────
    # STEP 1 — Fetch matching rule mappings
    # ──────────────────────────────────────────────

    def _get_rule_mappings_for_applicant(self):
        return frappe.db.sql("""
            SELECT erm.name, erm.failure_message
            FROM `tabEligibility Rule Mapping` erm
            WHERE erm.is_active         = 1
              AND erm.campus            = %(campus)s
              AND erm.admission_cycle   = %(admission_cycle)s
              AND erm.program           = %(program)s
        """, {
            "campus":          self.campus,
            "admission_cycle": self.admission_cycle,
            "program":         self.program,
        }, as_dict=True)

    # ──────────────────────────────────────────────
    # STEP 2 — Multi-category priority engine
    # ──────────────────────────────────────────────

    def _evaluate_mapping_with_category_priority(self, mapping):
        """
        Comprehensive eligibility engine:
        Checks ALL categories the applicant belongs to (against the mapping table)
        AND the 'General' (default) path using 'OR' logic.

        Result: Eligible if ANY (Category, Rule) combination passes.
        """
        mapping_name = mapping.get("name")
        failure_msg  = (mapping.get("failure_message") or "").strip() or \
            "You do not meet the eligibility criteria for the selected program."

        # 1. Fetch ALL rules for this mapping
        rules_in_mapping = frappe.db.get_all("Rule Mapping",
            filters={"parent": mapping_name},
            fields=["rule"]
        )

        if not rules_in_mapping:
            return True, ""

        # 2. Get reservation overrides defined for this mapping
        reservation_rows = frappe.db.sql("""
            SELECT category, priority, minimum_percentage
            FROM `tabRule Mapping Category`
            WHERE parent = %(mapping_name)s
            ORDER BY priority ASC
        """, {"mapping_name": mapping_name}, as_dict=True)

        # 3. Identify all evaluation paths (Matched categories + General)
        applicant_categories = self._get_applicant_categories()
        
        # Path 1: Categories matching the mapping table
        matched_categories = [
            row for row in reservation_rows
            if (row.category or "").strip() in applicant_categories
        ]
        
        # evaluation_paths = [MatchedCategoryRow1, MatchedCategoryRow2, ..., None (for General)]
        evaluation_paths = matched_categories + [None]

        # 4. Nested OR Evaluation: Success if ANY (Path, Rule) combination passes
        for cat_row in evaluation_paths:
            for r_row in rules_in_mapping:
                base_rule = self._get_base_rule(r_row.rule)
                if not base_rule:
                    continue

                # Threshold: Category Override or Rule Default
                if cat_row:
                    required_val = flt(cat_row.minimum_percentage)
                else:
                    required_val = self._get_required_value(base_rule)

                operator = (base_rule.get("operator") or ">=")
                
                # Perform academic value comparison
                passes_threshold = self._compare_any_academic_value(base_rule, required_val, operator)
                # Perform non-percentage checks (Degrees/HSC Groups)
                passes_non_percentage = self._evaluate_non_percentage_checks(base_rule)

                if passes_threshold and passes_non_percentage:
                    # ELIGIBLE: Found a valid qualifying path
                    self._set_applied_category_info(
                        category=cat_row.category if cat_row else "General",
                        priority=cat_row.priority if cat_row else None,
                        minimum=required_val
                    )
                    return True, ""

        # If all paths and all rules failed
        return False, failure_msg



    # ──────────────────────────────────────────────
    # STEP 3 — Base rule fetch
    # ──────────────────────────────────────────────

    def _get_base_rule(self, rule_name):
        if not rule_name:
            return None

        rules = frappe.db.sql("""
            SELECT *
            FROM `tabEligibility Rule`
            WHERE name            = %(rule_name)s
              AND is_active       = 1
              AND campus          = %(campus)s
              AND academic_year   = %(academic_year)s
              AND %(today)s BETWEEN effective_from AND effective_to
        """, {
            "rule_name":     rule_name,
            "campus":        self.campus,
            "academic_year": self.academic_year,
            "today":         nowdate(),
        }, as_dict=True)

        return rules[0] if rules else None

    # ──────────────────────────────────────────────
    # NON-PERCENTAGE CHECKS (used in CASE A)
    # ──────────────────────────────────────────────

    def _evaluate_non_percentage_checks(self, rule):
        """
        Run only the non-percentage checks from the base rule:
          - Allowed Degree check  (any matching UG or PG program qualifies)
          - HSC Group check       (multi-group: passes if applicant's group is in
                                   the rule's hsc_group child table)
        """
        rule_type           = rule.get("rule_type")
        qualification_level = rule.get("qualification_level")
        rule_name           = rule.get("name")

        allowed_degrees = frappe.db.sql("""
            SELECT degree_name
            FROM `tabEligibility Allowed Degree`
            WHERE parent = %(rule_name)s
        """, {"rule_name": rule_name}, as_dict=True)

        allowed_degree_list = [r.degree_name for r in allowed_degrees if r.degree_name]

        if allowed_degree_list:
            if qualification_level == "PG":
                applicant_degrees = self._get_pg_programs()
            else:
                applicant_degrees = self._get_ug_programs()

            if not any(deg in allowed_degree_list for deg in applicant_degrees):
                return False

        if rule_type == "HSC Group":
            if not self._check_hsc_group_eligibility(rule_name):
                return False

        return True

    # ──────────────────────────────────────────────
    # HSC GROUP CHECK — multi-group support
    # ──────────────────────────────────────────────

    def _check_hsc_group_eligibility(self, rule_name):
        """
        Check if the applicant's HSC group is in the list of allowed HSC groups
        defined in the Eligibility Rule's hsc_group child table (HSC Groups Mapping).

        Returns True if applicant's group matches any allowed group in the rule,
        or if the rule has NO groups defined (no restriction).
        """
        allowed_groups_rows = frappe.db.sql("""
            SELECT hsc_groups
            FROM `tabHSC Groups Mapping`
            WHERE parent = %(rule_name)s
              AND parenttype = 'Eligibility Rule'
              AND hsc_groups IS NOT NULL
              AND hsc_groups != ''
        """, {"rule_name": rule_name}, as_dict=True)

        allowed_hsc_groups = [
            row.hsc_groups.strip()
            for row in allowed_groups_rows
            if row.hsc_groups
        ]

        # If no groups are configured in the rule → no restriction → pass
        if not allowed_hsc_groups:
            return True

        # Get applicant's HSC group
        applicant_hsc_group = (getattr(self, "hsc_group", None) or "").strip()

        if not applicant_hsc_group:
            return False

        return applicant_hsc_group in allowed_hsc_groups

    # ──────────────────────────────────────────────
    # RULE EVALUATION (single base rule — full check)
    # ──────────────────────────────────────────────

    def evaluate_single_rule(self, rule):
        """
        Full evaluation of a base Eligibility Rule against the applicant.
        Checks: Allowed Degrees, HSC Group (multi-group), and numeric threshold
        (Percentage / CGPA).
        """
        rule_type           = rule.get("rule_type")
        qualification_level = rule.get("qualification_level")
        operator            = rule.get("operator") or ">="
        rule_name           = rule.get("name")

        allowed_degrees = frappe.db.sql("""
            SELECT degree_name
            FROM `tabEligibility Allowed Degree`
            WHERE parent = %(rule_name)s
        """, {"rule_name": rule_name}, as_dict=True)

        allowed_degree_list = [r.degree_name for r in allowed_degrees if r.degree_name]

        # ── HSC Group check (multi-group via child table) ────────────────────
        if rule_type == "HSC Group":
            if not self._check_hsc_group_eligibility(rule_name):
                return False

        if qualification_level in ("UG", "PG"):
            required_value = self.get_required_academic_value(rule)

            if qualification_level == "UG":
                child_rows = getattr(self, "ug_degree_details", None) or []
            else:
                child_rows = getattr(self, "pg_degree_details", None) or []

            if not child_rows:
                return False

            for row in child_rows:
                program_field = "ug_program" if qualification_level == "UG" else "pg_program"
                cgpa_field    = "ug_cgpa"    if qualification_level == "UG" else "pg_cgpa"

                row_program = getattr(row, program_field, None)
                row_cgpa    = flt(getattr(row, cgpa_field, None) or 0)

                if allowed_degree_list and row_program not in allowed_degree_list:
                    continue

                if rule_type in ("CGPA", "Percentage"):
                    if required_value is None:
                        continue
                    if not self._compare(row_cgpa, required_value, operator):
                        continue

                return True

            return False

        if rule_type in ("HSC Group", "Percentage"):
            applicant_value = flt(getattr(self, "hsc_percentage", None) or 0)
            required_value  = self.get_required_academic_value(rule)

            if required_value is None:
                return False

            return self._compare(applicant_value, required_value, operator)

        return True

    # ──────────────────────────────────────────────
    # MULTI-DEGREE ACADEMIC VALUE CHECK (CASE A)
    # ──────────────────────────────────────────────

    def _compare_any_academic_value(self, rule, required_min, operator):
        if not rule:
            return self._compare(flt(getattr(self, "hsc_percentage", 0) or 0), required_min, operator)

        qualification_level = rule.get("qualification_level")

        if qualification_level == "XII":
            value = flt(getattr(self, "hsc_percentage", None) or 0)
            return self._compare(value, required_min, operator)

        elif qualification_level == "UG":
            values = self._get_ug_cgpa_values()
            if not values:
                return False
            return any(self._compare(v, required_min, operator) for v in values)

        elif qualification_level == "PG":
            values = self._get_pg_cgpa_values()
            if not values:
                return False
            return any(self._compare(v, required_min, operator) for v in values)

        return False

    # ──────────────────────────────────────────────
    # VALUE HELPERS
    # ──────────────────────────────────────────────

    def _get_applicant_value(self, rule):
        if not rule:
            return flt(getattr(self, "hsc_percentage", 0) or 0)

        qualification_level = rule.get("qualification_level")

        if qualification_level == "XII":
            return flt(getattr(self, "hsc_percentage", None) or 0)
        elif qualification_level == "UG":
            values = self._get_ug_cgpa_values()
            return max(values) if values else 0.0
        elif qualification_level == "PG":
            values = self._get_pg_cgpa_values()
            return max(values) if values else 0.0

        return 0.0

    def _get_required_value(self, rule):
        if not rule:
            return None
        return self.get_required_academic_value(rule)

    def get_applicant_academic_value(self, qualification_level):
        if qualification_level == "XII":
            return flt(getattr(self, "hsc_percentage", None) or 0)
        if qualification_level == "UG":
            values = self._get_ug_cgpa_values()
            return max(values) if values else None
        if qualification_level == "PG":
            values = self._get_pg_cgpa_values()
            return max(values) if values else None
        return None

    def get_required_academic_value(self, rule):
        if rule.get("required_percentage"):
            return flt(rule["required_percentage"])
        if rule.get("required_cgpa"):
            return flt(rule["required_cgpa"])
        if rule.get("required_score"):
            return flt(rule["required_score"])
        return None

    def _compare(self, actual, required, operator):
        try:
            actual   = flt(actual)
            required = flt(required)
            if operator == ">=":
                return actual >= required
            elif operator == "<=":
                return actual <= required
            elif operator == "=":
                return actual == required
        except Exception:
            pass
        return False

    def compare_values(self, actual, required, operator):
        return self._compare(actual, required, operator)

    def _set_applied_category_info(self, category, priority, minimum):
        self.applied_category = category
        self.applied_priority = priority if priority is not None else ""
        self.applied_minimum  = minimum

    # ──────────────────────────────────────────────
    # CREATE / UPDATE ELIGIBILITY EVALUATION RECORD
    # ──────────────────────────────────────────────

    def create_or_update_evaluation(self, program_details_html=None):
        """
        Saves (insert or update) an Eligibility Evaluation record for this applicant.

        FIX — Duplicate Record Prevention:
        ────────────────────────────────────
        This method is now called ONLY from within validate_eligibility():
          • Ineligible path: called before frappe.throw() — required because throw
            exits the call stack before validate() can complete normally.
          • Eligible path: called at the end of validate_eligibility() directly.

        It is NO LONGER called separately from validate(). This eliminates the
        duplicate save that was occurring previously.

        The upsert logic (get existing → update OR insert new) prevents duplicate
        records even if called more than once for the same applicant.
        """
        if not all([self.program, self.campus, self.admission_cycle, self.academic_year]):
            return

        applicant_name = self.name or "New Applicant"

        existing = frappe.db.get_value(
            "Eligibility Evaluation",
            {"applicant_name": applicant_name},
            "name"
        )

        current_status = getattr(self, "evaluation_status", None) or "Eligible"
        current_reason = getattr(self, "rejected_reason", None) or ""

        exempts_entrance_test   = getattr(self, "exempts_entrance_test",   0)
        exempts_interview       = getattr(self, "exempts_interview",       0)
        national_test_rule_used = getattr(self, "national_test_rule_used", "")

        doc_data = {
            "doctype":                 "Eligibility Evaluation",
            "applicant_name":          applicant_name,
            "academic_year":           self.academic_year,
            "admission_cycle":         self.admission_cycle,
            "program":                 self.program,
            "campus":                  self.campus,
            "evaluation_status":       current_status,
            "failure_message":         current_reason,
            "exempts_entrance_test":   exempts_entrance_test,
            "exempts_interview":       exempts_interview,
            "national_test_rule_used": national_test_rule_used,
            "program_eligibility_details": program_details_html,
            "reservation_category": [
                {"category": cat}
                for cat in self._get_applicant_categories()
            ]
        }

        if existing:
            doc = frappe.get_doc("Eligibility Evaluation", existing)
            doc.update(doc_data)
        else:
            doc = frappe.get_doc(doc_data)

        try:
            doc.save(ignore_permissions=True)
            frappe.db.commit()
        except Exception as e:
            frappe.logger().warning(
                f"Failed to save Eligibility Evaluation for {applicant_name}: {str(e)}"
            )


# ──────────────────────────────────────────────
# WHITELIST API
# ──────────────────────────────────────────────


@frappe.whitelist()
def get_eligible_programs_for_campus(campus, admission_cycle):
    programs = frappe.db.sql("""
        SELECT DISTINCT erm.program
        FROM `tabEligibility Rule Mapping` erm
        WHERE erm.is_active         = 1
          AND erm.campus            = %(campus)s
          AND erm.admission_cycle   = %(admission_cycle)s
    """, {
        "campus":          campus,
        "admission_cycle": admission_cycle,
    }, as_dict=True)

    return [p.program for p in programs if p.program]


# ──────────────────────────────────────────────
# Async helper — create Eligibility Evaluation
# ──────────────────────────────────────────────


def create_eligibility_evaluation_async(
    applicant_name, status, failure_msg, categories,
    program, campus, admission_cycle, academic_year
):
    """Create or update Eligibility Evaluation record."""

    if not all([program, campus, admission_cycle, academic_year]):
        return

    existing = frappe.db.get_value(
        "Eligibility Evaluation",
        filters={"applicant_name": applicant_name},
        fieldname="name"
    )

    eval_data = {
        "doctype":           "Eligibility Evaluation",
        "applicant_name":    applicant_name,
        "academic_year":     academic_year,
        "admission_cycle":   admission_cycle,
        "program":           program,
        "campus":            campus,
        "evaluation_status": status,
        "failure_message":   failure_msg,
        "reservation_category": [
            {
                "category": row.get("category") if isinstance(row, dict) else row.category
            }
            for row in (categories or [])
        ] if categories else [],
    }

    if existing:
        doc = frappe.get_doc("Eligibility Evaluation", existing)
        doc.update(eval_data)
    else:
        doc = frappe.get_doc(eval_data)

    doc.save(ignore_permissions=True)


# ──────────────────────────────────────────────
# Hook functions
# ──────────────────────────────────────────────


def validate_applicant(doc, method):
    """Called via hooks.py doc_events validate"""
    doc.validate_eligibility()


def before_submit_applicant(doc, method):
    """Called via hooks.py doc_events before_submit"""
    if doc.evaluation_status == "Ineligible":
        frappe.throw(
            _("Not Eligible: {0}").format(
                doc.rejected_reason or "You are not eligible for the selected program."
            ),
            title=_("Submission Not Allowed")
        )

def set_intake_type(doc, method=None):
    """
    Copy intake_type from the linked Program.
    Program is the source of truth for intake type.
    BA LLB / BCom LLB / BBA LLB = CLAT
    LLM / LLM Business Law       = NLSAT
    PhD Law                      = Direct Merit
    """
    if doc.program:
        intake = frappe.db.get_value("Program", doc.program, "intake_type")
        if intake:
            doc.intake_type = intake

def notify_stage_entry(applicant_doc, stage):
    """
    Called when applicant enters a new stage.
    Creates portal notification. Sends email if template configured.
    Only fires if notify_applicant_on_entry = 1 on the stage.
    """
    if not getattr(stage, "notify_applicant_on_entry", 0):
        return

    try:
        frappe.get_doc({
            "doctype":           "Applicant Notification",
            "applicant":         applicant_doc.name,
            "title":             f"Stage Update: {stage.stage_name}",
            "message":           f"Your application has moved to the {stage.stage_name} stage.",
            "notification_type": "Stage Update",
            "link":              "/my-applications",
            "is_read":           0
        }).insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(f"notify_stage_entry failed: {e}", "Stage Notification")