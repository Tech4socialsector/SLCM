import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime, now


class AdmissionCycle(Document):

    def validate(self):
        self._validate_single_active_cycle()
        self._validate_programs()

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
                    f"Cycle <b>{existing}</b> is already Active. "
                    f"Close it before activating this one."
                )

    def _validate_programs(self):
        """No duplicate program+campus combination in the same cycle."""
        seen = set()
        for row in (self.programs or []):
            key = (row.program, row.campus or "")
            if key in seen:
                frappe.throw(
                    f"Program <b>{row.program_name or row.program}</b> "
                    f"is added more than once in this cycle."
                )
            seen.add(key)

    def get_active_programs(self):
        """Returns list of active program rows in this cycle."""
        return [p for p in (self.programs or []) if p.is_active]

    def on_update(self):
        if not self.flags.in_reservation_sync:
            self._sync_reservation_policies()

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
