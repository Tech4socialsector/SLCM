import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, format_date
from frappe.utils.data import get_link_to_form


class PACEAdmission(Document):
	def autoname(self):
		self.name = f"PACE-ADM-{self.academic_year}"

	def validate(self):
		self._validate_date_range()
		self._validate_single_active()
		self._validate_programmes()
		self._validate_readonly_if_closed()

	def _validate_readonly_if_closed(self):
		"""Prevent editing if the admission is already closed."""
		if not self.is_new():
			old_status = frappe.db.get_value("PACE Admission", self.name, "status")
			if old_status == "Closed":
				# If it's already closed, only allow changing the status field itself
				if self.is_dirty() and not self.is_dirty("status"):
					frappe.throw(
						_("This Admission record is <b>Closed</b> and cannot be modified. To make changes, first set the status back to 'Active' or 'Draft'."),
						title=_("Record Locked")
					)

	def on_submit(self):
		"""Handle any logic needed on submission."""
		pass

	def on_cancel(self):
		"""Set status to Closed when document is cancelled."""
		self.status = "Closed"
		self.db_set("status", "Closed")

	def _validate_date_range(self):
		if not self.admission_open_date or not self.admission_close_date:
			return
		
		if getdate(self.admission_open_date) > getdate(self.admission_close_date):
			frappe.throw(
				_("Admission Open Date cannot be after Admission Close Date."),
				title=_("Invalid Dates"),
			)

	def _validate_single_active(self):
		"""Only one PACE Admission can be Active at a time."""
		if self.status == "Active":
			# 1. Check if Academic Year is active
			ay_status = frappe.db.get_value("Academic Year", self.academic_year, "status")
			if ay_status != "Active":
				frappe.throw(
					_("The Academic Year <b>{0}</b> is not currently active. You can only activate admissions for the current active academic year.")
					.format(self.academic_year),
					title=_("Inactive Academic Year")
				)

			existing = frappe.db.get_value(
				"PACE Admission",
				{"status": "Active", "name": ("!=", self.name)},
				["name", "academic_year"],
				as_dict=True
			)
			if existing:
				link = get_link_to_form("PACE Admission", existing.name)
				frappe.throw(
					_("Another PACE Admission <b>{0}</b> is already Active. Please close it before activating this one.")
					.format(link),
					title=_("Active Admission Conflict")
				)

	def _validate_programmes(self):
		"""Check for duplicate programmes in the table."""
		seen = set()
		for row in (self.programmes or []):
			if row.programme in seen:
				frappe.throw(
					_("Duplicate entry: Programme <b>{0}</b> is already added.").format(row.programme),
					title=_("Duplicate Programme")
				)
			seen.add(row.programme)


@frappe.whitelist()
def check_overlap(name, open_date, close_date):
	"""
	Whitelist method to check for overlapping active admissions from client side.
	"""
	if not open_date or not close_date:
		return {"valid": True}

	try:
		start = getdate(open_date)
		end = getdate(close_date)
	except Exception:
		return {"valid": True}

	if start > end:
		return {
			"valid": False,
			"message": _("Admission Open Date cannot be after Admission Close Date.")
		}

	# Check for any active admission that overlaps with this period
	overlapping = frappe.get_all(
		"PACE Admission",
		filters={
			"status": "Active",
			"name": ("!=", name),
			"admission_open_date": ("<=", close_date),
			"admission_close_date": (">=", open_date),
			"docstatus": ("<", 2)
		},
		fields=["name", "academic_year", "admission_open_date", "admission_close_date"]
	)

	if overlapping:
		conflicts = []
		for o in overlapping:
			sd = format_date(o.admission_open_date, "dd MMM yyyy")
			ed = format_date(o.admission_close_date, "dd MMM yyyy")
			conflicts.append(f"• {o.name} ({sd} to {ed})")
		
		return {
			"valid": False,
			"message": _("The selected date range overlaps with existing Active admission(s):<br>{0}")
						.format("<br>".join(conflicts))
		}

	return {"valid": True}


def auto_close_outdated_admissions():
	"""
	Scheduled task to update status based on current date.
	Called daily via hooks.
	"""
	today = getdate()
	
	# Fetch all submitted admissions
	admissions = frappe.get_all(
		"PACE Admission",
		filters={"docstatus": ("<", 2)},
		fields=["name", "admission_open_date", "admission_close_date", "status"]
	)

	for adm in admissions:
		doc = frappe.get_doc("PACE Admission", adm.name)
		changed = False

		# Auto-open
		if doc.admission_open_date and getdate(doc.admission_open_date) == today and doc.status != "Active":
			# Only auto-open if the Academic Year is Active AND no other PACE Admission is Active
			ay_status = frappe.db.get_value("Academic Year", doc.academic_year, "status")
			if ay_status == "Active" and not frappe.db.exists("PACE Admission", {"status": "Active", "name": ("!=", doc.name)}):
				doc.db_set("status", "Active")
				changed = True
				frappe.logger().info(f"PACE Admission: Auto-opened {doc.name}")

		# Auto-close
		elif doc.admission_close_date and getdate(doc.admission_close_date) < today and doc.status != "Closed":
			doc.db_set("status", "Closed")
			changed = True
			frappe.logger().info(f"PACE Admission: Auto-closed {doc.name}")

		if changed:
			doc.notify_update()


@frappe.whitelist()
def update_status(name, status):
	"""
	Whitelisted method to update admission status.
	Handles both saving and submission for 'Active' transitions.
	"""
	doc = frappe.get_doc("PACE Admission", name)
	doc.status = status
	
	if status == "Active" and doc.docstatus == 0:
		doc.submit()
	else:
		doc.save()
	
	return doc.status
