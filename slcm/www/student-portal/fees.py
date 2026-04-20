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

        # ── Auto-fix: backfill fee details for students missing total_program_fee ──
        # Handles students created before the auto-fetch hook was added.
        _ensure_student_fee_populated(student)

        # ── Student Master fee data (authoritative programme fee source) ──
        # These fields are populated by the Student Fee Assignment workflow and
        # reflect the fee the student owes for their entire programme.
        # We use them for the hero/summary section so the totals always match
        # what the admin has defined at the programme level, regardless of which
        # individual invoices happen to exist.
        sm_total_fee   = frappe.utils.flt(student.total_program_fee or 0)
        # discount_amount is the calculated scholarship discount (from net_program_fee calc)
        # scholarship_amount in Scholarship Details section is the raw admin-entered value;
        # discount_amount in Fee Details section is what was actually applied to the fee.
        sm_scholarship = (frappe.utils.flt(student.discount_amount or 0)
                          or frappe.utils.flt(student.scholarship_amount or 0))
        sm_paid        = frappe.utils.flt(student.total_paid_amount or 0)
        sm_net         = (frappe.utils.flt(student.net_program_fee or 0)
                          or max(sm_total_fee - sm_scholarship, 0))
        sm_outstanding = max(sm_net - sm_paid, 0)
        sm_fee_status  = student.fee_payment_status or ""
        context.fee_structure_name = (
            frappe.db.get_value("Fee Structure", student.fee_structure, "fee_structure_name")
            if student.fee_structure else ""
        )

        # ── Fee Invoices ───────────────────────────────────────
        invoices = frappe.get_all(
            "Fee Invoice",
            filters={"student": student_name},
            fields=[
                "name", "academic_term", "program", "academic_year",
                "invoice_date", "due_date",
                "total_amount", "scholarship_amount", "final_payable_amount",
                "paid_amount", "outstanding_amount", "status",
            ],
            order_by="creation desc",
            ignore_permissions=True,
        )

        # ── Scholarship: prefer SM calculated discount; fall back to invoice aggregate ──
        # When a student is created via the admission pipeline the scholarship
        # lives on their Fee Invoice(s) (copied from AFA) but SM discount_amount
        # may still be 0 (not yet synced).  Summing across invoices gives the
        # correct figure in that scenario without touching the admission module.
        if not sm_scholarship and invoices:
            sm_scholarship = sum(frappe.utils.flt(i.scholarship_amount or 0) for i in invoices)

        # ── Hero / summary data source ─────────────────────────
        # Prefer Student Master data so the summary always reflects the
        # programme-level fee defined by the admin.  Invoices (shown below)
        # are used only for per-term payment detail.
        # When SM has no fee data at all, aggregate from invoices as a fallback.
        if sm_total_fee > 0:
            context.use_sm_fallback   = not bool(invoices)   # notice only when no invoices exist
            context.total_payable     = sm_net
            context.total_paid        = sm_paid
            context.total_outstanding = sm_outstanding
            context.total_scholarship = sm_scholarship
            context.has_dues          = sm_outstanding > 0
            context.sm_fee_status     = sm_fee_status
            context.sm_total_fee      = sm_total_fee
        else:
            # No SM fee data — fall back to aggregated invoice figures.
            # outstanding_amount can be negative after an overpayment correction;
            # clamp to 0 so totals never go negative.
            inv_payable     = sum(frappe.utils.flt(i.final_payable_amount or 0) for i in invoices)
            inv_paid        = sum(frappe.utils.flt(i.paid_amount or 0) for i in invoices)
            inv_outstanding = sum(max(frappe.utils.flt(i.outstanding_amount or 0), 0) for i in invoices)
            inv_scholarship = sum(frappe.utils.flt(i.scholarship_amount or 0) for i in invoices)
            context.use_sm_fallback   = False
            context.total_payable     = inv_payable
            context.total_paid        = inv_paid
            context.total_outstanding = inv_outstanding
            context.total_scholarship = inv_scholarship
            context.has_dues          = inv_outstanding > 0
            context.sm_fee_status     = ""
            context.sm_total_fee      = 0

        # Status → colour mapping
        STATUS_STYLE = {
            "Paid":           {"color": "var(--sp-success)", "bg": "var(--sp-success-bg)"},
            "Partially Paid": {"color": "var(--sp-warning)", "bg": "var(--sp-warning-bg)"},
            "Unpaid":         {"color": "var(--sp-danger)",  "bg": "var(--sp-danger-bg)"},
            "Overdue":        {"color": "var(--sp-danger)",  "bg": "var(--sp-danger-bg)"},
            "Cancelled":      {"color": "var(--sp-text-4)",  "bg": "var(--sp-bg)"},
        }

        today = frappe.utils.getdate(frappe.utils.today())

        for inv in invoices:
            sc = STATUS_STYLE.get(inv.status, STATUS_STYLE["Unpaid"])
            inv["status_color"] = sc["color"]
            inv["status_bg"]    = sc["bg"]
            inv["is_overdue"]   = (
                inv.status not in ("Paid", "Cancelled")
                and inv.due_date
                and frappe.utils.getdate(inv.due_date) < today
            )
            # Clamp displayed outstanding to 0 — it can be negative after an
            # overpayment correction but we should never show a negative amount.
            display_outstanding = max(frappe.utils.flt(inv.outstanding_amount), 0)
            inv["can_pay"] = (
                inv.status not in ("Paid", "Cancelled")
                and display_outstanding > 0
            )
            inv["formatted_payable"]     = "₹{:,.0f}".format(inv.final_payable_amount or 0)
            inv["formatted_paid"]        = "₹{:,.0f}".format(inv.paid_amount or 0)
            inv["formatted_outstanding"] = "₹{:,.0f}".format(display_outstanding)
            inv["outstanding_paisa"]     = int(display_outstanding * 100)

            # Payment history from child table
            try:
                payments = frappe.get_all(
                    "Fee Payment Entry",
                    filters={"parent": inv.name},
                    fields=["payment", "payment_date", "amount", "payment_mode"],
                    order_by="payment_date desc",
                    ignore_permissions=True,
                )
                inv["payments"] = payments
            except Exception:
                inv["payments"] = []

        context.invoices     = invoices
        context.has_invoices = len(invoices) > 0

        # ── Payment gateway availability ───────────────────────
        # Razorpay Settings is a Single doctype stored in tabSingles.
        # Check for a configured api_key — if present, the gateway is ready.
        # Avoids loading the Razorpay SDK (and its risk-detection / tracking
        # scripts) on sites where the gateway has not been set up yet.
        try:
            context.payment_enabled = bool(
                frappe.db.get_single_value("Razorpay Settings", "api_key")
            )
        except Exception:
            context.payment_enabled = False

        # Payer email for Razorpay prefill (exposed to template for data attribute)
        context.payer_email = (
            student.official_email_id or student.email or frappe.session.user
        )
        context.payer_name = " ".join(
            filter(None, [student.first_name, student.last_name])
        ) or student.name

        # Current enrollment (for the period label in the hero card)
        try:
            enrollment = frappe.get_all(
                "Student Enrollment",
                filters={"student": student_name, "status": "Enrolled"},
                fields=["name", "academic_year", "term_name", "cohort", "program"],
                order_by="creation desc",
                limit=1,
                ignore_permissions=True,
            )
            context.current_enrollment = enrollment[0] if enrollment else None
        except Exception:
            context.current_enrollment = None

    except Exception as e:
        frappe.log_error(f"Student Portal Fees error: {e}", "Student Portal")
        context.portal_error = str(e)
        _set_nav_defaults(context)

    return context


