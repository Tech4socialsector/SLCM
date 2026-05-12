import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import escape_html, getdate
from frappe.utils.data import format_date, get_link_to_form
from slcm.admission.utils.institution import is_multi_campus_enabled


def _overlap_rows_with_labels(overlaps):
    """Attach start_label / end_label (e.g. 12 Mar 2026) for API consumers."""
    out = []
    for row in overlaps:
        d = dict(row)
        d["start_label"] = (
            format_date(row.get("cycle_start_date"), "dd MMM yyyy")
            if row.get("cycle_start_date")
            else "—"
        )
        d["end_label"] = (
            format_date(row.get("cycle_end_date"), "dd MMM yyyy")
            if row.get("cycle_end_date")
            else "—"
        )
        out.append(d)
    return out


def get_overlapping_admission_cycles(start_date, end_date, exclude_name=None, status=None):
    """
    Return cycles whose [cycle_start_date, cycle_end_date] overlaps [start_date, end_date] (inclusive).
    Overlap iff existing_start <= end_date and existing_end >= start_date.
    """
    if not start_date or not end_date:
        return []
        
    start_d = getdate(start_date)
    end_d = getdate(end_date)
    
    if start_d > end_d:
        return []

    filters = {
        "cycle_start_date": ["<=", end_d],
        "cycle_end_date": [">=", start_d],
        "docstatus": ["<", 2],
    }
    
    if exclude_name:
        filters["name"] = ["!=", exclude_name]
    
    if status:
        filters["status"] = status
    else:
        # By default, only check against Draft/Active cycles
        filters["status"] = ["in", ["Draft", "Active"]]

    overlaps = frappe.get_all(
        "Admission Cycle",
        filters=filters,
        fields=["name", "cycle_name", "cycle_start_date", "cycle_end_date", "status"],
        order_by="cycle_start_date asc",
    )
    
    return overlaps


class AdmissionCycle(Document):

    def validate(self):
        self._validate_cycle_date_range()
        self._validate_application_date_range()
        self._validate_cycle_dates_no_overlap()
        self._validate_single_active_cycle()
        self._validate_programs()

    def on_submit(self):
        """Automatically set status to Active on submission."""
        if self.status != "Active":
            self.db_set("status", "Active")
            self.status = "Active" # Update local object for the rest of request

    def _validate_cycle_date_range(self):
        if not self.cycle_start_date or not self.cycle_end_date:
            return
        if getdate(self.cycle_start_date) > getdate(self.cycle_end_date):
            frappe.throw(
                _("Cycle Start Date cannot be after Cycle End Date."),
                title=_("Invalid dates"),
            )

    def _validate_application_date_range(self):
        if not self.application_start_date or not self.application_end_date:
            return
        app_start = getdate(self.application_start_date)
        app_end = getdate(self.application_end_date)
        cyc_start = getdate(self.cycle_start_date) if self.cycle_start_date else None
        cyc_end = getdate(self.cycle_end_date) if self.cycle_end_date else None

        if app_start > app_end:
            frappe.throw(
                _("Application Start Date cannot be after Application End Date."),
                title=_("Invalid dates"),
            )

        if cyc_start and app_start < cyc_start:
            frappe.throw(
                _("Application Start Date must be on or after Cycle Start Date."),
                title=_("Invalid dates"),
            )

        if cyc_end and app_end > cyc_end:
            frappe.throw(
                _("Application End Date must be on or before Cycle End Date."),
                title=_("Invalid dates"),
            )

    def _validate_cycle_dates_no_overlap(self):
        if self.status not in ["Draft", "Active"]:
            return
        if not self.cycle_start_date or not self.cycle_end_date:
            return

        conflicting_cycle = frappe.db.get_value(
            "Admission Cycle",
            {
                "status": ["in", ["Draft", "Active"]],
                "name": ("!=", self.name),
                "cycle_start_date": ("<=", self.cycle_end_date),
                "cycle_end_date": (">=", self.cycle_start_date),
                "docstatus": ("<", 2)
            },
            ["name", "cycle_name", "cycle_start_date", "cycle_end_date"],
            as_dict=True
        )

        if not conflicting_cycle:
            return

        sd = format_date(conflicting_cycle.cycle_start_date, "dd MMM yyyy") if conflicting_cycle.cycle_start_date else "—"
        ed = format_date(conflicting_cycle.cycle_end_date, "dd MMM yyyy") if conflicting_cycle.cycle_end_date else "—"
        label = escape_html(conflicting_cycle.cycle_name or conflicting_cycle.name or "")
        link = get_link_to_form("Admission Cycle", conflicting_cycle.name, label=label)

        msg = _("The selected date range overlaps with an existing Active admission cycle: <b>{0}</b> ({1} to {2})").format(
            link, sd, ed
        )
        msg += "<br><br>" + _("Please adjust the dates to avoid overlapping periods for multiple Active cycles.")
        
        frappe.throw(msg, title=_("Admission Cycle Dates Conflict"))


    def _validate_single_active_cycle(self):
        """Only one cycle can be Active at a time."""
        if self.status == "Active":
            existing = frappe.db.get_value(
                "Admission Cycle",
                {"status": "Active", "name": ("!=", self.name)},
                "cycle_name"
            )
            if existing:
                frappe.throw(
                    msg=_("Cycle <b>{0}</b> is already Active. Close it before activating this one.").format(existing),
                    title=_("Active Cycle Conflict"),
                    primary_action={
                        "label": _("Go to {0}").format(existing),
                        "client_action": "frappe.set_route",
                        "args": ["Form", "Admission Cycle", existing]
                    }
                )

    def _validate_programs(self):
        """Validate duplicate program rows with optional campus constraints."""
        multi_campus = is_multi_campus_enabled()
        seen = set()
        for row in (self.programs or []):
            campus = (row.campus or "").strip()
            if multi_campus and not campus:
                frappe.throw(
                    _("Campus is mandatory for Program <b>{0}</b> when Multi Campus is enabled.").format(
                        row.program_name or row.program or _("Unknown")
                    )
                )

            key = (row.program, campus) if multi_campus else (row.program,)
            if key in seen:
                if multi_campus:
                    frappe.throw(
                        _(
                            "Duplicate entry: Program <b>{0}</b> with Campus <b>{1}</b> is already added in this cycle."
                        ).format(row.program_name or row.program, campus)
                    )
                frappe.throw(
                    _("Duplicate entry: Program <b>{0}</b> is already added in this cycle.").format(
                        row.program_name or row.program
                    )
                )
            seen.add(key)

    def get_active_programs(self):
        """Returns list of active program rows in this cycle."""
        return [p for p in (self.programs or []) if p.is_active]

    def on_update(self):
        if not self.flags.in_reservation_sync:
            self._sync_reservation_policies()

    def before_cancel(self):
        if self.status not in ["Active", "Closed"]:
            frappe.throw(
                _("Only Active or Closed admission cycles can be cancelled. Current status: {0}").format(self.status),
                title=_("Invalid Status")
            )

    def on_cancel(self):
        self.status = "Closed"
        self.db_set("status", "Closed")

    def _sync_reservation_policies(self):
        """
        Sync total_seats from cycle programs to linked Reservation Policies.
        Recalculates category seats based on percentage if seats changed.
        """
        for row in (self.programs or []):
            if row.reservation_policy:
                try:
                    policy = frappe.get_doc("Program Reservation Policy", row.reservation_policy)
                    if int(policy.total_seats or 0) != int(row.seats or 0):
                        policy.total_seats = row.seats
                        # Recalculate child row seats proportionally
                        categories = policy.get("categories") or []
                        if len(categories) == 1:
                            # Single category: give it all seats even if percentage is missing
                            categories[0].seats = policy.total_seats
                            if not categories[0].percentage:
                                categories[0].percentage = 100.0
                        else:
                            for cat in categories:
                                if cat.percentage:
                                    cat.seats = int((policy.total_seats * cat.percentage) / 100)
                        
                        policy.flags.in_cycle_sync = True
                        policy.save(ignore_permissions=True)
                        
                        # Also update row application_count from policy summary if needed
                        # (Summary might have updated in policy.save via _recalculate_summary)
                        if row.application_count != policy.total_filled:
                            row.application_count = policy.total_filled
                            row.db_update()

                except Exception as e:
                    frappe.log_error(f"Failed to sync policy {row.reservation_policy}: {e}", "Admission Cycle")


