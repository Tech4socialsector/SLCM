import frappe
import json


def get_context(context):
	"""
	Inject the FLE doc name into the template server-side so the success page
	always works even when the ?name= URL param is missing.

	Priority order:
	1. ?name= URL param
	2. Latest completed Integration Request for this Razorpay payment
	"""
	name = frappe.request.args.get('name')

	if not name:
		# Find the most recently completed Razorpay Integration Request
		try:
			integration_requests = frappe.get_all(
				"Integration Request",
				filters={
					"reference_doctype": "Foundations for a Legal Education",
				},
				fields=["data", "reference_docname"],
				order_by="modified desc",
				limit=5
			)

			for ir in integration_requests:
				# Prefer one that has a razorpay_payment_id (meaning payment was completed)
				try:
					data = json.loads(ir.get("data") or "{}")
					if data.get("razorpay_payment_id") and ir.get("reference_docname"):
						name = ir["reference_docname"]
						break
				except Exception:
					continue

			# Fallback: just use the reference_docname from the latest IR
			if not name and integration_requests:
				name = integration_requests[0].get("reference_docname")

		except Exception:
			pass

	# Inject into template context so Jinja can embed it
	context.fle_doc_name = name or ""
