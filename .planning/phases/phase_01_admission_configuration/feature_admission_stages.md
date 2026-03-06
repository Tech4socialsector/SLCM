# Feature: Configurable Enable/Disable of Admission Stages
**Layer:** Operational

- **Configure Admission Stages Per Cycle:** Implement configuration to enable or disable admission stages per cycle.
- **Stage Dependency & Sequencing Control:** Implement stage sequencing logic.
- **Conditional Stage Visibility:** Implement stage sequencing logic for skipping disabled stages.
- **Stage-Specific Rule Enforcement:** Implement validation rules for stage actions.
- **Stage Configuration Locking:** Implement configuration locking once a stage is live.
- **Audit Logging for Stage Configuration Changes:** Implement audit trails for enabling/disabling stages.

---
### DocTypes:

**5. Admission Stage Config**
- `admission_cycle` (Link → Admission Cycle)
- `stage_name` (Select) - Application Screening, CLAT Import, NLSAT Exam, Shortlisting, Interview, Policy Discussion, Research Evaluation, Merit List, Document Verification, Fee Payment, Enrollment
- `is_enabled` (Check)
- `sequence` (Int)
- `is_locked` (Check)
- `applicable_workflow` (Select) - CLAT, NLSAT, PACE, All
- `responsible_role` (Link → Role)

**Validations:**
- `sequence` unique per cycle
- Cannot disable if applicants in this stage
- Cannot edit if `is_locked` = 1

---
### General Validations
- All `Link` fields must validate that the linked document exists and is active.
- All Date range fields must validate `start_date` < `end_date`.
- Audit log entry on every `submit` and `cancel`.
