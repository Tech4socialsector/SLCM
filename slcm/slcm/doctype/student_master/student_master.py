# Copyright (c) 2025, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_fullname, now_datetime, today, flt

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
    "Pending REGO":             ["slcm_Student", "slcm_Registration User", "System Manager"],
    "Pending FINO":             ["slcm_REGO Officer", "System Manager"],
    "Pending Registration":     ["slcm_FINO Officer", "System Manager"],
    "Pending Print & Scan":     ["slcm_Registration Officer", "System Manager"],
    "Pending Residences":       ["slcm_Documentation Officer", "System Manager"],
    "Pending IT":               ["slcm_Hostel Admin", "System Manager"],
    "Final Verification REGO":  ["slcm_IT Admin", "System Manager"],
    "Completed":                ["slcm_Registration Officer", "System Manager"],
    "Re-Open":                  ["System Manager"],
}


# ---------------------------------------------------------------------------
# Fee structure helpers (module-level, reusable across methods and jobs)
# ---------------------------------------------------------------------------

def _get_valid_fee_structure_for_program(program):
    """Return the currently date-valid active Fee Structure for the given program, or None."""
    current_date = today()
    result = frappe.db.sql(
        """
        SELECT name, total_amount, valid_from, valid_until
        FROM `tabFee Structure`
        WHERE program = %s
          AND status = 'Active'
          AND applicable = 'Student'
          AND valid_from <= %s
          AND (valid_until IS NULL OR valid_until >= %s)
        ORDER BY valid_from DESC, creation DESC
        LIMIT 1
        """,
        (program, current_date, current_date),
        as_dict=True,
    )
    return result[0] if result else None


def _resolve_program(programme):
    """Resolve a Cohort name (or bare Program name) to a Program name."""
    program = frappe.db.get_value("Cohort", programme, "program")
    if not program and frappe.db.exists("Program", programme):
        program = programme
    return program


def _calculate_discount(total_fee, applying_scholarship, scholarship_percentage, scholarship_amount):
    """Return scholarship discount amount based on student's scholarship fields."""
    scholarship_pct = flt(scholarship_percentage or 0)
    scholarship_amt = flt(scholarship_amount or 0)

    if applying_scholarship == "Yes" and scholarship_pct:
        return round((total_fee * scholarship_pct) / 100, 2)
    elif applying_scholarship == "Yes" and scholarship_amt:
        return min(scholarship_amt, total_fee)
    return 0.0


# ---------------------------------------------------------------------------
# Main DocType class
# ---------------------------------------------------------------------------

