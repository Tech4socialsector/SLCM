import frappe

no_cache = 1


def get_context(context):
    context.no_cache = 1

    if frappe.session.user == "Guest":
        context.is_guest = True
        return context

    context.is_guest = False
    context.active_page = "profile"

    student_name = _get_student_name()
    if not student_name:
        context.no_student = True
        _set_nav_defaults(context)
        return context

    context.no_student = False

    try:
        student = frappe.get_doc("Student Master", student_name, ignore_permissions=True)
        _set_student_nav(context, student)

        # ── Full profile data ──────────────────────────────────
        full_name = " ".join(filter(None, [student.first_name, student.middle_name, student.last_name]))

        context.profile = {
            # Personal
            "full_name":        full_name or student.name,
            "first_name":       student.first_name or "",
            "middle_name":      student.middle_name or "",
            "last_name":        student.last_name or "",
            "dob":              frappe.utils.formatdate(student.dob, "dd MMMM yyyy") if student.dob else "",
            "gender":           student.gender or "",
            "nationality":      student.nationality or "",
            "marital_status":   student.marital_status or "",
            "quota":            student.quota or "",
            "photo":            student.passport_size_photo or "",

            # Contact
            "email":            student.email or "",
            "official_email":   student.official_email_id or "",
            "personal_email":   student.personal_email or "",
            "phone":            student.phone or "",
            "present_address":  student.present_address or "",
            "permanent_address":student.permanent_address or "",
            "city":             student.city or "",
            "pincode":          student.pincode or "",
            "country":          student.country or "",

            # Academic
            "registration_id":  student.registration_id or "",
            "application_number": student.application_number or "",
            "programme":        frappe.db.get_value("Cohort", student.programme, "cohort_name") or student.programme or "",
            "department":       student.department or "",
            "batch_year":       student.batch_year or "",
            "academic_year":    student.academic_year or "",
            "current_term":     student.current_term or "",
            "current_year":     student.current_year or "",
            "current_cgpa":     round(student.current_cgpa or 0.0, 2),
            "student_status":   student.student_status or "",
            "academic_status":  student.academic_status or "",
            "specialisation":   student.specialisation or "",
            "programme_system": student.programme_system or "",
            "admission_type":   student.admission_type or "",

            # Hostel
            "is_hosteller":     bool(student.is_hosteller),
            "hostel_room":      student.hostel_room or "",
            "hostel_bed":       student.hostel_bed or "",

            # Bank
            "bank_name":        student.bank_name or "",
            "bank_account_number": student.bank_account_number or "",
            "ifsc_code":        student.ifsc_code or "",
            "branch_name":      student.branch_name or "",
            "account_holder":   student.account_holder_name or "",
        }

        # ── ID Card ────────────────────────────────────────────
        try:
            id_card = frappe.get_all(
                "ID Card Generation",
                filters={"student": student_name, "card_status": ["in", ["Generated", "Printed"]], "card_type": "Student"},
                fields=["name", "expiry_date", "card_status", "front_id_image"],
                order_by="creation desc",
                limit=1,
                ignore_permissions=True
            )
            context.id_card = id_card[0] if id_card else None
        except Exception:
            context.id_card = None

        # ── Parents ────────────────────────────────────────────
        try:
            parents_raw = frappe.get_all(
                "Student Parent",
                filters={"parent": student_name},
                fields=["relation", "first_name", "middle_name", "last_name",
                        "phone", "email", "occupation", "annual_income"],
                ignore_permissions=True
            )
            # Normalise field names for template
            parents = []
            for p in parents_raw:
                full = " ".join(filter(None, [p.get("first_name"), p.get("middle_name"), p.get("last_name")]))
                parents.append({
                    "parent_name": full or "—",
                    "relation": p.get("relation") or "",
                    "contact_number": p.get("phone") or "",
                    "email_id": p.get("email") or "",
                    "occupation": p.get("occupation") or "",
                })
            context.parents = parents
        except Exception:
            context.parents = []

        # ── Available Downloads ────────────────────────────────
        # Both conditions must be true: the field is populated AND the Applicant
        # document with that name actually exists in the database.
        context.can_download_application = bool(
            student.application_number
            and frappe.db.exists("Applicant", student.application_number)
        )
        context.can_download_registration = True   # always available for enrolled students

        # ── UG Degree ─────────────────────────────────────────
        try:
            ug = frappe.get_all(
                "UG Degree Detail",
                filters={"parent": student_name},
                fields=["ug_program", "college", "year_of_completion", "ug_cgpa"],
                ignore_permissions=True
            )
            # Normalize to template-friendly names
            context.ug_degrees = [
                {
                    "degree": d.get("ug_program") or "",
                    "institution": d.get("college") or "",
                    "year_of_passing": d.get("year_of_completion") or "",
                    "percentage": d.get("ug_cgpa") or "",
                }
                for d in ug
            ]
        except Exception:
            context.ug_degrees = []

    except Exception as e:
        frappe.log_error(f"Student Portal Profile error: {e}", "Student Portal")
        context.portal_error = str(e)
        _set_nav_defaults(context)

    return context


def _get_student_name():
    user = frappe.session.user
    name = frappe.db.get_value("Student Master", {"user": user}, "name")
    if not name:
        name = frappe.db.get_value("Student Master", {"email": user}, "name")
    if not name:
        name = frappe.db.get_value("Student Master", {"official_email_id": user}, "name")
    return name


def _set_student_nav(context, student):
    full_name = " ".join(filter(None, [student.first_name, student.middle_name, student.last_name]))
    context.student_name = full_name or student.name
    context.student_id = student.registration_id or student.name
    context.student_photo = student.passport_size_photo or ""
    context.student_initial = (context.student_name[0]).upper() if context.student_name else "S"
    context.programme_name = frappe.db.get_value("Cohort", student.programme, "cohort_name") or student.programme or ""
    context.department = student.department or ""
    context.batch_year = student.batch_year or ""


def _set_nav_defaults(context):
    user = frappe.session.user
    user_doc = frappe.db.get_value("User", user, ["full_name", "user_image"], as_dict=True)
    context.student_name = (user_doc.full_name if user_doc else "") or user.split("@")[0]
    context.student_id = ""
    context.student_photo = (user_doc.user_image if user_doc else "") or ""
    context.student_initial = (context.student_name[0]).upper() if context.student_name else "S"
    context.programme_name = ""
    context.department = ""
    context.batch_year = ""
