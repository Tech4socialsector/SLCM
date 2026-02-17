import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, nowdate, flt
from datetime import datetime

class Applicant(Document):
    def validate(self):
        """Validate eligibility on each save"""
        self.validate_eligibility()
    
    def before_submit(self):
        """Block submission if ineligible"""
        if self.evaluation_status == "Ineligible":
            frappe.throw(_("You are not eligible for the selected program."))
    
    def validate_eligibility(self):
        """Main eligibility validation logic"""
        if not all([self.program, self.campus, self.admission_cycle, self.academic_year]):
            # Clear status if required fields are missing
            self.evaluation_status = ""
            self.rejected_reason = ""
            return
        
        try:
            # Get applicable rule mappings
            rule_mappings = self.get_applicable_rule_mappings()
            
            if not rule_mappings:
                # No rules found - set as eligible by default
                self.evaluation_status = "Eligible"
                self.rejected_reason = ""
                return
            
            # Process each rule mapping
            for mapping in rule_mappings:
                is_eligible, failure_message = self.evaluate_rule_mapping(mapping)
                
                if not is_eligible:
                    self.evaluation_status = "Ineligible"
                    self.rejected_reason = failure_message
                    return
            
            # All rules passed
            self.evaluation_status = "Eligible"
            self.rejected_reason = ""
            
        except Exception as e:
            frappe.log_error(f"Eligibility validation error: {str(e)}", "Applicant Eligibility")
            # On error, don't block the process but log it
            pass
    
    def get_applicable_rule_mappings(self):
        """Fetch rule mappings that match applicant criteria"""
        
        # First, get rule mappings that match program, campus, and admission cycle
        rule_mappings = frappe.db.sql("""
            SELECT DISTINCT
                erm.name,
                erm.failure_message,
                erm.reservation_category
            FROM `tabEligibility Rule Mapping` erm
            INNER JOIN `tabEligibility Program` ep ON ep.parent = erm.name
            WHERE erm.is_active = 1
                AND erm.campus = %(campus)s
                AND erm.admission_cycle = %(admission_cycle)s
                AND ep.program = %(program)s
        """, {
            'campus': self.campus,
            'admission_cycle': self.admission_cycle,
            'program': self.program
        }, as_dict=True)
        
        # Filter by category if applicant has categories
        if self.categories and rule_mappings:
            # Get applicant categories
            applicant_categories = [row.category for row in self.categories]
            
            filtered_mappings = []
            for mapping in rule_mappings:
                # Get mapping categories
                mapping_categories = frappe.db.sql("""
                    SELECT category, priority
                    FROM `tabRule Mapping Category`
                    WHERE parent = %(mapping_name)s
                    ORDER BY priority ASC
                """, {'mapping_name': mapping.name}, as_dict=True)
                
                if not mapping_categories:
                    # No category restriction - applies to all
                    filtered_mappings.append(mapping)
                else:
                    # Check if applicant categories match
                    mapping_category_list = [cat.category for cat in mapping_categories]
                    if any(cat in applicant_categories for cat in mapping_category_list):
                        filtered_mappings.append(mapping)
            
            return filtered_mappings
        
        return rule_mappings
    
    def evaluate_rule_mapping(self, mapping):
        """Evaluate a single rule mapping against applicant data"""
        
        # Get all eligibility rules for this mapping
        eligibility_rules = frappe.db.sql("""
            SELECT er.*
            FROM `tabEligibility Rule` er
            INNER JOIN `tabEligibility Mapping` em ON em.eligibility_rule = er.name
            WHERE em.parent = %(mapping_name)s
                AND er.is_active = 1
                AND er.campus = %(campus)s
                AND er.academic_year = %(academic_year)s
                AND %(current_date)s BETWEEN er.effective_from AND er.effective_to
        """, {
            'mapping_name': mapping.name,
            'campus': self.campus,
            'academic_year': self.academic_year,
            'current_date': nowdate()
        }, as_dict=True)
        
        if not eligibility_rules:
            return True, ""  # No applicable rules found
        
        # Evaluate each rule - ALL rules must pass
        for rule in eligibility_rules:
            is_rule_satisfied = self.evaluate_single_rule(rule)
            
            if not is_rule_satisfied:
                return False, mapping.failure_message
        
        return True, ""
    
    def evaluate_single_rule(self, rule):
        """Evaluate a single eligibility rule - FIXED LOGIC"""
        
        rule_type = rule.get('rule_type')
        qualification_level = rule.get('qualification_level')
        operator = rule.get('operator', '>=')
        
        # Step 1: Check HSC Group if rule type is HSC Group
        if rule_type == "HSC Group":
            required_hsc_group = rule.get('hsc_group')
            applicant_hsc_group = self.hsc_group
            
            # HSC Group must match exactly
            if not applicant_hsc_group or applicant_hsc_group != required_hsc_group:
                frappe.log_error(f"HSC Group mismatch: Applicant={applicant_hsc_group}, Required={required_hsc_group}", "Eligibility Check")
                return False
        
        # Step 2: Check percentage/CGPA requirements
        if rule_type in ["HSC Group", "Percentage", "CGPA"]:
            # Get applicant's academic value
            applicant_value = self.get_applicant_academic_value(qualification_level, rule)
            required_value = self.get_required_academic_value(rule)
            
            if applicant_value is None or required_value is None:
                frappe.log_error(f"Missing values: Applicant={applicant_value}, Required={required_value}", "Eligibility Check")
                return False
            
            # Perform comparison
            result = self.compare_academic_values(applicant_value, required_value, operator)
            frappe.log_error(f"Academic comparison: {applicant_value} {operator} {required_value} = {result}", "Eligibility Check")
            return result
        
        return True
    
    def get_applicant_academic_value(self, qualification_level, rule):
        """Get applicant's academic value based on qualification level"""
        
        if qualification_level == "XII":
            # For HSC level, always use HSC percentage
            return flt(self.hsc_percentage or 0)
            
        elif qualification_level == "UG":
            # For UG level, use UG CGPA
            return flt(self.ug_cgpa or 0)
            
        elif qualification_level == "PG":
            # For PG level, use PG CGPA
            return flt(self.pg_cgpa or 0)
        
        return None
    
    def get_required_academic_value(self, rule):
        """Get required academic value from rule"""
        
        # Priority order: required_percentage > required_cgpa > required_score
        if rule.get('required_percentage'):
            return flt(rule.get('required_percentage', 0))
        elif rule.get('required_cgpa'):
            return flt(rule.get('required_cgpa', 0))
        elif rule.get('required_score'):
            return flt(rule.get('required_score', 0))
            
        return None
    
    def compare_academic_values(self, applicant_value, required_value, operator):
        """Compare academic values using the operator"""
        
        try:
            applicant_value = flt(applicant_value)
            required_value = flt(required_value)
            
            if operator == ">=":
                return applicant_value >= required_value
            elif operator == "<=":
                return applicant_value <= required_value
            elif operator == "=":
                return applicant_value == required_value
            
        except (ValueError, TypeError):
            return False
        
        return False


