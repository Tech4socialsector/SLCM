import frappe
from collections import defaultdict


def calculate_merit_with_rule(applicant, rule):
    """
    Calculates total merit score based on a pre-fetched rule.
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


def generate_merit(cycle, campus):
    """
    Builds a Campus-Level Master Merit System (Optimized).
    """
    # 1. Check for Existing Merit List
    existing_list = frappe.db.get_value(
        "Merit List", 
        {"admission_cycle": cycle, "campus": campus},
        ["name", "docstatus"],
        as_dict=True
    )
    
    if existing_list:
        # Merit list already exists - return it instead of throwing error
        list_name = existing_list.get("name")
        existing_merit = frappe.get_doc("Merit List", list_name)
        
        # Return the existing merit list (this will be handled gracefully by the caller)
        return existing_merit

    # 2. Fetch Eligible Applicants
    applicants = frappe.get_all(
        "test Applicant",
        filters={"admission_cycle": cycle, "campus": campus},
        fields=[
            "name", "program", "category",
            "hsc_percentage", "entrance_percentage", "interview_percentage"
        ]
    )

    if not applicants:
        frappe.throw("No eligible applicants found.")

    # 🚀 3. Fetch Merit Rule for Campus/Cycle
    # -----------------------------------------
    mapping = frappe.get_value(
        "Merit Rule Mapping",
        filters={"admission_cycle": cycle, "campus": campus, "is_active": 1},
        fieldname="merit_rule"
    )
    
    if not mapping:
        frappe.throw(
            f"No active Merit Rule Mapping found for Campus '{campus}' and Admission Cycle '{cycle}'. "
            f"Please create a Merit Rule Mapping before generating the merit list.",
            title="Missing Merit Rule Mapping"
        )
    
    # Get the merit rule document
    rule = frappe.get_doc("Merit Rule", mapping)

    # 4. Create Merit List Document
    merit = frappe.new_doc("Merit List")
    merit.admission_cycle = cycle
    merit.campus = campus
    merit.generated_on = frappe.utils.now_datetime()
    merit.status = "Generated"

    # 5. Calculate Total Scores and Append
    for app in applicants:
        total_score = calculate_merit_with_rule(app, rule)

        merit.append("merit_applicants", {
            "applicant": app.name,
            "program": app.program,
            "category": app.category,
            "hsc_percentage": app.hsc_percentage,
            "entrance_percentage": app.entrance_percentage,
            "interview_percentage": app.interview_percentage,
            "total_score": total_score,
            "status": "Selected"
        })

    # 6. Validate Non-Empty Merit List
    if not merit.merit_applicants:
        frappe.throw(
            f"No applicants could be processed for Campus '{campus}' and Cycle '{cycle}'. "
            f"Please ensure Merit Rule Mappings exist for all applicant categories or at least a 'GEN' (General) rule.",
            title="Empty Merit List"
        )

    # 🏆 7. Ranking Logic with Tie-Breaking
    # -------------------------------------
    # Priority: Total Score > Entrance % > HSC % > Interview %
    sort_key = lambda x: (
        x.total_score,
        x.entrance_percentage or 0,
        x.hsc_percentage or 0,
        x.interview_percentage or 0
    )

    # A) Overall Rank
    merit.merit_applicants.sort(key=sort_key, reverse=True)
    for i, row in enumerate(merit.merit_applicants):
        row.overall_rank = i + 1

    # B) Program Rank
    program_groups = defaultdict(list)
    for row in merit.merit_applicants:
        program_groups[row.program].append(row)

    for group in program_groups.values():
        group.sort(key=sort_key, reverse=True)
        for i, row in enumerate(group):
            row.program_rank = i + 1

    # C) Category Rank
    category_groups = defaultdict(list)
    for row in merit.merit_applicants:
        category_groups[row.category].append(row)

    for group in category_groups.values():
        group.sort(key=sort_key, reverse=True)
        for i, row in enumerate(group):
            row.category_rank = i + 1

    # 8. Save and Submit
    merit.insert()
    merit.submit()
    return merit
