import frappe

no_cache = 1

def get_context(context):
    context.no_cache = 1

    if frappe.session.user == "Guest":
        context.is_guest = True
        return context

    context.is_guest = False
    context.active_page = "fees"
    context.load_errors = {}

    student_name = _get_student_name()
    if not student_name:
        context.no_student = True
        _set_nav_defaults(context)
        return context

    context.no_student = False

    try:
        student = frappe.get_doc("Student Master", student_name)
        _set_student_nav(context, student)
        _ensure_student_fee_populated(student)

        # ── Programme-level fee summary from Student Master ──────────────────
        sm_total_fee   = frappe.utils.flt(student.total_program_fee or 0)
        sm_scholarship = (frappe.utils.flt(student.discount_amount or 0)
                          or frappe.utils.flt(student.scholarship_amount or 0))
        sm_paid_raw    = frappe.utils.flt(student.total_paid_amount or 0)
        sm_net         = (frappe.utils.flt(student.net_program_fee or 0)
                          or max(sm_total_fee - sm_scholarship, 0))

        sm_paid        = min(sm_paid_raw, sm_net) if sm_net > 0 else sm_paid_raw
        sm_outstanding = max(sm_net - sm_paid, 0)

        stored_status  = student.fee_payment_status or "Unpaid"
        if sm_net > 0:
            if sm_outstanding <= 0:
                sm_fee_status = "Paid"
            elif sm_paid > 0:
                sm_fee_status = "Partially Paid"
            else:
                if stored_status in ("Payment Initiated", "Authorized"):
                    sm_fee_status = stored_status
                else:
                    sm_fee_status = "Unpaid"
        else:
            sm_fee_status = stored_status or "Unpaid"

        _GATEWAY_LIVE = {"Payment Initiated", "Authorized"}
        if (sm_fee_status != stored_status
                and stored_status not in _GATEWAY_LIVE
                and sm_net > 0):
            try:
                frappe.db.set_value(
                    "Student Master", student_name, "fee_payment_status",
                    sm_fee_status, update_modified=False,
                )
            except Exception:
                pass

        if student.fee_structure:
            _fs_data = frappe.db.get_value(
                "Fee Structure", student.fee_structure,
                ["fee_structure_name", "valid_from", "valid_until", "status"],
                as_dict=True,
            ) or {}
            context.fee_structure_name        = _fs_data.get("fee_structure_name") or student.fee_structure
            context.fee_structure_valid_from  = str(_fs_data.get("valid_from") or "")
            context.fee_structure_valid_until = str(_fs_data.get("valid_until") or "")
            context.fee_structure_status      = _fs_data.get("status") or ""
        else:
            context.fee_structure_name        = ""
            context.fee_structure_valid_from  = ""
            context.fee_structure_valid_until = ""
            context.fee_structure_status      = ""
        context.fee_structure_doc_name = student.fee_structure or ""

        # Fee structure components
        fs_components = []
        if student.fee_structure:
            try:
                fs_components = frappe.db.sql(
                    """
                    SELECT fcc.component_name, fcc.amount, fcc.total_amount,
                           fcc.is_taxable, fcc.tax_rate, fcc.tax_amount
                    FROM `tabFee Component Child` fcc
                    WHERE fcc.parent = %s AND fcc.parenttype = 'Fee Structure'
                    ORDER BY fcc.idx
                    """,
                    student.fee_structure,
                    as_dict=True,
                )
            except Exception:
                context.load_errors["fs_components"] = True
                fs_components = []
        context.fs_components = fs_components

        # ── Fee Invoices ─────────────────────────────────────────────────────
        try:
            invoices = frappe.get_all(
                "Fee Invoice",
                filters={"student": student_name},
                fields=[
                    "name", "academic_term", "program", "academic_year",
                    "invoice_date", "due_date",
                    "total_amount", "scholarship_amount", "final_payable_amount",
                    "paid_amount", "outstanding_amount", "status",
                ],
                order_by="academic_term asc, creation asc",
                ignore_permissions=True,
            )
            # Fetch components and payments for invoices
            today = frappe.utils.getdate(frappe.utils.today())
            for inv in invoices:
                inv_payable_amt = frappe.utils.flt(inv.final_payable_amount or 0)
                inv_paid_amt    = frappe.utils.flt(inv.paid_amount or 0)
                if inv_payable_amt > 0:
                    inv_paid_amt = min(inv_paid_amt, inv_payable_amt)
                display_outstanding = max(inv_payable_amt - inv_paid_amt, 0)
                stored_inv_status = inv.status or "Unpaid"
                if stored_inv_status == "Cancelled":
                    effective_status = "Cancelled"
                elif inv_payable_amt > 0 and display_outstanding <= 0:
                    effective_status = "Paid"
                elif inv_payable_amt > 0 and inv_paid_amt > 0:
                    effective_status = "Partially Paid"
                else:
                    effective_status = stored_inv_status if stored_inv_status != "Paid" else "Unpaid"

                inv["eff_status"] = effective_status
                inv["is_overdue"]   = (
                    effective_status not in ("Paid", "Cancelled")
                    and inv.due_date
                    and frappe.utils.getdate(inv.due_date) < today
                )
                inv["can_pay"] = (
                    effective_status not in ("Paid", "Cancelled")
                    and display_outstanding > 0
                )
                inv["formatted_payable"]     = "₹{:,.0f}".format(inv_payable_amt)
                inv["formatted_paid"]        = "₹{:,.0f}".format(inv_paid_amt)
                inv["formatted_outstanding"] = "₹{:,.0f}".format(display_outstanding)
                inv["outstanding_amount"]    = display_outstanding
                inv["paid_amount"]           = inv_paid_amt

                try:
                    components = frappe.db.sql(
                        """
                        SELECT fcc.component_name, fcc.amount, fcc.total_amount,
                               COALESCE(fc.component_type, 'Other') AS component_type
                        FROM `tabFee Component Child` fcc
                        LEFT JOIN `tabFee Component` fc ON fcc.fee_component = fc.name
                        WHERE fcc.parent = %s AND fcc.parenttype = 'Fee Invoice'
                        ORDER BY fcc.idx
                        """,
                        inv.name,
                        as_dict=True,
                    )
                    inv["fee_components"] = components or []
                except Exception:
                    inv["fee_components"] = []

                try:
                    payments = frappe.get_all(
                        "Fee Payment Entry",
                        filters={"parent": inv.name},
                        fields=["payment", "payment_date", "amount", "payment_mode"],
                        order_by="payment_date desc",
                        ignore_permissions=True,
                    )
                    for p in payments:
                        p["reference_number"] = frappe.db.get_value("Fee Payment", p.payment, "reference_number") or ""
                        p["rzp_status"]  = "Captured"
                        p["is_rzp_only"] = False
                except Exception:
                    payments = []

                try:
                    attempt_irs = frappe.get_all(
                        "Integration Request",
                        filters={
                            "reference_doctype": "Fee Invoice",
                            "reference_docname": inv.name,
                            "status": ["not in", ["Pending", "Queued"]],
                        },
                        fields=["name", "modified", "status", "payment_id"],
                        order_by="modified desc",
                        ignore_permissions=True,
                    )
                    for ir in attempt_irs:
                        if ir.status == "Failed":
                            payments.append({
                                "payment": ir.payment_id or ir.name,
                                "payment_date": ir.modified,
                                "amount": 0,
                                "payment_mode": "Online Payment",
                                "reference_number": ir.payment_id or "",
                                "rzp_status": "Failed",
                                "is_rzp_only": True
                            })
                except Exception:
                    pass

                payments.sort(key=lambda x: x.get("payment_date") or "", reverse=True)
                for p in payments:
                    p["display_date"] = frappe.utils.formatdate(p["payment_date"], "dd MMM yyyy") if p.get("payment_date") else ""
                    p["formatted_amount"] = "₹{:,.0f}".format(frappe.utils.flt(p["amount"])) if p.get("amount") else "—"
                inv["payments"] = payments

            context.invoices = invoices
            context.has_invoices = bool(invoices)
            context.has_fee_data = sm_total_fee > 0 or bool(invoices)
        except Exception:
            context.load_errors["invoices"] = True
            context.load_errors["summary"] = True
            context.invoices = []
            context.has_invoices = False

        _use_sm_for_summary = sm_total_fee > 0 and not bool(context.invoices)

        if not sm_scholarship and context.invoices:
            sm_scholarship = sum(frappe.utils.flt(i.scholarship_amount or 0) for i in context.invoices)

        inv_payable = sum(frappe.utils.flt(i.final_payable_amount or 0) for i in context.invoices if i.get("eff_status") != "Cancelled")
        inv_paid    = sum(frappe.utils.flt(i.paid_amount or 0) for i in context.invoices if i.get("eff_status") != "Cancelled")
        inv_outstanding = max(inv_payable - inv_paid, 0)
        inv_outstanding_raw = sum(frappe.utils.flt(i.outstanding_amount or 0) for i in context.invoices if i.get("eff_status") != "Cancelled")

        if _use_sm_for_summary:
            context.total_fee         = sm_total_fee
            context.total_scholarship = sm_scholarship
            context.total_net         = max(sm_total_fee - sm_scholarship, 0)
            context.total_paid        = min(sm_paid_raw, context.total_net) if context.total_net > 0 else sm_paid_raw
            context.total_payable     = context.total_net
            context.total_outstanding = max(context.total_net - context.total_paid, 0)
            context.use_sm_fallback   = True
        else:
            context.total_fee         = sum(frappe.utils.flt(i.total_amount or 0) for i in context.invoices if i.get("eff_status") != "Cancelled")
            context.total_scholarship = sm_scholarship
            context.total_net         = inv_payable
            context.total_paid        = inv_paid
            context.total_payable     = inv_payable
            context.total_outstanding = inv_outstanding
            context.use_sm_fallback   = False

        context.has_dues            = context.total_outstanding > 0
        context.sm_fee_status       = sm_fee_status
        context.sm_total_fee        = sm_total_fee
        context.sm_scholarship_amt  = sm_scholarship
        context.inv_scholarship_amt = sm_scholarship
        context.inv_outstanding_raw = inv_outstanding_raw
        
        diff = abs(sm_outstanding - inv_outstanding)
        if not _use_sm_for_summary and diff > 10:
            context.has_sm_inv_mismatch = True
            context.mismatch_diff       = diff
        else:
            context.has_sm_inv_mismatch = False
            context.mismatch_diff       = 0.0

        if sm_paid_raw > context.total_net and context.total_net > 0:
            context.has_overpayment_flag = True
        else:
            context.has_overpayment_flag = False

        if context.load_errors.get("summary"):
            context.has_overpayment_flag = False
            context.has_sm_inv_mismatch = False

        # ── Concessions ────────────────────────────────────────────────────────
        try:
            concessions = frappe.get_all(
                "Fee Concession",
                filters={"student": student_name, "status": ["in", ["Draft", "Pending", "Approved", "Rejected"]]},
                fields=["name", "fee_structure", "concession_type", "concession_amount", "concession_percentage", "status", "approved_on"],
                order_by="creation desc",
                ignore_permissions=True,
            )
            for c in concessions:
                c["approved_on_fmt"] = frappe.utils.formatdate(c.approved_on, "dd MMM yyyy") if c.approved_on else ""
                if c.concession_amount:
                    c["formatted_amount"] = "₹{:,.0f}".format(c.concession_amount)
                elif c.concession_percentage:
                    c["formatted_amount"] = f"{c.concession_percentage}%"
                else:
                    c["formatted_amount"] = "—"
            context.concessions = concessions
            context.has_concessions = bool(concessions)
            context.primary_concession_type = concessions[0].concession_type if concessions else ""
        except Exception:
            context.load_errors["concessions"] = True
            context.concessions = []
            context.has_concessions = False
            context.primary_concession_type = ""

        # ── Credit Notes / Waivers ──────────────────────────────────────────────
        try:
            credits = frappe.get_all(
                "Student Credit Note",
                filters={"student": student_name, "docstatus": 1},
                fields=["name", "posting_date", "total_amount", "amount_allocated", "status"],
                order_by="posting_date desc",
                ignore_permissions=True,
            )
            total_avail = 0
            for cr in credits:
                avail = frappe.utils.flt(cr.total_amount) - frappe.utils.flt(cr.amount_allocated)
                total_avail += avail
                cr["available_amount"] = avail
                cr["formatted_available"] = "₹{:,.0f}".format(avail)
                cr["formatted_total"] = "₹{:,.0f}".format(frappe.utils.flt(cr.total_amount))
                cr["date_fmt"] = frappe.utils.formatdate(cr.posting_date, "dd MMM yyyy") if cr.posting_date else ""
            context.credit_notes = credits
            context.has_credit_notes = bool(credits)
            context.total_available_credit = total_avail
            context.formatted_total_credit = "₹{:,.0f}".format(total_avail)
        except Exception:
            context.load_errors["credits"] = True
            context.credit_notes = []
            context.has_credit_notes = False
            context.total_available_credit = 0
            context.formatted_total_credit = "₹0"

        # ── Fee Demands ────────────────────────────────────────────────────────
        try:
            demands = frappe.get_all(
                "Fee Demand",
                filters={"student": student_name},
                fields=[
                    "name", "fee_component", "academic_term", "academic_year",
                    "demand_date", "due_date", "demand_amount", "paid_amount",
                    "waived_amount", "outstanding_amount", "status", "remarks"
                ],
                order_by="due_date asc, creation asc",
                ignore_permissions=True,
            )
            da_total = da_paid = da_waived = da_overdue = 0
            da_total_amt = da_paid_amt = da_waived_amt = da_outstanding = 0
            today = frappe.utils.getdate(frappe.utils.today())
            overdue_list = []
            
            for d in demands:
                amt = frappe.utils.flt(d.demand_amount or 0)
                paid = frappe.utils.flt(d.paid_amount or 0)
                waived = frappe.utils.flt(d.waived_amount or 0)
                
                # Manual outstanding calculation as truth
                rem = max(amt - paid - waived, 0)
                if d.status == "Cancelled":
                    d["eff_status"] = "Cancelled"
                    rem = 0
                elif amt > 0 and rem <= 0:
                    d["eff_status"] = "Paid"
                elif paid > 0:
                    d["eff_status"] = "Partially Paid"
                else:
                    d["eff_status"] = "Unpaid"

                is_overdue = (d["eff_status"] not in ("Paid", "Cancelled") 
                              and d.due_date and frappe.utils.getdate(d.due_date) < today)
                d["is_overdue"] = is_overdue
                d["can_pay"] = (d["eff_status"] not in ("Paid", "Cancelled") and rem > 0)
                d["formatted_amount"] = "₹{:,.0f}".format(amt)
                d["formatted_outstanding"] = "₹{:,.0f}".format(rem)
                d["outstanding_amount"] = rem
                d["due_date_fmt"] = frappe.utils.formatdate(d.due_date, "dd MMM yyyy") if d.due_date else ""

                if d["eff_status"] != "Cancelled":
                    da_total += 1
                    da_total_amt += amt
                    da_paid_amt += paid
                    da_waived_amt += waived
                    da_outstanding += rem
                    
                    if d["eff_status"] == "Paid":
                        da_paid += 1
                    elif waived >= amt and amt > 0:
                        da_waived += 1
                        
                    if is_overdue:
                        da_overdue += 1
                        overdue_list.append(d)

            context.fee_demands = demands
            context.has_fee_demands = bool(demands)
            context.overdue_demands = overdue_list
            context.has_overdue_demands = bool(overdue_list)
            context.overdue_demand_count = len(overdue_list)
            context.overdue_total = sum(d["outstanding_amount"] for d in overdue_list)
            context.formatted_overdue_total = "₹{:,.0f}".format(context.overdue_total)

            da_pct = int(round(da_paid_amt / da_total_amt * 100)) if da_total_amt > 0 else 0

            context.da_total            = da_total
            context.da_paid             = da_paid
            context.da_waived           = da_waived
            context.da_overdue          = da_overdue
            context.da_pending          = da_total - da_paid - da_waived - da_overdue
            context.da_total_amt        = da_total_amt
            context.da_paid_amt         = da_paid_amt
            context.da_waived_amt       = da_waived_amt
            context.da_outstanding      = da_outstanding
            context.da_pct              = da_pct
            context.da_fmt_total        = "₹{:,.0f}".format(da_total_amt)
            context.da_fmt_paid         = "₹{:,.0f}".format(da_paid_amt)
            context.da_fmt_waived       = "₹{:,.0f}".format(da_waived_amt)
            context.da_fmt_outstanding  = "₹{:,.0f}".format(da_outstanding)
        except Exception:
            context.load_errors["demands"] = True
            context.fee_demands          = []
            context.has_fee_demands      = False
            context.overdue_demands      = []
            context.has_overdue_demands  = False
            context.overdue_demand_count = 0
            context.overdue_total        = 0
            context.formatted_overdue_total = "₹0"
            context.da_total = context.da_paid = context.da_waived = 0
            context.da_overdue = context.da_pending = 0
            context.da_pct = 0
            context.da_fmt_total = context.da_fmt_paid = "₹0"
            context.da_fmt_waived = context.da_fmt_outstanding = "₹0"
            context.da_outstanding = 0

        # ── Re-Examination Fees ──────────────────────────────────────────────
        try:
            re_exams = frappe.get_all(
                "Re Exam Application",
                filters={"student": student_name, "docstatus": 1, "fee_status": ["in", ["Unpaid", "Partially Paid", "Overdue"]]},
                fields=["name", "academic_term", "academic_year", "amount", "fee_status"],
                order_by="creation desc",
                ignore_permissions=True,
            )
            for re in re_exams:
                re["formatted_amount"] = "₹{:,.0f}".format(frappe.utils.flt(re.amount))
            context.re_exam_fees = re_exams
            context.has_re_exam_fees = bool(re_exams)
        except Exception:
            context.load_errors["re_exams"] = True
            context.re_exam_fees = []
            context.has_re_exam_fees = False

        # ── Hostel Fines ──────────────────────────────────────────────
        try:
            fines = frappe.get_all(
                "Hostel Fine",
                filters={"student": student_name, "status": ["in", ["Unpaid", "Partially Paid", "Overdue"]]},
                fields=["name", "fine_type", "amount", "outstanding_amount", "due_date", "status"],
                order_by="due_date asc",
                ignore_permissions=True,
            )
            for fine in fines:
                fine["formatted_amount"] = "₹{:,.0f}".format(frappe.utils.flt(fine.amount))
                fine["formatted_outstanding"] = "₹{:,.0f}".format(frappe.utils.flt(fine.outstanding_amount))
                fine["due_date_fmt"] = frappe.utils.formatdate(fine.due_date, "dd MMM yyyy") if fine.due_date else ""
            context.hostel_fines = fines
            context.has_hostel_fines = bool(fines)
        except Exception:
            context.load_errors["hostel_fines"] = True
            context.hostel_fines = []
            context.has_hostel_fines = False

        # ── Fee Refunds ────────────────────────────────────────────────────────
        try:
            refunds_raw = frappe.get_all(
                "Fee Refund",
                filters={"student": student_name, "status": ["not in", ["Reversed"]]},
                fields=[
                    "name", "fee_demand", "fee_component",
                    "refund_type", "refund_amount", "refund_date", "refund_mode",
                    "bank_name", "account_number", "utr_number",
                    "status", "approved_by", "approved_on", "reason", "remarks",
                ],
                order_by="refund_date desc, creation desc",
                ignore_permissions=True,
            )
            for r in refunds_raw:
                r["formatted_amount"] = "₹{:,.0f}".format(frappe.utils.flt(r.refund_amount or 0))
                r["refund_date_fmt"]  = frappe.utils.formatdate(r.refund_date, "dd MMM yyyy") if r.refund_date else ""
                r["approved_on_fmt"]  = frappe.utils.formatdate(r.approved_on, "dd MMM yyyy") if r.approved_on else ""
                r["approved_by_name"] = (
                    frappe.db.get_value("User", r.approved_by, "full_name") or r.approved_by
                ) if r.approved_by else ""
                acct = str(r.account_number or "")
                r["masked_account"] = ("•••• " + acct[-4:]) if len(acct) > 4 else acct
                try:
                    r["demand_paid_amount"] = frappe.utils.flt(
                        frappe.db.get_value("Fee Demand", r.fee_demand, "paid_amount") or 0
                    )
                except Exception:
                    r["demand_paid_amount"] = 0
            context.fee_refunds     = refunds_raw
            context.has_fee_refunds = bool(refunds_raw)
        except Exception:
            context.load_errors["refunds"] = True
            context.fee_refunds     = []
            context.has_fee_refunds = False

        # ── All Transactions (receipt list) ───────────────────────────────────
        try:
            all_txns = frappe.get_all(
                "Fee Receipt",
                filters={"student": student_name, "status": "Active"},
                fields=[
                    "name", "receipt_date", "amount", "payment_mode",
                    "reference_number", "transaction_date", "academic_year", "bank_name",
                ],
                order_by="receipt_date desc",
                ignore_permissions=True,
            )
            for txn in all_txns:
                txn["formatted_amount"] = "₹{:,.0f}".format(frappe.utils.flt(txn.amount or 0))
                txn["display_date"] = (
                    frappe.utils.formatdate(txn.receipt_date, "dd MMM yyyy")
                    if txn.receipt_date else ""
                )
            context.all_transactions = all_txns
            context.has_transactions  = bool(all_txns)
        except Exception:
            context.load_errors["transactions"] = True
            context.all_transactions = []
            context.has_transactions  = False

        # ── Payment gateway availability ──────────────────────────────────────
        try:
            context.payment_enabled = bool(
                frappe.db.get_single_value("Razorpay Settings", "api_key")
            )
        except Exception:
            context.payment_enabled = False

        try:
            user_doc = frappe.get_doc("User", frappe.session.user)
            context.payer_name = user_doc.full_name
            context.payer_email = user_doc.email
            context.payer_phone = user_doc.mobile_no or ""
        except Exception:
            context.payer_name = frappe.session.user
            context.payer_email = frappe.session.user
            context.payer_phone = ""

        _build_view_model(context)

    except Exception as e:
        frappe.log_error(f"Student Portal Fees error: {e}", "Student Portal")
        context.portal_error = str(e)
        _set_nav_defaults(context)
        _set_defaults(context)

    return context


