import frappe
import csv
from frappe.model.document import Document
from frappe.utils import now

class ClatRankImport(Document):
    def validate(self):
        cycle_type = frappe.db.get_value(
            "Admission Cycle", self.admission_cycle, "workflow_type"
        )
        if cycle_type != "CLAT":
            frappe.throw(
                "CLAT Rank Import can only be linked to a CLAT Admission Cycle.",
                title="Invalid Cycle Type"
            )

    def on_submit(self):
        self.db_set("imported_by", frappe.session.user)
        self.db_set("imported_on", now())
        self.db_set("status", "Processing")
        self.process_import()

    def process_import(self):
        try:
            file_doc = frappe.get_doc("File", {"file_url": self.import_file})
            content = file_doc.get_content()
            if isinstance(content, bytes):
                content = content.decode("utf-8")
            reader = csv.DictReader(content.splitlines())
            count = 0
            for row in reader:
                count += 1
            self.db_set("total_records", count)
            self.db_set("status", "Completed")
        except Exception as e:
            self.db_set("status", "Failed")
            self.db_set("error_log", str(e))
            frappe.log_error(str(e), "CLAT Rank Import Error")
