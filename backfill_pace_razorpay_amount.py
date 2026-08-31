import frappe

def execute():
    assignments = frappe.get_all(
        "PACE Applicant Fee Assignment",
        filters={"status": "Paid", "razorpay_paid_amount": ["in", [0, None]]},
        fields=["name", "transaction_id"]
    )
    
    count = 0
    for assignment in assignments:
        pr = frappe.get_all(
            "Payment Request",
            filters={
                "reference_doctype": "PACE Applicant Fee Assignment",
                "reference_name": assignment.name,
                "status": "Paid",
                "docstatus": 1
            },
            fields=["name", "amount", "transaction_id", "gateway_response"]
        )
        
        if pr:
            pr_data = pr[0]
            if pr_data.transaction_id == assignment.transaction_id or not assignment.transaction_id:
                amount_to_set = None
                if pr_data.get("gateway_response"):
                    import json
                    try:
                        resp_dict = json.loads(pr_data.gateway_response)
                        if "amount" in resp_dict:
                            amount_to_set = float(resp_dict["amount"]) / 100.0
                    except Exception:
                        pass
                
                if not amount_to_set:
                    amount_to_set = pr_data.get("amount")

                try:
                    frappe.db.set_value(
                        "PACE Applicant Fee Assignment", 
                        assignment.name, 
                        "razorpay_paid_amount", 
                        amount_to_set, 
                        update_modified=False
                    )
                    count += 1
                except Exception:
                    frappe.log_error(frappe.get_traceback(), f"Backfill failed for {assignment.name}")
                    
    frappe.db.commit()
    print(f"Successfully backfilled razorpay_paid_amount for {count} assignments.")
