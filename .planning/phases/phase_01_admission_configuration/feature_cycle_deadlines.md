# Feature: Cycle-Specific Deadlines & Rules
**Layer:** Operational

- **Configure Cycle-Level Deadlines:** Implement configuration to define and manage admission deadlines at the admission cycle level (application start/end, evaluation window, interview period, offer window).
- **Enforce Deadline-Based System Controls:** Implement system validations to enforce cycle-specific deadlines by blocking or allowing applicant and admin actions.
- **Eligibility & Screening:** Implement configurable admission rules at the cycle level.
- **Deadline Visibility & Status Management:** Implement real-time deadline visibility and cycle status indicators.
- **Audit & Change Tracking for Cycle Rules:** Implement audit logging for all changes made to cycle deadlines and rules.

---
### DocTypes:

**4. Admission Cycle Deadline**
- `admission_cycle` (Link → Admission Cycle)
- `application_start` (Date)
- `application_end` (Date)
- `evaluation_start` (Date)
- `evaluation_end` (Date)
- `interview_start` (Date)
- `interview_end` (Date)
- `offer_start` (Date)
- `offer_end` (Date)
- **Validations:**
  - `application_start` must be before `application_end`.
  - `evaluation_start` must be before `evaluation_end`.
  - `interview_start` must be before `interview_end`.
  - `offer_start` must be before `offer_end`.

---
### General Validations
- All `Link` fields must validate that the linked document exists and is active.
- All Date range fields must validate `start_date` < `end_date`.
- Audit log entry on every `submit` and `cancel`.
