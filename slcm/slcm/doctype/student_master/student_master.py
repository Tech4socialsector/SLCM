# Copyright (c) 2025, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_fullname, now_datetime

# ---------------------------------------------------------------------------
# Single source of truth for the registration state machine
# ---------------------------------------------------------------------------
VALID_TRANSITIONS = {
    "Draft":                    ["Selected"],
    "Selected":                 ["Pending REGO"],
    "Pending REGO":             ["Pending FINO"],
    "Pending FINO":             ["Pending Registration"],
    "Pending Registration":     ["Pending Print & Scan"],
    "Pending Print & Scan":     ["Pending Residences"],
    "Pending Residences":       ["Pending IT"],
    "Pending IT":               ["Final Verification REGO"],
    "Final Verification REGO":  ["Completed"],
    "Completed":                ["Re-Open"],
    "Re-Open":                  ["Pending REGO"],
}

# Roles that are allowed to move INTO each target status
TRANSITION_ROLES = {
    "Pending REGO":             ["Student", "Registration User", "System Manager"],
    "Pending FINO":             ["REGO Officer", "System Manager"],
    "Pending Registration":     ["FINO Officer", "System Manager"],
    "Pending Print & Scan":     ["Registration Officer", "System Manager"],
    "Pending Residences":       ["Documentation Officer", "System Manager"],
    "Pending IT":               ["Residence / Hostel Admin", "System Manager"],
    "Final Verification REGO":  ["IT Admin", "System Manager"],
    "Completed":                ["Registration Officer", "System Manager"],
    "Re-Open":                  ["System Manager"],
}


class StudentMaster(Document):
    def validate(self):
        self.validate_status_transition()

    def before_insert(self):
        """Auto-populate fee details from active Student Fee Structure on new record."""
        self._auto_fetch_fee_structure()

    def before_save(self):
        """Track status changes and append to audit history."""
        if self.is_new():
            return

        previous_status = frappe.db.get_value("Student Master", self.name, "registration_status")

        if previous_status == self.registration_status:
            return

        self.status_updated_by = frappe.session.user
        self.status_updated_on = now_datetime()

        confirmed_previous_state = None
        if previous_status and frappe.db.exists("Workflow State", previous_status):
            confirmed_previous_state = previous_status

        self.append("workflow_history", {
            "workflow_state":  self.registration_status,
            "previous_state":  confirmed_previous_state,
            "updated_by":      frappe.session.user,
            "updated_on":      now_datetime(),
            "remarks":         self.status_remarks,
        })

        frappe.get_doc({
            "doctype":          "Comment",
            "comment_type":     "Workflow",
            "reference_doctype": self.doctype,
            "reference_name":   self.name,
            "content": _("Status changed from {0} to {1} by {2}").format(
                previous_status or "Selected",
                self.registration_status,
                get_fullname(frappe.session.user),
            ),
        }).insert(ignore_permissions=True)

    def on_update(self):
        """Sync derived fields and send completion email."""
        self._sync_active_statuses()
        self._handle_registration_email()

    def _sync_active_statuses(self):
        """Keep student_status and academic_status consistent with registration_status."""
        if self.registration_status == "Completed":
            if self.student_status != "Active":
                frappe.db.set_value("Student Master", self.name, "student_status", "Active")
            if self.academic_status != "Active":
                frappe.db.set_value("Student Master", self.name, "academic_status", "Active")

    def _handle_registration_email(self):
        doc_before_save = self.get_doc_before_save()
        previous_status = doc_before_save.registration_status if doc_before_save else None

        if self.registration_status == "Completed" and previous_status != "Completed":
            from slcm.slcm.utils.student_email import handle_registration_completion
            handle_registration_completion(self.name, frappe.session.user)

    def _auto_fetch_fee_structure(self):
        """Populate fee fields from the active Student Fee Structure for this programme.

        Runs on before_insert so newly-created students (from admission or manually)
        always start with correct fee data without touching the Admission module.
        """
        if not self.programme:
            return
        # Skip if fee details are already populated
        if self.fee_structure or frappe.utils.flt(self.total_program_fee):
            return

        # Student Master.programme is a Link to Cohort; resolve → Program
        program = frappe.db.get_value("Cohort", self.programme, "program")
        if not program:
            # Fallback: AFA mapping sometimes stores the Program name directly
            if frappe.db.exists("Program", self.programme):
                program = self.programme
        if not program:
            return

        fs = frappe.db.get_value(
            "Fee Structure",
            {"program": program, "status": "Active", "applicable": "Student"},
            ["name", "total_amount"],
            as_dict=True,
            order_by="valid_from desc, creation desc",
        )
        if not fs:
            return

        total_fee = frappe.utils.flt(fs.total_amount or 0)
        if not total_fee:
            return

        self.fee_structure = fs.name
        self.total_program_fee = total_fee

        # Calculate discount from scholarship percentage or amount
        scholarship_pct = frappe.utils.flt(self.scholarship_percentage or 0)
        scholarship_amt = frappe.utils.flt(self.scholarship_amount or 0)

        if self.applying_scholarship == "Yes" and scholarship_pct:
            discount = round((total_fee * scholarship_pct) / 100, 2)
        elif self.applying_scholarship == "Yes" and scholarship_amt:
            discount = min(scholarship_amt, total_fee)
        else:
            discount = 0

        self.discount_amount = discount
        self.net_program_fee = total_fee - discount
        paid = frappe.utils.flt(self.total_paid_amount or 0)
        self.outstanding_balance = max(self.net_program_fee - paid, 0)

    def validate_status_transition(self):
        """Enforce the registration workflow sequence."""
        if self.is_new():
            if not self.registration_status:
                self.registration_status = "Selected"
            return

        previous_status = frappe.db.get_value("Student Master", self.name, "registration_status")

        if previous_status == self.registration_status:
            return

        if "System Manager" not in frappe.get_roles():
            if previous_status in VALID_TRANSITIONS:
                if self.registration_status not in VALID_TRANSITIONS[previous_status]:
                    frappe.throw(_(
                        "Invalid status transition from {0} to {1}. Please follow the workflow sequence."
                    ).format(previous_status, self.registration_status))


