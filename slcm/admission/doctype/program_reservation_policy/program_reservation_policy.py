import frappe
from frappe.model.document import Document
from slcm.admission.utils.institution import is_multi_campus_enabled


class ProgramReservationPolicy(Document):

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
            "Program Reservation Policy",
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

@frappe.whitelist()
def generate_matrices(name):
    import math
    doc = frappe.get_doc("Program Reservation Policy", name)
    doc.vertical_matrix = []
    doc.horizontal_matrix = []
    doc.compartmentalised_matrix = []

    vertical = doc.categories or []
    horizontal = doc.horizontal_reservations or []
    compartment = doc.compartmental_reservations or []

    # Pre-calculate compartmentalized seats per vertical category using Largest Remainder Method
    comp_seats_allocated = {}  # keys: (comp_category_name, vertical_category_name)
    
    for c in compartment:
        c_percentage = c.percentage or 0.0
        # Overall target for this compartmental reservation
        overall_target = int(round(((doc.total_seats or 0) * c_percentage) / 100.0))
        
        c_map = {}
        remainders = []
        for v in vertical:
            v_seats = v.seats or 0
            exact_val = v_seats * (c_percentage / 100.0)
            base_val = int(exact_val)
            c_map[v.category_name] = base_val
            remainders.append({
                "category_name": v.category_name,
                "remainder": exact_val - base_val,
                "priority": v.priority or 9999
            })
            
        shortfall = overall_target - sum(c_map.values())
        if shortfall > 0:
            remainders.sort(key=lambda x: (-x["remainder"], x["priority"]))
            for j in range(min(shortfall, len(remainders))):
                c_map[remainders[j]["category_name"]] += 1
                
        for v in vertical:
            comp_seats_allocated[(c.category_name, v.category_name)] = c_map.get(v.category_name, 0)

    # Generate HTML Preview
    html = '<div style="overflow-x: auto;"><table class="table table-bordered table-hover" style="background-color: var(--card-bg); border-radius: 8px; text-align: center; vertical-align: middle;">'
    html += '<thead style="background-color: var(--gray-100);">'
    html += '<tr><th style="text-align: left;">Main Category</th><th>Total Seats</th>'
    
    # Header columns: Compartment first (split), then Horizontal last (common)
    for c in compartment:
        html += f'<th>{c.category_name}</th>'
    for h in horizontal:
        html += f'<th>{h.category_name}</th>'
        
    html += '</tr></thead><tbody>'
    
    num_vertical = len(vertical)
    
    for i, v in enumerate(vertical):
        v_total = v.seats or 0
        html += '<tr>'
        html += f'<td style="text-align: left;"><strong>{v.category_name}</strong></td>'
        html += f'<td>{v_total}</td>'
        
        # 1. Compartmentalized categories: Split per vertical category row (Show these first)
        for c in compartment:
            c_seats = comp_seats_allocated.get((c.category_name, v.category_name), 0)
            html += f'<td>{c_seats}</td>'

        # 2. Horizontal categories: Only add the rowspan cells on the first row (Show these last)
        if i == 0:
            for h in horizontal:
                html += f'<td rowspan="{num_vertical}" style="vertical-align: middle; font-weight: bold; font-size: 1.2em; color: var(--primary-color); background-color: var(--gray-50);">'
                html += f'{h.seats or 0}'
                html += '</td>'
        
        html += '</tr>'
        
    if not vertical:
        html += '<tr><td colspan="100" style="text-align: center;">No vertical categories defined.</td></tr>'
        
    html += '</tbody></table></div>'
    
    doc.matrix_html = html
    doc.save()
    return html
