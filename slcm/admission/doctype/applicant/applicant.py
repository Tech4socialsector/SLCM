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


       # Always create/update evaluation record first
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


       if not all([self.program, self.campus, self.admission_cycle, self.academic_year]):
           self.evaluation_status = ""
           self.rejected_reason = ""
           return


       try:
           rule_mappings = self.get_applicable_rule_mappings()


           if not rule_mappings:
               self.evaluation_status = "Eligible"
               self.rejected_reason = ""
               return


           for mapping in rule_mappings:


               is_eligible, failure_message = self.evaluate_rule_mapping(mapping)


               if not is_eligible:
                   self.evaluation_status = "Ineligible"
                   self.rejected_reason = failure_message


                   frappe.msgprint(
                       _("Not Eligible: {0}").format(
                           failure_message or "You are not eligible for the selected program."
                       ),
                       title=_("Not Eligible"),
                       indicator="red"
                   )
                   return


           # Passed all rules
           self.evaluation_status = "Eligible"
           self.rejected_reason = ""


       except frappe.ValidationError:
           raise
       except Exception:
           frappe.log_error(
               frappe.get_traceback(),
               "Applicant Eligibility Validation Error"
           )


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


       # Safe getattr — new docs may not have these set yet
       current_status = getattr(self, "evaluation_status", None) or "Eligible"
       current_reason = getattr(self, "rejected_reason", None) or ""


       doc_data = {
           "doctype": "Eligibility Evaluation",
           "applicant_name": applicant_name,
           "academic_year": self.academic_year,
           "admission_cycle": self.admission_cycle,
           "program": self.program,
           "campus": self.campus,
           "evaluation_status": current_status,
           "failure_message": current_reason,
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
   # RULE FETCHING
   # ──────────────────────────────────────────────


   def get_applicable_rule_mappings(self):


       rule_mappings = frappe.db.sql("""
           SELECT erm.name, erm.failure_message, erm.rule
           FROM `tabEligibility Rule Mapping` erm
           WHERE erm.is_active = 1
               AND erm.campus = %(campus)s
               AND erm.admission_cycle = %(admission_cycle)s
               AND erm.program = %(program)s
       """, {
           "campus": self.campus,
           "admission_cycle": self.admission_cycle,
           "program": self.program
       }, as_dict=True)


       if not rule_mappings:
           return []


       applicant_categories = [
           row.category for row in (self.categories or [])
           if row.category
       ]


       filtered = []


       for mapping in rule_mappings:


           mapping_categories = frappe.db.sql("""
               SELECT category
               FROM `tabRule Mapping Category`
               WHERE parent = %(mapping_name)s
           """, {"mapping_name": mapping.name}, as_dict=True)


           mapping_category_list = [
               c.category for c in mapping_categories if c.category
           ]


           if not mapping_category_list:
               filtered.append(mapping)


           elif applicant_categories and any(
               cat in applicant_categories for cat in mapping_category_list
           ):
               filtered.append(mapping)


       return filtered


   # ──────────────────────────────────────────────
   # RULE EVALUATION
   # ──────────────────────────────────────────────


   def evaluate_rule_mapping(self, mapping):


       rule_name = mapping.get("rule")


       if not rule_name:
           return True, ""


       rules = frappe.db.sql("""
           SELECT *
           FROM `tabEligibility Rule`
           WHERE name = %(rule_name)s
               AND is_active = 1
               AND campus = %(campus)s
               AND academic_year = %(academic_year)s
               AND %(today)s BETWEEN effective_from AND effective_to
       """, {
           "rule_name": rule_name,
           "campus": self.campus,
           "academic_year": self.academic_year,
           "today": nowdate()
       }, as_dict=True)


       if not rules:
           return True, ""


       rule = rules[0]


       if not self.evaluate_single_rule(rule):
           return False, mapping.failure_message


       return True, ""


   def evaluate_single_rule(self, rule):


       rule_type = rule.get("rule_type")
       qualification_level = rule.get("qualification_level")
       operator = rule.get("operator") or ">="
       rule_name = rule.get("name")


       # ──────────────────────────────────────────
       # ALLOWED DEGREE CHECK
       # Child doctype : Eligibility Allowed Degree
       # Parent field  : allowed_degrees
       # Degree field  : degree_name  (Link → Program)
       # ──────────────────────────────────────────
       allowed_degrees = frappe.db.sql("""
           SELECT degree_name
           FROM `tabEligibility Allowed Degree`
           WHERE parent = %(rule_name)s
       """, {"rule_name": rule_name}, as_dict=True)


       allowed_degree_list = [
           row.degree_name for row in allowed_degrees if row.degree_name
       ]


       if allowed_degree_list:
           # Pick the correct applicant program field based on qualification level
           if qualification_level == "PG":
               applicant_degree = getattr(self, "pg_program", None)
           else:
               # Covers UG and XII (XII won't normally use degree check,
               # but safe to default to ug_program)
               applicant_degree = getattr(self, "ug_program", None)


           if not applicant_degree or applicant_degree not in allowed_degree_list:
               return False


       # ──────────────────────────────────────────
       # HSC Group check
       # ──────────────────────────────────────────
       if rule_type == "HSC Group":
           required = rule.get("hsc_group")
           actual = getattr(self, "hsc_group", None)


           if not actual or actual != required:
               return False


       # ──────────────────────────────────────────
       # Percentage / CGPA / HSC Group numeric check
       # ──────────────────────────────────────────
       if rule_type in ["HSC Group", "Percentage", "CGPA"]:


           applicant_value = self.get_applicant_academic_value(qualification_level)
           required_value = self.get_required_academic_value(rule)


           if applicant_value is None or required_value is None:
               return False


           return self.compare_values(applicant_value, required_value, operator)


       return True


   # ──────────────────────────────────────────────
   # VALUE HELPERS
   # ──────────────────────────────────────────────


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


   def compare_values(self, actual, required, operator):


       try:
           actual = flt(actual)
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




# ──────────────────────────────────────────────
# WHITELIST API
# ──────────────────────────────────────────────


@frappe.whitelist()
def get_eligible_programs_for_campus(campus, admission_cycle):


   programs = frappe.db.sql("""
       SELECT DISTINCT erm.program
       FROM `tabEligibility Rule Mapping` erm
       WHERE erm.is_active = 1
           AND erm.campus = %(campus)s
           AND erm.admission_cycle = %(admission_cycle)s
   """, {
       "campus": campus,
       "admission_cycle": admission_cycle
   }, as_dict=True)


   return [p.program for p in programs if p.program]




# ──────────────────────────────────────────────
# Async function to create Eligibility Evaluation
# ──────────────────────────────────────────────


def create_eligibility_evaluation_async(
   applicant_name, status, failure_msg, categories,
   program, campus, admission_cycle, academic_year
):
   """Create or update Eligibility Evaluation record asynchronously"""


   if not all([program, campus, admission_cycle, academic_year]):
       return


   existing = frappe.db.get_value(
       "Eligibility Evaluation",
       filters={"applicant_name": applicant_name},
       fieldname="name"
   )


   eval_data = {
       "doctype": "Eligibility Evaluation",
       "applicant_name": applicant_name,
       "academic_year": academic_year,
       "admission_cycle": admission_cycle,
       "program": program,
       "campus": campus,
       "evaluation_status": status,
       "failure_message": failure_msg,
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
   eligible, msg = doc.check_eligibility()
   if not eligible:
       frappe.throw(
           _("Not Eligible: {0}").format(
               msg or "You are not eligible for the selected program."
           ),
           title=_("Submission Not Allowed")
       )



