# Copyright (c) 2026, Azim Premji Foundation and contributors
# For license information, please see license.txt
"""
Fee Payment Zoho Journal Upload Report

Turns submitted Fee Payment records into a Zoho Books Journal Import file.

Per Fee Payment:
  1. Look up every Fee Demand it settled (via payment_demands / Fee Payment
     Demand Row) and group the allocated amount by Fee Component.
  2. Emit one Credit row per Fee Component (account = component's mapped
     ledger, falling back to the component name itself).
  3. Emit one Debit row for the full payment amount against the receiving
     account (bank account on the payment, or the Cash account for cash
     payments, or the configured default).

Journal amounts:
  Sum of component credits == payment amount == debit amount, so every
  payment is always balanced on its own.
"""

import io
import json

import frappe
from frappe import _
from frappe.utils import flt, formatdate, nowdate

# ── Constants ─────────────────────────────────────────────────────────────────
DEFAULT_BANK_ACCOUNT = "UBI Bank General"
DEFAULT_CASH_ACCOUNT = "Cash"
DEFAULT_CONTACT       = "Student"
DEFAULT_PREFIX        = "JN-FP-"
DEFAULT_JOURNAL_TYPE  = "Both"
DEFAULT_CURRENCY      = "INR"
DEFAULT_DESCRIPTION   = "Fee Payment"
DEFAULT_DEPARTMENT    = ""
DEFAULT_COURSE        = ""

PAYMENT_MODE_ACCOUNTS = {
    "Cash":           DEFAULT_CASH_ACCOUNT,
    "Bank Transfer":  DEFAULT_BANK_ACCOUNT,
    "Cheque":         DEFAULT_BANK_ACCOUNT,
    "Credit Card":    DEFAULT_BANK_ACCOUNT,
    "Debit Card":     DEFAULT_BANK_ACCOUNT,
    "Online Payment": DEFAULT_BANK_ACCOUNT,
    "Other":          DEFAULT_BANK_ACCOUNT,
}

# Zoho Books required column order — do NOT change
ZOHO_HEADERS = [
    "Journal Date", "Reference Number", "Journal Number Prefix",
    "Journal Number Suffix", "Notes", "Journal Type", "Currency",
    "Account", "Description", "Contact Name", "Debit", "Credit",
    "Department", "Course",
]
ZOHO_FIELD_MAP = {
    "Journal Date":          "journal_date",
    "Reference Number":      "reference_number",
    "Journal Number Prefix": "journal_number_prefix",
    "Journal Number Suffix": "journal_number_suffix",
    "Notes":                 "notes",
    "Journal Type":          "journal_type",
    "Currency":              "currency",
    "Account":               "account",
    "Description":           "description",
    "Contact Name":          "contact_name",
    "Debit":                 "debit",
    "Credit":                "credit",
    "Department":            "department",
    "Course":                "course",
}


# ── Entry point ───────────────────────────────────────────────────────────────

def execute(filters=None):
    filters = filters or {}
    config  = _resolve_config(filters)

    payments = _fetch_payments(filters)
    if not payments:
        frappe.msgprint(
            _("No submitted fee payments found for the selected filters."),
            indicator="orange", alert=True,
        )
        return _get_columns(), [], None, None, []

    rows, stats = _build_journal_rows(payments, config)

    return (
        _get_columns(),
        rows,
        None,
        _get_chart(stats["daily"]),
        _get_report_summary(stats),
    )


# ── Columns ───────────────────────────────────────────────────────────────────

