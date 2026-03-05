import frappe
from frappe.utils import now_datetime
from collections import defaultdict


def calculate_merit_with_rule(applicant, rule):
    """
    Calculates total merit score for an applicant based on the given rule.
    """
    total_score = 0
    
    # Pre-fetch merit components for efficiency if there are many rows
    component_map = {}
    component_names = [row.component_type for row in rule.components if row.is_active]
    
    if component_names:
        components = frappe.get_all(
            "Merit Component",
            filters={"name": ["in", component_names]},
            fields=["name", "field_name", "multiplier"]
        )
        component_map = {c.name: c for c in components}

    for row in rule.components:
        if not row.is_active:
            continue

        comp_meta = component_map.get(row.component_type)
        if not comp_meta:
            # Fallback for gracefully handling missing component definitions
            frappe.logger().warning(f"Merit Component '{row.component_type}' not found for calculation.")
            continue

        # Dynamic attribute lookup
        val = getattr(applicant, comp_meta.field_name, 0) or 0
        score = val * (comp_meta.multiplier or 1.0)

        total_score += score * (row.weight / 100)

    return total_score


def _rank_applicants(applicant_rows):
    """
    Applies overall and program ranking with tie-breaking.
    Tie-breaking priority: Total Score > HSC % (12th Mark) > Entrance Test Score
    """
    sort_key = lambda x: (
        x.total_score,
        x.hsc_percentage or 0,
        x.entrance_score or 0
    )

    # Overall Rank
    applicant_rows.sort(key=sort_key, reverse=True)
    for i, row in enumerate(applicant_rows):
        row.overall_rank = i + 1

    # Program Rank
    program_groups = defaultdict(list)
    for row in applicant_rows:
        program_groups[row.program].append(row)
    for group in program_groups.values():
        group.sort(key=sort_key, reverse=True)
        for i, row in enumerate(group):
            row.program_rank = i + 1


def generate_merit_for_level(cycle, campus, program_level):
    """
    Generates a Merit List for a specific Program Level (UG / PG / Research Cource).
    Uses the Merit Rule assigned to that program level via Merit Rule Mapping.
    """
    # Check if a Merit List already exists for this program level
    existing = frappe.db.get_value(
        "Merit List",
        {
            "admission_cycle": cycle,
            "campus": campus,
            "program_level": program_level
        },
        ["name", "docstatus"],
        as_dict=True
    )
    if existing:
        existing_doc = frappe.get_doc("Merit List", existing.get("name"))

        # If it is already submitted and has applicants, treat it as final.
        if existing_doc.docstatus == 1 and existing_doc.get("merit_applicants"):
            return existing_doc

        # Otherwise (draft/empty/partial), remove it so we can regenerate cleanly.
        # This situation commonly happens when a background job previously failed.
        if existing_doc.docstatus == 0:
            frappe.delete_doc("Merit List", existing_doc.name, ignore_permissions=True, force=True)
            frappe.db.commit()
        elif existing_doc.docstatus == 1 and not existing_doc.get("merit_applicants"):
            # Very rare: submitted but empty. Cancel then delete.
            existing_doc.cancel()
            frappe.delete_doc("Merit List", existing_doc.name, ignore_permissions=True, force=True)
            frappe.db.commit()

    # Fetch the active Merit Rule for this program level
    merit_rule_name = frappe.db.get_value(
        "Merit Rule Mapping",
        {
            "admission_cycle": cycle,
            "campus": campus,
            "program_level": program_level,
            "is_active": 1
        },
        "merit_rule"
    )
    if not merit_rule_name:
        frappe.throw(
            f"No active Merit Rule Mapping found for Program Level '{program_level}', "
            f"Campus '{campus}' and Admission Cycle '{cycle}'.",
            title="Missing Merit Rule Mapping"
        )

    rule = frappe.get_doc("Merit Rule", merit_rule_name)

    # Fetch applicants for this program level
    applicants = frappe.get_all(
        "Eligibility Result",
        filters={
            "admission_cycle": cycle,
            "campus": campus,
            "program_level": program_level
        },
        fields=[
            "name", "applicant_id", "candidate_name", "program", "program_level",
            "hsc_percentage", "entrance_test_score", "interview_score",
            "ug_cgpa", "pg_cgpa"
        ]
    )
    if not applicants:
        frappe.throw(
            f"No applicants found for Program Level '{program_level}', "
            f"Campus '{campus}' and Admission Cycle '{cycle}'.",
            title="No Applicants Found"
        )

    # Build Merit List
    merit = frappe.new_doc("Merit List")
    merit.admission_cycle = cycle
    merit.campus = campus
    merit.program_level = program_level
    merit.generated_on = now_datetime()
    merit.status = "Generated"

    for app in applicants:
        total_score = calculate_merit_with_rule(app, rule)

        if total_score < rule.minimum_marks:
            continue

        merit.append("merit_applicants", {
            "applicant_id": app.applicant_id,
            "candidate_name": app.candidate_name,
            "program": app.program,
            "program_level": app.program_level,
            "hsc_percentage": app.hsc_percentage,
            "entrance_score": app.entrance_test_score,
            "interview_score": app.interview_score,
            "ug_cgpa": app.ug_cgpa,
            "pg_cgpa": app.pg_cgpa,
            "total_score": total_score,
            "status": "Selected"
        })

    if not merit.merit_applicants:
        frappe.throw(
            f"No applicants could be processed for Program Level '{program_level}'.",
            title="Empty Merit List"
        )

    _rank_applicants(merit.merit_applicants)
    merit.insert()

    # Log merit calculation for each applicant
    from slcm.admission.doctype.admission_audit_log.audit_service import log_merit_action
    for row in merit.merit_applicants:
        log_merit_action(
            merit_list=merit.name,
            admission_cycle=merit.admission_cycle,
            applicant=row.applicant_id,
            program=row.program,
            action_type="Merit Calculated",
            remarks=f"Calculated via Merit Rule: {merit_rule_name}. Total Score: {row.total_score:.3f}"
        )

    merit.submit()
    frappe.db.commit()
    return merit