def _build_view_model(context):
    try:
        # paid_pct
        if context.total_payable > 0:
            pct = int(round(context.total_paid / context.total_payable * 100))
            if pct >= 100 and context.total_outstanding > 0:
                pct = 99
            context.paid_pct = pct
        else:
            context.paid_pct = None
            
        # programme_overdue count
        context.programme_overdue = 0
        context.programme_overdue_count = 0
        if not context.load_errors.get("summary"):
            for inv in context.invoices:
                if inv.get("is_overdue"):
                    context.programme_overdue += frappe.utils.flt(inv.get("outstanding_amount") or 0)
                    context.programme_overdue_count += 1
            
        # outstanding_rows (invoices + demands + re_exam + hostel_fines)
        out_rows = []
        today = frappe.utils.getdate(frappe.utils.today())
        
        if not context.load_errors.get("summary"):
            for inv in context.invoices:
                if inv.get("eff_status") not in ("Paid", "Cancelled") and frappe.utils.flt(inv.get("outstanding_amount")) > 0:
                    out_rows.append({
                        "type": "Invoice",
                        "component": "Programme Fee",
                        "sub_label": inv.get("academic_term") or inv.get("academic_year"),
                        "due_date": inv.get("due_date"),
                        "due_date_fmt": frappe.utils.formatdate(inv.get("due_date"), "dd MMM yyyy") if inv.get("due_date") else "",
                        "amount": inv.get("outstanding_amount"),
                        "formatted_amount": "₹{:,.0f}".format(frappe.utils.flt(inv.get("outstanding_amount"))),
                        "status": "Overdue" if inv.get("is_overdue") else "Pending",
                        "is_overdue": inv.get("is_overdue")
                    })
                    
        if not context.load_errors.get("demands"):
            for d in context.fee_demands:
                if d.get("eff_status") not in ("Paid", "Cancelled") and frappe.utils.flt(d.get("outstanding_amount")) > 0:
                    out_rows.append({
                        "type": "Demand",
                        "component": d.get("fee_component") or "Additional Charge",
                        "sub_label": d.get("remarks") or d.get("academic_term") or d.get("academic_year"),
                        "due_date": d.get("due_date"),
                        "due_date_fmt": d.get("due_date_fmt"),
                        "amount": d.get("outstanding_amount"),
                        "formatted_amount": d.get("formatted_outstanding"),
                        "status": "Overdue" if d.get("is_overdue") else "Pending",
                        "is_overdue": d.get("is_overdue")
                    })

        if not context.load_errors.get("re_exams"):
            for r in context.re_exam_fees:
                if r.get("fee_status") not in ("Paid", "Cancelled"):
                    out_rows.append({
                        "type": "Re-exam",
                        "component": "Re-Examination Fee",
                        "sub_label": r.get("academic_term") or r.get("academic_year") or r.get("name"),
                        "due_date": None,
                        "due_date_fmt": "",
                        "amount": frappe.utils.flt(r.get("amount")),
                        "formatted_amount": "₹{:,.0f}".format(frappe.utils.flt(r.get("amount"))),
                        "status": "Pending",
                        "is_overdue": False
                    })
                    
        if not context.load_errors.get("hostel_fines"):
            for h in context.hostel_fines:
                if h.get("status") not in ("Paid", "Cancelled") and frappe.utils.flt(h.get("outstanding_amount")) > 0:
                    is_ov = h.get("due_date") and frappe.utils.getdate(h.get("due_date")) < today
                    out_rows.append({
                        "type": "Hostel Fine",
                        "component": h.get("fine_type") or "Hostel Fine",
                        "sub_label": h.get("name"),
                        "due_date": h.get("due_date"),
                        "due_date_fmt": h.get("due_date_fmt"),
                        "amount": h.get("outstanding_amount"),
                        "formatted_amount": h.get("formatted_outstanding"),
                        "status": "Overdue" if is_ov else "Pending",
                        "is_overdue": is_ov
                    })

        out_rows.sort(key=lambda x: (x["due_date"] or frappe.utils.getdate("2099-12-31")))
        context.outstanding_rows = out_rows

        # payment_history
        # Combine invoice payments (failed/captured) and receipts
        history = []
        seen_refs = set()
        
        if not context.load_errors.get("summary"):
            for inv in context.invoices:
                for p in inv.get("payments", []):
                    ref = p.get("reference_number")
                    if ref and ref in seen_refs: continue
                    if ref: seen_refs.add(ref)
                    history.append({
                        "date": p.get("payment_date"),
                        "date_fmt": p.get("display_date"),
                        "description": "Programme Fee",
                        "amount": p.get("amount"),
                        "formatted_amount": p.get("formatted_amount"),
                        "mode": p.get("payment_mode") or "Online Payment",
                        "reference": ref,
                        "status": p.get("rzp_status"),
                        "receipt": None
                    })
                    
        if not context.load_errors.get("transactions"):
            for t in context.all_transactions:
                ref = t.get("reference_number")
                if ref and ref in seen_refs: continue
                if ref: seen_refs.add(ref)
                desc = "Fee Receipt"
                history.append({
                    "date": t.get("receipt_date"),
                    "date_fmt": t.get("display_date"),
                    "description": desc,
                    "amount": t.get("amount"),
                    "formatted_amount": t.get("formatted_amount"),
                    "mode": t.get("payment_mode"),
                    "reference": ref,
                    "status": "Success",
                    "receipt": t.get("name")
                })
                
        history.sort(key=lambda x: (x["date"] or ""), reverse=True)
        context.payment_history = history
        
        # fee_academic_years
        ay_set = set()
        if not context.load_errors.get("summary"):
            for inv in context.invoices:
                if inv.get("academic_year"): ay_set.add(inv.get("academic_year"))
        if not context.load_errors.get("demands"):
            for d in context.fee_demands:
                if d.get("academic_year"): ay_set.add(d.get("academic_year"))
        if not context.load_errors.get("transactions"):
            for t in context.all_transactions:
                if t.get("academic_year"): ay_set.add(t.get("academic_year"))
                
        context.fee_academic_years = sorted(list(ay_set), reverse=True)

    except Exception as e:
        frappe.log_error(f"Student Portal Fees ViewModel error: {e}")
        context.load_errors["view_model"] = True


