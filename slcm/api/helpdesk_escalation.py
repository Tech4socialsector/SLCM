"""
SLA-based auto-escalation for HD Ticket.

Scenario handled:
    Ticket assigned to Agent A in a Team. If Agent A does not send a first
    response within the team's configured "Escalate After (hours)" window,
    the ticket is automatically unassigned from Agent A and reassigned to
    the next available agent in the team's escalation order. Both agents
    (and, once the hop limit is hit, the team) are notified by email plus
    an in-app assignment notification for the new agent.

Entry point (wired in hooks.py `scheduler_events.cron`): run_sla_escalation()

Config lives on HD Team (see hd_team.json):
    enable_sla_escalation                       - master switch per team
    escalation_after_hours                      - grace period before a hop (supports
                                                   fractions for minutes, e.g. 0.5 = 30 min,
                                                   and multiples of 24 for days, e.g. 72 = 3 days)
    escalation_max_hops                         - stop auto-escalating after this many hops
    escalation_users                            - ordered override pool; falls back to `users`
    escalation_email_template_new_agent         - optional per-team override of DEFAULT_TEMPLATES
    escalation_email_template_previous_agent    - optional per-team override
    escalation_email_template_max_hops          - optional per-team override

State tracked on HD Ticket (see hd_ticket.json):
    escalation_count           - number of hops so far
    last_escalated_on          - timestamp of the last hop (grace period anchor)
    escalated_from_agents      - comma separated users already tried, so the
                                  rotation never reassigns back to someone
                                  who already missed the SLA on this ticket

Working-day awareness:
    The grace period only counts working days — Saturdays, Sundays, and any
    date covered by an Active "Holiday" entry in Institutional Calendar are
    skipped entirely. If the anchor (or any part of the grace window) falls
    on a non-working day, the clock pauses there and resumes counting from
    the start of the next working day. See `_add_working_minutes()`.
"""

import frappe
from frappe.utils import add_to_date, get_datetime, now_datetime

DEFAULT_TEMPLATES = {
    "new_agent": "HD Ticket SLA Escalation - New Agent",
    "previous_agent": "HD Ticket SLA Escalation - Previous Agent",
    "max_hops": "HD Ticket SLA Escalation - Max Hops Reached",
}

CANDIDATE_TICKET_FIELDS = [
    "name",
    "subject",
    "agent_group",
    "status",
    "creation",
    "first_responded_on",
    "escalation_count",
    "last_escalated_on",
    "escalated_from_agents",
    "_assign",
]


def run_sla_escalation():
    """Scheduled entry point — checks all open tickets against their team's SLA escalation config."""
    teams = frappe.get_all(
        "HD Team",
        filters={"enable_sla_escalation": 1, "disabled": 0},
        fields=[
            "name",
            "escalation_after_hours",
            "escalation_max_hops",
            "escalation_email_template_new_agent",
            "escalation_email_template_previous_agent",
            "escalation_email_template_max_hops",
        ],
    )
    if not teams:
        return

    for team in teams:
        _process_team(team)


def _process_team(team):
    """Resolve one team's config (grace period, hop limit, templates) and check all its open tickets."""
    grace_minutes = round(frappe.utils.flt(team.escalation_after_hours) * 60)
    if grace_minutes <= 0:
        grace_minutes = 60
    max_hops = frappe.utils.cint(team.escalation_max_hops) or 3
    templates = {
        "new_agent": team.escalation_email_template_new_agent or DEFAULT_TEMPLATES["new_agent"],
        "previous_agent": team.escalation_email_template_previous_agent or DEFAULT_TEMPLATES["previous_agent"],
        "max_hops": team.escalation_email_template_max_hops or DEFAULT_TEMPLATES["max_hops"],
    }

    tickets = frappe.get_all(
        "HD Ticket",
        filters={
            "agent_group": team.name,
            "status": "Open",
            "first_responded_on": ["is", "not set"],
        },
        fields=CANDIDATE_TICKET_FIELDS,
    )

    for ticket in tickets:
        try:
            _maybe_escalate_ticket(ticket, team.name, grace_minutes, max_hops, templates)
        except Exception:
            frappe.log_error(
                title="HD Ticket SLA Escalation failed",
                message=frappe.get_traceback(),
            )


