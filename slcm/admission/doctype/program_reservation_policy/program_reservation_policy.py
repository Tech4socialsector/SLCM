import frappe
from frappe.model.document import Document
from slcm.admission.utils.institution import is_multi_campus_enabled


class ProgramReservationPolicy(Document):

    def validate(self):
        self._validate_campus_requirement()
        self._validate_unique_per_cycle_program()
        self._validate_unique_priorities()
        self._validate_seat_sum()
        self._recalculate_summary()
        self._update_row_available_seats()

    def _validate_campus_requirement(self):
        if is_multi_campus_enabled() and not (self.campus or "").strip():
            frappe.throw("Campus is mandatory when Multi Campus is enabled.")

    def _validate_unique_priorities(self):
        priorities = []
        for row in (self.categories or []):
            if row.priority in priorities:
                frappe.throw(
                    f"Duplicate priority <b>{row.priority}</b> found for category <b>{row.category_name}</b>. "
                    "Each category must have a unique priority to ensure deterministic seat allocation.",
                    title="Duplicate Priority"
                )
            priorities.append(row.priority)

    def _validate_unique_per_cycle_program(self):
        multi_campus = is_multi_campus_enabled()
        filters = {
            "admission_cycle": self.admission_cycle,
            "program": self.program,
            "name": ("!=", self.name or "")
        }
        if multi_campus:
            filters["campus"] = (self.campus or "").strip()

        existing = frappe.db.get_value(
            "Program Reservation Policy",
            filters,
            "name"
        )
        if existing:
            if multi_campus:
                frappe.throw(
                    f"A reservation policy already exists for "
                    f"<b>{self.program}</b> in <b>{self.admission_cycle}</b> for campus <b>{self.campus}</b>."
                )
            frappe.throw(
                f"A reservation policy already exists for "
                f"<b>{self.program}</b> in <b>{self.admission_cycle}</b>. "
                f"Only one policy per program per cycle is allowed."
            )

    def _validate_seat_sum(self):
        total_cat = sum(int(r.seats or 0) for r in (self.categories or []))
        if total_cat > int(self.total_seats or 0):
            frappe.throw(
                f"Category seats total (<b>{total_cat}</b>) exceeds "
                f"Total Seats (<b>{self.total_seats}</b>). Please reduce category seats."
            )

    def _recalculate_summary(self):
        self.total_allocated = sum(int(r.seats or 0) for r in (self.categories or []))
        self.total_filled = sum(int(r.filled_seats or 0) for r in (self.categories or []))
        self.total_available = max(
            0, int(self.total_seats or 0) - self.total_filled
        )

    def _update_row_available_seats(self):
        for row in (self.categories or []):
            row.available_seats = max(
                0, int(row.seats or 0) - int(row.filled_seats or 0)
            )

    def on_update(self):
        self._recalculate_summary()
        self._sync_link_to_cycle_program()
        frappe.cache().delete_key(f"program_status_{self.program}_{self.admission_cycle}")

    def after_insert(self):
        self._sync_link_to_cycle_program()

    def _sync_link_to_cycle_program(self):
        """
        After save, find the matching program row inside
        the Admission Cycle and write reservation_policy = self.name.
        This keeps the Admission Cycle Program row in sync automatically.
        """
        try:
            cycle_doc = frappe.get_doc("Admission Cycle", self.admission_cycle)
            changed = False
            multi_campus = is_multi_campus_enabled()
            for row in (cycle_doc.programs or []):
                row_campus = (row.campus or "").strip()
                doc_campus = (self.campus or "").strip()
                same_program = row.program == self.program
                same_campus = (row_campus == doc_campus) if multi_campus else True
                if same_program and same_campus:
                    if row.get("reservation_policy") != self.name:
                        row.reservation_policy = self.name
                        changed = True
                    break
            if changed:
                cycle_doc.flags.in_reservation_sync = True
                cycle_doc.flags.ignore_validate = True
                cycle_doc.save(ignore_permissions=True)
                frappe.db.commit()
        except Exception as e:
            frappe.log_error(
                f"ProgramReservationPolicy._sync_link_to_cycle_program: {e}",
                "Reservation Policy Sync"
            )

    def get_fee_for_category(self, category=None):
        """
        Returns the application_fee for a given category code or name.
        Falls back to first row (General) if no match.
        """
        rows = self.categories or []
        if not rows:
            return 0, "Application Fee", None

        if category:
            for row in rows:
                if row.category == category or row.category_name == category:
                    return (
                        row.application_fee or 0,
                        f"{row.category_name or 'Application'} Fee",
                        row.category or row.category_name
                    )

        # Fallback: first row
        first = rows[0]
        return (
            first.application_fee or 0,
            f"{first.category_name or 'Application'} Fee",
            first.category or first.category_name
        )
