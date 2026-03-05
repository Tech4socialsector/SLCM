# Feature: Unified Applicant Pool Across Campuses
**Layer:** Operational

- **Implement Unified Applicant Pool:** Centralized applicant pool with single record per applicant.
- **Single Application Identity Across Campuses:** Unified application identifier.
- **Campus-Aware Application Mapping:** Mapping logic for applicant-campus associations.

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
