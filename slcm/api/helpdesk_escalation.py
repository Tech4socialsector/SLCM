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
"""

import frappe
from frappe.utils import add_to_date, now_datetime

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
    anchor = ticket.last_escalated_on or ticket.creation
    due_at = add_to_date(anchor, minutes=grace_minutes)
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


def _get_next_agent(team_name, tried_users):
    """Pick the next agent in the team's escalation pool who hasn't been tried yet."""
    pool = frappe.get_all(
        "HD Team Member",
        filters={"parent": team_name, "parenttype": "HD Team", "parentfield": "escalation_users"},
        fields=["user"],
        order_by="idx asc",
        pluck="user",
    )
    if not pool:
        pool = frappe.get_all(
            "HD Team Member",
            filters={"parent": team_name, "parenttype": "HD Team", "parentfield": "users"},
            fields=["user"],
            order_by="idx asc",
            pluck="user",
        )

    for user in pool:
        if user and user not in tried_users:
            return user
    return None


def _reassign(ticket, team_name, old_agent, new_agent, tried_users, grace_minutes, templates):
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
    if not recipient:
        return
    if frappe.db.get_single_value("HD Settings", "skip_email_workflow"):
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

    frappe.sendmail(
        recipients=recipient,
        subject=subject,
        message=message,
    )


def _log_activity(ticket_name, action):
    from helpdesk.helpdesk.doctype.hd_ticket_activity.hd_ticket_activity import log_ticket_activity

    log_ticket_activity(ticket_name, action)