def _get_student_name():
    try:
        user = frappe.session.user
        if user == "Guest": return None
        
        r1 = frappe.get_all("Student Master", filters={"user": user}, fields=["name", "fee_structure"], order_by="creation desc") or []
        r2 = frappe.get_all("Student Master", filters={"email": user}, fields=["name", "fee_structure"], order_by="creation desc") or []
        r3 = frappe.get_all("Student Master", filters={"official_email_id": user}, fields=["name", "fee_structure"], order_by="creation desc") or []
        
        all_records = r1 + r2 + r3
        if not all_records:
            return None
            
        for r in all_records:
            if r.fee_structure:
                return r.name
        return all_records[0].name
    except Exception:
        return None

def _set_nav_defaults(context):
    context.student_id = ""
    context.student_name = ""
    context.student_initial = ""
    context.student_photo = ""
    context.current_enrollment = ""
    context.programme_name = ""
    context.department = ""
    context.batch_year = ""

def _set_student_nav(context, student):
    full_name = " ".join(filter(None, [student.first_name, student.middle_name, student.last_name]))
    context.student_name = full_name or student.name
    context.student_id = student.registration_id or student.name
    context.student_photo = student.passport_size_photo or ""
    context.student_initial = (context.student_name[0]).upper() if context.student_name else "S"
    
    prog_name = ""
    dept = ""
    batch = ""
    try:
        prog_enr = frappe.get_all(
            "Program Enrollment",
            filters={"student": student.name, "docstatus": 1},
            fields=["program", "academic_year"],
            order_by="creation desc",
            limit_page_length=1
        )
        if prog_enr:
            enr = prog_enr[0]
            prog_name = frappe.db.get_value("Program", enr.program, "program_name") or enr.program
            dept = frappe.db.get_value("Program", enr.program, "department") or ""
            batch = enr.academic_year or ""
    except Exception:
        pass
    
    context.current_enrollment = f"{prog_name} ({batch})" if prog_name else ""
    context.programme_name = prog_name
    context.department = dept
    context.batch_year = batch

