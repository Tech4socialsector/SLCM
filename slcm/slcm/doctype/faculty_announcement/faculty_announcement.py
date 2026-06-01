import frappe
from frappe.model.document import Document
from frappe.utils import today, nowdate, getdate


class FacultyAnnouncement(Document):
	def validate(self):
		if self.expiry_date and self.publish_date and self.expiry_date < self.publish_date:
			frappe.throw("Expiry Date cannot be before Publish Date.")

	def before_save(self):
		if not self.publish_date:
			self.publish_date = today()


@frappe.whitelist(allow_guest=False)
def get_active_announcements(faculty=None, limit=50):
	"""Return Faculty Announcements visible to the given faculty member."""
	today_str = nowdate()

	records = frappe.get_all(
		"Faculty Announcement",
		filters=[["is_active", "=", 1], ["publish_date", "<=", today_str]],
		fields=[
			"name", "title", "content", "announcement_type", "priority",
			"publish_date", "expiry_date", "target_audience",
		],
		order_by="priority desc, publish_date desc",
		limit=int(limit),
		ignore_permissions=True,
	)

	faculty_data = None
	if faculty:
		faculty_data = frappe.db.get_value(
			"Faculty", faculty, ["department"], as_dict=True
		)

	visible = []
	today_date = getdate(today_str)
	for r in records:
		if r.expiry_date and getdate(r.expiry_date) < today_date:
			continue

		if r.target_audience == "All Faculty":
			visible.append(r)
			continue

		if not faculty_data:
			visible.append(r)
			continue

		if r.target_audience == "Specific Department(s)":
			target_departments = frappe.get_all(
				"Announcement Department Target",
				filters={"parent": r.name},
				fields=["department"],
				ignore_permissions=True,
			)
			if any(t.department == faculty_data.department for t in target_departments):
				visible.append(r)

		elif r.target_audience == "Specific Faculty":
			target_faculties = frappe.get_all(
				"Announcement Faculty Target",
				filters={"parent": r.name},
				fields=["faculty"],
				ignore_permissions=True,
			)
			if any(t.faculty == faculty for t in target_faculties):
				visible.append(r)

	return visible
