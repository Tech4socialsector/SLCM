"""
FLE Payment Journal Report

Settlement data is stored locally in FLE Payment Log by the
settlement.processed webhook handler (slcm/api/razorpay_webhook.py).

Journal Date  = settlement_date from FLE Payment Log
              → falls back to transaction_date when not yet settled
Debit         = gross paid_amount (what student paid)
Credit        = net_settled (after Razorpay fees/tax); falls back to paid_amount
"""

import frappe
from frappe import _


# ---------------------------------------------------------------------------
# Report entry points
# ---------------------------------------------------------------------------

def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		# ── Core journal fields ──────────────────────────────────────────────
		{"label": _("Journal Date"),          "fieldname": "journal_date",          "fieldtype": "Date",     "width": 110},
		{"label": _("Reference Number"),      "fieldname": "reference_number",      "fieldtype": "Data",     "width": 185},
		{"label": _("Journal Number Prefix"), "fieldname": "journal_number_prefix", "fieldtype": "Data",     "width": 145},
		{"label": _("Journal Number Suffix"), "fieldname": "journal_number_suffix", "fieldtype": "Data",     "width": 145},
		{"label": _("Notes"),                 "fieldname": "notes",                 "fieldtype": "Data",     "width": 180},
		{"label": _("Journal Type"),          "fieldname": "journal_type",          "fieldtype": "Data",     "width": 120},
		{"label": _("Currency"),              "fieldname": "currency",              "fieldtype": "Data",     "width":  80},
		{"label": _("Account Code"),          "fieldname": "account_code",          "fieldtype": "Data",     "width": 110},
		{"label": _("Account"),               "fieldname": "account",               "fieldtype": "Data",     "width": 160},
		{"label": _("Description"),           "fieldname": "description",           "fieldtype": "Data",     "width": 210},
		{"label": _("Contact Name"),          "fieldname": "contact_name",          "fieldtype": "Data",     "width": 160},
		{"label": _("Debit"),                 "fieldname": "debit",                 "fieldtype": "Currency", "width": 115},
		{"label": _("Credit"),                "fieldname": "credit",                "fieldtype": "Currency", "width": 115},
		{"label": _("Department"),            "fieldname": "department",            "fieldtype": "Data",     "width": 130},
		{"label": _("Course"),                "fieldname": "course",                "fieldtype": "Data",     "width": 200},
		{"label": _("Student ID"),            "fieldname": "student_id",            "fieldtype": "Data",     "width": 130},
		# ── Settlement fields (from FLE Payment Log, populated by webhook) ───
		{"label": _("Settlement ID"),         "fieldname": "settlement_id",         "fieldtype": "Data",     "width": 160},
		{"label": _("UTR Number"),            "fieldname": "utr",                   "fieldtype": "Data",     "width": 160},
		{"label": _("Settlement Status"),     "fieldname": "settlement_status",     "fieldtype": "Data",     "width": 120},
		{"label": _("Gateway Fees (INR)"),    "fieldname": "gateway_fees",          "fieldtype": "Currency", "width": 130},
		{"label": _("Gateway Tax (INR)"),     "fieldname": "gateway_tax",           "fieldtype": "Currency", "width": 120},
		{"label": _("Net Settled (INR)"),     "fieldname": "net_settled",           "fieldtype": "Currency", "width": 130},
		# ── Payment method details ────────────────────────────────────────────
		{"label": _("Payment Method"),        "fieldname": "payment_method",        "fieldtype": "Data",     "width": 120},
		{"label": _("Bank / Wallet / VPA"),   "fieldname": "bank_wallet_vpa",       "fieldtype": "Data",     "width": 180},
		# ── Candidate extras ─────────────────────────────────────────────────
		{"label": _("Email"),                 "fieldname": "email",                 "fieldtype": "Data",     "width": 190},
		{"label": _("Contact Number"),        "fieldname": "contact_number",        "fieldtype": "Data",     "width": 130},
		{"label": _("State"),                 "fieldname": "state",                 "fieldtype": "Data",     "width": 120},
	]


