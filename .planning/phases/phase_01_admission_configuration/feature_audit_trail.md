# Feature: Audit Trail for Multi-Campus Decisions
**Layer:** Regulatory

- **Configure Admission Years:** As an Admission Admin, I want to configure admission years so that admission cycles are grouped correctly and only one active year is maintained without allowing deletion when linked.
- **Define Admission Cycles:** As an Admission Admin, I want to define admission cycles with enforced timelines and stages so that the admission process runs in a controlled and predictable manner.
- **Define Admission Rounds:** As an Admission Admin, I want to define multiple admission rounds within a cycle so that multi-round admissions are supported with enforced deadlines.

---
### DocTypes:

**1. Admission Year**
- `year` (Data) - format YYYY-YY
- `is_active` (Check)
- `description` (Text)

**Validations:**
- Only one active year allowed
- Format must be YYYY-YY
- Cannot delete if linked to Admission Cycle

**Python Controller:**
```python
def validate(self):
    import re
    if not re.match(r'^\d{4}-\d{2}$', self.year):
        frappe.throw("Year format must be YYYY-YY e.g. 2024-25")
    if self.is_active:
        active = frappe.db.get_value("Admission Year",
            {"is_active": 1, "name": ["!=", self.name]}, "name")
        if active:
            frappe.throw(f"Year {active} is already active. Deactivate it first.")

def on_trash(self):
    if frappe.db.exists("Admission Cycle", {"admission_year": self.name}):
        frappe.throw("Cannot delete: linked to Admission Cycles")
```

**UI:**
- Warning if activating when another is active
- Display active year in header

**2. Admission Cycle**
- `cycle_name` (Data)
- `admission_year` (Link → Admission Year)
- `workflow_type` (Select) - CLAT, NLSAT, PACE
- `program` (Link → Program)
- `degree_type` (Select) - BA LLB, LLM, 3-Year LLB, MPP, PhD, MBL
- `start_date` (Date)
- `end_date` (Date)
- `status` (Select) - Draft, Active, Closed
- `clat_consortium_code` (Data) - depends_on: workflow_type = CLAT
- `nlsat_exam_date` (Date) - depends_on: workflow_type = NLSAT
- `total_seats` (Int)
- `reservation_matrix` (Table → Reservation Category)

**Validations:**
- `start_date` < `end_date`
- `workflow_type` mandatory
- CLAT: `clat_consortium_code` required
- NLSAT: `nlsat_exam_date` required
- Status transition: Draft → Active → Closed only

**Python Controller:**
```python
def validate(self):
    if self.start_date >= self.end_date:
        frappe.throw("Start Date must be before End Date")
    if self.workflow_type == "CLAT" and not self.clat_consortium_code:
        frappe.throw("CLAT Consortium Code is required for CLAT workflow")
    if self.workflow_type == "NLSAT" and not self.nlsat_exam_date:
        frappe.throw("NLSAT Exam Date is required for NLSAT workflow")
    total = sum(row.total_seats for row in self.reservation_matrix)
    if total != self.total_seats:
        frappe.throw(f"Reservation category seats ({total}) must equal Total Seats ({self.total_seats})")

def before_save(self):
    from frappe.utils import today, getdate
    today_date = getdate(today())
    if getdate(self.start_date) > today_date:
        self.status = "Draft"
    elif getdate(self.start_date) <= today_date <= getdate(self.end_date):
        self.status = "Active"
    else:
        self.status = "Closed"
```

**3. Admission Round**
- `round_name` (Data)
- `admission_cycle` (Link → Admission Cycle)
- `round_number` (Int)
- `round_type` (Select) - Application, Counseling, Interview, Merit List, Document Verification, Fee Payment
- `application_start` (Datetime)
- `application_end` (Datetime)
- `status` (Select) - Upcoming, Active, Closed

**Validations:**
- `round_number` unique per cycle
- `application_end` > `application_start`
- Cannot create if cycle is Closed

---
### General Validations
- All `Link` fields must validate that the linked document exists and is active.
- All Date range fields must validate `start_date` < `end_date`.
- Audit log entry on every `submit` and `cancel`.
