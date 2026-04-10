import frappe
from frappe import _

def get_context(context):
    """
    Controller for /pace/admission/<name>
    Fetches PACE Programme details and enriches the context for the template.
    """
    try:
        # 1. Get the programme slug from the URL path
        # In frappe's web engine, if the file is named pace_programme_details.py
        # and the URL is /pace/pace_programme_details/<slug>
        # then <slug> is available in frappe.form_dict.name or frappe.request.path
        slug = frappe.form_dict.get("name")

        if not slug:
            frappe.log_error("Programme slug missing in URL", "PACE Programme Details Error")
            frappe.throw(_("Programme not specified."), frappe.DoesNotExistError)

        # 2. Fetch the PACE Programme document by route (slug)
        # The URL slug corresponds to the 'route' field in the doctype
        programme_name = frappe.db.get_value("PACE Programme", {"route": slug}, "name")
        
        if not programme_name:
            # Fallback: try finding by name directly in case the slug IS the name
            if frappe.db.exists("PACE Programme", slug):
                programme_name = slug
            else:
                frappe.log_error(f"Programme with route '{slug}' not found", "PACE Programme Details Error")
                frappe.throw(
                    _("Programme '{0}' not found.").format(slug),
                    frappe.DoesNotExistError,
                )

        programme = frappe.get_doc("PACE Programme", programme_name)

        # 3. Guard: only expose published programmes to the public
        if not programme.published:
            frappe.throw(_("This programme is not currently published."), frappe.PermissionError)

        # ------------------------------------------------------------------
        # 4. Resolve course details
        # ------------------------------------------------------------------
        courses = []
        for idx, row in enumerate(programme.course or [], start=1):
            try:
                course_doc = frappe.get_doc("Course", row.course)
                courses.append(
                    {
                        "index": str(idx).zfill(2),
                        "name": course_doc.name,
                        "course_name": course_doc.course_name,
                        "description": getattr(course_doc, "description", ""),
                        "credits": getattr(course_doc, "total_credits", None),
                        "hours": getattr(course_doc, "total_hours", None),
                        "is_mandatory": getattr(course_doc, "is_mandatory", False),
                    }
                )
            except frappe.DoesNotExistError:
                continue

        # ------------------------------------------------------------------
        # 5. Admission status badge helper
        # ------------------------------------------------------------------
        status_map = {
            "Open": {"label": "Open", "css": "bg-green-600 text-white"},
            "Closed": {"label": "Closed", "css": "bg-error text-white"},
            "Upcoming": {"label": "Upcoming", "css": "bg-secondary text-white"},
        }
        admission_status = programme.admission_status or "Closed"
        status_badge = status_map.get(
            admission_status,
            {"label": admission_status, "css": "bg-stone-400 text-white"},
        )

        # ------------------------------------------------------------------
        # 5.5 Fetch Fees from PACE Admission
        # ------------------------------------------------------------------
        fee_indian = 0
        fee_foreign = 0
        active_admission = frappe.db.get_value("PACE Admission", {"active": 1}, "name")
        
        if active_admission:
            fees = frappe.db.get_value("PACE Admission Programme", 
                {"parent": active_admission, "programme": programme.name}, 
                ["appliocation_fee_indian", "appliocation_fee_foreign"], as_dict=True)
            if fees:
                fee_indian = fees.appliocation_fee_indian
                fee_foreign = fees.appliocation_fee_foreign

        # ------------------------------------------------------------------
        # 6. Build the context
        # ------------------------------------------------------------------
        context.update(
            {
                "programme_name":    programme.programme_name,
                "programme_code":    programme.programme_code,
                "route":             programme.route,
                "contact_email":     programme.contact_email,
                "banner_image":      programme.banner_image,
                "fee_indian":        frappe.utils.fmt_money(fee_indian, currency="INR"),
                "fee_foreign":       frappe.utils.fmt_money(fee_foreign, currency="INR"),
                "admission_status":  admission_status,
                "status_badge":      status_badge,
                "duration":          programme.duration,
                "instructions_text": programme.instructions_text,
                "instructions_link": programme.instructions_link,
                "show_overview_tab":         programme.show_overview_tab,
                "show_eligibility_tab":      programme.show_eligibility_tab,
                "show_apply_introduction":   programme.show_apply_introduction,
                "overview":    programme.overview,
                "eligibility": programme.eligibility,
                "apply_intro": programme.apply_intro,
                "courses": courses,
                "title":       programme.programme_name,
                "description": frappe.utils.strip_html_tags(programme.overview or "")[:160],
            }
        )

    except Exception as e:
        # Avoid logging DoesNotExistError as an error in the log if it's just a 404
        if not isinstance(e, frappe.DoesNotExistError):
            frappe.log_error(frappe.get_traceback(), "PACE Programme Details Controller Error")
        
        if not frappe.conf.developer_mode and not isinstance(e, (frappe.DoesNotExistError, frappe.PermissionError)):
            frappe.throw(_("An error occurred while loading the programme details. Please contact support."))
        else:
            raise e