def _get_columns():
    return [
        {"label": _("Journal Date"),           "fieldname": "journal_date",          "fieldtype": "Date",     "width": 110},
        {"label": _("Reference Number"),        "fieldname": "reference_number",      "fieldtype": "Data",     "width": 160},
        {"label": _("Journal Number Prefix"),   "fieldname": "journal_number_prefix", "fieldtype": "Data",     "width": 145},
        {"label": _("Journal Number Suffix"),   "fieldname": "journal_number_suffix", "fieldtype": "Int",      "width": 145},
        {"label": _("Notes"),                   "fieldname": "notes",                 "fieldtype": "Data",     "width": 340},
        {"label": _("Journal Type"),            "fieldname": "journal_type",          "fieldtype": "Data",     "width":  85},
        {"label": _("Currency"),                "fieldname": "currency",              "fieldtype": "Data",     "width":  75},
        {"label": _("Account"),                 "fieldname": "account",               "fieldtype": "Data",     "width": 260},
        {"label": _("Description"),             "fieldname": "description",           "fieldtype": "Data",     "width": 100},
        {"label": _("Contact Name"),            "fieldname": "contact_name",          "fieldtype": "Data",     "width": 130},
        {"label": _("Debit"),                   "fieldname": "debit",                 "fieldtype": "Currency", "width": 130},
        {"label": _("Credit"),                  "fieldname": "credit",                "fieldtype": "Currency", "width": 130},
        {"label": _("Department"),              "fieldname": "department",            "fieldtype": "Data",     "width": 110},
        {"label": _("Course"),                  "fieldname": "course",                "fieldtype": "Data",     "width": 130},
        # Display-only (never exported to Zoho)
        {"label": _("Row Type"),                "fieldname": "row_type",              "fieldtype": "Data",     "width":  85},
        {"label": _("Fee Payment"),             "fieldname": "fee_payment",           "fieldtype": "Link",     "options": "Fee Payment", "width": 130},
        {"label": _("Student"),                 "fieldname": "student",               "fieldtype": "Link",     "options": "Student Master", "width": 130},
        {"label": _("Payment Mode"),            "fieldname": "payment_mode",          "fieldtype": "Data",     "width": 110},
    ]


# ── Dynamic config ────────────────────────────────────────────────────────────

def _resolve_config(filters):
    return {
        "bank_account": (filters.get("bank_account") or "").strip() or DEFAULT_BANK_ACCOUNT,
        "cash_account": (filters.get("cash_account") or "").strip() or DEFAULT_CASH_ACCOUNT,
        "prefix":       (filters.get("journal_prefix") or "").strip() or DEFAULT_PREFIX,
        "department":   (filters.get("department") or "").strip() or DEFAULT_DEPARTMENT,
        "course":       (filters.get("course") or "").strip() or DEFAULT_COURSE,
    }


# ── Data fetch ────────────────────────────────────────────────────────────────

def _fetch_payments(filters):
    conditions = ["fp.status = 'Submitted'"]
    values = {}

    if filters.get("from_date"):
        conditions.append("fp.payment_date >= %(from_date)s")
        values["from_date"] = filters["from_date"]
    if filters.get("to_date"):
        conditions.append("fp.payment_date <= %(to_date)s")
        values["to_date"] = filters["to_date"]
    if filters.get("payment_mode"):
        conditions.append("fp.payment_mode = %(payment_mode)s")
        values["payment_mode"] = filters["payment_mode"]
    if filters.get("program"):
        conditions.append("fp.program = %(program)s")
        values["program"] = filters["program"]

    where_clause = " AND ".join(conditions)

    payments = frappe.db.sql(
        f"""
        SELECT
            fp.name              AS fee_payment,
            fp.student            AS student,
            fp.student_name       AS student_name,
            fp.program            AS program,
            fp.payment_date       AS payment_date,
            fp.payment_mode       AS payment_mode,
            fp.amount             AS amount,
            fp.bank_account       AS bank_account,
            fp.reference_number   AS reference_number,
            fp.remarks            AS remarks
        FROM `tabFee Payment` fp
        WHERE {where_clause}
        ORDER BY fp.payment_date ASC, fp.name ASC
        """,
        values,
        as_dict=True,
    )
    if not payments:
        return []

    payment_names = [p.fee_payment for p in payments]
    demand_rows = frappe.db.sql(
        """
        SELECT
            fpdr.parent            AS fee_payment,
            fpdr.amount_allocated  AS amount_allocated,
            fd.fee_component       AS fee_component,
            fd.description         AS demand_description
        FROM `tabFee Payment Demand Row` fpdr
        LEFT JOIN `tabFee Demand` fd ON fd.name = fpdr.fee_demand
        WHERE fpdr.parent IN %(names)s
        """,
        {"names": payment_names},
        as_dict=True,
    )

    demands_by_payment = {}
    for row in demand_rows:
        demands_by_payment.setdefault(row.fee_payment, []).append(row)

    programs = {p.program for p in payments if p.program}
    dept_by_program = {}
    if programs:
        for r in frappe.db.get_all(
            "Programme", filters={"name": ["in", list(programs)]},
            fields=["name", "department"],
        ):
            dept_by_program[r.name] = r.department or ""

    component_names = {
        d.fee_component for rows in demands_by_payment.values() for d in rows if d.fee_component
    }
    ledger_by_component = {}
    if component_names:
        for r in frappe.db.get_all(
            "Fee Component", filters={"name": ["in", list(component_names)]},
            fields=["name", "ledger"],
        ):
            ledger_by_component[r.name] = r.ledger or ""

    for p in payments:
        p["demands"]    = demands_by_payment.get(p.fee_payment, [])
        p["department"] = dept_by_program.get(p.program, "")
        p["ledger_map"] = ledger_by_component

    return payments


