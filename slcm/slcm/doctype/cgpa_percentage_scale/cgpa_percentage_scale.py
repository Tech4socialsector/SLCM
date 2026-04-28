import frappe
from frappe.model.document import Document


class CGPAPercentageScale(Document):
    pass


# ── Shared lookup used by term_result and student_result_publish ──────────────

def lookup_percentage_for_cgpa(cgpa):
    """
    Return the Final Percentage for a given CGPA from the stored scale table.
    Uses the largest CGPA entry that is <= the given value (floor lookup).
    Returns None if the table is empty or CGPA is below the lowest entry.
    """
    if cgpa is None:
        return None
    try:
        cgpa_val = round(float(cgpa), 2)
        rows = frappe.db.sql(
            """
            SELECT cgpa, percentage
            FROM `tabCGPA Percentage Scale Detail`
            WHERE parenttype = 'CGPA Percentage Scale'
              AND parentfield = 'cgpa_mappings'
            ORDER BY cgpa ASC
            """,
            as_dict=True,
        )
        if not rows:
            return None
        best = None
        for row in rows:
            if round(float(row.cgpa or 0), 2) <= cgpa_val:
                best = row
            else:
                break
        return round(float(best.percentage), 2) if best else None
    except Exception:
        return None


@frappe.whitelist()
def get_scale():
    """Return all CGPA → Percentage entries ordered by CGPA."""
    rows = frappe.db.sql(
        """
        SELECT cgpa, percentage
        FROM `tabCGPA Percentage Scale Detail`
        WHERE parenttype = 'CGPA Percentage Scale'
          AND parentfield = 'cgpa_mappings'
        ORDER BY cgpa ASC
        """,
        as_dict=True,
    )
    return rows


@frappe.whitelist()
def save_scale(data):
    """Replace all scale entries with the provided list [{cgpa, percentage}, ...]."""
    import json
    if isinstance(data, str):
        data = json.loads(data)

    doc = frappe.get_single("CGPA Percentage Scale")
    doc.set("cgpa_mappings", [])
    for row in data:
        doc.append("cgpa_mappings", {
            "cgpa": round(float(row["cgpa"]), 2),
            "percentage": round(float(row["percentage"]), 2),
        })
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"saved": len(data)}


@frappe.whitelist()
def populate_scale():
    """
    Pre-fill the scale using the standard linear formula:
        percentage = 50 + (CGPA - 3) * 12.5
    Covers CGPA 0.00 → 7.00 in 0.01 steps.
    """
    doc = frappe.get_single("CGPA Percentage Scale")
    doc.set("cgpa_mappings", [])

    cgpa = 0.00
    while cgpa <= 7.001:
        cgpa_r = round(cgpa, 2)
        if cgpa_r < 3.0:
            pct = 0.0
        else:
            pct = round(50 + (cgpa_r - 3) * 12.5, 2)
        doc.append("cgpa_mappings", {"cgpa": cgpa_r, "percentage": pct})
        cgpa = round(cgpa + 0.01, 2)

    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"populated": len(doc.cgpa_mappings)}