def _maybe_escalate_ticket(ticket, team_name, grace_minutes, max_hops, templates):
    """Check if one ticket is overdue for a hop, then either escalate it or flag the hop limit."""
    anchor = ticket.last_escalated_on or ticket.creation
    due_at = _add_working_minutes(anchor, grace_minutes)
    if now_datetime() < due_at:
        return

    current_agent = _get_current_assignee(ticket.name)
    tried_users = _parse_tried_users(ticket.escalated_from_agents)
    if current_agent and current_agent not in tried_users:
        tried_users.append(current_agent)

    if ticket.escalation_count >= max_hops:
        _notify_hop_limit_reached(ticket, team_name, current_agent, max_hops, templates)
        return

    next_agent = _get_next_agent(team_name, tried_users)
    if not next_agent:
        # No more agents to escalate to — surface it instead of looping silently
        _notify_hop_limit_reached(ticket, team_name, current_agent, max_hops, templates)
        return

    _reassign(ticket, team_name, current_agent, next_agent, tried_users, grace_minutes, templates)


def _get_current_assignee(ticket_name):
    """Return the ticket's oldest open ToDo assignee, i.e. who the ticket is with right now."""
    assignees = frappe.get_all(
        "ToDo",
        filters={
            "reference_type": "HD Ticket",
            "reference_name": ticket_name,
            "status": "Open",
        },
        fields=["allocated_to"],
        order_by="creation asc",
        limit=1,
    )
    return assignees[0].allocated_to if assignees else None


def _parse_tried_users(raw):
    """Turn the ticket's stored 'escalated_from_agents' CSV back into a list of user emails."""
    if not raw:
        return []
    return [u.strip() for u in raw.split(",") if u.strip()]


def _format_grace_period(total_minutes):
    """Render a minute count as e.g. '3 days', '1 day 2 hr', or '45 min' for humans."""
    days, remainder_minutes = divmod(total_minutes, 24 * 60)
    hours, minutes = divmod(remainder_minutes, 60)

    parts = []
    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} hr")
    if minutes or not parts:
        parts.append(f"{minutes} min")
    return " ".join(parts)


def _is_working_day(date):
    """True if `date` is not a Saturday/Sunday and not covered by an Active
    'Holiday' entry in Institutional Calendar (same query pattern as
    Time Table.check_holiday_conflict)."""
    if date.weekday() >= 5:  # Monday=0 ... Saturday=5, Sunday=6
        return False

    holidays = frappe.get_all(
        "Institutional Calendar",
        filters={
            "entry_type": "Holiday",
            "start_date": ["<=", date],
            "end_date": [">=", date],
            "status": ["!=", "Inactive"],
            "docstatus": ["<", 2],
        },
        limit=1,
    )
    return not holidays


def _add_working_minutes(anchor, grace_minutes):
    """Return the datetime `grace_minutes` of working time after `anchor`,
    skipping weekends and Institutional Calendar holidays entirely — the
    clock pauses on a non-working day and resumes at midnight of the next
    working day, so a breach that starts (or spans) a holiday/weekend is
    only counted once real working time has elapsed."""
    from datetime import timedelta

    current = get_datetime(anchor)
    remaining = grace_minutes

    # Fast-forward past any non-working day the anchor itself falls on.
    while not _is_working_day(current.date()):
        current = get_datetime(current.date() + timedelta(days=1))

    while remaining > 0:
        end_of_day = get_datetime(current.date() + timedelta(days=1))
        minutes_left_today = (end_of_day - current).total_seconds() / 60

        if remaining <= minutes_left_today:
            return add_to_date(current, minutes=remaining)

        remaining -= minutes_left_today
        current = end_of_day
        while not _is_working_day(current.date()):
            current = get_datetime(current.date() + timedelta(days=1))

    return current


