import frappe
from frappe.model.document import Document
from slcm.admission.utils.institution import is_multi_campus_enabled


class ProgrammeReservationPolicy(Document):

    def validate(self):
        self._validate_campus_requirement()
        self._validate_unique_per_cycle_program()
        self._validate_unique_priorities()
        self._validate_percentage_sum()
        self._validate_seat_sum()
        self._update_row_available_seats()
        self._recalculate_summary()
        
        if not self.categories:
            self.matrix_html = ""

    def _validate_percentage_sum(self):
        total_percent = sum(float(r.percentage or 0) for r in (self.categories or []))
        if total_percent > 100.001:  # Allow a tiny epsilon for floating point precision
            frappe.throw(
                f"Total category percentage (<b>{total_percent}%</b>) cannot exceed <b>100%</b>. "
                "Please adjust the percentages.",
                title="Invalid Percentage"
            )

    def _validate_campus_requirement(self):
        pass

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
        filters = {
            "admission_cycle": self.admission_cycle,
            "program": self.program,
            "campus": self.campus,
            "name": ("!=", self.name or "")
        }

        existing = frappe.db.get_value(
            "Programme Reservation Policy",
            filters,
            "name"
        )
        if existing:
            campus_str = f" for campus <b>{self.campus}</b>" if self.campus else ""
            frappe.throw(
                f"A reservation policy already exists for "
                f"<b>{self.program}</b> in <b>{self.admission_cycle}</b>{campus_str}. "
                "Each program at a campus must have only one policy per cycle."
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
        # Sum Vertical filled seats for the total summary
        self.total_filled = sum(int(r.filled_seats or 0) for r in (self.categories or []))
        self.total_available = max(
            0, int(self.total_seats or 0) - self.total_filled
        )

    def _update_row_available_seats(self):
        # 1. Update Vertical
        for row in (self.categories or []):
            row.available_seats = max(0, int(row.seats or 0) - int(row.filled_seats or 0))
        
        # 2. Update Horizontal/Compartmental
        for sub_table in [self.horizontal_reservations, self.compartmental_reservations]:
            for row in (sub_table or []):
                row.available_seats = max(0, int(row.seats or 0) - int(row.filled_seats or 0))

    @frappe.whitelist()
    def refresh_availability(self):
        """
        Aggregates filled_seats from latest Seat Allocation 
        and updates all child tables.
        """
        sa_filters = {
            "admission_cycle": self.admission_cycle,
            "status": ["in", ["Published", "Allocated"]],
            "docstatus": ["<", 2]
        }
        
        sa_names = frappe.get_all("Seat Allocation", filters=sa_filters, pluck="name")
        if not sa_names:
            return False

        applicants = frappe.get_all("Seat Selection Applicant",
            filters={
                "program": self.program,
                "parent": ["in", sa_names]
            },
            fields=["allocated_category", "selection_status"]
        )
        
        allocated_statuses = ["Selected", "Offer Issued", "Offer Accepted", "Accepted", "Fee Paid"]
        filled_counts = {}
        
        for app in applicants:
            if app.selection_status in allocated_statuses:
                # Handle combined categories like "SC + Women"
                cats = [c.strip() for c in (app.allocated_category or "").split("+")]
                for c in cats:
                    if not c: continue
                    filled_counts[c] = filled_counts.get(c, 0) + 1

        # Update all tables
        for row in (self.categories or []):
            row.filled_seats = filled_counts.get(row.category_name, 0)
        
        for row in (self.horizontal_reservations or []):
            row.filled_seats = filled_counts.get(row.category_name, 0)

        for row in (self.compartmental_reservations or []):
            row.filled_seats = filled_counts.get(row.category_name, 0)

        self.save()
        return True

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
            for row in (cycle_doc.programs or []):
                same_program = row.program == self.program
                if same_program:
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
                f"ProgrammeReservationPolicy._sync_link_to_cycle_program: {e}",
                "Reservation Policy Sync"
            )

    def get_fee_for_category(self, category=None):
        """
        Returns the application_fee for a given category code or name.
        Falls back to first row (General) if no match.
        Note: Defaults to Indian fee as nationality context is not passed.
        """
        rows = self.categories or []
        if not rows:
            return 0, "Application Fee", None

        if category:
            for row in rows:
                if row.category == category or row.category_name == category:
                    return (
                        row.application_fee_for_indian or 0,
                        f"{row.category_name or 'Application'} Fee",
                        row.category or row.category_name
                    )

        # Fallback: first row
        first = rows[0]
        return (
            first.application_fee_for_indian or 0,
            f"{first.category_name or 'Application'} Fee",
            first.category or first.category_name
        )

    def render_matrix_html(self):
        import math
        vertical = self.categories or []
        horizontal = self.horizontal_reservations or []
        compartment = self.compartmental_reservations or []

        # Tally waitlist counts if seat allocation exists
        sa_filters = {
            "admission_cycle": self.admission_cycle,
            "program": self.program,
            "status": ["in", ["Published", "Allocated", "Draft"]],
            "docstatus": ["<", 2]
        }
        if self.campus:
            sa_filters["campus"] = self.campus

        sa_names = frappe.get_all("Seat Allocation", filters=sa_filters, pluck="name")
        
        waitlist_counts = {}
        total_waitlist_per_v = {}
        horizontal_waitlist = {}

        if sa_names:
            meta = frappe.get_meta("Seat Selection Applicant")
            has_new_fields = meta.has_field("vertical_category")
            
            fields = ["applicant_id", "allocated_category", "selection_status"]
            if has_new_fields:
                fields.extend(["vertical_category", "compartmentalized_category"])

            applicants = frappe.get_all("Seat Selection Applicant",
                filters={
                    "parent": ["in", sa_names],
                    "program": self.program,
                    "selection_status": "Waitlisted"
                },
                fields=fields
            )

            for app in applicants:
                v_cat = app.get("vertical_category")
                c_cat = app.get("compartmentalized_category")
                h_cats_str = app.get("horizontal_categories") or ""

                if not v_cat:
                    cats = [c.strip() for c in (app.get("allocated_category") or "").split("+") if c.strip()]
                    v_cat = cats[0] if cats else "General"
                
                v_key = (v_cat or "General").strip()
                c_key = (c_cat or "").strip()
                
                waitlist_counts[(v_key, c_key)] = waitlist_counts.get((v_key, c_key), 0) + 1
                total_waitlist_per_v[v_key] = total_waitlist_per_v.get(v_key, 0) + 1

                if h_cats_str:
                    for h_item in h_cats_str.split(","):
                        h_name = h_item.strip()
                        if h_name:
                            horizontal_waitlist[h_name] = horizontal_waitlist.get(h_name, 0) + 1

        def get_waitlisted(v_name, c_name=None):
            w_sum = 0
            for (v_k, c_k), count in waitlist_counts.items():
                v_match = (v_k == v_name) or (v_name and v_k and (v_k.lower() in v_name.lower() or v_name.lower() in v_k.lower()))
                if not v_match:
                    continue
                if c_name:
                    c_match = (c_k == c_name) or (c_name and c_k and (c_k.lower() in c_name.lower() or c_name.lower() in c_k.lower()))
                    if c_match:
                        w_sum += count
                else:
                    if not c_k:
                        w_sum += count
            return w_sum

        def get_waitlisted_v_total(v_name):
            w_sum = 0
            for v_k, count in total_waitlist_per_v.items():
                if (v_k == v_name) or (v_name and v_k and (v_k.lower() in v_name.lower() or v_name.lower() in v_k.lower())):
                    w_sum += count
            return w_sum

        def get_horizontal_waitlisted(h_name):
            h_sum = 0
            for h_k, count in horizontal_waitlist.items():
                if (h_k == h_name) or (h_name and h_k and (h_k.lower() in h_name.lower() or h_name.lower() in h_k.lower())):
                    h_sum += count
            return h_sum

        # Generate HTML Preview (Original Design layout matching Image 1)
        html = '<div style="overflow-x: auto;"><table class="table table-bordered table-hover" style="background-color: var(--card-bg); border-radius: 8px; text-align: center; vertical-align: middle;">'
        html += '<thead style="background-color: var(--gray-100);">'
        html += '<tr><th style="text-align: left;">Main Category</th><th>Total Seats</th>'
        
        # Header columns: Compartment first (split), then Horizontal last (common)
        for c in compartment:
            pct = f" ({int(c.percentage) if float(c.percentage or 0).is_integer() else c.percentage}%)" if c.percentage else ""
            c_name = c.category_name or ""
            c_label = f"{c_name}{pct}" if pct and pct.strip() not in c_name else c_name
            html += f'<th>{c_label}</th>'

        for h in horizontal:
            pct = f" ({int(h.percentage) if float(h.percentage or 0).is_integer() else h.percentage}%)" if h.percentage else ""
            h_name = h.category_name or ""
            h_label = f"{h_name}{pct}" if pct and pct.strip() not in h_name else h_name
            html += f'<th>{h_label}</th>'
            
        html += '</tr></thead><tbody>'
        
        num_vertical = len(vertical)
        
        for i, v in enumerate(vertical):
            v_total = v.seats or 0
            pct = f" ({int(v.percentage) if float(v.percentage or 0).is_integer() else v.percentage}%)" if v.percentage else ""
            v_name = v.category_name or ""
            v_label = f"{v_name}{pct}" if pct and pct.strip() not in v_name else v_name

            v_wait = (getattr(v, "waitlist_seats", 0) or 0) or get_waitlisted_v_total(v.category_name)
            v_cell = f"{v_total} ({v_wait})" if v_wait > 0 else f"{v_total}"

            html += '<tr>'
            html += f'<td style="text-align: left;"><strong>{v_label}</strong></td>'
            html += f'<td>{v_cell}</td>'
            
            # 1. Compartmentalized categories: Split per vertical category row (Show these first)
            for c in compartment:
                c_seats = math.floor(v_total * ((c.percentage or 0) / 100.0))
                comp_wait_row = 0
                if getattr(v, "compartmentalized_category", None) and (v.compartmentalized_category == c.category_name or c.category_name in (v.compartmentalized_category or "")):
                    comp_wait_row = getattr(v, "compartmentalized_waitlist_seats", 0) or 0
                if not comp_wait_row and getattr(c, "waitlist_seats", 0):
                    comp_wait_row = c.waitlist_seats or 0

                c_wait = comp_wait_row or get_waitlisted(v.category_name, c.category_name)
                c_cell = f"{c_seats} ({c_wait})" if c_wait > 0 else f"{c_seats}"
                html += f'<td>{c_cell}</td>'

            # 2. Horizontal categories: Only add the rowspan cells on the first row (Show these last)
            if i == 0:
                for h in horizontal:
                    h_wait = (getattr(h, "waitlist_seats", 0) or 0) or get_horizontal_waitlisted(h.category_name)
                    h_cell = f"{h.seats or 0} ({h_wait})" if h_wait > 0 else f"{h.seats or 0}"
                    html += f'<td rowspan="{num_vertical}" style="vertical-align: middle; font-weight: bold; font-size: 1.2em; color: var(--primary-color); background-color: var(--gray-50);">'
                    html += f'{h_cell}'
                    html += '</td>'
            
            html += '</tr>'
            
        if not vertical:
            html += '<tr><td colspan="100" style="text-align: center;">No vertical categories defined.</td></tr>'
            
        html += '</tbody></table></div>'
        return html


@frappe.whitelist()
def generate_matrices(name):
    doc = frappe.get_doc("Programme Reservation Policy", name)
    doc.vertical_matrix = []
    doc.horizontal_matrix = []
    doc.compartmentalised_matrix = []

    html = doc.render_matrix_html()
    doc.matrix_html = html
    doc.save()
    return html
