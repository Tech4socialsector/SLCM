# Feature: Applicant Campus Preference Handling
**Layer:** Operational

- **Capture Campus Preferences in Application:** Select and prioritize multiple campus preferences.
- **Validate Campus Preferences:** Only active campuses, enforce max preference limits.
- **Preference-Based Seat Allocation:** Preference-aware seat allocation logic.
- **Campus-Specific Status Tracking:** Per-campus application status tracking.

---
### DocTypes:

**6. Applicant Campus Preference**
- `applicant` (Link → Applicant)
- `admission_cycle` (Link → Admission Cycle)
- `campus` (Link → Company)
- `preference_order` (Int)
- `status` (Select) - Pending, Under Evaluation, Shortlisted, Offered, Accepted, Rejected
- **Validations:**
  - `preference_order` must be unique per applicant per cycle.
  - Maximum 3 campus preferences per applicant per cycle.
  - Cannot add preference if campus has no active offering.
  - Cannot change preference after application is submitted.

---
### General Validations
- All `Link` fields must validate that the linked document exists and is active.
- All Date range fields must validate `start_date` < `end_date`.
- Audit log entry on every `submit` and `cancel`.
