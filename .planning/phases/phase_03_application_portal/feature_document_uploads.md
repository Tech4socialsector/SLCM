# Feature: Secure Document Uploads
**Layer:** Regulatory

- **Secure Document Upload Framework:** Multiple document types with size, format, count validations.
- **Document Reuse Across Campuses:** Single-upload multi-campus reuse.
- **Role-Based Document Access:** Applicant=own only, Evaluator=assigned campus, Admin=all.
- **Document Locking & Integrity:** Lock post-submission, SHA checksum validation.

---
### DocTypes:

**8. Applicant Document**
- `applicant` (Link → Applicant, Mandatory)
- `document_type` (Select, options: 10th Certificate / 12th Certificate / Degree Certificate / CLAT Scorecard / NLSAT Scorecard / Category Certificate / PwD Certificate / Research Proposal / ID Proof / Photo)
- `file` (Attach, Mandatory)
- `checksum` (Data, Read Only)
- `is_verified` (Check)
- `verified_by` (Link → User, Read Only)
- `verified_on` (Datetime, Read Only)
- `is_locked` (Check, Read Only)
- `rejection_reason` (Text, depends_on: eval:doc.is_verified==0)
- `campus` (Link → Company)
- `admission_cycle` (Link → Admission Cycle)

**Validations:**
- `file` is mandatory
- `checksum` auto-generated SHA-256 on upload
- Cannot replace file if `is_locked` = 1
- PwD Certificate mandatory if applicant category = PwD
- Category Certificate mandatory if category = SC/ST/OBC/EWS
- Research Proposal mandatory if program = PhD

**Python Controller:**
```python
def before_save(self):
    if self.file:
        import hashlib
        file_doc = frappe.get_doc("File", {"file_url": self.file})
        file_content = file_doc.get_content()
        self.checksum = hashlib.sha256(file_content).hexdigest()

def validate(self):
    if self.is_locked:
        frappe.throw("Document is locked and cannot be modified")
    if not self.file:
        frappe.throw("File is mandatory")

def on_submit(self):
    self.is_locked = 1
    self.verified_on = frappe.utils.now()
```

---
### General Validations
- All `Link` fields must validate that the linked document exists and is active.
- All Date range fields must validate `start_date` < `end_date`.
- Audit log entry on every `submit` and `cancel`.
