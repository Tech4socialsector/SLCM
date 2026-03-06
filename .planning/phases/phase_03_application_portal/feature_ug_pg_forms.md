# Feature: Configurable UG/PG Application Forms
**Layer:** Operational

- **Application Form Configuration Framework:** Configurable form framework without hardcoded fields.
- **Form Versioning by Admission Cycle:** Version control for application forms per cycle.
- **Program-Level Form Mapping:** Associate forms with programs, degrees, cycles.

---
### DocTypes:

**9. Application Form Config**
- `form_name` (Data, Mandatory)
- `degree_type` (Select, Mandatory, options: BA LLB / LLM / 3-Year LLB / MPP / PhD / MBL)
- `workflow_type` (Select, Mandatory, options: CLAT / NLSAT / PACE)
- `admission_cycle` (Link → Admission Cycle)
- `version` (Int, Read Only)
- `is_active` (Check)
- `fields` (Table → Application Form Field)

**Validations:**
- Cannot edit if submitted application uses this form
- `version` auto-increments on save
- `degree_type` and `workflow_type` mandatory

**10. Program Form Mapping**
- `program` (Link → Program)
- `form` (Link → Application Form Config)
- `admission_cycle` (Link → Admission Cycle)
- **Validations:**
  - No specific validations provided. General validations apply.

---
### General Validations
- All `Link` fields must validate that the linked document exists and is active.
- All Date range fields must validate `start_date` < `end_date`.
- Audit log entry on every `submit` and `cancel`.
