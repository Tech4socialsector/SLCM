# Feature: Campus-Specific Seat Matrices & Cut-Offs
**Layer:** Operational

- **Configure Campus-Wise Seat Matrix:** Seat matrices per campus, program, category, round.
- **Enforce Campus-Specific Cut-Offs:** Cut-off rank/score enforcement during merit list generation.
- **Seat Matrix Validation & Locking:** Validate total seats and lock once allocation begins.

---
### DocTypes:

**7. Campus Seat Matrix**
- `campus` (Link → Company)
- `program` (Link → Program)
- `admission_cycle` (Link → Admission Cycle)
- `workflow_type` (Select) - CLAT, NLSAT, PACE
- `admission_round` (Link → Admission Round)
- `total_seats` (Int)
- `filled_seats` (Int)
- `is_locked` (Check)
- `reservation_breakdown` (Table → Reservation Category)

**Validations:**
- `filled_seats` cannot exceed `total_seats`
- `is_locked` blocks all edits
- Reservation breakdown must sum to `total_seats`

---
### General Validations
- All `Link` fields must validate that the linked document exists and is active.
- All Date range fields must validate `start_date` < `end_date`.
- Audit log entry on every `submit` and `cancel`.
