import frappe


def execute():
	"""Make result fields nullable so that NULL = not yet generated (distinct from 0.0 = actual zero)."""
	for field in ("term_gpa", "term_percentage", "cumulative_gpa", "cumulative_percentage"):
		frappe.db.sql(
			f"ALTER TABLE `tabStudent Result Publish` MODIFY COLUMN `{field}` decimal(21,9) NULL DEFAULT NULL"
		)
