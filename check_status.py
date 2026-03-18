import frappe

def check_cancellation_status(name):
	# Site name should be inferred from the environment or specified
	# Assuming frappe is initialized
	try:
		doc = frappe.get_doc("Admission Cancellation", name)
		print(f"Admission Cancellation: {doc.name}")
		print(f"Status: {doc.status}")
		print(f"Applicant: {doc.applicant}")
		print(f"Payment Request: {doc.payment_request}")

		refunds = frappe.get_all("Refund Request", 
			filters={"applicant": doc.applicant},
			fields=["name", "status"]
		)
		if refunds:
			for r in refunds:
				print(f"Refund Request: {r.name}, Status: {r.status}")
		else:
			print("No Refund Request found for this applicant.")
	except Exception as e:
		print(f"Error: {e}")

if __name__ == "__main__":
	# Need to initialize frappe
	# This usually needs to be run via 'bench execute' or similar
	# But I can try to find a site and init
	pass