# ── Helpers ────────────────────────────────────────────────────────────────

def _get_student_name():
    user = frappe.session.user
    for field in ("user", "email", "official_email_id"):
        name = frappe.db.get_value("Student Master", {field: user}, "name")
        if name:
            return name
    return None


def _set_student_nav(context, student):
    full_name = " ".join(filter(None, [student.first_name, student.middle_name, student.last_name]))
    context.student_name   = full_name or student.name
    context.student_id     = student.registration_id or student.name
    context.student_photo  = student.passport_size_photo or ""
    context.student_initial = (context.student_name[0]).upper() if context.student_name else "S"
    context.programme_name = (
        frappe.db.get_value("Cohort", student.programme, "cohort_name")
        or student.programme or ""
    )
    context.department = student.department or ""
    context.batch_year = student.batch_year or ""


def _ensure_student_fee_populated(student):
    """Backfill fee details on Student Master if missing.

    Handles existing students created before the before_insert hook was added.
    Only runs when total_program_fee is 0, so it never overwrites real data.
    Silently skips on any error to avoid blocking the fees page.
    """
    if frappe.utils.flt(student.total_program_fee):
        return   # already populated — nothing to do
    if not student.programme:
        return

    try:
        program = frappe.db.get_value("Cohort", student.programme, "program")
        if not program and frappe.db.exists("Program", student.programme):
            program = student.programme
        if not program:
            return

        current_date = frappe.utils.today()
        fs_rows = frappe.db.sql(
            """
            SELECT name, total_amount, valid_from, valid_until
            FROM `tabFee Structure`
            WHERE program = %s
              AND status = 'Active'
              AND applicable = 'Student'
              AND valid_from <= %s
              AND (valid_until IS NULL OR valid_until >= %s)
            ORDER BY valid_from DESC, creation DESC
            LIMIT 1
            """,
            (program, current_date, current_date),
            as_dict=True,
        )
        fs = fs_rows[0] if fs_rows else None
        if not fs or not frappe.utils.flt(fs.total_amount):
            return

        total_fee = frappe.utils.flt(fs.total_amount)
        scholarship_pct = frappe.utils.flt(student.scholarship_percentage or 0)
        scholarship_amt = frappe.utils.flt(student.scholarship_amount or 0)

        if student.applying_scholarship == "Yes" and scholarship_pct:
            discount = round((total_fee * scholarship_pct) / 100, 2)
        elif student.applying_scholarship == "Yes" and scholarship_amt:
            discount = min(scholarship_amt, total_fee)
        else:
            discount = 0

        net_fee = total_fee - discount
        paid = frappe.utils.flt(student.total_paid_amount or 0)
        outstanding = max(net_fee - paid, 0)

        frappe.db.set_value("Student Master", student.name, {
            "fee_structure":     fs.name,
            "total_program_fee": total_fee,
            "discount_amount":   discount,
            "net_program_fee":   net_fee,
            "outstanding_balance": outstanding,
        }, update_modified=False)

        # Refresh the in-memory doc so this page render uses the new values
        student.fee_structure     = fs.name
        student.total_program_fee = total_fee
        student.discount_amount   = discount
        student.net_program_fee   = net_fee
        student.outstanding_balance = outstanding

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Fee backfill failed")


def _set_nav_defaults(context):
    user     = frappe.session.user
    user_doc = frappe.db.get_value("User", user, ["full_name", "user_image"], as_dict=True)
    context.student_name   = (user_doc.full_name if user_doc else "") or user.split("@")[0]
    context.student_id     = ""
    context.student_photo  = (user_doc.user_image if user_doc else "") or ""
    context.student_initial = (context.student_name[0]).upper() if context.student_name else "S"
    context.programme_name = ""
    context.department     = ""
    context.batch_year     = ""
