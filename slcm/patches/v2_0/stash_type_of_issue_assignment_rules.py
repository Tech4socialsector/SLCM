"""
Type of Issue used to be a free-text Select field on HD Ticket, with a
matching "HD Ticket Type Of Issue Assignment Rule" child table on HD Ticket
Type for team routing (exact string match against the Select value). It is
being replaced with a proper "HD Ticket Type Of Issue" Link master, so
System Managers can add new issue types from the desk UI (Frappe Cloud has
no bench access) instead of via a fixture-exported JS options map.

This runs pre_model_sync, while `tabHD Ticket Type Of Issue Assignment
Rule` still exists, and stashes its rows (which carry team overrides) into
a temp table. The child table itself, and its doctype, are being removed
by this same release - see migrate_type_of_issue_to_link_doctype
(post_model_sync) for where the stash is consumed.
"""

import frappe


def execute():
	if "tabHD Ticket Type Of Issue Assignment Rule" not in frappe.db.get_tables(cached=False):
		return

	frappe.db.sql_ddl("DROP TABLE IF EXISTS `__type_of_issue_assignment_rule_stash`")
	frappe.db.sql(
		"""
		CREATE TABLE `__type_of_issue_assignment_rule_stash` AS
		SELECT parent AS ticket_type, type_of_issue, team
		FROM `tabHD Ticket Type Of Issue Assignment Rule`
		WHERE parenttype = 'HD Ticket Type'
		"""
	)
	frappe.db.commit()