# ── Journal row builder ───────────────────────────────────────────────────────

def _build_journal_rows(payments, config):
    rows         = []
    suffix       = _next_suffix(config["prefix"])
    daily_totals = {}

    for p in payments:
        amount = flt(p.amount)
        if amount <= 0:
            continue

        components = _split_by_component(p)
        if not components:
            # No demand breakdown available — fall back to a single generic credit
            components = [("Unallocated Fee", amount)]

        date_str = formatdate(p.payment_date, "dd-MM-yyyy")
        notes = f"Fee payment on {date_str} via {p.payment_mode or 'Unknown'}" + (
            f" | Ref: {p.reference_number}" if p.reference_number else ""
        )

        debit_account = (p.bank_account or "").strip() or (
            config["cash_account"] if p.payment_mode == "Cash" else config["bank_account"]
        )

        daily_totals[str(p.payment_date)] = daily_totals.get(str(p.payment_date), 0) + amount

        shared = {
            "journal_date":          p.payment_date,
            "reference_number":      p.reference_number or p.fee_payment,
            "journal_number_prefix": config["prefix"],
            "journal_number_suffix": suffix,
            "notes":                 notes,
            "journal_type":          DEFAULT_JOURNAL_TYPE,
            "currency":              DEFAULT_CURRENCY,
            "description":           DEFAULT_DESCRIPTION,
            "contact_name":          p.student_name or DEFAULT_CONTACT,
            "department":            p.department or config["department"],
            "course":                p.program or config["course"],
            "fee_payment":           p.fee_payment,
            "student":               p.student,
            "payment_mode":          p.payment_mode,
        }

        for account_name, comp_amount in components:
            rows.append({
                **shared,
                "account":  account_name,
                "debit":    0,
                "credit":   comp_amount,
                "row_type": "Credit",
            })

        rows.append({
            **shared,
            "account":  debit_account,
            "debit":    amount,
            "credit":   0,
            "row_type": "Debit",
        })

        suffix += 1

    rows.sort(key=lambda r: (r["journal_date"], r["journal_number_suffix"], r["row_type"]))

    total_debit  = round(sum(r["debit"]  for r in rows), 2)
    total_credit = round(sum(r["credit"] for r in rows), 2)
    balanced     = abs(total_debit - total_credit) < 0.01

    stats = {
        "total_payments": len({r["fee_payment"] for r in rows}),
        "total_rows":     len(rows),
        "total_debit":    total_debit,
        "total_credit":   total_credit,
        "balanced":       balanced,
        "daily":          daily_totals,
    }
    return rows, stats