class StudentMaster(Document):
    def validate(self):
        self.validate_status_transition()

    def before_insert(self):
        """Auto-populate fee details from the currently valid Fee Structure on new record."""
        self._auto_fetch_fee_structure()

    def before_save(self):
        """Track status and fee structure changes and append to audit history."""
        if self.is_new():
            return

        self._track_fee_structure_change()

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

    def _track_fee_structure_change(self):
        """If fee_structure was changed manually, update fee fields and log to history."""
        prev_fs = frappe.db.get_value("Student Master", self.name, "fee_structure")
        if prev_fs == self.fee_structure or not self.fee_structure:
            return

        try:
            fs_doc = frappe.get_doc("Fee Structure", self.fee_structure)
        except Exception:
            return

        total_fee = flt(fs_doc.total_amount or 0)
        if total_fee:
            discount = _calculate_discount(
                total_fee,
                self.applying_scholarship,
                self.scholarship_percentage,
                self.scholarship_amount,
            )
            net_fee = total_fee - discount
            self.total_program_fee  = total_fee
            self.discount_amount    = discount
            self.net_program_fee    = net_fee
            self.outstanding_balance = max(net_fee - flt(self.total_paid_amount or 0), 0)

        if fs_doc.instalment_enabled and fs_doc.max_instalments:
            self.number_of_instalments = fs_doc.max_instalments

        fs_label = fs_doc.fee_structure_name or self.fee_structure
        self.append("fee_structure_history", {
            "fee_structure":       self.fee_structure,
            "fee_structure_label": fs_label,
            "total_program_fee":   flt(fs_doc.total_amount or 0),
            "valid_from":          fs_doc.valid_from,
            "valid_until":         fs_doc.valid_until,
            "applied_on":          now_datetime(),
            "applied_by":          frappe.session.user,
            "reason":              "Manual change by admin",
        })

    def on_update(self):
        """Sync derived fields and send completion email."""
        self._sync_active_statuses()
        self._handle_registration_email()
        _rebuild_fee_invoices(self)

    def _rebuild_fee_invoices_table(self):
        """Internal: rebuild fee_invoices child rows. Called from on_update and the API."""
        _rebuild_fee_invoices(self)

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
        """Populate fee fields from the currently date-valid Fee Structure.

        Runs on before_insert. Skips if fee data is already provided (e.g. from
        the admission pipeline). Records the assignment in the history table.
        """
        if not self.programme:
            return
        if self.fee_structure or flt(self.total_program_fee):
            return

        program = _resolve_program(self.programme)
        if not program:
            return

        fs = _get_valid_fee_structure_for_program(program)
        if not fs:
            return

        total_fee = flt(fs.total_amount or 0)
        if not total_fee:
            return

        discount = _calculate_discount(
            total_fee,
            self.applying_scholarship,
            self.scholarship_percentage,
            self.scholarship_amount,
        )

        self.fee_structure = fs.name
        self.total_program_fee = total_fee
        self.discount_amount = discount
        self.net_program_fee = total_fee - discount
        self.outstanding_balance = max(self.net_program_fee - flt(self.total_paid_amount or 0), 0)

        fs_label = frappe.db.get_value("Fee Structure", fs.name, "fee_structure_name") or fs.name
        self.append("fee_structure_history", {
            "fee_structure":       fs.name,
            "fee_structure_label": fs_label,
            "total_program_fee":   total_fee,
            "valid_from":          fs.valid_from,
            "valid_until":         fs.valid_until,
            "applied_on":          now_datetime(),
            "applied_by":          frappe.session.user,
            "reason":              "Auto-assigned on student creation",
        })

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
# ---------------------------------------------------------------------------
def before_save_hook(doc, method=None):
    doc.before_save()


# ---------------------------------------------------------------------------
# Fee Structure change trigger (called from Fee Structure on_update hook)
# ---------------------------------------------------------------------------
def on_fee_structure_update(doc, method=None):
    """Enqueue a background sync when a Student fee structure is saved with relevant changes."""
    if doc.applicable != "Student":
        return
    if doc.status != "Active":
        return

    changed = (
        doc.has_value_changed("status")
        or doc.has_value_changed("valid_from")
        or doc.has_value_changed("valid_until")
        or doc.has_value_changed("total_amount")
    )
    if not changed:
        return

    frappe.enqueue(
        "slcm.slcm.doctype.student_master.student_master.sync_fee_structures_for_program",
        program=doc.program,
        queue="default",
        timeout=600,
        job_id=f"fee_sync_{doc.program}_{today()}",
    )
    frappe.msgprint(
        _("Fee structure change detected. Student fee data will be updated in the background."),
        indicator="blue",
        alert=True,
    )


# ---------------------------------------------------------------------------
# Sync helpers – used by both the background job and the daily scheduler
# ---------------------------------------------------------------------------

