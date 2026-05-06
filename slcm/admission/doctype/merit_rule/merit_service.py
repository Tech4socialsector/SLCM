import frappe
from frappe import _
from frappe.utils import now_datetime
from collections import defaultdict


def calculate_merit_with_rule(applicant, rule):
    """
    Calculates total merit score for an applicant based on the given rule.
    Supports simple fields in Eligibility Result and averaging values from
    ug_degree_details and pg_degree_details child tables.
    """
    total_score = 0
    
    # Pre-fetch merit components for efficiency
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
            frappe.logger().warning(f"Merit Component '{row.component_type}' not found.")
            continue

        field_name = comp_meta.field_name
        val = 0

        # Smart mapping for common field names to child tables
        resolved_table = None
        if field_name == "ug_cgpa" or field_name == "ug_degree_details":
            resolved_table = "ug_degree_details"
        elif field_name == "pg_cgpa" or field_name == "pg_degree_details":
            resolved_table = "pg_degree_details"

        if resolved_table:
            child_rows = applicant.get(resolved_table) or []
            if child_rows:
                scores = []
                for r in child_rows:
                    row_val = 0
                    if resolved_table == "ug_degree_details":
                        row_val = r.get("ug_cgpa") or r.get("percentage_cgpa_obtained") or 0
                    else:
                        row_val = r.get("pg_cgpa") or r.get("percentagecgpa_obtained") or 0
                    scores.append(float(row_val))
                
                if scores:
                    val = sum(scores) / len(scores)
        
        # Explicit dot notation fallback: table_field.column_name
        elif "." in field_name:
            table_field, child_field = field_name.split(".", 1)
            child_rows = applicant.get(table_field) or []
            if child_rows:
                scores = [getattr(r, child_field, 0) or 0 for r in child_rows]
                val = sum(scores) / len(scores)
        else:
            # Dynamic attribute lookup for main DocType fields
            val = getattr(applicant, field_name, 0) or 0

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
    Generates a Merit List for a specific Program Level.
    """
    # Check if a Merit List already exists
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

        # If already published, do not allow automatic re-generation via this service
        if existing_doc.status == "Published":
            return existing_doc

        # If status is "Generated" or "Draft", we allow re-generation
        # To do this, we must clear the old document
        if existing_doc.docstatus == 1:
            existing_doc.cancel()
            frappe.delete_doc("Merit List", existing_doc.name, ignore_permissions=True, force=True)
            frappe.db.commit()
        elif existing_doc.docstatus == 0:
            frappe.delete_doc("Merit List", existing_doc.name, ignore_permissions=True, force=True)
            frappe.db.commit()

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

    # Fetch applicants names only first to iterate and get full docs (to include child tables)
    applicant_names = frappe.get_all(
        "Eligibility Result",
        filters={
            "admission_cycle": cycle,
            "campus": campus,
            "program_level": program_level
        },
        pluck="name"
    )
    
    if not applicant_names:
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

    total_applicants = len(applicant_names)
    for i, name in enumerate(applicant_names):
        # Publish real progress to the frontend
        frappe.publish_progress(
            (i + 1) * 100 / total_applicants, 
            title=_("Generating Merit List"), 
            description=_("Processing applicant {0} of {1}").format(i + 1, total_applicants)
        )
        
        app = frappe.get_doc("Eligibility Result", name)
        total_score = calculate_merit_with_rule(app, rule)

        status = "Selected" if total_score >= rule.minimum_marks else "Rejected"

        merit.append("merit_applicants", {
            "applicant_id": app.applicant_id,
            "candidate_name": app.candidate_name,
            "program": app.program,
            "program_level": app.program_level,
            "hsc_percentage": app.get("hsc_percentage") or 0,
            "entrance_score": app.get("entrance_test_score") or 0,
            "interview_score": app.get("interview_score") or 0,
            "ug_cgpa": app.get("ug_cgpa") or 0,
            "pg_cgpa": app.get("pg_cgpa") or 0,
            "total_score": total_score,
            "status": status
        })

    if not merit.merit_applicants:
        frappe.throw(
            f"No applicants could be processed for Program Level '{program_level}'.",
            title="Empty Merit List"
        )

    _rank_applicants(merit.merit_applicants)
    
    # Sort child table rows by overall_rank so they appear in order in the UI
    merit.merit_applicants.sort(key=lambda x: x.overall_rank)
    for i, row in enumerate(merit.merit_applicants):
        row.idx = i + 1
        
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

    # merit.submit() removed as per request to keep it editable/non-submittable
    frappe.db.commit()
    return merit
