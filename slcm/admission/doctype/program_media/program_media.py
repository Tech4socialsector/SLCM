import frappe
from frappe.model.document import Document


class ProgramMedia(Document):

    def validate(self):
        if self.media_type == "Image" and not self.image:
            frappe.throw("Please attach an image for Image type media.")
        if self.media_type == "Video" and not self.video_url:
            frappe.throw("Please enter a Video URL for Video type media.")
        if self.media_type == "Brochure" and not self.brochure_pdf:
            frappe.throw("Please attach a PDF for Brochure type media.")

    def on_update(self):
        frappe.cache().delete_key("portal_program_media")
        frappe.cache().delete_key(f"program_media_{self.program}")