def _sync_single_student_fee(student_name):
    """Check and update the fee structure for one student. Returns True if updated."""
    student = frappe.get_doc("Student Master", student_name)

    if not student.programme:
        return False

    program = _resolve_program(student.programme)
    if not program:
        return False

    fs = _get_valid_fee_structure_for_program(program)
    if not fs:
        return False

    if student.fee_structure == fs.name:
        return False

    total_fee = flt(fs.total_amount or 0)
    if not total_fee:
        return False

    discount = _calculate_discount(
        total_fee,
        student.applying_scholarship,
        student.scholarship_percentage,
        student.scholarship_amount,
    )
    net_fee    = total_fee - discount
    paid       = flt(student.total_paid_amount or 0)
    outstanding = max(net_fee - paid, 0)

    fs_label = frappe.db.get_value("Fee Structure", fs.name, "fee_structure_name") or fs.name

    student.fee_structure      = fs.name
    student.total_program_fee  = total_fee
    student.discount_amount    = discount
    student.net_program_fee    = net_fee
    student.outstanding_balance = outstanding

    student.append("fee_structure_history", {
        "fee_structure":       fs.name,
        "fee_structure_label": fs_label,
        "total_program_fee":   total_fee,
        "valid_from":          fs.valid_from,
        "valid_until":         fs.valid_until,
        "applied_on":          now_datetime(),
        "applied_by":          "System",
        "reason":              "Auto-synced: new fee structure validity period is active",
    })

    student.save(ignore_permissions=True)
    return True


def sync_fee_structures_for_program(program):
    """Update fee structures for all active students in the given program.

    Called as a background job when a Fee Structure is saved.
    """
    students = frappe.get_all(
        "Student Master",
        filters={"student_status": "Active"},
        fields=["name", "programme"],
        limit=0,
    )

    updated = 0
    errors  = 0

    for s in students:
        if not s.programme:
            continue
        resolved = _resolve_program(s.programme)
        if resolved != program:
            continue

        try:
            if _sync_single_student_fee(s.name):
                updated += 1
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Fee Structure Sync Error: {s.name}",
            )
            errors += 1

    frappe.logger().info(
        f"Fee Structure Sync for program '{program}': {updated} updated, {errors} errors"
    )


def auto_sync_all_student_fee_structures():
    """Daily scheduler: update fee structures for every active student."""
    students = frappe.get_all(
        "Student Master",
        filters={"student_status": "Active"},
        fields=["name"],
        limit=0,
    )

    updated = 0
    errors  = 0

    for s in students:
        try:
            if _sync_single_student_fee(s.name):
                updated += 1
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Daily Fee Sync Error: {s.name}",
            )
            errors += 1

    if updated or errors:
        frappe.logger().info(
            f"Daily Fee Sync: {updated} updated, {errors} errors / {len(students)} total active students"
        )


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
        doc_checks = {
            "aadhaar_card":        "aadhaar_verified",
            "pan_card":            "pan_verified",
            "offer_letter":        "offer_letter_verified",
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
    """Return fee details from the currently date-valid Student Fee Structure for the given cohort."""
    if not programme:
        return None

    program = _resolve_program(programme)
    if not program:
        return None

    fs = _get_valid_fee_structure_for_program(program)
    if not fs:
        return None

    return {
        "fee_structure":      fs.name,
        "fee_structure_name": frappe.db.get_value("Fee Structure", fs.name, "fee_structure_name") or fs.name,
        "total_program_fee":  flt(fs.total_amount or 0),
        "valid_from":         str(fs.valid_from or ""),
        "valid_until":        str(fs.valid_until or ""),
    }


# ---------------------------------------------------------------------------
# Fee Invoice child-table helpers
# ---------------------------------------------------------------------------

def _rebuild_fee_invoices(sm_doc):
    """Rebuild the fee_invoices child table rows from live Fee Invoice records.

    Accepts a StudentMaster document instance. Uses db_update() so it never
    triggers validate/on_update loops.
    """
    try:
        invoices = frappe.get_all(
            "Fee Invoice",
            filters={"student": sm_doc.name},
            fields=[
                "name", "academic_term", "invoice_date", "due_date",
                "final_payable_amount", "paid_amount", "outstanding_amount", "status",
            ],
            order_by="invoice_date desc, creation desc",
            ignore_permissions=True,
        )

        sm_doc.set("fee_invoices", [])
        for inv in invoices:
            sm_doc.append("fee_invoices", {
                "invoice":            inv.name,
                "academic_term":      inv.academic_term or "",
                "invoice_date":       inv.invoice_date,
                "due_date":           inv.due_date,
                "net_payable":        flt(inv.final_payable_amount or 0),
                "paid_amount":        flt(inv.paid_amount or 0),
                "outstanding_amount": max(flt(inv.outstanding_amount or 0), 0),
                "status":             inv.status or "Unpaid",
            })

        sm_doc.db_update()
        frappe.db.commit()
        return len(invoices)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "_rebuild_fee_invoices failed")
        return 0


