# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today


def validate_offer_config_fee_deadlines(config):
    """
    Each linked Fee Structure must have Valid Until set and strictly after today
    (cannot be today or in the past). Used when activating Offer Configuration and when generating offers.
    """
    if isinstance(config, str):
        config = frappe.get_doc("Offer Configuration", config)
    rows = getattr(config, "fee_structure", None) or []
    if not rows:
        return
    today_d = getdate(today())
    errors = []
    for row in rows:
        fs = getattr(row, "fee_structure", None)
        if not fs:
            continue
        valid_until = frappe.db.get_value("Fee Structure", fs, "valid_until")
        if not valid_until:
            errors.append(
                _("Fee Structure {0}: Valid Until is required before using this configuration.").format(
                    frappe.bold(fs)
                )
            )
            continue
        if getdate(valid_until) <= today_d:
            errors.append(
                _(
                    "Fee Structure {0}: Valid Until ({1}) must be after today ({2}). "
                    "Past and same-day deadlines are not allowed."
                ).format(frappe.bold(fs), valid_until, today_d)
            )
    if errors:
        frappe.throw("<br>".join(errors), title=_("Invalid fee structure deadlines"))


class OfferConfiguration(Document):

    def autoname(self):
        """Naming: OC-{Year}-{Cycle}-{Campus}"""
        if self.admission_year and self.admission_cycle and self.campus:
            self.name = f"OC-{self.admission_year}-{self.admission_cycle}-{self.campus}"

    def validate(self):
        if self.is_active:
            self.validate_single_active_config()
            validate_offer_config_fee_deadlines(self)
        self.validate_duplicate_programs()

    def validate_duplicate_programs(self):
        programs = []
        if getattr(self, "offer_letter_pdf", []):
            for row in self.offer_letter_pdf:
                if row.program in programs:
                    frappe.throw(
                        f"Program {frappe.bold(row.program)} is duplicated in the Offer Letter PDF child table."
                    )
                programs.append(row.program)

    def validate_single_active_config(self):
        existing = frappe.get_all(
            "Offer Configuration",
            filters={
                "admission_year": self.admission_year,
                "admission_cycle": self.admission_cycle,
                "campus": self.campus,
                "is_active": 1,
                "name": ["!=", self.name]
            },
            fields=["name"],
            limit=1
        )

        if existing:
            frappe.throw(
                f"Only one active Offer Configuration is allowed for "
                f"Admission Year : {self.admission_year} - Admission Cycle : {self.admission_cycle} - Campus : {self.campus}"
            )