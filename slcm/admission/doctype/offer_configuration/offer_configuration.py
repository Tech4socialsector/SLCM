# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today


def validate_offer_config_fee_deadlines(config, program=None):
    """
    Each linked Fee Structure must have Valid Until set and strictly after today
    (cannot be today or in the past). Used when activating Offer Configuration and when generating offers.
    """
    if isinstance(config, str):
        config = frappe.get_doc("Offer Configuration", config)
    if hasattr(config, "is_active") and not config.is_active:
        return
    rows = getattr(config, "fee_structure", None) or []
    if not rows:
        return
    today_d = getdate(today())
    errors = []
    
    if config.due_date and getdate(config.due_date) <= today_d:
        errors.append(_("Offer Acceptance Deadline (Offer Due Date) must be after today ({0}).").format(today_d))
        
    for row in rows:
        fs = getattr(row, "fee_structure", None)
        if not fs:
            continue
            
        fee_doc = frappe.db.get_value("Fee Structure", fs, ["valid_until", "due_date_for_confirmation_fee", "program"], as_dict=True)
        if not fee_doc:
            continue
            
        if program and fee_doc.program != program:
            continue
            
        valid_until = fee_doc.valid_until
        conf_fee = fee_doc.due_date_for_confirmation_fee
        
        if not valid_until:
            errors.append(
                _("Fee Structure {0}: Valid Until is required before using this configuration.").format(
                    frappe.bold(fs)
                )
            )
        elif getdate(valid_until) <= today_d:
            errors.append(
                _(
                    "Fee Structure {0}: Valid Until ({1}) must be after today ({2}). "
                    "Past and same-day deadlines are not allowed."
                ).format(frappe.bold(fs), valid_until, today_d)
            )
            
        if conf_fee and getdate(conf_fee) <= today_d:
            errors.append(
                _(
                    "Fee Structure {0}: Confirmation Fee Deadline ({1}) must be after today ({2})."
                ).format(frappe.bold(fs), conf_fee, today_d)
            )
            
    if errors:
        frappe.throw("<br>".join(errors), title=_("Invalid Configuration Deadlines"))


class OfferConfiguration(Document):

    def validate(self):
        self.validate_single_config()
        if self.is_active:
            validate_offer_config_fee_deadlines(self)

    def validate_single_config(self):
        existing = frappe.get_all(
            "Offer Configuration",
            filters={
                "admission_year": self.admission_year,
                "admission_cycle": self.admission_cycle,
                "campus": self.campus,
                "name": ["!=", self.name]
            },
            fields=["name"],
            limit=1
        )

        if existing:
            frappe.throw(
                f"Only one Offer Configuration is allowed for "
                f"Admission Year : {self.admission_year} - Admission Cycle : {self.admission_cycle} - Campus : {self.campus}"
            )