@frappe.whitelist()
def send_parent_login_invite(student_name):
    if not frappe.db.exists("Student Master", student_name):
        frappe.throw(_("Student Master not found: {0}").format(student_name))

    sm = frappe.get_doc("Student Master", student_name, ignore_permissions=True)
    full_student_name = f"{sm.first_name} {sm.last_name or ''}".strip()

    parents = sm.get("parents") or []
    if not parents:
        frappe.throw(_("No parent records found on this Student Master."))

    results = []
    for p in parents:
        if not p.email:
            results.append({"name": f"{p.first_name} {p.last_name or ''}".strip(), "status": "no_email"})
            continue
        from slcm.slcm.doctype.parent_login_invite_tool.parent_login_invite_tool import _create_parent_user_and_invite
        parent_full = f"{p.first_name} {p.last_name or ''}".strip()
        already = frappe.db.exists("User", p.email)
        _create_parent_user_and_invite(p.email, parent_full, full_student_name)
        results.append({
            "name": parent_full,
            "email": p.email,
            "status": "existing" if already else "invited",
        })

    return results


@frappe.whitelist()
def get_fee_structure_details(fee_structure):
    """Return key fields from a Fee Structure for auto-population in the Student Master form."""
    if not fee_structure or not frappe.db.exists("Fee Structure", fee_structure):
        return None

    fs = frappe.get_doc("Fee Structure", fee_structure)
    components = []
    for c in (fs.components or []):
        components.append({
            "component_name": c.component_name,
            "amount":         flt(c.amount or 0),
            "total_amount":   flt(c.total_amount or c.amount or 0),
        })

    return {
        "fee_structure":       fs.name,
        "fee_structure_name":  fs.fee_structure_name or fs.name,
        "total_amount":        flt(fs.total_amount or 0),
        "valid_from":          str(fs.valid_from or ""),
        "valid_until":         str(fs.valid_until or ""),
        "status":              fs.status,
        "instalment_enabled":  int(fs.instalment_enabled or 0),
        "max_instalments":     int(fs.max_instalments or 0),
        "components":          components,
    }