# ---------------------------------------------------------------------------
# Hook called from hooks.py doc_events before_save
# (keeps the hook pointing to a single stable entry point)
# ---------------------------------------------------------------------------
def before_save_hook(doc, method=None):
    doc.before_save()


# ---------------------------------------------------------------------------
# Whitelisted API
# ---------------------------------------------------------------------------
@frappe.whitelist()
def update_registration_status(student_id, new_status, remarks=None):
    """Update registration status with role-based and sequence validation."""
    user_roles = frappe.get_roles()
    is_admin = "System Manager" in user_roles or frappe.session.user == "Administrator"

    if not remarks or not remarks.strip():
        frappe.throw(_("Remarks is mandatory for status update"))

    student = frappe.get_doc("Student Master", student_id)
    current_status = student.registration_status or "Selected"

    if not is_admin:
        required_roles = TRANSITION_ROLES.get(new_status, [])
        if not any(role in user_roles for role in required_roles):
            frappe.throw(_(
                "You do not have permission to set status to {0}. Required roles: {1}"
            ).format(new_status, ", ".join(required_roles)))

        if current_status in VALID_TRANSITIONS:
            if new_status not in VALID_TRANSITIONS[current_status]:
                frappe.throw(_(
                    "Invalid status transition from {0} to {1}. Please follow the workflow sequence."
                ).format(current_status, new_status))

    _validate_transition_requirements(student, new_status)

    student.registration_status = new_status
    student.status_updated_by = frappe.session.user
    student.status_updated_on = now_datetime()
    student.status_remarks = remarks

    try:
        student.save(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.db.rollback()
        frappe.throw(_("Error updating status: {0}").format(str(e)))

    return {"status": "success", "message": _("Status updated to {0}").format(new_status)}


@frappe.whitelist()
def get_available_status_actions(student_id):
    """Return valid next actions for the current user and student status."""
    student = frappe.get_doc("Student Master", student_id)
    current_status = student.registration_status or "Selected"
    user_roles = frappe.get_roles()
    is_admin = "System Manager" in user_roles or frappe.session.user == "Administrator"

    ACTION_LABELS = {
        "Pending REGO":             "Submit for REGO",
        "Pending FINO":             "Approve Documents",
        "Pending Registration":     "Approve Finances",
        "Pending Print & Scan":     "Submit for Print & Scan",
        "Pending Residences":       "Upload Documents",
        "Pending IT":               "Allocate Room",
        "Final Verification REGO":  "Allocate Assets",
        "Completed":                "Complete Registration",
        "Re-Open":                  "Re-Open",
    }

    available_actions = []

    if is_admin:
        for state in VALID_TRANSITIONS:
            if state != current_status:
                available_actions.append({
                    "action":     f"Set to {state}",
                    "next_state": state,
                    "label":      f"Set to {state}",
                })
    else:
        next_states = VALID_TRANSITIONS.get(current_status, [])
        for next_state in next_states:
            required_roles = TRANSITION_ROLES.get(next_state, [])
            if any(role in user_roles for role in required_roles):
                available_actions.append({
                    "action":     ACTION_LABELS.get(next_state, next_state),
                    "next_state": next_state,
                    "label":      ACTION_LABELS.get(next_state, next_state),
                })

    return {"current_status": current_status, "available_actions": available_actions}


@frappe.whitelist()
def validate_new_enrollment(student_id):
    """Check whether a student is eligible to be enrolled."""
    try:
        student = frappe.get_doc("Student Master", student_id)
    except frappe.DoesNotExistError:
        return {"allowed": False, "message": "Student record not found."}

    if student.academic_status == "Inactive":
        return {"allowed": False, "message": "Student Academic Status is Inactive."}

    if student.student_status == "Inactive":
        return {"allowed": False, "message": "Student Status is Inactive."}

    if student.registration_status != "Completed":
        return {
            "allowed": False,
            "message": (
                f"Student Registration Status is '{student.registration_status}'. "
                "Must be 'Completed' to enroll."
            ),
        }

    if not student.programme:
        return {"allowed": False, "message": "Programme (Cohort) is not set in Student Master."}

    existing_enrollment = frappe.db.exists(
        "Student Enrollment",
        {"student": student.name, "cohort": student.programme, "docstatus": ["<", 2]},
    )

    if existing_enrollment:
        return {
            "allowed": False,
            "message": (
                f"Student is already enrolled in this Cohort ({student.programme}). "
                f"Enrollment ID: {existing_enrollment}"
            ),
        }

    return {"allowed": True}


@frappe.whitelist()
def bulk_student_enrollment(students):
    """Bulk-enroll a list of students."""
    import json

    if isinstance(students, str):
        students = json.loads(students)

    success = []
    failed  = []

    for student_id in students:
        validation = validate_new_enrollment(student_id)

        if not validation.get("allowed"):
            failed.append({"student": student_id, "reason": validation.get("message")})
            continue

        try:
            student = frappe.get_doc("Student Master", student_id)

            new_enrollment = frappe.get_doc({
                "doctype":      "Student Enrollment",
                "student":      student.name,
                "student_name": " ".join(filter(None, [
                    student.first_name, student.middle_name, student.last_name
                ])),
                "cohort":        student.programme,
                "batch_year_ref": student.batch_year,
                "academic_year": student.academic_year,
                "status":        "Enrolled",
                "enrollment_date": frappe.utils.today(),
            })

            new_enrollment.insert()
            success.append(student_id)

        except Exception as e:
            frappe.log_error(message=str(e), title="Bulk Enrollment Error")
            failed.append({"student": student_id, "reason": str(e)})

    return {"success": success, "failed": failed}


# ---------------------------------------------------------------------------
# Internal transition requirement validator
# ---------------------------------------------------------------------------
def _validate_transition_requirements(student, new_status):
    """Raise frappe.throw if mandatory fields/docs are missing for the transition."""

    if new_status == "Pending FINO":
        required_docs = ["aadhaar_card", "pan_card", "std_x_marksheet", "passport_size_photo"]
        missing = [d for d in required_docs if not student.get(d)]
        if missing:
            labels = [frappe.get_meta("Student Master").get_label(d) for d in missing]
            frappe.throw(_(
                "Cannot move to Pending FINO. Missing documents: {0}"
            ).format(", ".join(labels)))

    elif new_status == "Pending Registration":
        if student.fee_payment_status not in ["Paid", "Partially Paid"]:
            frappe.throw(_(
                "Cannot move to Pending Registration. "
                "Fee Payment Status must be 'Paid' or 'Partially Paid'. Current: {0}"
            ).format(student.fee_payment_status))

    elif new_status == "Pending Print & Scan":
        required_fields = ["first_name", "last_name", "dob", "gender", "email", "phone", "programme", "department"]
        missing = [f for f in required_fields if not student.get(f)]
        if missing:
            labels = [frappe.get_meta("Student Master").get_label(f) for f in missing]
            frappe.throw(_(
                "Cannot move to Pending Print & Scan. Missing mandatory details: {0}"
            ).format(", ".join(labels)))

    elif new_status == "Pending Residences":
        if not student.id_card_issued:
            frappe.throw(_("Cannot move to Pending Residences. ID Card must be issued."))
        if not student.aadhaar_verified:
            frappe.throw(_("Cannot move to Pending Residences. Aadhaar must be verified."))

    elif new_status == "Pending IT":
        if student.is_hosteller:
            if not student.hostel_room:
                frappe.throw(_("Cannot move to Pending IT. Hostel Room must be allocated for hostellers."))
            if not student.keys_handed_over:
                frappe.throw(_("Cannot move to Pending IT. Keys must be handed over."))

    elif new_status == "Final Verification REGO":
        if not student.official_email_id:
            frappe.throw(_("Cannot move to Final Verification. Official Email ID must be set."))

    elif new_status == "Completed":
        # All key documents must be uploaded AND verified before completing
        doc_checks = {
            "aadhaar_card":    "aadhaar_verified",
            "pan_card":        "pan_verified",
            "offer_letter":    "offer_letter_verified",
            "student_declaration": "student_declaration_verified",
        }
        for doc_field, verified_field in doc_checks.items():
            if not student.get(doc_field):
                label = frappe.get_meta("Student Master").get_label(doc_field)
                frappe.throw(_("Cannot complete registration. {0} is not uploaded.").format(label))
            if not student.get(verified_field):
                label = frappe.get_meta("Student Master").get_label(doc_field)
                frappe.throw(_("Cannot complete registration. {0} is not verified.").format(label))

        if not student.id_card_issued:
            frappe.throw(_("Cannot complete registration. ID Card must be issued."))
        if not student.official_email_id:
            frappe.throw(_("Cannot complete registration. Official Email ID must be set."))


@frappe.whitelist()
def fetch_program_fee_details(programme):
	"""Return fee details from the active Student Fee Structure for the given cohort."""
	if not programme:
		return None
	program = frappe.db.get_value("Cohort", programme, "program")
	if not program:
		return None
	fs = frappe.db.get_value(
		"Fee Structure",
		{"program": program, "status": "Active", "applicable": "Student"},
		["name", "fee_structure_name", "total_amount", "academic_year", "academic_term"],
		as_dict=True,
		order_by="valid_from desc, creation desc",
	)
	if not fs:
		return None
	return {
		"fee_structure": fs.name,
		"fee_structure_name": fs.fee_structure_name or fs.name,
		"total_program_fee": frappe.utils.flt(fs.total_amount or 0),
		"academic_year": fs.academic_year or "",
		"academic_term": fs.academic_term or "",
	}
