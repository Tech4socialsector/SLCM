import frappe
from frappe.utils import now_datetime
from collections import defaultdict


def calculate_merit_with_rule(applicant, rule):
    """
    Calculates total merit score for an applicant based on the given rule.
    """
    total_score = 0
    for row in rule.components:
        if not row.is_active:
            continue

        score = 0
        if row.component_type == "HSC Percentage":
            score = applicant.hsc_percentage or 0
        elif row.component_type == "Entrance Test":
            score = applicant.entrance_percentage or 0
        elif row.component_type == "Interview":
            score = applicant.interview_percentage or 0

        total_score += score * (row.weight / 100)

    return total_score


def _rank_applicants(applicant_rows):
    """
    Applies overall, program, and category ranking with tie-breaking.
    Tie-breaking priority: Total Score > Entrance % > HSC % > Interview %
    """
    sort_key = lambda x: (
        x.total_score,
        x.entrance_percentage or 0,
        x.hsc_percentage or 0,
        x.interview_percentage or 0
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

    # Category Rank
    category_groups = defaultdict(list)
    for row in applicant_rows:
        category_groups[row.reservation_category].append(row)
    for group in category_groups.values():
        group.sort(key=sort_key, reverse=True)
        for i, row in enumerate(group):
            row.category_rank = i + 1


def generate_merit_for_level(cycle, campus, program_level):
    """
    Generates a Merit List for a specific Program Level (UG / PG / PhD).
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
        "Admission Result",
        filters={
            "admission_cycle": cycle,
            "campus": campus,
            "program_level": program_level
        },
        fields=[
            "name", "program", "program_level", "reservation_category",
            "hsc_percentage", "entrance_percentage", "interview_percentage"
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
        merit.append("merit_applicants", {
            "applicant": app.name,
            "program": app.program,
            "program_level": app.program_level,
            "reservation_category": app.reservation_category,
            "hsc_percentage": app.hsc_percentage,
            "entrance_percentage": app.entrance_percentage,
            "interview_percentage": app.interview_percentage,
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
    merit.submit()
    frappe.db.commit()
    return merit
