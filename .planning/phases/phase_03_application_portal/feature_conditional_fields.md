# Feature: Conditional Fields & Dynamic Sections
**Layer:** Operational

- **Conditional Field Configuration:** Fields appear based on applicant responses.
- **Conditional Validation Rules:** Conditional fields become mandatory when triggered.
- **Applicant-Facing Logic & Messaging:** Clear indicators explaining why fields are required.

---
### DocTypes:

**10. Form Condition Rule**
- `form_config` (Link → Application Form Config, Mandatory)
- `trigger_field` (Data, Mandatory)
- `condition` (Select, Mandatory, options: = / != / > / < / is set / is not set)
- `trigger_value` (Data)
- `target_field` (Data, Mandatory)
- `action` (Select, Mandatory, options: Show / Hide / Mandatory / Read Only)
- `help_text` (Text)

**Validations:**
- `trigger_field` != `target_field`
- `condition` and `action` mandatory

---
### General Validations
- All `Link` fields must validate that the linked document exists and is active.
- All Date range fields must validate `start_date` < `end_date`.
- Audit log entry on every `submit` and `cancel`.