def _split_by_component(payment):
    """Group a payment's allocated demand amounts by Fee Component.
    Returns a list of (account_name, amount) tuples.
    """
    totals = {}
    for d in payment.demands:
        comp   = d.fee_component or d.demand_description or "Unallocated Fee"
        ledger = payment.ledger_map.get(d.fee_component, "") if d.fee_component else ""
        account_name = ledger or comp
        totals[account_name] = totals.get(account_name, 0) + flt(d.amount_allocated)

    # Guard against demand allocations not summing to the full payment amount
    # (partial allocation / unlinked balance) — plug the gap as "Unallocated Fee"
    allocated_total = round(sum(totals.values()), 2)
    remainder = round(flt(payment.amount) - allocated_total, 2)
    if abs(remainder) >= 0.01:
        totals["Unallocated Fee"] = totals.get("Unallocated Fee", 0) + remainder

    return [(k, v) for k, v in totals.items() if abs(v) >= 0.01]


def _next_suffix(prefix):
    series_name = f"{prefix}.####"
    try:
        result = frappe.db.sql(
            "SELECT current FROM `tabSeries` WHERE name = %s", (series_name,)
        )
        return int(result[0][0]) + 1 if result else 1
    except Exception:
        return 1


# ── Summary cards ─────────────────────────────────────────────────────────────

def _get_report_summary(stats):
    balanced = stats.get("balanced", False)
    return [
        {
            "value":     stats["total_payments"],
            "label":     _("Fee Payments"),
            "datatype":  "Int",
            "indicator": "Blue",
        },
        {
            "value":     stats["total_rows"],
            "label":     _("Journal Rows"),
            "datatype":  "Int",
            "indicator": "Blue",
        },
        {
            "value":     stats["total_debit"],
            "label":     _("Total Debit (₹)"),
            "datatype":  "Currency",
            "currency":  "INR",
            "indicator": "Blue",
        },
        {
            "value":     stats["total_credit"],
            "label":     _("Total Credit (₹)"),
            "datatype":  "Currency",
            "currency":  "INR",
            "indicator": "Green",
        },
        {
            "value":     "Balanced ✓" if balanced else "UNBALANCED ✗",
            "label":     _("Debit = Credit"),
            "datatype":  "Data",
            "indicator": "Green" if balanced else "Red",
        },
    ]


# ── Trend chart ───────────────────────────────────────────────────────────────

def _get_chart(daily_totals):
    if not daily_totals:
        return None
    sorted_days = sorted(daily_totals)
    return {
        "data": {
            "labels":   [formatdate(d, "dd MMM") for d in sorted_days],
            "datasets": [{"name": _("Amount (₹)"), "values": [daily_totals[d] for d in sorted_days]}],
        },
        "type":        "bar",
        "colors":      ["#5e64ff"],
        "axisOptions": {"xIsSeries": True},
    }


# ── Utilities ─────────────────────────────────────────────────────────────────

def _format_zoho_date(val):
    try:
        return formatdate(val, "dd-MM-yyyy")
    except Exception:
        return str(val) if val else ""


def _cell(value, header):
    if value is None:
        return ""
    if header == "Journal Date":
        return _format_zoho_date(value)
    if header in ("Debit", "Credit"):
        v = flt(value)
        return v if v else ""
    return str(value) if value else ""


# ── Zoho Books export ─────────────────────────────────────────────────────────

@frappe.whitelist()
def download_zoho_upload_file(filters=None, file_format="csv"):
    """
    Generate Zoho Books–compatible journal upload file (14 columns only).
    Hard-blocks export if Debit != Credit.
    """
    import base64

    if isinstance(filters, str):
        try:
            filters = json.loads(filters)
        except Exception:
            filters = {}
    filters = filters or {}

    config   = _resolve_config(filters)
    payments = _fetch_payments(filters)
    if not payments:
        frappe.throw(_("No submitted fee payments found for the selected filters."))

    rows, stats = _build_journal_rows(payments, config)
    if not rows:
        frappe.throw(_("No journal rows matched the applied filters."))

    if not stats["balanced"]:
        diff = round(stats["total_debit"] - stats["total_credit"], 2)
        frappe.throw(
            _(
                "Export blocked — journal is not balanced.<br>"
                "Total Debit: ₹{0} | Total Credit: ₹{1} | Difference: ₹{2}"
            ).format(
                f"{stats['total_debit']:,.2f}",
                f"{stats['total_credit']:,.2f}",
                f"{diff:,.2f}",
            ),
            title=_("Validation Failed — Unbalanced Journal"),
        )

    from_d     = filters.get("from_date", "")
    to_d       = filters.get("to_date", nowdate())
    date_label = f"{from_d}_{to_d}".strip("_") or nowdate()

    if file_format == "xlsx":
        content, filename, mime = _build_xlsx(rows, date_label, stats, config)
    else:
        content, filename, mime = _build_csv(rows, date_label)

    return {
        "filename":     filename,
        "content":      base64.b64encode(content).decode("utf-8"),
        "mime":         mime,
        "row_count":    len(rows),
        "balanced":     stats["balanced"],
        "total_debit":  stats["total_debit"],
        "total_credit": stats["total_credit"],
    }


