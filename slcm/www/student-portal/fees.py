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
        student = frappe.get_doc("Student Master", student_name)
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
        sm_paid_raw    = frappe.utils.flt(student.total_paid_amount or 0)
        sm_net         = (frappe.utils.flt(student.net_program_fee or 0)
                          or max(sm_total_fee - sm_scholarship, 0))

        # ── Data-sanity guard ──────────────────────────────────────────────
        # total_paid_amount can exceed net_program_fee due to data-entry errors
        # or overpayment corrections. Clamp the displayed paid amount to the net
        # payable so the progress bar and outstanding never look inconsistent.
        sm_paid        = min(sm_paid_raw, sm_net) if sm_net > 0 else sm_paid_raw
        sm_outstanding = max(sm_net - sm_paid, 0)

        # ── Derive fee_payment_status from actual numbers ──────────────────
        # The stored fee_payment_status can be stale (set by gateway events and
        # never corrected after an offline/admin payment).  Recalculate it from
        # the authoritative numeric fields so the badge always matches the math.
        stored_status  = student.fee_payment_status or "Unpaid"
        # Only override "terminal" statuses that should reflect the current balance.
        # Leave gateway-lifecycle statuses (Payment Initiated, Authorized, etc.)
        # alone when the invoice is still genuinely in-flight (outstanding > 0).
        if sm_net > 0:
            if sm_outstanding <= 0:
                sm_fee_status = "Paid"
            elif sm_paid > 0:
                sm_fee_status = "Partially Paid"
            else:
                # Keep gateway status if it's an active lifecycle state
                if stored_status in ("Payment Initiated", "Authorized"):
                    sm_fee_status = stored_status
                else:
                    sm_fee_status = "Unpaid"
        else:
            sm_fee_status = stored_status or "Unpaid"

        # ── Auto-heal stale status on Student Master ───────────────────────
        # If the derived status differs from the stored one and the stored one
        # is a "resting" state (not an in-flight gateway status), write the
        # corrected value back so future page loads are consistent.
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
        # When Fee Invoices exist they are the ground truth for what the student
        # actually owes and what the payment gateway will charge against.
        # Using SM numbers in the hero while invoice cards show different numbers
        # causes visible inconsistency (e.g. hero ₹20,045 vs invoice ₹21,100 when
        # scholarship is on SM but not yet applied to the invoice).
        # Rule: if invoices exist → aggregate from invoices for the hero summary.
        #       if no invoices yet → use SM data (fallback / pre-invoice state).
        # SM data is still used for: payment status badge, fee structure label,
        # and the scholarship mismatch detection flag below.
        _use_sm_for_summary = sm_total_fee > 0 and not bool(invoices)

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
            # ── Per-invoice data-sanity ────────────────────────────────────
            # Clamp paid to payable to prevent display corruption when admin
            # has entered more paid than the net payable (e.g. overpayment).
            inv_payable_amt = frappe.utils.flt(inv.final_payable_amount or 0)
            inv_paid_amt    = frappe.utils.flt(inv.paid_amount or 0)
            if inv_payable_amt > 0:
                inv_paid_amt = min(inv_paid_amt, inv_payable_amt)
            display_outstanding = max(inv_payable_amt - inv_paid_amt, 0)

            # ── Derive invoice status from numbers (same logic as SM) ──────
            # Frappe's Fee Invoice status field can be stale after manual edits.
            stored_inv_status = inv.status or "Unpaid"
            if stored_inv_status == "Cancelled":
                effective_status = "Cancelled"
            elif inv_payable_amt > 0 and display_outstanding <= 0:
                effective_status = "Paid"
            elif inv_payable_amt > 0 and inv_paid_amt > 0:
                effective_status = "Partially Paid"
            else:
                effective_status = stored_inv_status if stored_inv_status != "Paid" else "Unpaid"

            inv["_effective_status"] = effective_status
            sc = STATUS_STYLE.get(effective_status, STATUS_STYLE["Unpaid"])
            inv["status_color"] = sc["color"]
            inv["status_bg"]    = sc["bg"]
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
            inv["outstanding_paisa"]     = int(display_outstanding * 100)
            # Expose sanitised amounts back so template calculations are consistent
            inv["outstanding_amount"]    = display_outstanding
            inv["paid_amount"]           = inv_paid_amt

            # Payment history: successful entries + all Razorpay-reported IR statuses
            try:
                payments = frappe.get_all(
                    "Fee Payment Entry",
                    filters={"parent": inv.name},
                    fields=["payment", "payment_date", "amount", "payment_mode"],
                    order_by="payment_date desc",
                    ignore_permissions=True,
                )
                for p in payments:
                    # Look up the actual bank/Razorpay reference from Fee Payment doc
                    # Fee Payment Entry.payment stores the internal Fee Payment doc name;
                    # the human-readable reference (Razorpay payment ID, cheque number,
                    # bank transfer ref) lives in Fee Payment.reference_number.
                    try:
                        p["reference_number"] = frappe.db.get_value(
                            "Fee Payment", p.payment, "reference_number") or ""
                    except Exception:
                        p["reference_number"] = ""
                    p["rzp_status"]  = "Captured"
                    p["is_rzp_only"] = False
            except Exception:
                payments = []

            # All Integration Requests for this invoice with a known Razorpay status
            # (exclude Pending = order created but no response yet)
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
                    # Skip "Completed" IRs whose amounts are already in Fee Payment Entry
                    if ir.status == "Completed":
                        continue
                    payments.append({
                        "payment":      ir.payment_id or ir.name,
                        "payment_date": ir.modified,
                        "amount":       0,
                        "payment_mode": "",
                        "rzp_status":   ir.status,
                        "is_rzp_only":  True,
                    })
            except Exception:
                pass

            inv["payments"] = payments

            # Receipts: find submitted Fee Payment records with a receipt issued
            try:
                fp_rows = frappe.get_all(
                    "Fee Payment",
                    filters={"fee_invoice": inv.name, "status": "Submitted",
                             "receipt": ["is", "set"]},
                    fields=["name", "receipt", "reference_number",
                            "payment_mode", "amount", "payment_date"],
                    ignore_permissions=True,
                )
                receipts = []
                for fp in fp_rows:
                    receipts.append({
                        "receipt_name":     fp.receipt,
                        "reference_number": fp.reference_number or "",
                        "payment_mode":     fp.payment_mode or "",
                        "formatted_amount": "₹{:,.0f}".format(
                            frappe.utils.flt(fp.amount or 0)),
                        "payment_date":     fp.payment_date,
                    })
                inv["receipts"]    = receipts
                inv["has_receipt"] = bool(receipts)
            except Exception:
                inv["receipts"]    = []
                inv["has_receipt"] = False

            # Fee component breakdown (tuition, hostel, exam, etc.)
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

        context.invoices     = invoices
        context.has_invoices = len(invoices) > 0

        # ── Apply hero/summary context ─────────────────────────────────────
        # Done after the per-invoice loop so sanitised invoice figures are ready.
        if _use_sm_for_summary:
            # No invoices yet — use Student Master as the only available source.
            context.use_sm_fallback      = sm_outstanding > 0
            context.total_payable        = sm_net
            context.total_paid           = sm_paid
            context.total_outstanding    = sm_outstanding
            context.total_scholarship    = sm_scholarship
            context.has_dues             = sm_outstanding > 0
            context.sm_fee_status        = sm_fee_status
            context.sm_total_fee         = sm_total_fee
            context.has_overpayment_flag = sm_paid_raw > sm_net and sm_net > 0
            context.has_sm_inv_mismatch  = False
            context.sm_scholarship_amt   = sm_scholarship
            context.inv_scholarship_amt  = 0.0
            context.mismatch_diff        = 0.0
            context.inv_outstanding_raw  = sm_outstanding
        else:
            # Invoices exist (or SM has no fee data) — always aggregate from invoices.
            # Invoice figures are the ground truth: they drive the payment gateway and
            # are what the student actually pays against.  Using SM totals when invoices
            # disagree (e.g. scholarship on SM but not yet pushed to invoice) produces
            # a confusing hero vs. invoice card number mismatch.
            inv_payable     = sum(frappe.utils.flt(i.final_payable_amount or 0) for i in invoices)
            inv_paid        = sum(frappe.utils.flt(i.get("paid_amount") or 0) for i in invoices)
            inv_outstanding = sum(frappe.utils.flt(i.get("outstanding_amount") or 0) for i in invoices)
            inv_scholarship = sum(frappe.utils.flt(i.scholarship_amount or 0) for i in invoices)

            # Derive payment status from invoice-aggregated numbers
            if inv_payable > 0:
                if inv_outstanding <= 0:
                    agg_status = "Paid"
                elif inv_paid > 0:
                    agg_status = "Partially Paid"
                else:
                    # Keep gateway lifecycle status from SM if still in-flight
                    if sm_fee_status in ("Payment Initiated", "Authorized"):
                        agg_status = sm_fee_status
                    else:
                        agg_status = "Unpaid"
            else:
                agg_status = sm_fee_status or ""

            # Detect SM-vs-invoice scholarship mismatch:
            # SM scholarship > invoice scholarship means the concession hasn't been
            # applied to the issued invoice yet — Finance Office needs to update the
            # invoice.  Show a clear notice so the student understands the discrepancy.
            sm_sch_rounded  = round(sm_scholarship, 2)
            inv_sch_rounded = round(inv_scholarship, 2)
            has_mismatch = (
                sm_sch_rounded > inv_sch_rounded
                and abs(sm_sch_rounded - inv_sch_rounded) > 0.5   # ignore rounding noise
                and inv_payable > 0
            )

            # If there's an unapplied scholarship (mismatch), compute what the student
            # should effectively owe after that scholarship is applied.  This lets the
            # hero show the correct amount even before Finance updates the invoice.
            effective_outstanding = inv_outstanding
            if has_mismatch:
                pending_sch = round(sm_scholarship - inv_scholarship, 2)
                effective_outstanding = max(inv_outstanding - pending_sch, 0)

            context.use_sm_fallback      = False
            context.total_payable        = inv_payable
            context.total_paid           = inv_paid
            context.total_outstanding    = effective_outstanding
            context.total_scholarship    = sm_scholarship          # show full SM scholarship
            context.has_dues             = effective_outstanding > 0
            context.sm_fee_status        = agg_status
            context.sm_total_fee         = sm_total_fee
            context.has_overpayment_flag = inv_paid > inv_payable and inv_payable > 0
            # Mismatch flag — scholarship recorded on SM but not applied to invoice(s)
            context.has_sm_inv_mismatch  = has_mismatch
            context.sm_scholarship_amt   = sm_scholarship
            context.inv_scholarship_amt  = inv_scholarship
            context.mismatch_diff        = round(sm_scholarship - inv_scholarship, 2)
            context.inv_outstanding_raw  = inv_outstanding        # actual invoice outstanding

        # ── All Transactions (flat receipt list) ───────────────
        try:
            all_txns = frappe.get_all(
                "Fee Receipt",
                filters={"student": student_name, "status": "Active"},
                fields=[
                    "name", "receipt_date", "amount", "payment_mode",
                    "reference_number", "transaction_date", "academic_year",
                    "bank_name",
                ],
                order_by="receipt_date desc",
                ignore_permissions=True,
            )
            for txn in all_txns:
                txn["formatted_amount"] = "₹{:,.0f}".format(
                    frappe.utils.flt(txn.amount or 0))
                txn["display_date"] = (
                    frappe.utils.formatdate(txn.receipt_date, "dd MMM yyyy")
                    if txn.receipt_date else ""
                )
            context.all_transactions = all_txns
            context.has_transactions  = bool(all_txns)
        except Exception:
            context.all_transactions = []
            context.has_transactions  = False

        # ── Concessions ────────────────────────────────────────
        try:
            concessions = frappe.get_all(
                "Fee Concession",
                filters={"student": student_name},
                fields=[
                    "name", "concession_type", "waiver_mode", "waiver_value",
                    "waiver_amount", "original_amount", "fee_component",
                    "status", "reason", "remarks", "approved_by", "approved_on",
                ],
                order_by="approved_on desc, creation desc",
                ignore_permissions=True,
            )
            for c in concessions:
                c["formatted_waiver"]   = "₹{:,.0f}".format(frappe.utils.flt(c.waiver_amount or 0))
                c["formatted_original"] = "₹{:,.0f}".format(frappe.utils.flt(c.original_amount or 0))
                c["waiver_display"] = (
                    "{:.0f}% of {}".format(
                        frappe.utils.flt(c.waiver_value),
                        "₹{:,.0f}".format(frappe.utils.flt(c.original_amount or 0)),
                    )
                    if c.waiver_mode == "Percentage"
                    else "₹{:,.0f} fixed".format(frappe.utils.flt(c.waiver_value or 0))
                )
                c["approved_on_fmt"] = (
                    frappe.utils.formatdate(c.approved_on, "dd MMM yyyy")
                    if c.approved_on else ""
                )
                if c.approved_by:
                    c["approved_by_name"] = (
                        frappe.db.get_value("User", c.approved_by, "full_name")
                        or c.approved_by
                    )
                else:
                    c["approved_by_name"] = ""

            context.concessions     = concessions
            context.has_concessions = bool(concessions)
            # Primary type for the hero scholarship stat box label
            context.primary_concession_type = next(
                (c.concession_type for c in concessions
                 if c.status == "Approved" and c.concession_type), ""
            )
        except Exception:
            context.concessions              = []
            context.has_concessions          = False
            context.primary_concession_type  = ""

        # ── Fee Demands ────────────────────────────────────────
        try:
            demands_raw = frappe.get_all(
                "Fee Demand",
                filters={"student": student_name, "status": ["not in", ["Cancelled"]]},
                fields=[
                    "name", "fee_component", "description", "demand_type",
                    "demand_date", "due_date", "status", "academic_year",
                    "original_amount", "waiver_amount", "net_payable",
                    "paid_amount", "credit_adjusted", "outstanding_amount",
                    "trigger_ref_doctype", "trigger_ref_name",
                ],
                order_by="due_date asc, creation asc",
                ignore_permissions=True,
            )
            _today = frappe.utils.getdate(frappe.utils.today())
            overdue_list = []
            for d in demands_raw:
                d["formatted_original"]    = "₹{:,.0f}".format(frappe.utils.flt(d.original_amount or 0))
                d["formatted_waiver"]      = "₹{:,.0f}".format(frappe.utils.flt(d.waiver_amount or 0))
                d["formatted_net"]         = "₹{:,.0f}".format(frappe.utils.flt(d.net_payable or 0))
                d["formatted_paid"]        = "₹{:,.0f}".format(frappe.utils.flt(d.paid_amount or 0))
                d["formatted_outstanding"] = "₹{:,.0f}".format(frappe.utils.flt(d.outstanding_amount or 0))
                settled = frappe.utils.flt(d.paid_amount or 0) + frappe.utils.flt(d.credit_adjusted or 0)
                d["settled_amount"]        = settled
                d["formatted_settled"]     = "₹{:,.0f}".format(settled)
                d["has_credit_adj"]        = frappe.utils.flt(d.credit_adjusted or 0) > 0
                d["formatted_credit_adj"]  = "₹{:,.0f}".format(frappe.utils.flt(d.credit_adjusted or 0))
                d["due_date_fmt"]          = (
                    frappe.utils.formatdate(d.due_date, "dd MMM yyyy") if d.due_date else ""
                )
                d["demand_date_fmt"]       = (
                    frappe.utils.formatdate(d.demand_date, "dd MMM yyyy") if d.demand_date else ""
                )
                if d.due_date and d.status not in ("Paid", "Waived"):
                    diff = (frappe.utils.getdate(d.due_date) - _today).days
                    d["days_overdue"] = abs(diff) if diff < 0 else 0
                    d["is_demand_overdue"] = diff < 0
                else:
                    d["days_overdue"] = 0
                    d["is_demand_overdue"] = False
                if d.status == "Overdue" or d["is_demand_overdue"]:
                    overdue_list.append(d)

            context.fee_demands          = demands_raw
            context.has_fee_demands      = bool(demands_raw)
            context.overdue_demands      = overdue_list
            context.has_overdue_demands  = bool(overdue_list)
            context.overdue_demand_count = len(overdue_list)
            context.overdue_total        = sum(
                frappe.utils.flt(d.outstanding_amount or 0) for d in overdue_list
            )
            context.formatted_overdue_total = "₹{:,.0f}".format(context.overdue_total)

            # ── Demand Analytics (for the Payment Analytics panel) ──────────
            _flt = frappe.utils.flt
            da_total      = len(demands_raw)
            da_paid       = sum(1 for d in demands_raw if d.status == "Paid")
            da_waived     = sum(1 for d in demands_raw if d.status == "Waived")
            da_pending    = sum(1 for d in demands_raw if d.status in ("Pending", "Overdue")
                                and not (d.status == "Overdue" or d.get("is_demand_overdue")))
            da_overdue    = len(overdue_list)
            da_total_amt  = sum(_flt(d.net_payable or 0)        for d in demands_raw)
            da_paid_amt   = sum(_flt(d.paid_amount or 0) +
                                _flt(d.credit_adjusted or 0)    for d in demands_raw)
            da_waived_amt = sum(_flt(d.waiver_amount or 0)      for d in demands_raw)
            da_outstanding= sum(_flt(d.outstanding_amount or 0) for d in demands_raw
                                if d.status not in ("Paid","Waived","Cancelled"))
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

        # ── Fee Refunds ────────────────────────────────────────
        try:
            refunds_raw = frappe.get_all(
                "Fee Refund",
                filters={"student": student_name, "status": ["not in", ["Reversed"]]},
                fields=[
                    "name", "fee_demand", "fee_component",
                    "refund_type", "refund_amount", "refund_date", "refund_mode",
                    "bank_name", "account_number", "utr_number",
                    "status", "approved_by", "approved_on",
                    "reason", "remarks",
                ],
                order_by="refund_date desc, creation desc",
                ignore_permissions=True,
            )
            for r in refunds_raw:
                r["formatted_amount"] = "₹{:,.0f}".format(frappe.utils.flt(r.refund_amount or 0))
                r["refund_date_fmt"]  = (
                    frappe.utils.formatdate(r.refund_date, "dd MMM yyyy") if r.refund_date else ""
                )
                r["approved_on_fmt"]  = (
                    frappe.utils.formatdate(r.approved_on, "dd MMM yyyy") if r.approved_on else ""
                )
                r["approved_by_name"] = (
                    frappe.db.get_value("User", r.approved_by, "full_name") or r.approved_by
                ) if r.approved_by else ""
                acct = str(r.account_number or "")
                r["masked_account"] = ("•••• " + acct[-4:]) if len(acct) > 4 else acct
                # Attach the demand's paid_amount so the portal can show a clear warning
                # when a refund exists but no payment was recorded (data-entry error scenario)
                try:
                    r["demand_paid_amount"] = frappe.utils.flt(
                        frappe.db.get_value("Fee Demand", r.fee_demand, "paid_amount") or 0
                    )
                except Exception:
                    r["demand_paid_amount"] = 0
            context.fee_refunds     = refunds_raw
            context.has_fee_refunds = bool(refunds_raw)
        except Exception:
            context.fee_refunds     = []
            context.has_fee_refunds = False

        # ── Student Credit Notes ───────────────────────────────
        try:
            credit_notes_raw = frappe.get_all(
                "Student Credit Note",
                filters={"student": student_name, "status": ["in", ["Active", "Exhausted"]]},
                fields=[
                    "name", "credit_type", "academic_year",
                    "credit_amount", "available_credit", "used_credit",
                    "status", "source_receipt", "remarks",
                ],
                order_by="creation desc",
                ignore_permissions=True,
            )
            for cn in credit_notes_raw:
                cn["formatted_credit"]    = "₹{:,.0f}".format(frappe.utils.flt(cn.credit_amount or 0))
                cn["formatted_available"] = "₹{:,.0f}".format(frappe.utils.flt(cn.available_credit or 0))
                cn["formatted_used"]      = "₹{:,.0f}".format(frappe.utils.flt(cn.used_credit or 0))
                amt = frappe.utils.flt(cn.credit_amount or 0)
                used = frappe.utils.flt(cn.used_credit or 0)
                cn["used_pct"] = int(min((used / amt * 100), 100)) if amt > 0 else 0
            context.credit_notes     = credit_notes_raw
            context.has_credit_notes = bool(credit_notes_raw)
            context.total_available_credit = sum(
                frappe.utils.flt(cn.available_credit or 0)
                for cn in credit_notes_raw if cn.status == "Active"
            )
            context.formatted_total_credit = "₹{:,.0f}".format(context.total_available_credit)
        except Exception:
            context.credit_notes             = []
            context.has_credit_notes         = False
            context.total_available_credit   = 0
            context.formatted_total_credit   = "₹0"

        # ── Re Exam Registrations ─────────────────────────────
        try:
            re_exams_raw = frappe.get_all(
                "Re Exam Registration",
                filters={"student": student_name, "status": "Registered"},
                fields=["name", "exam_plan", "course", "re_exam_fee", "payment_status"],
                order_by="creation desc",
                ignore_permissions=True,
            )
            for r in re_exams_raw:
                r["course_name"] = (
                    frappe.db.get_value("Course", r.course, "course_name") or r.course or ""
                )
                r["exam_plan_name"] = r.exam_plan or ""
                r["formatted_fee"]  = "₹{:,.0f}".format(frappe.utils.flt(r.re_exam_fee or 0))
                r["can_pay"] = (
                    frappe.utils.flt(r.re_exam_fee or 0) > 0
                    and r.payment_status in ("Pending", "Payment Failed", "Payment Initiated")
                )
            context.re_exam_fees     = re_exams_raw
            context.has_re_exam_fees = bool(re_exams_raw)
        except Exception:
            context.re_exam_fees     = []
            context.has_re_exam_fees = False

        # ── Hostel Fines ───────────────────────────────────────
        try:
            fines = frappe.get_all(
                "Hostel Fine",
                filters={"student": student_name, "status": ["in", ["Unpaid", "Paid"]]},
                fields=["name", "reason", "amount", "fine_date", "status"],
                order_by="fine_date desc",
                ignore_permissions=True,
            )
            for f in fines:
                f["formatted_amount"] = "₹{:,.0f}".format(frappe.utils.flt(f.amount or 0))
            context.hostel_fines     = fines
            context.has_hostel_fines = bool(fines)
        except Exception:
            context.hostel_fines     = []
            context.has_hostel_fines = False

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
        frappe.db.get_value("Batch", student.programme, "cohort_name")
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
        program = frappe.db.get_value("Batch", student.programme, "program")
        if not program and frappe.db.exists("Programme", student.programme):
            program = student.programme
        if not program:
            return

        current_date = frappe.utils.today()
        fs_rows = frappe.db.sql(
            """
            SELECT name, total_amount_for_indian AS total_amount, valid_from, valid_until
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