@frappe.whitelist()
def reopen_cycle(name):
    """
    Reopen a Closed admission cycle.
    Sets status back to 'Active' and docstatus back to 1 (Submitted).
    Performs conflict checks (Single Active Cycle + Date Overlaps).
    """
    if not name:
        return {"success": False, "message": _("Missing Cycle Name")}

    doc = frappe.get_doc("Admission Cycle", name)
    if doc.status == "Active":
        return {"success": True, "message": _("Cycle is already Active")}

    # 1. Check for any other Active cycle
    existing_active = frappe.db.get_value(
        "Admission Cycle",
        {"status": "Active", "name": ("!=", doc.name)},
        "cycle_name"
    )
    if existing_active:
        return {
            "success": False,
            "message": _("Cycle <b>{0}</b> is already Active. Close it before reopening this one.").format(existing_active),
            "conflict_name": existing_active
        }

    # 2. Check for date overlaps with other Active cycles (though there should be none due to rule #1)
    overlaps = get_overlapping_admission_cycles(
        doc.cycle_start_date, doc.cycle_end_date, exclude_name=doc.name, status="Active"
    )
    if overlaps:
        return {
            "success": False,
            "message": _("Reopening this cycle would cause a date conflict with another active cycle.")
        }

    # Perform the reopen
    try:
        doc.db_set("status", "Active")
        doc.db_set("docstatus", 1)  # Restore to Submitted state
        return {"success": True, "message": _("Admission Cycle reopened successfully.")}
    except Exception as e:
        frappe.log_error(f"Reopen Admission Cycle fail: {e}", "Admission Cycle")
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def check_admission_cycle_date_overlap(name=None, cycle_start_date=None, cycle_end_date=None, status=None):
    """
    Desk client: check whether the given period overlaps other cycles.
    Returns { valid, overlaps: [{ name, cycle_name, cycle_start_date, cycle_end_date }], message }.
    """
    if not cycle_start_date or not cycle_end_date:
        return {"valid": True, "overlaps": [], "message": ""}

    try:
        start_d = getdate(cycle_start_date)
        end_d = getdate(cycle_end_date)
    except Exception:
        return {"valid": True, "overlaps": [], "message": ""}

    if start_d > end_d:
        return {
            "valid": False,
            "overlaps": [],
            "message": _("Cycle Start Date cannot be after Cycle End Date."),
        }

    overlaps = get_overlapping_admission_cycles(start_d, end_d, exclude_name=name or None, status=status)
    if not overlaps:
        return {"valid": True, "overlaps": [], "message": ""}

    enriched = _overlap_rows_with_labels(overlaps)
    return {
        "valid": False,
        "overlaps": enriched,
        "message": "",
    }
