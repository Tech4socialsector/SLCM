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

        # 4. Resolve Course details
        # ------------------------------------------------------------------
        courses = []
        for idx, row in enumerate(programme.course or [], start=1):
            if not row.course:
                continue
            try:
                c_name = row.course
                prog_course = frappe.get_doc("PACE Programme Course", c_name)
                
                units = []
                for u_row in sorted(prog_course.unites or [], key=lambda x: x.order or 99):
                    units.append({
                        "title": u_row.unit_title,
                        "description": u_row.unit_description,
                        "order": u_row.order
                    })

                courses.append({
                    "id": c_name.replace(" ", "-").lower(),
                    "title": prog_course.course_title,
                    "intro": prog_course.course_intro,
                    "units": units,
                    "order": row.order or idx
                })
            except frappe.DoesNotExistError:
                continue

        # ------------------------------------------------------------------
        # 4.1 Resolve Faculty details
        # ------------------------------------------------------------------
        from frappe.utils import cint
        page = cint(frappe.form_dict.get("page")) or 1
        page_size = 4
        
        all_faculty = [row.faculty for row in programme.faculty or [] if row.faculty]
        total_faculty = len(all_faculty)
        total_pages = (total_faculty + page_size - 1) // page_size
        
        if page < 1:
            page = 1
        elif page > total_pages and total_pages > 0:
            page = total_pages
            
        start_idx = (page - 1) * page_size
        paginated_faculty_ids = all_faculty[start_idx:start_idx + page_size]

        faculty = []
        for fid in paginated_faculty_ids:
            try:
                f_doc = frappe.get_doc("Faculty", fid)
                faculty.append({
                    "name": f"{f_doc.first_name} {f_doc.last_name or ''}".strip(),
                    "designation": getattr(f_doc, "designation", ""),
                    "photo": f_doc.photo or "/assets/slcm/images/default-avatar.png",
                    "qualification": getattr(f_doc, "qualification", ""),
                    "email": getattr(f_doc, "email", ""),
                    "phone": getattr(f_doc, "phone", ""),
                    "is_hod": getattr(f_doc, "is_hod", 0),
                    "experience_years": getattr(f_doc, "experience_years", None) or "",
                    "specialization": getattr(f_doc, "specialization", "") or "",
                    "highlights": getattr(f_doc, "highlights", "") or "",
                    "institution": getattr(f_doc, "institution", "") or "",
                })
            except frappe.DoesNotExistError:
                continue

        # ------------------------------------------------------------------
        # 4.2 Resolve FAQs
        # ------------------------------------------------------------------
        faq_page = cint(frappe.form_dict.get("faq_page")) or 1
        faq_page_size = 5
        
        all_faqs = frappe.get_all("PACE FAQs", 
            filters={"programme": programme.name}, 
            fields=["question", "answer", "category"],
            order_by="idx asc")
            
        total_faqs = len(all_faqs)
        faq_total_pages = (total_faqs + faq_page_size - 1) // faq_page_size
        
        if faq_page < 1:
            faq_page = 1
        elif faq_page > faq_total_pages and faq_total_pages > 0:
            faq_page = faq_total_pages
            
        faq_start_idx = (faq_page - 1) * faq_page_size
        faqs = all_faqs[faq_start_idx:faq_start_idx + faq_page_size]

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
        # 5.5 Fetch Fees from PACE Admission and PACE Fee Structure
        # ------------------------------------------------------------------
        fee_indian = 0
        fee_foreign = 0
        active_admission_data = frappe.db.get_value("PACE Admission", {"status": "Active", "docstatus": ["<", 2]}, ["name", "academic_year"], as_dict=True)
        active_admission = active_admission_data.name if active_admission_data else None
        academic_year = active_admission_data.academic_year if active_admission_data else ""
        
        if active_admission:
            fees = frappe.db.get_value("PACE Admission Programme", 
                {"parent": active_admission, "programme": programme.name}, 
                ["application_fee_indian", "application_fee_foreign"], as_dict=True)
            if fees:
                fee_indian = fees.application_fee_indian
                fee_foreign = fees.application_fee_foreign

        # Fetch PACE Fee Structure dynamically mapped to the same academic year
        indian_fees = []
        foreign_fees = []
        other_fees = []
        
        indian_total_val = fee_indian
        foreign_total_val = fee_foreign
        
        if academic_year:
            fee_structure_docs = frappe.get_all(
                "PACE Fee Structure",
                filters={"pace_program": programme.name, "academic_year": academic_year, "status": "Active"},
                fields=["name"]
            )
            for fs in fee_structure_docs:
                fs_doc = frappe.get_doc("PACE Fee Structure", fs.name)
                
                for row in fs_doc.get("fee_components_for_indians") or []:
                    indian_fees.append({
                        "category": row.fee_component,
                        "amount": frappe.utils.fmt_money(row.total_amount, currency="INR")
                    })
                    indian_total_val += row.total_amount
                    
                for row in fs_doc.get("fee_components_for_foreign") or []:
                    foreign_fees.append({
                        "category": row.fee_component,
                        "amount": frappe.utils.fmt_money(row.total_amount, currency="INR")
                    })
                    foreign_total_val += row.total_amount
                    
                for row in fs_doc.get("other_fees") or []:
                    other_fees.append({
                        "category": row.fee_component,
                        "amount": frappe.utils.fmt_money(row.total_amount, currency="INR")
                    })

        context.update(
            {
                "programme_name":    programme.programme_name,
                "programme_prefix":  programme.programme_prefix,
                "programme_code":    programme.programme_code,
                "route":             programme.route,
                "contact_email":     programme.contact_email,
                "banner_image":      programme.banner_image,
                "fee_indian":        frappe.utils.fmt_money(fee_indian, currency="INR"),
                "fee_foreign":       frappe.utils.fmt_money(fee_foreign, currency="INR"),
                "indian_fees":       indian_fees,
                "foreign_fees":      foreign_fees,
                "other_fees":        other_fees,
                "indian_total":      frappe.utils.fmt_money(indian_total_val, currency="INR"),
                "foreign_total":     frappe.utils.fmt_money(foreign_total_val, currency="INR"),
                "admission_status":  admission_status,
                "status_badge":      status_badge,
                "duration":          programme.duration,
                "duration_type":     programme.duration_type,
                "course_count":      len(courses) if courses else 0,
                "instructions_text": programme.instructions_text,
                "instructions_link": programme.instructions_link,
                "show_overview_tab":         programme.show_overview_tab,
                "show_eligibility_tab":      programme.show_eligibility_tab,
                "show_apply_introduction":   programme.show_apply_introduction,
                "overview":    programme.overview,
                "eligibility": programme.eligibility,
                "apply_intro": programme.apply_intro,
                "courses": courses,
                "faculty": faculty,
                "faculty_page": page,
                "faculty_total_pages": total_pages,
                "faqs": faqs,
                "faq_page": faq_page,
                "faq_total_pages": faq_total_pages,
                "title":       programme.programme_name,
                "description": frappe.utils.strip_html_tags(programme.overview or "")[:160],
                "academic_year": academic_year,
                "existing_application": frappe.db.get_value(
                    "PACE Application", 
                    {"email_address": frappe.db.get_value("User", frappe.session.user, "email") or frappe.session.user, "programme": programme.name}, 
                    ["name", "status"], 
                    as_dict=True, 
                    order_by="creation desc"
                ) if frappe.session.user and frappe.session.user != "Guest" else None
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
