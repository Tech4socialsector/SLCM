import frappe
@frappe.whitelist()
def apply_template_to_cycle(template_name, cycle_name):
    """
    Reads Admission Stage Template and creates Admission Stage Config
    records for the given cycle, in sequence order.
    Replaces any existing stage configs for that cycle.
    """
    template = frappe.get_doc("Admission Stage Template", template_name)
    existing = frappe.get_all(
        "Admission Stage Config",
        filters={"admission_cycle": cycle_name},
        fields=["name"]
    )
    for e in existing:
        frappe.delete_doc("Admission Stage Config", e.name, ignore_permissions=True)

    for stage in sorted(template.stages, key=lambda s: s.sequence):
        if not stage.is_enabled:
            continue
        doc = frappe.get_doc({
            "doctype": "Admission Stage Config",
            "admission_cycle": cycle_name,
            "stage_name": stage.stage_name,
            "stage_type": stage.stage_type,
            "sequence": stage.sequence,
            "is_enabled": stage.is_enabled,
            "is_mandatory": stage.is_mandatory,
            "evaluation_config": stage.evaluation_config,
            "deadline_offset_days": stage.deadline_offset_days,
            "notify_applicant_on_entry": stage.notify_applicant_on_entry,
            "notification_template": stage.notification_template,
            "responsible_role": stage.responsible_role,
            "requires_approval_to_unlock": stage.requires_approval_to_unlock
        })
        doc.insert(ignore_permissions=True)

    frappe.db.commit()
    return True


def get_next_stage(cycle_name, current_stage_name):
    """
    Returns the next enabled stage after the current one.
    Returns None if current is the last stage.
    """
    all_stages = frappe.get_all(
        "Admission Stage Config",
        filters={"admission_cycle": cycle_name, "is_enabled": 1},
        fields=["name", "stage_name", "sequence"],
        order_by="sequence asc"
    )
    for i, stage in enumerate(all_stages):
        if stage.stage_name == current_stage_name:
            if i + 1 < len(all_stages):
                return all_stages[i + 1]
            return None
    return None


def can_unlock_next_stage(cycle_name, current_stage_name, user=None):
    """
    Checks if next stage can be unlocked.
    Returns (True, None) if allowed.
    Returns (False, reason) if blocked.
    """
    current = frappe.db.get_value(
        "Admission Stage Config",
        {"admission_cycle": cycle_name, "stage_name": current_stage_name},
        ["requires_approval_to_unlock", "name"],
        as_dict=True
    )
    if not current:
        return False, f"Stage '{current_stage_name}' not found in cycle."
    if current.requires_approval_to_unlock:
        if not frappe.has_permission("Admission Stage Config", "submit", user=user or frappe.session.user):
            return False, "This stage requires Super Admin approval to unlock the next stage."
    return True, None
