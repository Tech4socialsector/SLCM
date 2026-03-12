import frappe
from frappe import _
from slcm.admission.utils.portal import get_portal_config

no_cache = 1

def get_context(context):
    context.portal_config = get_portal_config()
    _user = frappe.session.user
    context.today = frappe.utils.getdate(frappe.utils.today())

    # ── Active Admission Cycle ───────────────────────────────────
    active_cycle_name = frappe.db.get_value("Admission Cycle", {"status": "Active"}, "name")
    if active_cycle_name:
        active_cycle_doc = frappe.get_doc("Admission Cycle", active_cycle_name)
        context.active_cycle = frappe._dict({
            "name": active_cycle_doc.name,
            "cycle_start_date": frappe.utils.getdate(active_cycle_doc.cycle_start_date) if active_cycle_doc.cycle_start_date else None,
            "cycle_end_date": frappe.utils.getdate(active_cycle_doc.cycle_end_date) if active_cycle_doc.cycle_end_date else None
        })
    else:
        context.active_cycle = None
    
    # Initialize all context variables
    context.no_applicant = False
    context.applicant = None
    context.all_applicants = []
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
        _app_param = frappe.form_dict.get('app')
        
        # Match dashboard logic for finding applications
        fields = ["name", "applicant_id", "candidate_name", "program", "campus", 
                  "admission_cycle", "application_status", "annual_house_hold_income", 
                  "percentage", "whether_scstobc_ncl", "pwd", "karnataka_category"]
        
        apps_by_owner = frappe.get_all("Applicant", filters={"owner": _user}, fields=fields, ignore_permissions=True)
        apps_by_email = frappe.get_all("Applicant", filters={"email": _user}, fields=fields, ignore_permissions=True)
        
        combined = {a.name: a for a in (apps_by_owner + apps_by_email)}
        applicant_records = sorted(combined.values(), key=lambda x: x.name, reverse=True)

        if not applicant_records:
            context.no_applicant = True
            return context

        # Pick specific app if requested, else newest
        applicant = None
        if _app_param and _app_param in combined:
            applicant = combined[_app_param]
        else:
            applicant = applicant_records[0]
            
        context.applicant = applicant
        context.all_applicants = applicant_records

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
            sc_st_obc = (getattr(applicant, "whether_scstobc_ncl", None) or "").strip()
            if sc_st_obc and sc_st_obc.lower() != "na":
                applicant_categories.add(sc_st_obc)
            if (getattr(applicant, "pwd", None) or "").strip() == "Yes":
                applicant_categories.add("PWD")
            if (getattr(applicant, "karnataka_category", None) or "").strip() == "Yes":
                applicant_categories.add("Karnataka category")

        # 3. Fetch All Scholarship Applications
        all_apps = frappe.get_all(
            "Scholarship Application",
            filters={"applicant_id": applicant.name},
            fields=["name", "scholarship_scheme", "status", "creation", "modified", "approval_date", "calculated_benefit", "final_fee_amount", "rejection_reason", "original_fee_amount"],
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
                    "apply_on": scheme_doc.apply_on,
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
        from slcm.admission.utils.scholarship_availability import get_available_scholarships_for_dashboard
        
        raw_eligible = get_available_scholarships_for_dashboard(
            applicant.name,
            applicant.admission_cycle,
            applicant.campus,
            applicant.program,
            [applicant.application_status]
        )

        eligible_schemes = []
        for s in raw_eligible:
            s_full = get_scheme_data(s.get('name'))
            if s_full:
                eligible_schemes.append(s_full)

        context.eligible_scholarships = eligible_schemes

        # 5. KPI Counts
        context.kpis = {
            "eligible": len(eligible_schemes),
            "applied": len(all_apps),
            "approved": len(context.approved_scholarships),
            "amount_awarded": sum([flt(app.calculated_benefit) for app in context.approved_scholarships if app.calculated_benefit])
        }

    except Exception as e:
        frappe.log_error(f"Scholarship Dashboard Error: {e}", "Scholarship Dashboard")
        context.error = str(e)

    return context

def flt(v):
    from frappe.utils import flt as _flt
    return _flt(v)
