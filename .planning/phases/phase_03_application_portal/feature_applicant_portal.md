# Feature: Applicant Portal for Status Tracking & Communication
**Layer:** Operational

- **Applicant Dashboard Implementation:** Dashboard showing progress, stage-wise status, campus outcomes.
- **Campus & Stage-Aware Status Tracking:** Status updates per campus and stage.
- **Actionable Applicant Notifications:** Links for pay fee, book interview, upload document, accept offer.

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

**7. Applicant**
Fields (in this exact order):

Section: Application Info
- `application_id` (Data, Read Only, In List View)
- `naming_series` (Select, options: NLSIU-APP-.YYYY.-)
- `title` (Select, options: Mr. / Mrs. / Ms. / Dr. / Prof.)
- `application_type` (Select, Mandatory, options: CLAT / NLSAT / PACE)
- `program` (Link → Program, Mandatory)
- `campus` (Link → Company, Mandatory)
- `academic_year` (Link → Academic Year, Mandatory)
- `application_status` (Select, options: Draft / Submitted / Under Evaluation / Shortlisted / Interview Scheduled / Offered / Accepted / Rejected / Waitlisted)
- `amended_from` (Link → Applicant, Read Only)
- `rejected_reason` (Text, depends_on: eval:doc.application_status=='Rejected')

Section: Personal Details
- `candidate_photo` (Attach Image)
- `candidate_name` (Data, Mandatory, In List View)
- `email` (Data, Mandatory)
- `mobile_number` (Data, Mandatory)
- `alternate_contact` (Data)
- `gender` (Select, options: Male / Female / Other / Prefer not to say)
- `date_of_birth` (Date, Mandatory)
- `nationality` (Data)
- `religion` (Data)
- `id_proof` (Attach)
- `source_of_information` (Select, options: Social Media / Friend / School / Advertisement / Other)
- `please_mention` (Data, depends_on: eval:doc.source_of_information=='Other')
- `declaration_undertaking` (Check, Mandatory)
- `consent_third_party` (Check)

Section: Family Details
- `father_name` (Data)
- `father_email` (Data)
- `father_mobile` (Data)
- `father_occupation` (Data)
- `annual_house_hold_income` (Currency)
- `mother_name` (Data)
- `mother_email` (Data)
- `mother_mobile` (Data)
- `mother_occupation` (Data)

Section: Guardian Details
- `guardian_required` (Check)
- `guardian_name` (Data, depends_on: eval:doc.guardian_required==1)
- `guardian_mobile` (Data, depends_on: eval:doc.guardian_required==1)
- `guardian_email` (Data, depends_on: eval:doc.guardian_required==1)

Section: Correspondence Address
- `correspondence_address` (Text)
- `city` (Data)
- `state` (Data)
- `pincode` (Data)

Section: Class X Details
- `class_x_year_of_completion` (Int)
- `class_x_school` (Data)
- `class_x_board` (Data)
- `class_x_percentage` (Float)
- `class_x_cgpa` (Float)
- `class_x_marksheet` (Attach)

Section: Class XII Details
- `class_xii_exam_name` (Data)
- `class_xii_year_of_completion` (Int)
- `class_xii_school` (Data)
- `class_xii_board` (Data)
- `class_xii_percentage` (Float)
- `class_xii_cgpa` (Float)
- `class_xii_marksheet` (Attach)

Section: Higher Education
- `ug_degree_completion` (Select, options: Completed / Pursuing / Not Applicable)
- `ug_degree_details` (Text, depends_on: eval:doc.ug_degree_completion!='Not Applicable')
- `post_degree_work_experience` (Check)
- `years_of_work_experience` (Float, depends_on: eval:doc.post_degree_work_experience==1)

