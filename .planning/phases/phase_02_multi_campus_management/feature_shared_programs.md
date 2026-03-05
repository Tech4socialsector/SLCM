# Feature: Shared Programs Across Multiple Campuses
**Layer:** Operational

- **Configure Shared Program Offerings:** Single program offered across multiple campuses.
- **Campus-Specific Constraints for Shared Programs:** Campus-level constraints for shared programs.
- **Applicant Visibility for Shared Programs:** Applicant-facing views for shared programs.

---
### DocTypes:

**8. Campus Program Offering**
- `campus` (Link → Company)
- `program` (Link → Program)
- `admission_cycle` (Link → Admission Cycle)
- `is_active` (Check)
- `max_intake` (Int)
- `eligibility_note` (Text)
- **Validations:**
  - No specific validations provided. General validations apply.

---
### General Validations
- All `Link` fields must validate that the linked document exists and is active.
- All Date range fields must validate `start_date` < `end_date`.
- Audit log entry on every `submit` and `cancel`.
