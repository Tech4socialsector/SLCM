import frappe
from frappe import _
from slcm.admission.utils.portal import get_portal_config

no_cache = 1

def get_context(context):
    context.portal_config = get_portal_config()
    _user = frappe.session.user
    
    # Initialize all context variables
    context.no_applicant = False
    context.applicant = None
    context.eligible_scholarships = []
    context.applied_scholarships = []
    context.approved_scholarships = []
    context.rejected_scholarships = []
    context.kpis = {"eligible": 0, "applied": 0, "approved": 0, "amount_awarded": 0}
    context.error = None

    if _user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect=/merit-and-scholarship/scholarships"
        raise frappe.Redirect

    try:
        # 1. Fetch Applicant Details
        applicant_records = frappe.get_all(
            "Applicant",
            filters={"owner": _user},
            fields=["name", "applicant_id", "candidate_name", "program", "campus", "admission_cycle", "application_status", "annual_house_hold_income", "percentage"],
            ignore_permissions=True
        )
        if not applicant_records:
            applicant_records = frappe.get_all(
                "Applicant",
                filters={"email": _user},
                fields=["name", "applicant_id", "candidate_name", "program", "campus", "admission_cycle", "application_status", "annual_house_hold_income", "percentage"],
                ignore_permissions=True
            )

        if not applicant_records:
            context.no_applicant = True
            return context

        applicant = applicant_records[0]
        context.applicant = applicant

        # 2. Get Categories from Eligibility Result
        applicant_categories = set()
        eligibility_result = frappe.get_all(
            "Eligibility Result",
            filters={"applicant_id": applicant.name},
            fields=["name"],
            ignore_permissions=True
        )
        
        if eligibility_result:
            er_doc = frappe.get_doc("Eligibility Result", eligibility_result[0].name, ignore_permissions=True)
            for cat_row in er_doc.get("category", []):
                if cat_row.category:
                    applicant_categories.add(cat_row.category)
        
        if not applicant_categories:
            app_full = frappe.get_doc("Applicant", applicant.name, ignore_permissions=True)
            sc_st_obc = (getattr(app_full, "whether_scstobc_ncl", None) or "").strip()
            if sc_st_obc and sc_st_obc.lower() != "na":
                applicant_categories.add(sc_st_obc)
            if (getattr(app_full, "pwd", None) or "").strip() == "Yes":
                applicant_categories.add("PWD")
            if (getattr(app_full, "karnataka_category", None) or "").strip() == "Yes":
                applicant_categories.add("Karnataka category")

        # 3. Fetch All Scholarship Applications
        all_apps = frappe.get_all(
            "Scholarship Application",
            filters={"applicant_id": applicant.name},
            fields=["name", "scholarship_scheme", "status", "creation", "approval_date", "calculated_benefit", "final_fee_amount"],
            order_by="creation desc",
            ignore_permissions=True
        )
        
        applied_scheme_names = [app.scholarship_scheme for app in all_apps]
        
        scheme_cache = {}
        def get_scheme_data(scheme_id):
            if scheme_id in scheme_cache: return scheme_cache[scheme_id]
            try:
                scheme_doc = frappe.get_doc("Scholarship Scheme", scheme_id, ignore_permissions=True)
                rules = frappe.get_all(
                    "Scholarship Coverage Rule",
                    filters={"parent": scheme_id},
                    fields=["fee_component", "coverage_type", "coverage_value", "maximum_cap"],
                    ignore_permissions=True
                )
                data = {
                    "name": scheme_doc.name,
                    "scheme_name": scheme_doc.scheme_name,
                    "scheme_type": scheme_doc.scheme_type,
                    "description": scheme_doc.description,
                    "max_amount": scheme_doc.max_amount,
                    "coverage_type": scheme_doc.coverage_type,
                    "coverage_value": scheme_doc.coverage_value,
                    "application_end": scheme_doc.application_end,
                    "eligibility_criteria": scheme_doc.eligibility_criteria,
                    "coverage_rules": rules
                }
                scheme_cache[scheme_id] = data
                return data
            except:
                return None

        # Categorize Applications
        for app in all_apps:
            s_data = get_scheme_data(app.scholarship_scheme)
            if s_data:
                app.update(s_data)
                if app.status == "Approved":
                    context.approved_scholarships.append(app)
                elif app.status == "Rejected":
                    context.rejected_scholarships.append(app)
                else:
                    context.applied_scholarships.append(app)

        # 4. Fetch Eligible Schemes
        eligible_schemes = []
        active_mappings = frappe.get_all(
            "Scholarship Scheme Mapping",
            filters={"is_active": 1},
            fields=["scholarship_scheme", "admission_cycle", "campus", "program", "category"],
            ignore_permissions=True
        )

        is_selected = applicant.application_status in ["Selected", "Offered", "Fee Paid", "Admission Confirmed"]
        
        seen_eligible = set()
        for mapping in active_mappings:
            scheme_id = mapping.scholarship_scheme
            if scheme_id in applied_scheme_names or scheme_id in seen_eligible:
                continue
            
            mapping_match = True
            if mapping.program and mapping.program != applicant.program: mapping_match = False
            if mapping.campus and mapping.campus != applicant.campus: mapping_match = False
            if mapping.admission_cycle and mapping.admission_cycle != applicant.admission_cycle: mapping_match = False
            if mapping.category and mapping.category not in applicant_categories: mapping_match = False

            if mapping_match and is_selected:
                s_data = get_scheme_data(scheme_id)
                if s_data:
                    eligible_schemes.append(s_data)
                    seen_eligible.add(scheme_id)

        context.eligible_scholarships = eligible_schemes

        # 5. KPI Counts
        context.kpis = {
            "eligible": len(eligible_schemes),
            "applied": len(all_apps),
            "approved": len(context.approved_scholarships),
            "amount_awarded": sum([app.calculated_benefit for app in context.approved_scholarships if app.calculated_benefit])
        }

    except Exception as e:
        frappe.log_error(f"Scholarship Dashboard Error: {e}", "Scholarship Dashboard")
        context.error = str(e)

    return context
