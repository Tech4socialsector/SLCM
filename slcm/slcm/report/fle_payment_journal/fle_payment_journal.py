"""
FLE Payment Journal Report
- Journal Date  : Razorpay settlement date (fetched via API)
- Reference No  : transaction_id (Razorpay payment ID)
- Extra fields  : UTR, Settlement ID, fees, tax, net amount, payment method, bank/UPI
"""

import json
import datetime

import frappe
from frappe import _

try:
	import razorpay as _razorpay_lib
except ImportError:
	_razorpay_lib = None


# ---------------------------------------------------------------------------
# Razorpay helpers
# ---------------------------------------------------------------------------

def _get_rzp_client():
	"""Return an authenticated Razorpay client or None if not configured."""
	if not _razorpay_lib:
		return None
	try:
		settings = frappe.get_single("Razorpay Settings")
		api_key = settings.api_key
		api_secret = settings.get_password("api_secret")
		if api_key and api_secret:
			return _razorpay_lib.Client(auth=(api_key, api_secret))
	except Exception:
		pass
	return None


def _fetch_payment(client, payment_id: str) -> dict:
	"""Fetch Razorpay payment entity. Returns {} on failure."""
	if not client or not payment_id:
		return {}
	try:
		return client.payment.fetch(payment_id) or {}
	except Exception:
		return {}


def _fetch_settlement(client, payment_id: str) -> dict:
	"""
	Fetch settlement linked to a Razorpay payment.
	Endpoint: GET /v1/payments/{payment_id}/settlements
	Returns the settlement dict or {} on failure.
	"""
	if not client or not payment_id:
		return {}
	try:
		# The razorpay SDK does not expose this endpoint directly in all versions;
		# fall back to the underlying requests session the client already has.
		import requests
		settings = frappe.get_single("Razorpay Settings")
		api_key = settings.api_key
		api_secret = settings.get_password("api_secret")
		url = f"https://api.razorpay.com/v1/payments/{payment_id}/settlements"
		resp = requests.get(url, auth=(api_key, api_secret), timeout=15)
		if resp.status_code == 200:
			return resp.json() or {}
	except Exception:
		pass
	return {}


def _settlement_date(settlement: dict):
	"""Convert Razorpay settlement created_at (Unix ts) to a Python date, or None."""
	ts = settlement.get("created_at")
	if ts:
		try:
			return datetime.datetime.utcfromtimestamp(int(ts)).date()
		except Exception:
			pass
	return None


def _paise_to_rupees(paise) -> float:
	"""Convert integer paise to rupees."""
	try:
		return round(int(paise) / 100, 2)
	except Exception:
		return 0.0


# ---------------------------------------------------------------------------
# Report entry points
# ---------------------------------------------------------------------------

def execute(filters: dict | None = None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns() -> list[dict]:
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
		# ── Settlement fields (from Razorpay API) ────────────────────────────
		{"label": _("Settlement ID"),         "fieldname": "settlement_id",         "fieldtype": "Data",     "width": 160},
		{"label": _("UTR Number"),            "fieldname": "utr",                   "fieldtype": "Data",     "width": 160},
		{"label": _("Settlement Status"),     "fieldname": "settlement_status",     "fieldtype": "Data",     "width": 120},
		{"label": _("Gateway Fees (INR)"),    "fieldname": "gateway_fees",          "fieldtype": "Currency", "width": 130},
		{"label": _("Gateway Tax (INR)"),     "fieldname": "gateway_tax",           "fieldtype": "Currency", "width": 120},
		{"label": _("Net Settled (INR)"),     "fieldname": "net_settled",           "fieldtype": "Currency", "width": 130},
		# ── Payment method details (from Razorpay payment entity) ────────────
		{"label": _("Payment Method"),        "fieldname": "payment_method",        "fieldtype": "Data",     "width": 120},
		{"label": _("Bank / Wallet / VPA"),   "fieldname": "bank_wallet_vpa",       "fieldtype": "Data",     "width": 180},
		{"label": _("Card Network"),          "fieldname": "card_network",          "fieldtype": "Data",     "width": 110},
		# ── Candidate extras ─────────────────────────────────────────────────
		{"label": _("Email"),                 "fieldname": "email",                 "fieldtype": "Data",     "width": 190},
		{"label": _("Contact Number"),        "fieldname": "contact_number",        "fieldtype": "Data",     "width": 130},
		{"label": _("State"),                 "fieldname": "state",                 "fieldtype": "Data",     "width": 120},
	]