@frappe.whitelist()
def get_dynamic_defaults():
    return {
        "bank_account":   DEFAULT_BANK_ACCOUNT,
        "cash_account":   DEFAULT_CASH_ACCOUNT,
        "journal_prefix": DEFAULT_PREFIX,
        "department":     DEFAULT_DEPARTMENT,
        "course":         DEFAULT_COURSE,
    }


# ── CSV builder ───────────────────────────────────────────────────────────────

def _build_csv(rows, date_label):
    import csv
    buf    = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(ZOHO_HEADERS)
    for r in rows:
        writer.writerow([_cell(r.get(ZOHO_FIELD_MAP[h]), h) for h in ZOHO_HEADERS])
    content  = buf.getvalue().encode("utf-8-sig")
    filename = f"zoho_fee_journal_{date_label}.csv"
    return content, filename, "text/csv"


# ── XLSX builder ──────────────────────────────────────────────────────────────

def _build_xlsx(rows, date_label, stats, config):
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        frappe.throw(_("openpyxl is not installed. Run: bench pip install openpyxl"))

    PURPLE    = "5E64FF"
    INDIGO    = "3949AB"
    WHITE     = "FFFFFF"
    GREEN_BG  = "E8F5E9"
    BLUE_BG   = "E3F2FD"
    STRIPE    = "F7F8FF"
    TOTAL_BG  = "E8EAF6"
    OK_CLR    = "2E7D32"
    ERR_CLR   = "C62828"
    BD        = "C5CAE9"

    thin_s  = Side(style="thin",   color=BD)
    thick_s = Side(style="medium", color=PURPLE)
    t_bdr   = Border(left=thin_s,  right=thin_s,  top=thin_s,  bottom=thin_s)
    h_bdr   = Border(left=thick_s, right=thick_s, top=thick_s, bottom=thick_s)

    n_cols     = len(ZOHO_HEADERS)
    debit_col  = ZOHO_HEADERS.index("Debit")  + 1
    credit_col = ZOHO_HEADERS.index("Credit") + 1
    balanced   = stats.get("balanced", False)

    wb = openpyxl.Workbook()

    # ── Sheet 1: Journal Upload ───────────────────────────────────────────────
    ws = wb.active
    ws.title = "Journal Upload"
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "D3"

    ws.row_dimensions[1].height = 30
    ws.append([""] * n_cols)
    tc = ws.cell(row=1, column=1,
        value=f"Fee Payment Journal  |  Zoho Books Import  |  {date_label}")
    tc.font      = Font(bold=True, size=10, color=WHITE, name="Calibri")
    tc.fill      = PatternFill("solid", fgColor=PURPLE)
    tc.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n_cols)

    ws.row_dimensions[2].height = 34
    ws.append(ZOHO_HEADERS)
    for ci, h in enumerate(ZOHO_HEADERS, 1):
        cell = ws.cell(row=2, column=ci)
        cell.font      = Font(bold=True, color=WHITE, size=10, name="Calibri")
        cell.fill      = PatternFill("solid", fgColor=INDIGO)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border    = h_bdr

    for ri, r in enumerate(rows, 3):
        rt = r.get("row_type", "")
        bg = PatternFill("solid", fgColor=GREEN_BG if rt == "Credit"
                          else BLUE_BG if rt == "Debit"
                          else (STRIPE if ri % 2 == 0 else WHITE))
        ws.row_dimensions[ri].height = 16

        for ci, h in enumerate(ZOHO_HEADERS, 1):
            val  = _cell(r.get(ZOHO_FIELD_MAP[h]), h)
            cell = ws.cell(row=ri, column=ci, value=val)
            cell.fill = bg; cell.border = t_bdr

            if h in ("Debit", "Credit"):
                cell.font          = Font(bold=bool(val), size=9, name="Calibri",
                                          color="1565C0" if h == "Debit" else "2E7D32")
                cell.number_format = "#,##0.00"
                cell.alignment     = Alignment(horizontal="right", vertical="center")
            elif h == "Journal Date":
                cell.font      = Font(size=9, name="Calibri")
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif h in ("Journal Number Suffix", "Journal Type", "Currency",
                       "Department", "Course"):
                cell.font      = Font(size=9, name="Calibri")
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif h == "Account":
                clr = "6A1B9A" if rt == "Credit" else "1565C0"
                cell.font      = Font(size=9, name="Calibri", color=clr)
                cell.alignment = Alignment(vertical="center")
            else:
                cell.font      = Font(size=9, name="Calibri")
                cell.alignment = Alignment(vertical="center")

    total_ri = len(rows) + 3
    ws.row_dimensions[total_ri].height = 22
    for ci in range(1, n_cols + 1):
        cell = ws.cell(row=total_ri, column=ci)
        cell.fill      = PatternFill("solid", fgColor=TOTAL_BG)
        cell.font      = Font(bold=True, size=10, name="Calibri", color="1A237E")
        cell.border    = h_bdr
        cell.alignment = Alignment(horizontal="right", vertical="center")
        if ci == 1:
            cell.value     = "TOTAL"
            cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        elif ci == debit_col:
            cell.value = stats["total_debit"]; cell.number_format = "#,##0.00"
        elif ci == credit_col:
            cell.value = stats["total_credit"]; cell.number_format = "#,##0.00"

    for ci, h in enumerate(ZOHO_HEADERS, 1):
        vals   = [str(_cell(r.get(ZOHO_FIELD_MAP[h]), h) or "") for r in rows]
        maxlen = max(len(str(h)), *(len(v) for v in vals)) if vals else len(str(h))
        ws.column_dimensions[get_column_letter(ci)].width = min(maxlen + 3, 50)

    # ── Sheet 2: Summary ──────────────────────────────────────────────────────
    ws2 = wb.create_sheet("Summary")
    ws2.sheet_view.showGridLines = False
    ws2.column_dimensions["A"].width = 34
    ws2.column_dimensions["B"].width = 26

    s_hdr   = Font(bold=True, color=WHITE, size=10, name="Calibri")
    s_hfill = PatternFill("solid", fgColor=PURPLE)
    s_lbl   = Font(bold=True, size=10, name="Calibri", color="424242")
    s_val   = Font(size=10, name="Calibri")
    s_ok    = Font(bold=True, size=10, name="Calibri", color=OK_CLR)
    s_err   = Font(bold=True, size=10, name="Calibri", color=ERR_CLR)
    s_bdr   = Border(
        left=Side(style="thin", color="CCCCCC"), right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"),  bottom=Side(style="thin", color="CCCCCC"),
    )

    summary_rows = [
        ("Report Details", ""),
        ("Report Name",   "Fee Payment Zoho Journal Upload"),
        ("Date Range",    date_label),
        ("Generated On",  nowdate()),
        ("", ""),
        ("Journal Configuration", ""),
        ("Default Bank Account", config.get("bank_account") or DEFAULT_BANK_ACCOUNT),
        ("Default Cash Account", config.get("cash_account") or DEFAULT_CASH_ACCOUNT),
        ("Journal Prefix",       config.get("prefix")       or DEFAULT_PREFIX),
        ("", ""),
        ("Payment Statistics", ""),
        ("Total Fee Payments", stats["total_payments"]),
        ("Total Journal Rows", stats["total_rows"]),
        ("", ""),
        ("Journal Totals", ""),
        ("Total Debit",                 stats["total_debit"]),
        ("Total Credit",                stats["total_credit"]),
        ("Difference (Debit − Credit)", round(stats["total_debit"] - stats["total_credit"], 2)),
        ("", ""),
        ("Validation", ""),
        ("Debit = Credit",   "YES — Balanced ✓" if balanced else "NO — UNBALANCED ✗"),
        ("Ready for Import", "YES" if balanced else "NO — Fix before importing"),
    ]

    ws2.row_dimensions[1].height = 28
    t2 = ws2.cell(row=1, column=1, value="Zoho Books Journal Upload — Summary")
    t2.font = Font(bold=True, size=13, color=PURPLE, name="Calibri")
    t2.alignment = Alignment(horizontal="left", vertical="center")
    ws2.merge_cells("A1:B1")

    for ri, (label, value) in enumerate(summary_rows, 2):
        ws2.row_dimensions[ri].height = 18
        cl = ws2.cell(row=ri, column=1, value=label)
        cv = ws2.cell(row=ri, column=2, value=value)
        if not label:
            continue
        if value == "":
            cl.font = s_hdr; cl.fill = s_hfill
            cl.alignment = Alignment(horizontal="left", vertical="center", indent=1)
            ws2.merge_cells(start_row=ri, start_column=1, end_row=ri, end_column=2)
            continue
        cl.font = s_lbl; cl.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        cl.border = s_bdr; cv.border = s_bdr
        if label in ("Total Debit", "Total Credit", "Difference (Debit − Credit)"):
            cv.number_format = "#,##0.00"; cv.font = s_val
        elif label in ("Debit = Credit", "Ready for Import"):
            cv.font = s_ok if balanced else s_err
        else:
            cv.font = s_val
        cv.alignment = Alignment(
            horizontal="right" if isinstance(value, (int, float)) else "left",
            vertical="center",
        )

    # ── Sheet 3: Instructions ─────────────────────────────────────────────────
    ws3 = wb.create_sheet("Import Instructions")
    ws3.sheet_view.showGridLines = False
    ws3.column_dimensions["A"].width = 90

    steps = [
        ("Zoho Books Journal Import — Step-by-step Guide", True),
        ("", False),
        ("Step 1 — Verify data in the 'Journal Upload' sheet.", False),
        ("Step 2 — Check 'Summary' sheet: Debit = Credit must show YES.", False),
        ("Step 3 — In Zoho Books: Accountant → Journal → ⋮ → Import Journals.", False),
        ("Step 4 — Upload this XLSX file (or the CSV version).", False),
        ("Step 5 — Map columns if prompted, preview and confirm.", False),
        ("", False),
        ("Amount Notes", True),
        ("Each Fee Payment produces one Credit row per Fee Component it settles", False),
        ("(via its linked Fee Demands), plus one Debit row for the full amount", False),
        ("against the receiving bank/cash account — always balanced per payment.", False),
        ("", False),
        ("Column Reference", True),
        ("Journal Date          — dd-MM-yyyy  (e.g. 21-02-2026)", False),
        ("Reference Number      — Transaction reference or Fee Payment ID", False),
        ("Journal Number Prefix — Configured prefix  (default: JN-FP-)", False),
        ("Journal Number Suffix — Auto-incremented integer", False),
        ("Notes                 — Payment date, mode, and reference", False),
        ("Account               — Must exactly match Zoho Books chart of accounts", False),
        ("Debit / Credit        — Only one value per row; other is blank", False),
    ]

    for ri, (text, heading) in enumerate(steps, 1):
        ws3.row_dimensions[ri].height = 18
        cell = ws3.cell(row=ri, column=1, value=text)
        cell.font = (
            Font(bold=True, size=11, color=PURPLE, name="Calibri") if heading
            else Font(size=10, name="Calibri", color="424242")
        )
        cell.alignment = Alignment(vertical="center")

    buf = io.BytesIO()
    wb.save(buf)
    return (
        buf.getvalue(),
        f"zoho_fee_journal_{date_label}.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