@frappe.whitelist()
def change_fee_structure_admin(student_name, new_fee_structure, reason):
    """Admin-only API: change a student's fee structure with audit trail.

    Updates all derived fee fields and appends a history entry with the given reason.
    """
    user_roles = frappe.get_roles()
    allowed_roles = ["System Manager", "slcm_FINO Officer", "Administrator"]
    if not any(r in user_roles for r in allowed_roles) and frappe.session.user != "Administrator":
        frappe.throw(_("You do not have permission to change the Fee Structure."))

    if not frappe.db.exists("Student Master", student_name):
        frappe.throw(_("Student Master not found: {0}").format(student_name))
    if not frappe.db.exists("Fee Structure", new_fee_structure):
        frappe.throw(_("Fee Structure not found: {0}").format(new_fee_structure))

    reason = (reason or "").strip()
    if not reason:
        frappe.throw(_("Reason is mandatory when changing the Fee Structure."))

    sm = frappe.get_doc("Student Master", student_name, ignore_permissions=True)
    fs = frappe.get_doc("Fee Structure", new_fee_structure)

    total_fee = flt(fs.total_amount or 0)
    discount = _calculate_discount(
        total_fee,
        sm.applying_scholarship,
        sm.scholarship_percentage,
        sm.scholarship_amount,
    )
    net_fee     = total_fee - discount
    outstanding = max(net_fee - flt(sm.total_paid_amount or 0), 0)

    sm.fee_structure       = new_fee_structure
    sm.total_program_fee   = total_fee
    sm.discount_amount     = discount
    sm.net_program_fee     = net_fee
    sm.outstanding_balance = outstanding

    if fs.instalment_enabled and fs.max_instalments:
        sm.number_of_instalments = fs.max_instalments

    fs_label = fs.fee_structure_name or new_fee_structure
    sm.append("fee_structure_history", {
        "fee_structure":       new_fee_structure,
        "fee_structure_label": fs_label,
        "total_program_fee":   total_fee,
        "valid_from":          fs.valid_from,
        "valid_until":         fs.valid_until,
        "applied_on":          now_datetime(),
        "applied_by":          frappe.session.user,
        "reason":              reason,
    })

    sm.save(ignore_permissions=True)
    frappe.db.commit()

    _append_payment_log(
        student_name,
        "Fee Structure Changed",
        amount=total_fee,
        from_status=frappe.db.get_value("Student Master", student_name, "fee_payment_status") or "",
        to_status="",
        remarks=f"Fee structure changed to {fs_label}. Reason: {reason}",
    )

    return {
        "status":              "success",
        "fee_structure":       new_fee_structure,
        "fee_structure_name":  fs_label,
        "total_program_fee":   total_fee,
        "net_program_fee":     net_fee,
        "valid_from":          str(fs.valid_from or ""),
        "valid_until":         str(fs.valid_until or ""),
    }


@frappe.whitelist()
def sync_fee_invoices(student_name):
    """Module-level whitelisted function — called from the JS button.

    Rebuilds the fee_invoices child table for the given Student Master and
    returns the count of synced rows.
    """
    if not frappe.db.exists("Student Master", student_name):
        frappe.throw(_("Student Master not found: {0}").format(student_name))

    sm_doc = frappe.get_doc("Student Master", student_name, ignore_permissions=True)
    count  = _rebuild_fee_invoices(sm_doc)
    return {"synced": count}



# ── Payment Log helper ────────────────────────────────────────────────────────

def _append_payment_log(student_name, event_type, **kwargs):
    """Insert a Student Fee Payment Log row directly, bypassing SM validate.

    Args:
        student_name  : Student Master primary key
        event_type    : Select value (Payment Initiated / Captured / …)
        amount        : float — payment amount involved
        invoice       : str  — Fee Invoice name
        payment_mode  : str  — Online Payment / Cash / Counter
        razorpay_payment_id : str
        from_status   : str  — SM fee_payment_status before the event
        to_status     : str  — SM fee_payment_status after the event
        triggered_by  : str  — user (defaults to frappe.session.user)
        remarks       : str  — free-text note
    """
    try:
        row = frappe.get_doc({
            "doctype":              "Student Fee Payment Log",
            "parent":               student_name,
            "parenttype":           "Student Master",
            "parentfield":          "fee_payment_log",
            "event_type":           event_type,
            "timestamp":            kwargs.get("timestamp") or now_datetime(),
            "amount":               kwargs.get("amount") or 0,
            "invoice":              kwargs.get("invoice") or "",
            "payment_mode":         kwargs.get("payment_mode") or "",
            "razorpay_payment_id":  kwargs.get("razorpay_payment_id") or "",
            "triggered_by":         kwargs.get("triggered_by") or frappe.session.user,
            "from_status":          kwargs.get("from_status") or "",
            "to_status":            kwargs.get("to_status") or "",
            "remarks":              kwargs.get("remarks") or "",
        })
        row.insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Payment log insert failed — {student_name}")