def _get_next_agent(team_name, tried_users):
    """Pick the next agent in the team's escalation pool who hasn't been tried yet."""
    override_field_exists = frappe.get_meta("HD Team").has_field("escalation_users")
    pool = []
    if override_field_exists:
        pool = frappe.get_all(
            "HD Team Member",
            filters={"parent": team_name, "parenttype": "HD Team", "parentfield": "escalation_users"},
            fields=["user"],
            order_by="idx asc",
            pluck="user",
        )

    if not pool:
        if override_field_exists:
            # The "escalation_users" field exists on the doctype but this team has no rows
            # under it (empty override, or every override user was removed) — surface it
            # loudly instead of silently escalating through the plain team list, which can
            # pick the wrong "next" agent relative to the order the admin actually intended.
            frappe.log_error(
                title="HD Ticket SLA Escalation: escalation order override empty",
                message=(
                    f"Team '{team_name}' has the Escalation Order override field, but no rows "
                    f"are configured under it. Falling back to the team's plain Users list."
                ),
            )
        else:
            # The field itself doesn't exist yet on this site (e.g. not yet added via
            # Customize Form) — this is expected until an admin adds it, but still worth
            # a one-time-per-cache-window note so it isn't mistaken for "working as configured".
            cache_key = f"hd_team_escalation_users_field_missing_notified:{team_name}"
            if not frappe.cache().get_value(cache_key):
                frappe.cache().set_value(cache_key, 1, expires_in_sec=6 * 60 * 60)
                frappe.log_error(
                    title="HD Ticket SLA Escalation: escalation order field not configured",
                    message=(
                        f"Team '{team_name}' has no 'escalation_users' field on HD Team yet, so "
                        f"the Escalation Order override is inactive and escalation is using the "
                        f"plain Users list order instead."
                    ),
                )
        pool = frappe.get_all(
            "HD Team Member",
            filters={"parent": team_name, "parenttype": "HD Team", "parentfield": "users"},
            fields=["user"],
            order_by="idx asc",
            pluck="user",
        )

    for user in pool:
        if not user or user in tried_users:
            continue
        if not frappe.db.get_value("User", user, "enabled"):
            # Disabled account (e.g. agent offboarded) — skip, don't stall escalation on them
            continue
        return user
    return None


def _reassign(ticket, team_name, old_agent, new_agent, tried_users, grace_minutes, templates):
    """Perform one hop: close the old ToDo, assign the new agent, bump ticket state, notify both agents."""
    from frappe.desk.form.assign_to import add as assign_to_add

    # Silently close the old ToDo — avoid assign_to.remove()/clear(), which fire a
    # noisy "assignment removed" notification to the outgoing agent.
    if old_agent:
        frappe.db.set_value(
            "ToDo",
            {
                "reference_type": "HD Ticket",
                "reference_name": ticket.name,
                "allocated_to": old_agent,
                "status": "Open",
            },
            "status",
            "Cancelled",
        )

    grace_label = _format_grace_period(grace_minutes)

    # assign_to.add() creates the ToDo and fires Frappe's standard in-app
    # assignment notification to the new agent.
    assign_to_add(
        {
            "doctype": "HD Ticket",
            "name": ticket.name,
            "assign_to": [new_agent],
            "description": f"Auto-reassigned: no first response within {grace_label}",
        },
        ignore_permissions=True,
    )

    escalation_count = frappe.utils.cint(ticket.escalation_count) + 1
    frappe.db.set_value(
        "HD Ticket",
        ticket.name,
        {
            "escalation_count": escalation_count,
            "last_escalated_on": now_datetime(),
            "escalated_from_agents": ",".join(tried_users),
        },
        update_modified=False,
    )

    _log_activity(
        ticket.name,
        f"auto-escalated from {old_agent or 'unassigned'} to {new_agent} (no first response in {grace_label})",
    )

    _send_escalation_emails(ticket, team_name, old_agent, new_agent, escalation_count, grace_label, templates)


def _notify_hop_limit_reached(ticket, team_name, current_agent, max_hops, templates):
    """Tell the team lead pool (+ current agent) that auto-escalation has stopped and needs a human."""
    # Throttle: only notify once per breach, not every scheduler tick.
    cache_key = f"hd_ticket_escalation_limit_notified:{ticket.name}"
    if frappe.cache().get_value(cache_key):
        return
    frappe.cache().set_value(cache_key, 1, expires_in_sec=6 * 60 * 60)

    recipients = _get_team_lead_recipients(team_name)
    if current_agent:
        recipients.append(current_agent)
    recipients = list(dict.fromkeys(r for r in recipients if r))
    if not recipients:
        return

    ticket_url = frappe.utils.get_url(f"/helpdesk/tickets/{ticket.name}")
    for recipient in recipients:
        _send_templated_email(
            templates["max_hops"],
            recipient,
            {
                "recipient_name": frappe.utils.get_fullname(recipient),
                "ticket_name": ticket.name,
                "ticket_subject": ticket.subject,
                "team_name": team_name,
                "escalation_count": ticket.escalation_count,
                "escalation_max_hops": max_hops,
                "ticket_url": ticket_url,
            },
        )

    _log_activity(ticket.name, f"SLA escalation limit ({max_hops}) reached — notified team for manual action")


