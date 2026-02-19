import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate, flt


class Applicant(Document):

    # ──────────────────────────────────────────────
    # VALIDATE
    # ──────────────────────────────────────────────

    def validate(self):
        self.validate_eligibility()

        # Always create/update evaluation record
        self.create_or_update_evaluation()

        # Block save if ineligible
        if self.evaluation_status == "Ineligible":
            frappe.throw(
                _("Not Eligible: {0}").format(
                    self.rejected_reason or "You are not eligible for the selected program."
                ),
                title=_("Not Eligible")
            )

    def before_submit(self):
        if self.evaluation_status == "Ineligible":
            frappe.throw(
                _("Submission Not Allowed: Applicant is not eligible."),
                title=_("Submission Not Allowed")
            )

    # ──────────────────────────────────────────────
    # CORE ELIGIBILITY LOGIC
    # ──────────────────────────────────────────────

    def validate_eligibility(self):
        """
        Main eligibility entry point.

        Flow:
        ─────
        STEP 0 — National Test Exemption check.
            • If the applicant has a national test result (national_test_name + percentage)
              and a matching active National Test Exemption Rule is found for the
              applicant's program/campus/admission_cycle/academic_year:

                - Evaluate applicant's percentage against mark_percentage + operator.

                - If PASSED and "Overrides Academic Rule" is checked:
                    → Mark Eligible immediately. Skip all academic rule checks.
                    → Store exemption flags (exempts_entrance_test, exempts_interview).

                - If PASSED but "Overrides Academic Rule" is NOT checked:
                    → Store exemption flags, then continue to academic rule checks.

                - If FAILED (percentage not met):
                    → Proceed to academic rule checks as normal (no bypass).

        STEP 1 — Academic Eligibility Rule Mapping checks (unchanged).
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

            # National test passed but does NOT override → store flags, continue academic check
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
                    self.evaluation_status = "Ineligible"
                    self.rejected_reason   = failure_message

                    frappe.msgprint(
                        _("Not Eligible: {0}").format(failure_message),
                        title=_("Not Eligible"),
                        indicator="red"
                    )
                    return

            # Passed all mappings
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

        Returns {"passed": False, ...} when:
          - Applicant has no national_test_name
          - No matching active rule found for program/campus/cycle/year/test/date
          - Applicant's percentage does not satisfy the rule's threshold
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

        # Find matching active National Test Exemption Rule.
        # The rule must have the applicant's program in its Applicable Program child table.
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
        """Store national test exemption flags on the doc (persisted via Eligibility Evaluation)."""
        self.exempts_entrance_test   = 1 if result.get("exempts_entrance_test")   else 0
        self.exempts_interview       = 1 if result.get("exempts_interview")        else 0
        self.national_test_rule_used = result.get("rule_name", "")

    def _clear_national_test_flags(self):
        """Clear national test exemption flags when no exemption applies."""
        self.exempts_entrance_test   = 0
        self.exempts_interview       = 0
        self.national_test_rule_used = ""

    # ──────────────────────────────────────────────
    # STEP 1 — Fetch matching rule mappings
    # ──────────────────────────────────────────────

    def _get_rule_mappings_for_applicant(self):
        """
        Return all active Eligibility Rule Mappings for the
        applicant's program + campus + admission_cycle.
        """
        return frappe.db.sql("""
            SELECT erm.name, erm.rule, erm.failure_message
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

                applicant_value = self._get_applicant_value(base_rule)
                required_min    = flt(winning.minimum_percentage)
                operator        = (base_rule.get("operator") or ">=") if base_rule else ">="

                if not self._compare(applicant_value, required_min, operator):
                    return False, failure_msg

                # Non-percentage checks (HSC Group, Allowed Degree) still apply
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
        """
        Fetch the active Eligibility Rule matching campus + academic_year + date range.
        Returns the rule dict or None.
        """
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
          - Allowed Degree check
          - HSC Group check

        Used in CASE A where the percentage threshold is already overridden
        by the winning reservation category's minimum_percentage, but all
        other conditions still apply.

        Returns True if all checks pass, False otherwise.
        """
        rule_type           = rule.get("rule_type")
        qualification_level = rule.get("qualification_level")
        rule_name           = rule.get("name")

        # ── Allowed Degree check ─────────────────────────────────────────────
        allowed_degrees = frappe.db.sql("""
            SELECT degree_name
            FROM `tabEligibility Allowed Degree`
            WHERE parent = %(rule_name)s
        """, {"rule_name": rule_name}, as_dict=True)

        allowed_degree_list = [r.degree_name for r in allowed_degrees if r.degree_name]

        if allowed_degree_list:
            applicant_degree = getattr(
                self,
                "pg_program" if qualification_level == "PG" else "ug_program",
                None
            )
            if not applicant_degree or applicant_degree not in allowed_degree_list:
                return False

        # ── HSC Group check ──────────────────────────────────────────────────
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

        # ── Allowed Degree check ─────────────────────────────────────────────
        allowed_degrees = frappe.db.sql("""
            SELECT degree_name
            FROM `tabEligibility Allowed Degree`
            WHERE parent = %(rule_name)s
        """, {"rule_name": rule_name}, as_dict=True)

        allowed_degree_list = [r.degree_name for r in allowed_degrees if r.degree_name]

        if allowed_degree_list:
            applicant_degree = getattr(
                self,
                "pg_program" if qualification_level == "PG" else "ug_program",
                None
            )
            if not applicant_degree or applicant_degree not in allowed_degree_list:
                return False

        # ── HSC Group check ──────────────────────────────────────────────────
        if rule_type == "HSC Group":
            required = rule.get("hsc_group")
            actual   = getattr(self, "hsc_group", None)
            if not actual or actual != required:
                return False

        # ── Numeric check ────────────────────────────────────────────────────
        if rule_type in ["HSC Group", "Percentage", "CGPA"]:
            applicant_value = self.get_applicant_academic_value(qualification_level)
            required_value  = self.get_required_academic_value(rule)

            if applicant_value is None or required_value is None:
                return False

            return self._compare(applicant_value, required_value, operator)

        return True

    # ──────────────────────────────────────────────
    # VALUE HELPERS
    # ──────────────────────────────────────────────

    def _get_applicant_value(self, rule):
        if not rule:
            return flt(self.hsc_percentage or 0)
        return self.get_applicant_academic_value(rule.get("qualification_level"))

    def _get_required_value(self, rule):
        if not rule:
            return None
        return self.get_required_academic_value(rule)

    def get_applicant_academic_value(self, qualification_level):
        if qualification_level == "XII":
            return flt(self.hsc_percentage or 0)
        if qualification_level == "UG":
            return flt(self.ug_cgpa or 0)
        if qualification_level == "PG":
            return flt(self.pg_cgpa or 0)
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

    # Kept for backward compatibility
    def compare_values(self, actual, required, operator):
        return self._compare(actual, required, operator)

    def _set_applied_category_info(self, category, priority, minimum):
        self.applied_category = category
        self.applied_priority = priority if priority is not None else ""
        self.applied_minimum  = minimum

    # ──────────────────────────────────────────────
    # CREATE / UPDATE ELIGIBILITY EVALUATION RECORD
    # ──────────────────────────────────────────────

    def create_or_update_evaluation(self):
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

        # National test exemption flags (set by _apply_national_test_flags)
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
            # ── National test exemption data ─────────────────────────────────
            "exempts_entrance_test":   exempts_entrance_test,
            "exempts_interview":       exempts_interview,
            "national_test_rule_used": national_test_rule_used,
            # ── Reservation categories ───────────────────────────────────────
            "reservation_category": [
                {"category": row.category}
                for row in (self.categories or [])
                if row.category
            ]
        }

        if existing:
            doc_data["name"] = existing

        doc = frappe.get_doc(doc_data)
        doc.save(ignore_permissions=True)

        # Commit so record persists even if applicant save fails
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
        eval_data["name"] = existing

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