def _ensure_student_fee_populated(student):
    # Just a stub to match original logic, logic is inside hooks in reality
    pass

def _set_defaults(context):
    context.total_fee               = 0.0
    context.total_scholarship       = 0.0
    context.total_paid              = 0.0
    context.total_net               = 0.0
    context.total_payable           = 0.0
    context.total_outstanding       = 0.0
    context.has_dues                = False
    context.sm_fee_status           = ""
    context.fee_structure_name      = ""
    context.fee_structure_doc_name  = ""
    context.fee_structure_valid_from  = ""
    context.fee_structure_valid_until = ""
    context.fee_structure_status    = ""
    context.fs_components           = []
    context.has_invoices            = False
    context.has_sm_inv_mismatch     = False
    context.sm_scholarship_amt      = 0.0
    context.inv_scholarship_amt     = 0.0
    context.mismatch_diff           = 0.0
    context.inv_outstanding_raw     = 0.0
    context.has_overpayment_flag    = False
    context.concessions             = []
    context.has_concessions         = False
    context.fee_demands             = []
    context.has_fee_demands         = False
    context.overdue_demands         = []
    context.has_overdue_demands     = False
    context.overdue_demand_count    = 0
    context.overdue_total           = 0
    context.formatted_overdue_total = "₹0"
    context.fee_refunds             = []
    context.has_fee_refunds         = False
    context.all_transactions        = []
    context.has_transactions        = False
    context.portal_error            = ""
    context.payment_enabled         = False
    context.payer_name              = ""
    context.payer_email             = ""
    context.payer_phone             = ""
    context.ward_student_name       = ""
    
    context.load_errors = {}
    context.paid_pct = None
    context.programme_overdue = 0
    context.programme_overdue_count = 0
    context.outstanding_rows = []
    context.payment_history = []
    context.fee_academic_years = []
    
    context.credit_notes = []
    context.has_credit_notes = False
    context.total_available_credit = 0
    context.formatted_total_credit = "₹0"
    
    context.re_exam_fees = []
    context.has_re_exam_fees = False
    
    context.hostel_fines = []
    context.has_hostel_fines = False

