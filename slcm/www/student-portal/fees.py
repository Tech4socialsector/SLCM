import frappe

no_cache = 1


def get_context(context):
    context.no_cache = 1

    if frappe.session.user == "Guest":
        context.is_guest = True
        return context

    context.is_guest = False
    context.active_page = "fees"

    student_name = _get_student_name()
    if not student_name:
        context.no_student = True
        _set_nav_defaults(context)
        return context

    context.no_student = False

    try:
        student = frappe.get_doc("Student Master", student_name, ignore_permissions=True)
        _set_student_nav(context, student)

        # ── Fee Invoices ──────────────────────────────────────
        invoices = frappe.get_all(
            "Fee Invoice",
            filters={"student": student_name},
            fields=[
                "name", "academic_term", "program", "academic_year",
                "invoice_date", "due_date",
                "total_amount", "scholarship_amount", "final_payable_amount",
                "paid_amount", "outstanding_amount", "status"
            ],
            order_by="creation desc",
            ignore_permissions=True
        )

        # Compute summary
        total_payable = sum(inv.final_payable_amount or 0 for inv in invoices)
        total_paid = sum(inv.paid_amount or 0 for inv in invoices)
        total_outstanding = sum(inv.outstanding_amount or 0 for inv in invoices)
        total_scholarship = sum(inv.scholarship_amount or 0 for inv in invoices)

        context.total_payable = total_payable
        context.total_paid = total_paid
        context.total_outstanding = total_outstanding
        context.total_scholarship = total_scholarship
        context.has_dues = total_outstanding > 0

        # Status colors
        STATUS_STYLE = {
            "Paid":             {"color": "var(--sp-success)", "bg": "var(--sp-success-bg)"},
            "Partially Paid":   {"color": "var(--sp-warning)", "bg": "var(--sp-warning-bg)"},
            "Unpaid":           {"color": "var(--sp-danger)",  "bg": "var(--sp-danger-bg)"},
            "Overdue":          {"color": "var(--sp-danger)",  "bg": "var(--sp-danger-bg)"},
            "Cancelled":        {"color": "var(--sp-text-4)",  "bg": "var(--sp-bg)"},
        }

        today = frappe.utils.getdate(frappe.utils.today())

        for inv in invoices:
            sc = STATUS_STYLE.get(inv.status, STATUS_STYLE["Unpaid"])
            inv["status_color"] = sc["color"]
            inv["status_bg"] = sc["bg"]
            inv["is_overdue"] = (
                inv.status not in ("Paid", "Cancelled") and
                inv.due_date and
                frappe.utils.getdate(inv.due_date) < today
            )
            inv["formatted_payable"] = "₹{:,.0f}".format(inv.final_payable_amount or 0)
            inv["formatted_paid"] = "₹{:,.0f}".format(inv.paid_amount or 0)
            inv["formatted_outstanding"] = "₹{:,.0f}".format(inv.outstanding_amount or 0)

            # Fetch payment entries for this invoice (child table)
            try:
                payments = frappe.get_all(
                    "Fee Payment Entry",
                    filters={"parent": inv.name},
                    fields=["payment", "payment_date", "amount", "payment_mode"],
                    order_by="payment_date desc",
                    ignore_permissions=True
                )
                inv["payments"] = payments
            except Exception:
                inv["payments"] = []

        context.invoices = invoices
        context.has_invoices = len(invoices) > 0

        # ── Fee Structure from enrollment ──────────────────────
        try:
            enrollment = frappe.get_all(
                "Student Enrollment",
                filters={"student": student_name, "status": "Enrolled"},
                fields=["name", "academic_year", "term_name", "cohort", "program"],
                order_by="creation desc",
                limit=1,
                ignore_permissions=True
            )
            context.current_enrollment = enrollment[0] if enrollment else None
        except Exception:
            context.current_enrollment = None

    except Exception as e:
        frappe.log_error(f"Student Portal Fees error: {e}", "Student Portal")
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