def _get_team_lead_recipients(team_name):
    """Users with System Manager/Agent Manager style oversight — fall back to the full team pool."""
    return frappe.get_all(
        "HD Team Member",
        filters={"parent": team_name, "parenttype": "HD Team", "parentfield": "users"},
        pluck="user",
    )


def _send_escalation_emails(ticket, team_name, old_agent, new_agent, escalation_count, grace_label, templates):
    """Email the new agent (always) and the previous agent (if any) about this hop."""
    ticket_url = frappe.utils.get_url(f"/helpdesk/tickets/{ticket.name}")

    _send_templated_email(
        templates["new_agent"],
        new_agent,
        {
            "new_agent_name": frappe.utils.get_fullname(new_agent),
            "ticket_name": ticket.name,
            "ticket_subject": ticket.subject,
            "team_name": team_name,
            "previous_agent_name": frappe.utils.get_fullname(old_agent) if old_agent else "Unassigned",
            "escalation_count": escalation_count,
            "ticket_url": ticket_url,
        },
    )

    if old_agent:
        _send_templated_email(
            templates["previous_agent"],
            old_agent,
            {
                "previous_agent_name": frappe.utils.get_fullname(old_agent),
                "ticket_name": ticket.name,
                "ticket_subject": ticket.subject,
                "new_agent_name": frappe.utils.get_fullname(new_agent),
                "escalation_after": grace_label,
                "ticket_url": ticket_url,
            },
        )


def _send_templated_email(template_name, recipient, context):
    """Render an Email Template for one recipient and send it, logging (not raising) on any failure."""
    if not recipient:
        return
    if frappe.db.get_single_value("HD Settings", "skip_email_workflow"):
        return

    user = frappe.db.get_value("User", recipient, ["enabled", "email"], as_dict=True)
    if not user:
        frappe.log_error(
            title="HD Ticket SLA Escalation: recipient user not found",
            message=(
                f"'{recipient}' is not a valid User (check for a typo in the team's "
                f"Users / Escalation Order list). Skipped notification for template "
                f"'{template_name}'."
            ),
        )
        return
    if not user.enabled:
        frappe.log_error(
            title="HD Ticket SLA Escalation: recipient user disabled",
            message=f"User '{recipient}' is disabled. Skipped notification for template '{template_name}'.",
        )
        return
    if not user.email:
        frappe.log_error(
            title="HD Ticket SLA Escalation: recipient has no email",
            message=f"User '{recipient}' has no email set. Skipped notification for template '{template_name}'.",
        )
        return

    if not frappe.db.exists("Email Template", template_name):
        frappe.log_error(
            title="HD Ticket SLA Escalation: template not found",
            message=f"Email Template '{template_name}' does not exist, skipped notification to {recipient}",
        )
        return

    template = frappe.get_doc("Email Template", template_name)
    subject = frappe.render_template(template.subject, context)
    message = frappe.render_template(template.response, context)

    try:
        frappe.sendmail(
            recipients=user.email,
            subject=subject,
            message=message,
        )
    except Exception:
        frappe.log_error(
            title="HD Ticket SLA Escalation: sendmail failed",
            message=(
                f"Failed to send template '{template_name}' to '{recipient}'.\n\n"
                f"{frappe.get_traceback()}"
            ),
        )


def _log_activity(ticket_name, action):
    """Write a line to the ticket's Activity tab, reusing Helpdesk's own activity logger."""
    from helpdesk.helpdesk.doctype.hd_ticket_activity.hd_ticket_activity import log_ticket_activity

    log_ticket_activity(ticket_name, action)
