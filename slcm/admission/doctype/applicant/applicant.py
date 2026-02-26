import frappe
from frappe.model.document import Document
from frappe.utils import validate_email_address, getdate, date_diff, today, now
from slcm.admission.utils.regulatory import log_audit_trail

class Applicant(Document):

    def validate(self):
        self.validate_email()
        self.validate_age()
        self.validate_percentages()
        self.validate_reservation_documents()
        self.validate_preferences()
        self.validate_declaration()
        self.validate_eligibility()

        # for BOTH eligible and ineligible outcomes, so it always runs even
        # when frappe.throw() is raised for ineligible applicants.
        # We still call it here as a safety net for the eligible path.
        program_table_html = self._build_program_eligibility_html()
        self.create_or_update_evaluation(program_details_html=program_table_html)

        # NOTE: DO NOT add another frappe.throw() here.
        # validate_eligibility() already throws with the full HTML message
        # (ineligibility reason + program table) in one single call.
        # A second throw here would override that rich message with a plain one.

        # for BOTH eligible and ineligible outcomes, so it always runs even
        # when frappe.throw() is raised for ineligible applicants.
        # We still call it here as a safety net for the eligible path.
        program_table_html = self._build_program_eligibility_html()
        self.create_or_update_evaluation(program_details_html=program_table_html)

        # NOTE: DO NOT add another frappe.throw() here.
        # validate_eligibility() already throws with the full HTML message
        # (ineligibility reason + program table) in one single call.
        # A second throw here would override that rich message with a plain one.

    def on_update(self):
        from slcm.admission.doctype.admission_result.admission_result import sync_applicant_to_admission_result
        sync_applicant_to_admission_result(self.name)

    def before_submit(self):
        if self.evaluation_status == "Ineligible":
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
                    # so create_or_update_evaluation() in validate() never executes
                    # for ineligible applicants. We must save here explicitly.
                    self.create_or_update_evaluation(program_details_html=program_table_html)

                    full_message = self._build_ineligibility_message(failure_message, program_table_html)

                    # ONE single frappe.throw() — contains reason + program table
                    frappe.throw(
                        msg=full_message,
                        title=_("Eligibility Evaluation Results"),
                        wide=True,
                        is_minimizable=True
                    )
                    return  # never reached — throw exits — kept for clarity

            # Passed all mappings → Eligible
            self.evaluation_status = "Eligible"
            self.rejected_reason   = ""

        except frappe.ValidationError:
            raise
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                "Applicant Eligibility Validation Error"
            )

    # ──────────────────────────────────────────────
    # INELIGIBILITY MESSAGE BUILDER  (Frappe-native)
    # ──────────────────────────────────────────────

    def _build_ineligibility_message(self, failure_message, program_table_html):
        """
        Builds the full ineligibility HTML message using only Frappe's
        native CSS classes and design tokens — no inline colours.

        Structure:
          ┌─ Alert banner (indicator-pill red)  ──────────────────┐
          │  ✕  <failure_message>                                  │
          └────────────────────────────────────────────────────────┘
          ┌─ Program table section  ──────────────────────────────┐
          │  Heading + summary counts + full eligibility table     │
          └────────────────────────────────────────────────────────┘
        """
        escaped_reason = frappe.utils.escape_html(failure_message)

        return """
        <div class="msgprint-content">

            <!-- ── Ineligibility Alert ───────────────────────────────── -->
            <div class="alert alert-danger" style="display:flex;align-items:flex-start;gap:10px;margin-bottom:16px;">
                <span class="indicator-pill red no-margin" style="margin-top:3px;flex-shrink:0;"></span>
                <div>
                    <div style="font-weight:600;font-size:var(--text-base);">{reason}</div>
                    <div class="text-muted" style="font-size:var(--text-sm);margin-top:2px;">
                        {note}
                    </div>
                </div>
            </div>

            <!-- ── Program Options ───────────────────────────────────── -->
            {table}

        </div>
        """.format(
            reason=escaped_reason,
            note=_("The applicant does not meet the eligibility criteria for the selected program."),
            table=program_table_html,
        )

    # ──────────────────────────────────────────────
    # PROGRAM ELIGIBILITY TABLE (rendered inside throw)
    # ──────────────────────────────────────────────

    def _build_program_eligibility_html(self):
        """
        Returns styled HTML listing EVERY program on the applicant's
        campus + admission cycle with a full eligibility check per program.

        Layout:
          • Section heading with campus · cycle
          • Summary counts (eligible / ineligible)
          • Table: Program | Your Eligibility | Reason (if not eligible)

        Uses only Frappe's native CSS classes — no custom inline colours.
        The currently selected program is marked with a "Selected" badge.
        """
        all_programs = frappe.db.sql("""
            SELECT DISTINCT pm.program
            FROM `tabEligibility Rule Mapping` erm
            INNER JOIN `tabProgram Mapping` pm ON pm.parent = erm.name
            WHERE erm.is_active       = 1
              AND erm.campus          = %(campus)s
              AND erm.admission_cycle = %(admission_cycle)s
            ORDER BY pm.program ASC
        """, {
            "campus":          self.campus,
            "admission_cycle": self.admission_cycle,
        }, as_dict=True)

        if not all_programs:
            return (
                "<p class='text-muted' style='font-size:var(--text-sm);'>{0}</p>".format(
                    _("No programs found for this campus and admission cycle.")
                )
            )

        rows_html        = ""
        eligible_count   = 0
        ineligible_count = 0

        for prog_row in all_programs:
            prog_name = prog_row.get("program")
            if not prog_name:
                continue

            is_prog_eligible, reason = self._check_eligibility_for_program(prog_name)
            is_selected = (prog_name == self.program)

            if is_prog_eligible:
                eligible_count += 1
                pill_class   = "indicator-pill green no-margin"
                status_label = _("Eligible")
                reason_html  = "<span class='text-muted'>—</span>"
                row_class    = ""
            else:
                ineligible_count += 1
                pill_class   = "indicator-pill red no-margin"
                status_label = _("Not Eligible")
                reason_html  = (
                    "<span style='font-size:var(--text-sm);'>{0}</span>".format(
                        frappe.utils.escape_html(reason or "")
                    )
                )
                row_class    = ""

            # Program name cell — bold + "Selected" badge for the active program
            if is_selected:
                prog_display = """
                    <strong>{name}</strong>
                    &nbsp;<span class="indicator-pill blue no-margin"
                        style="font-size:10px;padding:1px 6px;vertical-align:middle;">
                        {label}
                    </span>
                """.format(
                    name  = frappe.utils.escape_html(prog_name),
                    label = _("Selected"),
                )
            else:
                prog_display = frappe.utils.escape_html(prog_name)

            rows_html += """
                <tr class="{row_class}">
                    <td class="list-subject" style="padding:8px 10px;vertical-align:middle;">
                        {prog}
                    </td>
                    <td style="padding:8px 10px;vertical-align:middle;text-align:center;white-space:nowrap;">
                        <span class="{pill}" style="vertical-align:middle;"></span>
                        &nbsp;<span style="font-size:var(--text-sm);font-weight:500;">{status}</span>
                    </td>
                    <td style="padding:8px 10px;vertical-align:middle;">
                        {reason}
                    </td>
                </tr>
            """.format(
                row_class = row_class,
                prog      = prog_display,
                pill      = pill_class,
                status    = status_label,
                reason    = reason_html,
            )

        # ── Summary counts ───────────────────────────────────────────────────
        summary_html = """
            <div style="display:flex;align-items:center;gap:16px;
                        margin-bottom:10px;flex-wrap:wrap;">
                <span>
                    <span class="indicator-pill green no-margin" style="vertical-align:middle;"></span>
                    &nbsp;<strong>{ec}</strong>
                    <span class="text-muted" style="font-size:var(--text-sm);">
                        &nbsp;{el}
                    </span>
                </span>
                <span class="text-muted">/</span>
                <span>
                    <span class="indicator-pill red no-margin" style="vertical-align:middle;"></span>
                    &nbsp;<strong>{ic}</strong>
                    <span class="text-muted" style="font-size:var(--text-sm);">
                        &nbsp;{il}
                    </span>
                </span>
                <span class="text-muted" style="font-size:var(--text-sm);">
                    ({total}&nbsp;{tl})
                </span>
            </div>
        """.format(
            ec    = eligible_count,
            el    = _("eligible"),
            ic    = ineligible_count,
            il    = _("not eligible"),
            total = eligible_count + ineligible_count,
            tl    = _("total"),
        )

        # ── Section heading ──────────────────────────────────────────────────
        heading_html = """
            <div style="display:flex;align-items:baseline;gap:6px;margin-bottom:4px;">
                <span style="font-weight:600;font-size:var(--text-base);">{heading}</span>
                <span class="text-muted" style="font-size:var(--text-sm);">
                    &mdash;&nbsp;{campus}&nbsp;&middot;&nbsp;{cycle}
                </span>
            </div>
        """.format(
            heading = _("Available Programs"),
            campus  = frappe.utils.escape_html(self.campus or ""),
            cycle   = frappe.utils.escape_html(self.admission_cycle or ""),
        )

        # ── Full table ───────────────────────────────────────────────────────
        table_html = """
            <div style="margin-top:8px;">
                {heading}
                <hr class="divider" style="margin:6px 0 10px 0;">
                {summary}
                <div style="overflow-x:auto;">
                    <table class="table table-bordered table-hover" style="margin-bottom:0;">
                        <thead>
                            <tr>
                                <th style="width:40%;">{col1}</th>
                                <th style="width:20%;text-align:center;">{col2}</th>
                                <th>{col3}</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows}
                        </tbody>
                    </table>
                </div>
            </div>
        """.format(
            heading = heading_html,
            summary = summary_html,
            col1    = _("Program"),
            col2    = _("Eligibility"),
            col3    = _("Reason (if not eligible)"),
            rows    = rows_html,
        )

        return table_html

    def _check_eligibility_for_program(self, program_name):
        """
        Runs the full eligibility engine for a given program using the current
        applicant's scores, categories, campus, admission_cycle, and academic_year —
        WITHOUT permanently modifying self.

        Temporarily swaps self.program → runs check → restores original in finally.

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

            # Rule mappings for this program
            rule_mappings = frappe.db.sql("""
                SELECT erm.name, erm.rule, erm.failure_message
                FROM `tabEligibility Rule Mapping` erm
                INNER JOIN `tabProgram Mapping` pm ON pm.parent = erm.name
                WHERE erm.is_active       = 1
                  AND erm.campus          = %(campus)s
                  AND erm.admission_cycle = %(admission_cycle)s
                  AND pm.program          = %(program)s
            """, {
                "campus":          self.campus,
                "admission_cycle": self.admission_cycle,
                "program":         program_name,
            }, as_dict=True)

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

    def validate_declaration(self):
        if self.docstatus == 1 and not self.declaration_undertaking:
            frappe.throw(
                "Declaration Undertaking must be accepted before submission.",
                title="Declaration Required"
            )

    def before_save(self):
        if not self.application_id:
            self.application_id = frappe.generate_hash(length=8).upper()

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
            SELECT erm.name, erm.rule, erm.failure_message
            FROM `tabEligibility Rule Mapping` erm
            INNER JOIN `tabProgram Mapping` pm ON pm.parent = erm.name
            WHERE erm.is_active         = 1
              AND erm.campus            = %(campus)s
              AND erm.admission_cycle   = %(admission_cycle)s
              AND pm.program            = %(program)s
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
        Priority-based multi-category eligibility engine.

        CASE A — Applicant's category matches a reservation row:
            • Winning category's minimum_percentage overrides base rule threshold.
            • Non-percentage checks (HSC Group, Allowed Degree) still run.

        CASE B — No category match:
            • Full base rule evaluation (percentage + group + degree).

        Returns (is_eligible: bool, failure_message: str)
        """
        rule_name    = mapping.get("rule")
        mapping_name = mapping.get("name")

        failure_msg = (mapping.get("failure_message") or "").strip() or \
            "You do not meet the eligibility criteria for the selected program."

        base_rule = self._get_base_rule(rule_name)

        reservation_rows = frappe.db.sql("""
            SELECT category, priority, minimum_percentage
            FROM `tabRule Mapping Category`
            WHERE parent = %(mapping_name)s
            ORDER BY priority ASC
        """, {"mapping_name": mapping_name}, as_dict=True)

        applicant_categories = set(
            (row.category or "").strip()
            for row in (self.categories or [])
            if row.category
        )

    def before_submit(self):
        if self.evaluation_status == "Ineligible":
            frappe.throw(
                _("Submission Not Allowed: Applicant is not eligible."),
                title=_("Submission Not Allowed")
            )

    def on_update(self):
        from slcm.admission.doctype.admission_result.admission_result import sync_applicant_to_admission_result
        sync_applicant_to_admission_result(self.name)

    def on_cancel(self):
        self.db_set("application_status", "Draft")
        log_audit_trail(
            self.doctype, self.name,
            "Cancelled", "application_status",
            "Submitted", "Draft", "General"
        )


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
               • Full program table  (all campus programs + full eligibility check)

        On eligibility:
          1. Sets self.evaluation_status = "Eligible".
          2. Returns normally — create_or_update_evaluation() is then called by
             validate() as usual.
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
                    # so create_or_update_evaluation() in validate() never executes
                    # for ineligible applicants. We must save here explicitly.
                    self.create_or_update_evaluation(program_details_html=program_table_html)

                    full_message = self._build_ineligibility_message(failure_message, program_table_html)

                    # ONE single frappe.throw() — contains reason + program table
                    frappe.throw(
                        msg=full_message,
                        title=_("Eligibility Evaluation Results"),
                        wide=True,
                        is_minimizable=True
                    )
                    return  # never reached — throw exits — kept for clarity

            # Passed all mappings → Eligible
            self.evaluation_status = "Eligible"
            self.rejected_reason   = ""

        except frappe.ValidationError:
            raise
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                "Applicant Eligibility Validation Error"
            )

    # ──────────────────────────────────────────────
    # INELIGIBILITY MESSAGE BUILDER  (Frappe-native)
    # ──────────────────────────────────────────────

    def _build_ineligibility_message(self, failure_message, program_table_html):
        """
        Builds the full ineligibility HTML message using only Frappe's
        native CSS classes and design tokens — no inline colours.

        Structure:
          ┌─ Alert banner (indicator-pill red)  ──────────────────┐
          │  ✕  <failure_message>                                  │
          └────────────────────────────────────────────────────────┘
          ┌─ Program table section  ──────────────────────────────┐
          │  Heading + summary counts + full eligibility table     │
          └────────────────────────────────────────────────────────┘
        """
        escaped_reason = frappe.utils.escape_html(failure_message)

        return """
        <div class="msgprint-content">

            <!-- ── Ineligibility Alert ───────────────────────────────── -->
            <div class="alert alert-danger" style="display:flex;align-items:flex-start;gap:10px;margin-bottom:16px;">
                <span class="indicator-pill red no-margin" style="margin-top:3px;flex-shrink:0;"></span>
                <div>
                    <div style="font-weight:600;font-size:var(--text-base);">{reason}</div>
                    <div class="text-muted" style="font-size:var(--text-sm);margin-top:2px;">
                        {note}
                    </div>
                </div>
            </div>

            <!-- ── Program Options ───────────────────────────────────── -->
            {table}

        </div>
        """.format(
            reason=escaped_reason,
            note=_("The applicant does not meet the eligibility criteria for the selected program."),
            table=program_table_html,
        )

    # ──────────────────────────────────────────────
    # PROGRAM ELIGIBILITY TABLE (rendered inside throw)
    # ──────────────────────────────────────────────

    def _build_program_eligibility_html(self):
        """
        Returns styled HTML listing EVERY program on the applicant's
        campus + admission cycle with a full eligibility check per program.

        Layout:
          • Section heading with campus · cycle
          • Summary counts (eligible / ineligible)
          • Table: Program | Your Eligibility | Reason (if not eligible)

        Uses only Frappe's native CSS classes — no custom inline colours.
        The currently selected program is marked with a "Selected" badge.
        """
        all_programs = frappe.db.sql("""
            SELECT DISTINCT pm.program
            FROM `tabEligibility Rule Mapping` erm
            INNER JOIN `tabProgram Mapping` pm ON pm.parent = erm.name
            WHERE erm.is_active       = 1
              AND erm.campus          = %(campus)s
              AND erm.admission_cycle = %(admission_cycle)s
            ORDER BY pm.program ASC
        """, {
            "campus":          self.campus,
            "admission_cycle": self.admission_cycle,
        }, as_dict=True)

        if not all_programs:
            return (
                "<p class='text-muted' style='font-size:var(--text-sm);'>{0}</p>".format(
                    _("No programs found for this campus and admission cycle.")
                )
            )

        rows_html        = ""
        eligible_count   = 0
        ineligible_count = 0

        for prog_row in all_programs:
            prog_name = prog_row.get("program")
            if not prog_name:
                continue

            is_prog_eligible, reason = self._check_eligibility_for_program(prog_name)
            is_selected = (prog_name == self.program)

            if is_prog_eligible:
                eligible_count += 1
                pill_class   = "indicator-pill green no-margin"
                status_label = _("Eligible")
                reason_html  = "<span class='text-muted'>—</span>"
                row_class    = ""
            else:
                ineligible_count += 1
                pill_class   = "indicator-pill red no-margin"
                status_label = _("Not Eligible")
                reason_html  = (
                    "<span style='font-size:var(--text-sm);'>{0}</span>".format(
                        frappe.utils.escape_html(reason or "")
                    )
                )
                row_class    = ""

            # Program name cell — bold + "Selected" badge for the active program
            if is_selected:
                prog_display = """
                    <strong>{name}</strong>
                    &nbsp;<span class="indicator-pill blue no-margin"
                        style="font-size:10px;padding:1px 6px;vertical-align:middle;">
                        {label}
                    </span>
                """.format(
                    name  = frappe.utils.escape_html(prog_name),
                    label = _("Selected"),
                )
            else:
                prog_display = frappe.utils.escape_html(prog_name)

            rows_html += """
                <tr class="{row_class}">
                    <td class="list-subject" style="padding:8px 10px;vertical-align:middle;">
                        {prog}
                    </td>
                    <td style="padding:8px 10px;vertical-align:middle;text-align:center;white-space:nowrap;">
                        <span class="{pill}" style="vertical-align:middle;"></span>
                        &nbsp;<span style="font-size:var(--text-sm);font-weight:500;">{status}</span>
                    </td>
                    <td style="padding:8px 10px;vertical-align:middle;">
                        {reason}
                    </td>
                </tr>
            """.format(
                row_class = row_class,
                prog      = prog_display,
                pill      = pill_class,
                status    = status_label,
                reason    = reason_html,
            )

        # ── Summary counts ───────────────────────────────────────────────────
        summary_html = """
            <div style="display:flex;align-items:center;gap:16px;
                        margin-bottom:10px;flex-wrap:wrap;">
                <span>
                    <span class="indicator-pill green no-margin" style="vertical-align:middle;"></span>
                    &nbsp;<strong>{ec}</strong>
                    <span class="text-muted" style="font-size:var(--text-sm);">
                        &nbsp;{el}
                    </span>
                </span>
                <span class="text-muted">/</span>
                <span>
                    <span class="indicator-pill red no-margin" style="vertical-align:middle;"></span>
                    &nbsp;<strong>{ic}</strong>
                    <span class="text-muted" style="font-size:var(--text-sm);">
                        &nbsp;{il}
                    </span>
                </span>
                <span class="text-muted" style="font-size:var(--text-sm);">
                    ({total}&nbsp;{tl})
                </span>
            </div>
        """.format(
            ec    = eligible_count,
            el    = _("eligible"),
            ic    = ineligible_count,
            il    = _("not eligible"),
            total = eligible_count + ineligible_count,
            tl    = _("total"),
        )

        # ── Section heading ──────────────────────────────────────────────────
        heading_html = """
            <div style="display:flex;align-items:baseline;gap:6px;margin-bottom:4px;">
                <span style="font-weight:600;font-size:var(--text-base);">{heading}</span>
                <span class="text-muted" style="font-size:var(--text-sm);">
                    &mdash;&nbsp;{campus}&nbsp;&middot;&nbsp;{cycle}
                </span>
            </div>
        """.format(
            heading = _("Available Programs"),
            campus  = frappe.utils.escape_html(self.campus or ""),
            cycle   = frappe.utils.escape_html(self.admission_cycle or ""),
        )

        # ── Full table ───────────────────────────────────────────────────────
        table_html = """
            <div style="margin-top:8px;">
                {heading}
                <hr class="divider" style="margin:6px 0 10px 0;">
                {summary}
                <div style="overflow-x:auto;">
                    <table class="table table-bordered table-hover" style="margin-bottom:0;">
                        <thead>
                            <tr>
                                <th style="width:40%;">{col1}</th>
                                <th style="width:20%;text-align:center;">{col2}</th>
                                <th>{col3}</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows}
                        </tbody>
                    </table>
                </div>
            </div>
        """.format(
            heading = heading_html,
            summary = summary_html,
            col1    = _("Program"),
            col2    = _("Eligibility"),
            col3    = _("Reason (if not eligible)"),
            rows    = rows_html,
        )

        return table_html

    def _check_eligibility_for_program(self, program_name):
        """
        Runs the full eligibility engine for a given program using the current
        applicant's scores, categories, campus, admission_cycle, and academic_year —
        WITHOUT permanently modifying self.

        Temporarily swaps self.program → runs check → restores original in finally.

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

            # Rule mappings for this program
            rule_mappings = frappe.db.sql("""
                SELECT erm.name, erm.rule, erm.failure_message
                FROM `tabEligibility Rule Mapping` erm
                INNER JOIN `tabProgram Mapping` pm ON pm.parent = erm.name
                WHERE erm.is_active       = 1
                  AND erm.campus          = %(campus)s
                  AND erm.admission_cycle = %(admission_cycle)s
                  AND pm.program          = %(program)s
            """, {
                "campus":          self.campus,
                "admission_cycle": self.admission_cycle,
                "program":         program_name,
            }, as_dict=True)

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
            SELECT erm.name, erm.rule, erm.failure_message
            FROM `tabEligibility Rule Mapping` erm
            INNER JOIN `tabProgram Mapping` pm ON pm.parent = erm.name
            WHERE erm.is_active         = 1
              AND erm.campus            = %(campus)s
              AND erm.admission_cycle   = %(admission_cycle)s
              AND pm.program            = %(program)s
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
        Priority-based multi-category eligibility engine.

        CASE A — Applicant's category matches a reservation row:
            • Winning category's minimum_percentage overrides base rule threshold.
            • Non-percentage checks (HSC Group, Allowed Degree) still run.

        CASE B — No category match:
            • Full base rule evaluation (percentage + group + degree).

        Returns (is_eligible: bool, failure_message: str)
        """
        rule_name    = mapping.get("rule")
        mapping_name = mapping.get("name")

        failure_msg = (mapping.get("failure_message") or "").strip() or \
            "You do not meet the eligibility criteria for the selected program."

        base_rule = self._get_base_rule(rule_name)

        reservation_rows = frappe.db.sql("""
            SELECT category, priority, minimum_percentage
            FROM `tabRule Mapping Category`
            WHERE parent = %(mapping_name)s
            ORDER BY priority ASC
        """, {"mapping_name": mapping_name}, as_dict=True)

        applicant_categories = set(
            (row.category or "").strip()
            for row in (self.categories or [])
            if row.category
        )

        # ── CASE A ──────────────────────────────────────────────────────────
        if applicant_categories and reservation_rows:
            matched = [
                row for row in reservation_rows
                if (row.category or "").strip() in applicant_categories
            ]

            if matched:
                matched.sort(key=lambda r: (r.priority if r.priority is not None else 9999))
                winning = matched[0]

                required_min = flt(winning.minimum_percentage)
                operator     = (base_rule.get("operator") or ">=") if base_rule else ">="

                if not self._compare_any_academic_value(base_rule, required_min, operator):
                    return False, failure_msg

                if base_rule and not self._evaluate_non_percentage_checks(base_rule):
                    return False, failure_msg

                self._set_applied_category_info(
                    category=winning.category,
                    priority=winning.priority,
                    minimum=required_min
                )
                return True, ""

        # ── CASE B ──────────────────────────────────────────────────────────
        if not base_rule:
            return True, ""

        if not self.evaluate_single_rule(base_rule):
            return False, failure_msg

        self._set_applied_category_info(
            category="General",
            priority=None,
            minimum=self._get_required_value(base_rule)
        )
        return True, ""

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
          - HSC Group check
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
            required = rule.get("hsc_group")
            actual   = getattr(self, "hsc_group", None)
            if not actual or actual != required:
                return False

        return True

    # ──────────────────────────────────────────────
    # RULE EVALUATION (single base rule — full check)
    # ──────────────────────────────────────────────

    def evaluate_single_rule(self, rule):
        """
        Full evaluation of a base Eligibility Rule against the applicant.
        Checks: Allowed Degrees, HSC Group, and numeric threshold (Percentage / CGPA).
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

        if rule_type == "HSC Group":
            required = rule.get("hsc_group")
            actual   = getattr(self, "hsc_group", None)
            if not actual or actual != required:
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

        Called in TWO places:
          1. Inside validate_eligibility() immediately before frappe.throw() when
             the applicant is INELIGIBLE — so the Ineligible record is persisted
             even though the throw prevents validate() from completing normally.
          2. At the end of validate() as a safety net for the ELIGIBLE path.

        This ensures BOTH Eligible and Ineligible outcomes are always recorded.
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
                {"category": row.category}
                for row in (self.categories or [])
                if row.category
            ]
        }

        if existing:
            doc = frappe.get_doc("Eligibility Evaluation", existing)
            doc.update(doc_data)
        else:
            doc = frappe.get_doc(doc_data)

        doc.save(ignore_permissions=True)
        frappe.db.commit()

        frappe.db.commit()


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