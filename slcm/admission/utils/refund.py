import frappe
from frappe.utils import flt, date_diff, nowdate


def get_applicant_refund_policies(applicant):
	"""
	Fetches refund policies mapped to the applicant's Fee Structure.
	Returns a dict with:
	  - policies: list of active policy dicts sorted by days_from_payment asc
	  - days_since_payment: int
	  - fee_structure: str (name of the matched Fee Structure)
	"""
	# 1. Resolve basic details
	details = frappe.db.get_value(
		"Applicant", applicant,
		["program", "campus", "admission_cycle", "academic_year"],
		as_dict=1
	)
	if not details:
		frappe.log_error(f"Refund Utility: No details found for applicant {applicant}", "Refund Error")
		return {"policies": [], "days_since_payment": 0, "fee_structure": None}

	program = details.program
	campus = details.campus
	cycle = details.admission_cycle
	year = details.academic_year

	# Priority 0: Directly from Offer Letter if assigned
	fee_structure = frappe.db.get_value(
		"Offer Letter",
		{"applicant": applicant, "status": ["not in", ["Rejected", "Withdrawn"]]},
		"fee_structure",
		order_by="creation desc"
	)

	# Priority 1: Via Offer Configuration (Cycle + Campus)
	if not fee_structure:
		config_names = frappe.get_all(
			"Offer Configuration",
			filters={"admission_cycle": cycle, "campus": campus, "is_active": 1},
			pluck="name"
		)

		matched_fs_names = []
		for cn in config_names:
			config_doc = frappe.get_doc("Offer Configuration", cn)
			for row in config_doc.fee_structure:
				fs_name = row.fee_structure
				fs_meta = frappe.db.get_value("Fee Structure", fs_name, ["program", "is_refund_available"], as_dict=1)
				if fs_meta and fs_meta.program == program:
					matched_fs_names.append(fs_name)
					if fs_meta.is_refund_available:
						# Check for any active policy rows
						if frappe.db.exists("Fee Structure Refund Policy", {"parent": fs_name, "is_active": 1}):
							fee_structure = fs_name
							break
			if fee_structure:
				break
	
	# Priority 2: Direct lookup by Program + Academic Year (Fallback)
	if not fee_structure:
		fee_structure = frappe.db.get_value("Fee Structure", 
			{"academic_year": year, "program": program, "status": "Active", "is_refund_available": 1}, 
			"name"
		)
			
	# Priority 3: Broadest Fallback - Any Active FS for this Program with refunds enabled
	if not fee_structure:
		fee_structure = frappe.db.get_value("Fee Structure", 
			{"program": program, "status": "Active", "is_refund_available": 1}, 
			"name", order_by="creation desc"
		)
	
	# Ultimate Fallback: Just take the first one we matched in Priority 1 even if no policies found yet
	if not fee_structure and matched_fs_names:
		fee_structure = matched_fs_names[0]

	if not fee_structure:
		frappe.log_error(f"Refund Utility: No Fee Structure found for {applicant} (Prog: {program}, Campus: {campus}, Cycle: {cycle})", "Refund Error")
		return {"policies": [], "days_since_payment": 0, "fee_structure": None, "is_confirmation_fee_refundable": False, "confirmation_fee_refund_percentage": 0.0}

	# 3. Get policies from Fee Structure
	fs_doc = frappe.get_doc("Fee Structure", fee_structure)

	if not fs_doc.is_refund_available:
		frappe.log_error(f"Refund Utility: Refund NOT enabled on FS {fee_structure}", "Refund Info")
		return {"policies": [], "days_since_payment": 0, "fee_structure": fee_structure, "is_confirmation_fee_refundable": False, "confirmation_fee_refund_percentage": 0.0}

	# Collect policies
	policies = []
	for row in fs_doc.get("refund_policies", []):
		if row.is_active:
			# Ensure we have values (they might be in the linked Refund Policy)
			days = row.days_from_payment
			perc = row.refund_percentage
			
			if (days is None or perc is None) and row.refund_policy:
				linked = frappe.db.get_value("Refund Policy", row.refund_policy, ["days_from_payment", "refund_percentage"], as_dict=1)
				if linked:
					days = days if days is not None else linked.days_from_payment
					perc = perc if perc is not None else linked.refund_percentage

			policies.append({
				"policy_name": row.refund_policy,
				"days_from_payment": days,
				"refund_percentage": perc
			})
	
	if not policies:
		frappe.log_error(f"Refund Utility: No active policies in FS {fee_structure}", "Refund Info")

	policies = sorted(policies, key=lambda p: (p.get("days_from_payment") or 0))

	# 4. Calculate days since last payment
	days_since_payment = 0
	last_payment_date = get_last_payment_date(applicant)
	if last_payment_date:
		days_since_payment = date_diff(nowdate(), last_payment_date)

	is_conf_applicable = bool(fs_doc.get("is_confirmation_fee_applicable"))
	is_conf_refundable = bool(fs_doc.get("is_confirmation_fee_refundable"))
	is_conf_fee_refundable = bool(is_conf_applicable and is_conf_refundable)
	conf_fee_pct = flt(fs_doc.get("confirmation_fee_refund_percentage") or 0.0) if is_conf_fee_refundable else 0.0

	return {
		"policies": policies,
		"days_since_payment": days_since_payment,
		"fee_structure": fee_structure,
		"is_confirmation_fee_refundable": is_conf_fee_refundable,
		"confirmation_fee_refund_percentage": conf_fee_pct
	}





def get_last_payment_date(applicant):
	"""
	Returns the date of the most recent payment for the applicant.
	Uses Applicant Payment Receipt (which is tied to admission fee payments).
	"""
	last_receipt = frappe.db.get_value(
		"Applicant Payment Receipt",
		{"applicant": applicant, "docstatus": ["<", 2]},
		"payment_date",
		order_by="payment_date desc"
	)
	return last_receipt
