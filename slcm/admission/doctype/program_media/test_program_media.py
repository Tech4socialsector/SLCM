import frappe
import unittest


class TestProgramMedia(unittest.TestCase):

    def test_required_fields(self):
        meta = frappe.get_meta("Program Media")
        fieldnames = [f.fieldname for f in meta.fields]
        for f in ["program", "media_type", "image", "video_url",
                  "brochure_pdf", "caption", "sequence",
                  "is_featured", "is_active"]:
            self.assertIn(f, fieldnames)

    def test_image_without_file_blocked(self):
        doc = frappe.new_doc("Program Media")
        doc.program = "TEST"
        doc.media_type = "Image"
        doc.image = ""
        self.assertRaises(frappe.ValidationError, doc.validate)

    def test_video_without_url_blocked(self):
        doc = frappe.new_doc("Program Media")
        doc.program = "TEST"
        doc.media_type = "Video"
        doc.video_url = ""
        self.assertRaises(frappe.ValidationError, doc.validate)
