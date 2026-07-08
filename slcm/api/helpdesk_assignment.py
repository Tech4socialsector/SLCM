"""
Auto-assign HD Ticket team based on the raising student's Programme and Year.

Logic (runs in before_validate on HD Ticket):
1. If ticket already has a team set (manually by agent), do nothing.
2. Identify the Student Master linked to raised_by email.
3. Read student's programme (→ Program link on Cohort) and current_year.
4. Look up the ticket type's year_wise_assignment_rules child table for a
   matching row: programme + current_year → team.
   - A rule with programme blank matches any programme.
   - A rule with current_year blank matches any year.
   - More-specific rules (both filled) take priority over partial ones.
5. If a match is found, set agent_group on the ticket.
"""

import frappe


def auto_assign_team_by_student(doc, method=None):
    """Hook: HD Ticket before_validate."""
    # Skip if team is already explicitly set
    if doc.agent_group:
        return

    if not doc.ticket_type:
        return

    # Fetch year_wise_assignment_rules from HD Ticket Type (custom child table)
    rules = frappe.get_all(
        "HD Ticket Type Assignment Rule",
        filters={"parent": doc.ticket_type, "parenttype": "HD Ticket Type"},
        fields=["programme", "current_year", "team"],
        order_by="idx asc",
    )

    if not rules:
        return

    student = _get_student(doc.raised_by)
    if not student:
        return

    student_programme = student.get("programme")   # Program name (via Cohort.program)
    student_year = student.get("current_year") or ""

    matched_team = _best_match(rules, student_programme, student_year)
    if matched_team:
        doc.agent_group = matched_team


def _get_student(email):
    """Return dict with programme and current_year for the student, or None."""
    if not email:
        return None

    # Student Master links Cohort in the 'programme' field; Cohort has 'program' and 'current_year'
    sm = frappe.db.get_value(
        "Student Master",
        {"user": email},
        ["programme", "current_year"],
        as_dict=True,
    )
    if not sm:
        sm = frappe.db.get_value(
            "Student Master",
            {"email": email},
            ["programme", "current_year"],
            as_dict=True,
        )
    if not sm:
        sm = frappe.db.get_value(
            "Student Master",
            {"official_email_id": email},
            ["programme", "current_year"],
            as_dict=True,
        )
    if not sm:
        return None

    # programme field on Student Master is a Link to Cohort.
    # We need the Program linked from that Cohort.
    cohort_programme = None
    if sm.get("programme"):
        cohort_programme = frappe.db.get_value("Batch", sm["programme"], "program")

    return {
        "programme": cohort_programme,
        "current_year": (sm.get("current_year") or "").strip(),
    }


def _best_match(rules, student_programme, student_year):
    """
    Return the HD Team name for the best matching rule.

    Priority (highest first):
      1. programme + current_year both match
      2. programme matches, current_year blank in rule
      3. programme blank in rule, current_year matches
      4. both blank in rule (catch-all)
    Returns None if no rule matches at all.
    """
    best_team = None
    best_score = -1

    for rule in rules:
        rule_prog = (rule.get("programme") or "").strip()
        rule_year = (rule.get("current_year") or "").strip()

        prog_match = (not rule_prog) or (rule_prog == (student_programme or ""))
        year_match = (not rule_year) or (rule_year == (student_year or ""))

        if not (prog_match and year_match):
            continue

        # Score: 2 pts for explicit programme match, 1 pt for explicit year match
        score = (2 if rule_prog else 0) + (1 if rule_year else 0)
        if score > best_score:
            best_score = score
            best_team = rule.get("team")

    return best_team