# Client-side hooks for real-time validation
@frappe.whitelist()
def check_eligibility_on_change(doc):
    """Called from client side when fields change"""
    try:
        doc = frappe._dict(doc)
        applicant = frappe.new_doc("Applicant")
        
        # Set values
        for field in ['program', 'campus', 'admission_cycle', 'academic_year', 
                     'hsc_group', 'hsc_percentage', 'hsc_score', 'ug_program', 'ug_cgpa', 
                     'pg_program', 'pg_cgpa', 'categories']:
            if field in doc:
                setattr(applicant, field, doc[field])
        
        # Validate eligibility
        applicant.validate_eligibility()
        
        return {
            'evaluation_status': applicant.evaluation_status,
            'rejected_reason': applicant.rejected_reason
        }
        
    except Exception as e:
        frappe.log_error(f"Client eligibility check error: {str(e)}", "Applicant Eligibility")
        return {
            'evaluation_status': '',
            'rejected_reason': ''
        }

# Additional validation functions for hooks
def validate_applicant(doc, method):
    """Hook function for document validation"""
    doc.validate_eligibility()

def before_submit_applicant(doc, method):
    """Hook function before submit"""
    if doc.evaluation_status == "Ineligible":
        frappe.throw(_("You are not eligible for the selected program."))
