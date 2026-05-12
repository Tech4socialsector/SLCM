"""
Run with:
  bench --site <sitename> execute slcm.fix_workspace.run
"""
import frappe
import json


def run():
	print("\n===== EXAMINATION MANAGEMENT WORKSPACE FIX =====\n")

	# ── Step 1: Diagnose ──────────────────────────────
	existing = frappe.db.sql(
		"SELECT name, label, for_user, public FROM `tabWorkspace` WHERE name LIKE %s OR label LIKE %s",
		("%xamination%", "%xamination%"),
		as_dict=True,
	)
	print(f"Found {len(existing)} existing record(s):")
	for e in existing:
		print(f"  name={e.name!r}, label={e.label!r}, for_user={e.for_user!r}")

	# ── Step 2: Delete all matching records via raw SQL ──
	for e in existing:
		frappe.db.sql("DELETE FROM `tabWorkspace Shortcut` WHERE parent=%s", e.name)
		frappe.db.sql("DELETE FROM `tabWorkspace Link` WHERE parent=%s", e.name)
		frappe.db.sql("DELETE FROM `tabWorkspace` WHERE name=%s", e.name)
		print(f"Deleted: {e.name!r}")

	frappe.db.commit()
	print("All old records removed.\n")

	# ── Step 3: Insert workspace row ─────────────────
	content = json.dumps([
		{"id": "em-h1", "type": "header",   "data": {"text": "<span class=\"h4\"><b>Examination Planner</b></span>", "col": 12}},
		{"id": "em-s1", "type": "shortcut", "data": {"shortcut_name": "Examination Planner",   "col": 3}},
		{"id": "em-sp", "type": "spacer",   "data": {"col": 12}},
		{"id": "em-h2", "type": "header",   "data": {"text": "<span class=\"h4\"><b>Masters</b></span>", "col": 12}},
		{"id": "em-s2", "type": "shortcut", "data": {"shortcut_name": "Exam Plan",              "col": 3}},
		{"id": "em-s3", "type": "shortcut", "data": {"shortcut_name": "Evaluation Schema",      "col": 3}},
		{"id": "em-s4", "type": "shortcut", "data": {"shortcut_name": "Exam Component",         "col": 3}},
		{"id": "em-s5", "type": "shortcut", "data": {"shortcut_name": "Exam Assessment Type",   "col": 3}},
	])

	now = frappe.utils.now()
	frappe.db.sql(
		"""INSERT INTO `tabWorkspace`
			(name, creation, modified, modified_by, owner, docstatus,
			 label, title, module, app, `public`, icon, indicator_color,
			 for_user, is_hidden, sequence_id, content)
		VALUES
			(%s, %s, %s, %s, %s, %s,
			 %s, %s, %s, %s, %s, %s, %s,
			 %s, %s, %s, %s)""",
		(
			"Examination Management", now, now, "Administrator", "Administrator", 0,
			"Examination Management", "Examination Management", "SLCM", "slcm", 1, "file-text", "red",
			"", 0, 5.0, content,
		),
	)
	print("Workspace row inserted.")

	# ── Step 4: Insert shortcuts ──────────────────────
	shortcuts = [
		("Page",    "examination-planner",  "Examination Planner",   "Red",   "",     ""),
		("DocType", "Exam Plan",             "Exam Plan",             "Blue",  "List", "[]"),
		("DocType", "Evaluation Schema",     "Evaluation Schema",     "Green", "List", "[]"),
		("DocType", "Exam Component",        "Exam Component",        "Grey",  "List", "[]"),
		("DocType", "Exam Assessment Type",  "Exam Assessment Type",  "Grey",  "List", "[]"),
	]
	for i, (stype, link_to, label, color, doc_view, stats_filter) in enumerate(shortcuts, start=1):
		row_name = frappe.generate_hash(length=10)
		frappe.db.sql(
			"""INSERT INTO `tabWorkspace Shortcut`
				(name, creation, modified, modified_by, owner, docstatus,
				 parent, parenttype, parentfield, idx,
				 type, link_to, label, color, doc_view, url, stats_filter)
			VALUES
				(%s, %s, %s, %s, %s, %s,
				 %s, %s, %s, %s,
				 %s, %s, %s, %s, %s, %s, %s)""",
			(
				row_name, now, now, "Administrator", "Administrator", 0,
				"Examination Management", "Workspace", "shortcuts", i,
				stype, link_to, label, color, doc_view, "", stats_filter,
			),
		)
		print(f"  Shortcut {i}: [{stype}] {label}")

	# ── Step 5: Insert sidebar links ─────────────────
	links = [
		("Exam Plan",            "Exam Plan",            "DocType", 1),
		("Evaluation Schema",    "Evaluation Schema",    "DocType", 1),
		("Exam Component",       "Exam Component",       "DocType", 0),
		("Exam Assessment Type", "Exam Assessment Type", "DocType", 0),
	]
	for i, (label, link_to, link_type, onboard) in enumerate(links, start=1):
		row_name = frappe.generate_hash(length=10)
		frappe.db.sql(
			"""INSERT INTO `tabWorkspace Link`
				(name, creation, modified, modified_by, owner, docstatus,
				 parent, parenttype, parentfield, idx,
				 label, link_to, link_type, onboard, type, hidden)
			VALUES
				(%s, %s, %s, %s, %s, %s,
				 %s, %s, %s, %s,
				 %s, %s, %s, %s, %s, %s)""",
			(
				row_name, now, now, "Administrator", "Administrator", 0,
				"Examination Management", "Workspace", "links", i,
				label, link_to, link_type, onboard, "Link", 0,
			),
		)
		print(f"  Link {i}: {label}")

	frappe.db.commit()

	# ── Step 6: Verify ────────────────────────────────
	sc_count = frappe.db.sql(
		"SELECT COUNT(*) FROM `tabWorkspace Shortcut` WHERE parent='Examination Management'",
	)[0][0]
	lk_count = frappe.db.sql(
		"SELECT COUNT(*) FROM `tabWorkspace Link` WHERE parent='Examination Management'",
	)[0][0]
	print(f"\nVerification:")
	print(f"  Shortcuts in DB : {sc_count}  (expected 5)")
	print(f"  Links in DB     : {lk_count}  (expected 4)")
	print("\n===== DONE — hard refresh the browser =====\n")