Section: Reservation Category
- `reservation_category` (Select, options: General / SC / ST / OBC / EWS / PwD / NRI / Karnataka Domicile)
- `ews` (Check, depends_on: eval:doc.reservation_category=='EWS')
- `ews_certificate` (Attach, mandatory_depends_on: eval:doc.ews==1)
- `caste_certificate` (Attach, mandatory_depends_on: eval:["SC","ST","OBC"].includes(doc.reservation_category))
- `pwd` (Check, depends_on: eval:doc.reservation_category=='PwD')
- `pwd_required_test` (Check, depends_on: eval:doc.pwd==1)
- `scribe_allotment` (Check, depends_on: eval:doc.pwd==1)
- `pwd_certificate` (Attach, mandatory_depends_on: eval:doc.pwd==1)

Section: Karnataka Category
- `karnataka_category` (Check)
- `ka_study_7_years` (Check, depends_on: eval:doc.karnataka_category==1)
- `ka_study_7_years_certificate` (Attach, depends_on: eval:doc.ka_study_7_years==1)
- `ka_defence_child` (Check, depends_on: eval:doc.karnataka_category==1)
- `ka_defence_certificate` (Attach, depends_on: eval:doc.ka_defence_child==1)
- `ka_govt_child` (Check, depends_on: eval:doc.karnataka_category==1)
- `ka_govt_certificate` (Attach, depends_on: eval:doc.ka_govt_child==1)
- `ka_ais_child` (Check, depends_on: eval:doc.karnataka_category==1)
- `ka_ais_certificate` (Attach, depends_on: eval:doc.ka_ais_child==1)
- `ka_capf_child` (Check, depends_on: eval:doc.karnataka_category==1)
- `ka_capf_certificate` (Attach, depends_on: eval:doc.ka_capf_child==1)

Section: Campus Preferences
- `first_preference` (Link → Company, Mandatory)
- `second_preference` (Link → Company)
- `third_preference` (Link → Company)

Section: Documents
- `cv` (Attach)

**Python Controller:**
```python
def validate(self):
    from frappe.utils import validate_email_address, getdate, date_diff, today
    if not validate_email_address(self.email):
        frappe.throw("Invalid email address")
    age = date_diff(today(), self.date_of_birth) / 365
    if age < 17:
        frappe.throw("Applicant must be at least 17 years old")
    if self.class_x_percentage and not (0 <= self.class_x_percentage <= 100):
        frappe.throw("Class X Percentage must be between 0 and 100")
    if self.class_xii_percentage and not (0 <= self.class_xii_percentage <= 100):
        frappe.throw("Class XII Percentage must be between 0 and 100")
    if self.reservation_category == "EWS" and not self.ews_certificate:
        frappe.throw("EWS Certificate is mandatory")
    if self.reservation_category in ["SC", "ST", "OBC"] and not self.caste_certificate:
        frappe.throw("Caste Certificate is mandatory")
    if self.reservation_category == "PwD" and not self.pwd_certificate:
        frappe.throw("PwD Certificate is mandatory")
    if not self.first_preference:
        frappe.throw("First Campus Preference is mandatory")

def before_save(self):
    if not self.application_id:
        self.application_id = frappe.generate_hash(length=8).upper()
    self.candidate_name = self.candidate_name

def on_submit(self):
    self.application_status = "Submitted"
    self.db_set("submitted_on", frappe.utils.now())

def on_cancel(self):
    self.application_status = "Draft"
```

**JS Behavior:**
```javascript
frappe.ui.form.on("Applicant", {
    refresh: function(frm) {
        // color-coded status badge:
        // Draft=grey, Submitted=blue, Shortlisted=orange,
        // Offered=green, Accepted=darkgreen, Rejected=red
        // show application completion progress bar
    },
    application_type: function(frm) {
        // CLAT: show info "CLAT Rank captured in Campus Preference"
        // NLSAT: show info "NLSAT Score captured after exam"
        // PACE: show info "Admission based on academic merit"
    },
    reservation_category: function(frm) {
        // clear all certificate fields on category change
    },
    guardian_required: function(frm) {
        // toggle guardian fields
    },
    declaration_undertaking: function(frm) {
        // if unchecked: msgprint warning "Declaration is mandatory for submission"
    }
});
```

---
### General Validations
- All `Link` fields must validate that the linked document exists and is active.
- All Date range fields must validate `start_date` < `end_date`.
- Audit log entry on every `submit` and `cancel`.