def get_data(filters):
	# ── Build SQL conditions ─────────────────────────────────────────────────
	status_filter = filters.get("payment_status") or "Captured"
	conditions = "WHERE fpl.payment_status = %(payment_status)s"
	values = {"payment_status": status_filter}

	if filters.get("from_date"):
		conditions += " AND DATE(fpl.transaction_date) >= %(from_date)s"
		values["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		conditions += " AND DATE(fpl.transaction_date) <= %(to_date)s"
		values["to_date"] = filters["to_date"]

	rows = frappe.db.sql(f"""
		SELECT
			fpl.name                     AS log_name,
			fpl.transaction_date         AS transaction_date,
			fpl.transaction_id           AS transaction_id,
			fpl.paid_amount              AS paid_amount,
			fpl.full_name                AS full_name,
			fpl.email                    AS email,
			fpl.gateway_response         AS gateway_response,
			fpl.reference_no             AS reference_no,
			fpl.account_number_or_upi_id AS account_number_or_upi_id,
			-- Settlement fields (populated by settlement.processed webhook)
			fpl.settlement_id            AS settlement_id,
			fpl.settlement_utr           AS settlement_utr,
			fpl.settlement_date          AS settlement_date,
			fpl.settlement_status        AS settlement_status,
			fpl.gateway_fees             AS gateway_fees,
			fpl.gateway_tax              AS gateway_tax,
			fpl.net_settled              AS net_settled,
			fle.candidate_contact_number AS contact_number,
			fle.candidates_state         AS state
		FROM `tabFLE Payment Log` fpl
		LEFT JOIN `tabFoundations for a Legal Education` fle
			ON fle.name = fpl.reference_no
		{conditions}
		ORDER BY fpl.transaction_date ASC, fpl.name ASC
	""", values, as_dict=1)

	# ── Filter-driven static values ─────────────────────────────────────────
	prefix       = filters.get("journal_number_prefix") or ""
	suffix       = filters.get("journal_number_suffix") or ""
	journal_type = filters.get("journal_type") or ""
	currency     = filters.get("currency") or "INR"
	account_code = filters.get("account_code") or ""
	account      = filters.get("account") or ""
	department   = filters.get("department") or ""
	course       = filters.get("course") or "Foundations for a Legal Education"

	data = []
	for row in rows:
		payment_id = row.transaction_id or ""
		paid       = row.paid_amount or 0

		# ── Journal Date ─────────────────────────────────────────────────────
		# Use locally stored settlement_date (set by webhook) when available.
		# Fall back to transaction_date when payment is not yet settled.
		if row.settlement_date:
			journal_date = row.settlement_date
		elif row.transaction_date:
			journal_date = (
				row.transaction_date.date()
				if hasattr(row.transaction_date, "date")
				else row.transaction_date
			)
		else:
			journal_date = None

		# ── Settlement financials ─────────────────────────────────────────────
		settlement_id     = row.settlement_id or ""
		utr               = row.settlement_utr or ""
		settlement_status = row.settlement_status or ""
		gateway_fees      = row.gateway_fees or 0.0
		gateway_tax       = row.gateway_tax or 0.0
		net_settled       = row.net_settled or 0.0

		# ── Debit / Credit ────────────────────────────────────────────────────
		# Debit  = gross amount the student paid (full fee)
		# Credit = net amount settled to institution's bank (after gateway fees)
		# Difference = gateway_fees + gateway_tax (visible in the report columns)
		debit  = paid
		credit = net_settled if net_settled else paid

		# ── Payment method (from stored gateway_response JSON) ───────────────
		method, bank_wallet = _parse_payment_method(row.gateway_response, row.account_number_or_upi_id)

		# ── Notes ────────────────────────────────────────────────────────────
		notes = _build_notes(row.gateway_response, row.account_number_or_upi_id)

		data.append({
			# ── Journal ───────────────────────────────────────────────────────
			"journal_date":          journal_date,
			"reference_number":      payment_id,
			"journal_number_prefix": prefix,
			"journal_number_suffix": suffix,
			"notes":                 notes,
			"journal_type":          journal_type,
			"currency":              currency,
			"account_code":          account_code,
			"account":               account,
			"description":           f"FLE Payment - {row.full_name}" if row.full_name else "FLE Payment",
			"contact_name":          row.full_name,
			"debit":                 debit,
			"credit":                credit,
			"department":            department,
			"course":                course,
			"student_id":            row.reference_no,
			# ── Settlement ────────────────────────────────────────────────────
			"settlement_id":         settlement_id,
			"utr":                   utr,
			"settlement_status":     settlement_status,
			"gateway_fees":          gateway_fees,
			"gateway_tax":           gateway_tax,
			"net_settled":           net_settled,
			# ── Payment method ────────────────────────────────────────────────
			"payment_method":        method,
			"bank_wallet_vpa":       bank_wallet,
			# ── Candidate ─────────────────────────────────────────────────────
			"email":                 row.email or "",
			"contact_number":        row.contact_number or "",
			"state":                 row.state or "",
		})

	return data


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_payment_method(gateway_response, account_number_or_upi_id):
	"""
	Extract payment method and bank/wallet/VPA from stored gateway_response JSON.
	Returns (method_str, bank_wallet_vpa_str).
	"""
	import json

	method     = ""
	bank_wallet = account_number_or_upi_id or ""

	if not gateway_response:
		return method, bank_wallet

	try:
		resp   = json.loads(gateway_response)
		entity = resp.get("payload", {}).get("payment", {}).get("entity", resp)

		method = entity.get("method") or ""
		parts  = []
		for key in ("bank", "wallet", "vpa"):
			val = entity.get(key) or ""
			if val:
				parts.append(str(val))
		if parts:
			bank_wallet = " | ".join(parts)
	except Exception:
		pass

	return method.title() if method else "", bank_wallet


def _build_notes(gateway_response, account_number_or_upi_id):
	"""
	Build Notes string from stored gateway_response JSON.
	"""
	import json

	parts = []

	if gateway_response:
		try:
			resp   = json.loads(gateway_response)
			entity = resp.get("payload", {}).get("payment", {}).get("entity", resp)
			for key in ("method", "bank", "wallet", "vpa", "description"):
				val = entity.get(key) or ""
				if val:
					parts.append(str(val))
		except Exception:
			parts.append(str(gateway_response)[:80])

	if not parts and account_number_or_upi_id:
		parts.append(account_number_or_upi_id)

	return " | ".join(parts)
