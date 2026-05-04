import frappe


def execute():
    """Migrate Re Exam Registration: split the old combined `status` field into
    separate `status` (registration state) and `payment_status` (payment state).

    Old status values → new mapping:
      Registered       → status=Registered,  payment_status=Pending
      Payment Initiated→ status=Registered,  payment_status=Initiated
      Authorized       → status=Registered,  payment_status=Authorized
      Paid             → status=Registered,  payment_status=Paid
      Payment Failed   → status=Registered,  payment_status=Failed
      Refunded         → status=Registered,  payment_status=Refunded
      Cancelled        → status=Cancelled,   payment_status=  (blank)
    """
    payment_status_map = {
        "Registered":        ("Registered", "Pending"),
        "Payment Initiated": ("Registered", "Initiated"),
        "Authorized":        ("Registered", "Authorized"),
        "Paid":              ("Registered", "Paid"),
        "Payment Failed":    ("Registered", "Failed"),
        "Refunded":          ("Registered", "Refunded"),
        "Cancelled":         ("Cancelled",  ""),
    }

    rows = frappe.db.sql(
        "SELECT name, status FROM `tabRe Exam Registration`",
        as_dict=True,
    )

    for row in rows:
        new_status, new_payment_status = payment_status_map.get(
            row.status, ("Registered", "Pending")
        )
        frappe.db.set_value(
            "Re Exam Registration",
            row.name,
            {"status": new_status, "payment_status": new_payment_status},
            update_modified=False,
        )

    frappe.db.commit()