def get_data(filters: dict) -> list[dict]:
	# ── Build SQL conditions ────────────────────────────────────────────────
	status_filter = filters.get("payment_status") or "Captured"
	conditions = "WHERE fpl.payment_status = %(payment_status)s"
	values: dict = {"payment_status": status_filter}

	if filters.get("from_date"):
		conditions += " AND DATE(fpl.transaction_date) >= %(from_date)s"
		values["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		conditions += " AND DATE(fpl.transaction_date) <= %(to_date)s"
		values["to_date"] = filters["to_date"]

	rows = frappe.db.sql(f"""
		SELECT
			fpl.name                    AS log_name,
			fpl.transaction_date        AS transaction_date,
			fpl.transaction_id          AS transaction_id,
			fpl.paid_amount             AS paid_amount,
			fpl.full_name               AS full_name,
			fpl.email                   AS email,
			fpl.gateway_response        AS gateway_response,
			fpl.reference_no            AS reference_no,
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

	# ── Razorpay client (one per report run) ────────────────────────────────
	rzp = _get_rzp_client()

	data = []
	for row in rows:
		payment_id = row.transaction_id or ""

		# ── Razorpay payment entity ─────────────────────────────────────────
		rzp_payment   = _fetch_payment(rzp, payment_id)
		rzp_settlement = _fetch_settlement(rzp, payment_id)

		# Journal Date: prefer settlement date, fall back to transaction_date
		journal_date = _settlement_date(rzp_settlement)
		if not journal_date and row.transaction_date:
			journal_date = (
				row.transaction_date.date()
				if hasattr(row.transaction_date, "date")
				else row.transaction_date
			)

		# Notes: gateway method + bank/UPI info
		notes = _build_notes(row.gateway_response, rzp_payment)

		# Payment method breakdown
		method        = rzp_payment.get("method") or ""
		bank_wallet   = _bank_wallet_vpa(rzp_payment)
		card_network  = ""
		if rzp_payment.get("card"):
			card_network = rzp_payment["card"].get("network") or ""

		# Settlement financials
		settlement_id     = rzp_settlement.get("id") or ""
		utr               = rzp_settlement.get("utr") or ""
		settlement_status = rzp_settlement.get("status") or ""
		fees_paise        = rzp_settlement.get("fees") or rzp_payment.get("fee") or 0
		tax_paise         = rzp_settlement.get("tax") or rzp_payment.get("tax") or 0
		net_settled_paise = rzp_settlement.get("amount") or 0

		gateway_fees = _paise_to_rupees(fees_paise)
		gateway_tax  = _paise_to_rupees(tax_paise)
		net_settled  = _paise_to_rupees(net_settled_paise) if net_settled_paise else (
			(row.paid_amount or 0) - gateway_fees - gateway_tax
		)

		paid = row.paid_amount or 0

		data.append({
			# ── Journal ──────────────────────────────────────────────────
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
			"debit":                 paid,
			"credit":                paid,
			"department":            department,
			"course":                course,
			"student_id":            row.reference_no,
			# ── Settlement ───────────────────────────────────────────────
			"settlement_id":         settlement_id,
			"utr":                   utr,
			"settlement_status":     settlement_status,
			"gateway_fees":          gateway_fees,
			"gateway_tax":           gateway_tax,
			"net_settled":           net_settled,
			# ── Payment method ───────────────────────────────────────────
			"payment_method":        method.title() if method else "",
			"bank_wallet_vpa":       bank_wallet,
			"card_network":          card_network,
			# ── Candidate ────────────────────────────────────────────────
			"email":                 row.email or "",
			"contact_number":        row.contact_number or "",
			"state":                 row.state or "",
		})

	return data


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_notes(gateway_response: str | None, rzp_payment: dict) -> str:
	"""
	Build Notes string: prefer live Razorpay payment entity data,
	fall back to parsing stored gateway_response JSON.
	"""
	parts = []

	method = rzp_payment.get("method") or ""
	if method:
		parts.append(method.title())

	bank = rzp_payment.get("bank") or ""
	if bank:
		parts.append(bank)

	wallet = rzp_payment.get("wallet") or ""
	if wallet:
		parts.append(wallet)

	vpa = rzp_payment.get("vpa") or ""
	if vpa:
		parts.append(vpa)

	if parts:
		return " | ".join(parts)

	# Fall back to stored JSON
	if not gateway_response:
		return ""
	try:
		resp = json.loads(gateway_response)
		entity = resp.get("payload", {}).get("payment", {}).get("entity", resp)
		for key in ("method", "bank", "wallet", "vpa", "description"):
			val = entity.get(key) or ""
			if val:
				parts.append(str(val))
		return " | ".join(parts) if parts else ""
	except Exception:
		return str(gateway_response)[:80]


def _bank_wallet_vpa(rzp_payment: dict) -> str:
	"""Return a single string combining bank / wallet / VPA if present."""
	parts = []
	for key in ("bank", "wallet", "vpa"):
		val = rzp_payment.get(key) or ""
		if val:
			parts.append(val)
	return " | ".join(parts)
