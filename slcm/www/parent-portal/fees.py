import frappe
from slcm.slcm.utils.parent_portal import get_parent_context

no_cache = 1


def get_context(context):
    student = get_parent_context(context)
    if context.is_guest or context.not_a_parent or not student:
        _set_defaults(context)
        return context

    context.active_page = "fees"

    try:
        # student is already a full Student Master doc from get_parent_context
        sm = student

        # ── Programme-level fee summary from Student Master ──────────
        sm_total   = frappe.utils.flt(sm.total_program_fee or 0)
        sm_disc    = (frappe.utils.flt(sm.discount_amount or 0)
                      or frappe.utils.flt(sm.scholarship_amount or 0))
        sm_paid    = frappe.utils.flt(sm.total_paid_amount or 0)
        sm_net     = (frappe.utils.flt(sm.net_program_fee or 0)
                      or max(sm_total - sm_disc, 0))
        sm_outstanding = max(sm_net - sm_paid, 0)
        sm_fee_status  = sm.fee_payment_status or ""

        if sm.fee_structure:
            _fs_data = frappe.db.get_value(
                "Fee Structure", sm.fee_structure,
                ["fee_structure_name", "valid_from", "valid_until", "status"],
                as_dict=True,
            ) or {}
            context.fee_structure_name     = _fs_data.get("fee_structure_name") or sm.fee_structure
            context.fee_structure_valid_from  = str(_fs_data.get("valid_from") or "")
            context.fee_structure_valid_until = str(_fs_data.get("valid_until") or "")
            context.fee_structure_status      = _fs_data.get("status") or ""
        else:
            context.fee_structure_name        = ""
            context.fee_structure_valid_from  = ""
            context.fee_structure_valid_until = ""
            context.fee_structure_status      = ""
        context.fee_structure_doc_name = sm.fee_structure or ""

        # Fetch fee structure components for the programme-level breakdown card
        fs_components = []
        if sm.fee_structure:
            try:
                fs_components = frappe.db.sql(
                    """
                    SELECT fcc.component_name, fcc.amount, fcc.total_amount,
                           fcc.is_taxable, fcc.tax_rate, fcc.tax_amount
                    FROM `tabFee Component Child` fcc
                    WHERE fcc.parent = %s AND fcc.parenttype = 'Fee Structure'
                    ORDER BY fcc.idx
                    """,
                    sm.fee_structure,
                    as_dict=True,
                )
            except Exception:
                fs_components = []
        context.fs_components = fs_components

        # ── Fee Invoices ─────────────────────────────────────────────
        invoices = frappe.get_all(
            "Fee Invoice",
            filters={"student": student.name},
            fields=[
                "name", "academic_term", "program", "academic_year",
                "invoice_date", "due_date",
                "total_amount", "scholarship_amount", "final_payable_amount",
                "paid_amount", "outstanding_amount", "status",
            ],
            order_by="academic_term asc, creation asc",
            ignore_permissions=True,
        )

        # Fallback scholarship from invoices if SM doesn't have it
        if not sm_disc and invoices:
            sm_disc = sum(frappe.utils.flt(i.scholarship_amount or 0) for i in invoices)

        # Decide which totals to show
        if sm_total > 0:
            context.total_fee         = sm_total
            context.total_scholarship = sm_disc
            context.total_paid        = sm_paid
            context.total_net         = sm_net
            context.total_outstanding = sm_outstanding
            context.has_dues          = sm_outstanding > 0
            context.sm_fee_status     = sm_fee_status
        else:
            inv_payable     = sum(frappe.utils.flt(i.final_payable_amount or 0) for i in invoices)
            inv_paid        = sum(frappe.utils.flt(i.paid_amount or 0) for i in invoices)
            inv_outstanding = sum(max(frappe.utils.flt(i.outstanding_amount or 0), 0) for i in invoices)
            inv_scholarship = sum(frappe.utils.flt(i.scholarship_amount or 0) for i in invoices)
            context.total_fee         = inv_payable
            context.total_scholarship = inv_scholarship
            context.total_paid        = inv_paid
            context.total_net         = inv_payable
            context.total_outstanding = inv_outstanding
            context.has_dues          = inv_outstanding > 0
            context.sm_fee_status     = ""

        STATUS_STYLE = {
            "Paid":           {"color": "var(--pp-success)", "bg": "var(--pp-success-bg)", "icon": "check_circle"},
            "Partially Paid": {"color": "var(--pp-warning)", "bg": "var(--pp-warning-bg)", "icon": "pending"},
            "Unpaid":         {"color": "var(--pp-danger)",  "bg": "var(--pp-danger-bg)",  "icon": "receipt_long"},
            "Overdue":        {"color": "var(--pp-danger)",  "bg": "var(--pp-danger-bg)",  "icon": "error"},
            "Cancelled":      {"color": "var(--pp-text-4)",  "bg": "var(--pp-border-light)", "icon": "cancel"},
        }

        today = frappe.utils.getdate(frappe.utils.today())
        term_map = {}

        for inv in invoices:
            sc = STATUS_STYLE.get(inv.status, STATUS_STYLE["Unpaid"])
            inv["status_color"] = sc["color"]
            inv["status_bg"]    = sc["bg"]
            inv["status_icon"]  = sc["icon"]
            inv["is_overdue"]   = (
                inv.status not in ("Paid", "Cancelled")
                and inv.due_date
                and frappe.utils.getdate(inv.due_date) < today
            )
            display_outstanding = max(frappe.utils.flt(inv.outstanding_amount or 0), 0)
            inv["formatted_payable"]     = "₹{:,.0f}".format(frappe.utils.flt(inv.final_payable_amount or 0))
            inv["formatted_paid"]        = "₹{:,.0f}".format(frappe.utils.flt(inv.paid_amount or 0))
            inv["formatted_outstanding"] = "₹{:,.0f}".format(display_outstanding)
            inv["can_pay"] = (
                inv.status not in ("Paid", "Cancelled")
                and display_outstanding > 0
            )

            # Fee component breakdown
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

            # Payment history
            try:
                payments = frappe.get_all(
                    "Fee Payment Entry",
                    filters={"parent": inv.name},
                    fields=["payment", "payment_date", "amount", "payment_mode"],
                    order_by="payment_date desc",
                    ignore_permissions=True,
                )
                for p in payments:
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

            # Group by term
            term_key = inv.academic_term or "General"
            if term_key not in term_map:
                term_map[term_key] = {
                    "term": term_key,
                    "academic_year": inv.academic_year or "",
                    "invoices": [],
                    "term_total": 0.0,
                    "term_paid": 0.0,
                    "term_outstanding": 0.0,
                }
            term_map[term_key]["invoices"].append(inv)
            term_map[term_key]["term_total"]       += frappe.utils.flt(inv.final_payable_amount or 0)
            term_map[term_key]["term_paid"]        += frappe.utils.flt(inv.paid_amount or 0)
            term_map[term_key]["term_outstanding"] += display_outstanding

        # Format term totals
        for t in term_map.values():
            t["formatted_term_total"]       = "₹{:,.0f}".format(t["term_total"])
            t["formatted_term_paid"]        = "₹{:,.0f}".format(t["term_paid"])
            t["formatted_term_outstanding"] = "₹{:,.0f}".format(t["term_outstanding"])
            t["term_has_dues"]              = t["term_outstanding"] > 0

        context.term_groups  = list(term_map.values())
        context.has_invoices = bool(invoices)
        context.has_fee_data = sm_total > 0 or bool(invoices)

        # ── Payment gateway availability ─────────────────────────────
        try:
            context.payment_enabled = bool(
                frappe.db.get_single_value("Razorpay Settings", "api_key")
            )
        except Exception:
            context.payment_enabled = False

        # Student name needed by parent payment API
        context.ward_student_name = student.name

    except Exception as e:
        frappe.log_error(f"Parent Portal Fees error: {e}", "Parent Portal")
        context.portal_error = str(e)
        _set_defaults(context)

    return context


def _set_defaults(context):
    context.total_fee              = 0.0
    context.total_scholarship      = 0.0
    context.total_paid             = 0.0
    context.total_net              = 0.0
    context.total_outstanding      = 0.0
    context.has_dues               = False
    context.sm_fee_status          = ""
    context.fee_structure_name        = ""
    context.fee_structure_doc_name    = ""
    context.fee_structure_valid_from  = ""
    context.fee_structure_valid_until = ""
    context.fee_structure_status      = ""
    context.fs_components             = []
    context.term_groups            = []
    context.has_invoices           = False
    context.has_fee_data           = False
    context.portal_error           = ""
    context.payment_enabled        = False
    context.ward_student_name      = ""
