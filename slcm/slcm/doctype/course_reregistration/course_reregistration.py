import frappe
from frappe.model.document import Document
from frappe.utils import flt


class CourseReregistration(Document):
	def validate(self):
		self.total_fee = flt(self.number_of_courses) * flt(self.fee_per_course)

	def on_submit(self):
		from slcm.slcm.fee.event_hooks import on_course_reregistration_submit
		on_course_reregistration_submit(self)

	def on_cancel(self):
		from slcm.slcm.fee.event_hooks import on_course_reregistration_cancel
		on_course_reregistration_cancel(self)
