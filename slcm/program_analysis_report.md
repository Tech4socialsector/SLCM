# Analysis Report: Impact of Renaming `Program` to `Programme` in SLCM

This report provides a detailed breakdown of where the `Program` doctype is used within the `slcm/slcm`, `slcm/admission`, and `slcm/www` modules, and outlines the impact of renaming it to `Programme`.

## 1. Executive Summary
| Impact Area | Count / Description | Remarks |
| :--- | :--- | :--- |
| **Direct Link Fields** | 70 fields across 70 DocTypes | Fields that explicitly reference options: `Program` |
| **Indirect DocType Links** | 34 fields across 30 DocTypes | Fields referencing related doctypes (e.g. `Program Course`, `Program Batch Section`) |
| **Portal / WWW References** | 36 files affected | HTML templates, Javascript handlers, and portal controllers |
| **Total Source Code Hits** | 1235 instances | In Python, JavaScript, HTML, and JSON files |

---

## 2. DocTypes Containing 'Program' in Their Name
If we rename `Program` to `Programme`, we must decide whether we also rename related doctypes for consistency. These doctypes will require database table renames, folder/file renames, and code updates:

### Doctypes to Rename (Current spelling: `program`):
#### in `slcm/slcm`:
- `program` &rarr; change to `programme`
- `program_batch_section` &rarr; change to `programme_batch_section`
- `program_course` &rarr; change to `programme_course`
- `program_enrollment` &rarr; change to `programme_enrollment`
- `program_enrollment_course` &rarr; change to `programme_enrollment_course`

#### in `slcm/admission`:
- `admission_cycle_program` &rarr; change to `admission_cycle_programme`
- `eligibility_program` &rarr; change to `eligibility_programme`
- `program_career_item` &rarr; change to `programme_career_item`
- `program_curriculum_item` &rarr; change to `programme_curriculum_item`
- `program_faculty_item` &rarr; change to `programme_faculty_item`
- `program_level` &rarr; change to `programme_level`
- `program_mapping` &rarr; change to `programme_mapping`
- `program_media` &rarr; change to `programme_media`
- `program_reservation_category` &rarr; change to `programme_reservation_category`
- `program_reservation_policy` &rarr; change to `programme_reservation_policy`
- `program_reservation_sub_quota` &rarr; change to `programme_reservation_sub_quota`

### Doctypes Already Using Correct Spelling (No Rename Required):
- `announcement_programme_target`
- `term_programme_mapping`

---

## 3. Direct References in DocType Definitions
These are standard DocTypes whose definitions contain Link/Table fields referencing `Program`. If `Program` is renamed to `Programme`, the `options` field in these doctype JSONs **must** be updated to `'Programme'`:

| DocType | Field Name | Field Type | Label | File Path |
| :--- | :--- | :--- | :--- | :--- |
| `Admission Application` | `program` | `Link` | Program | [admission_application.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/admission_application/admission_application.json) |
| `Admission Audit Log` | `program` | `Link` | Program | [admission_audit_log.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/admission_audit_log/admission_audit_log.json) |
| `Admission Cancellation` | `program` | `Link` | Programme | [admission_cancellation.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/admission_cancellation/admission_cancellation.json) |
| `Admission Cycle Program` | `program` | `Link` | Programme | [admission_cycle_program.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/admission_cycle_program/admission_cycle_program.json) |
| `Admission Report Config` | `program` | `Link` | Program | [admission_report_config.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/admission_report_config/admission_report_config.json) |
| `Applicant` | `program` | `Link` | Programme | [applicant.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/applicant/applicant.json) |
| `Applicant Campus Preference` | `program` | `Link` | Program | [applicant_campus_preference.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/applicant_campus_preference/applicant_campus_preference.json) |
| `Applicant Fee Assignment` | `program` | `Link` | Programme | [applicant_fee_assignment.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/applicant_fee_assignment/applicant_fee_assignment.json) |
| `Applicant Payment Receipt` | `program` | `Link` | Programme | [applicant_payment_receipt.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/applicant_payment_receipt/applicant_payment_receipt.json) |
| `Attendance Summary` | `programme` | `Link` | Programme | [attendance_summary.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/attendance_summary/attendance_summary.json) |
| `Bulk Fee Collection` | `programme` | `Link` | Programme | [bulk_fee_collection.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/bulk_fee_collection/bulk_fee_collection.json) |
| `Bulk Fee Structure Update` | `program` | `Link` | Program | [bulk_fee_structure_update.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/bulk_fee_structure_update/bulk_fee_structure_update.json) |
| `Campus Seat Matrix` | `program` | `Link` | Program | [campus_seat_matrix.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/campus_seat_matrix/campus_seat_matrix.json) |
| `Class Configuration` | `programme` | `Link` | Programme | [class_configuration.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/class_configuration/class_configuration.json) |
| `Class Schedule` | `programme` | `Link` | Program | [class_schedule.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/class_schedule/class_schedule.json) |
| `Cohort` | `program` | `Link` | Program | [cohort.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/cohort/cohort.json) |
| `Compliance Report Config` | `filter_by_program` | `Link` | Program | [compliance_report_config.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/compliance_report_config/compliance_report_config.json) |
| `Course List` | `program` | `Link` | Program | [course_list.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/course_list/course_list.json) |
| `Course Management` | `program` | `Link` | Programmes | [course_management.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/course_management/course_management.json) |
| `Course Offering` | `program` | `Link` | Program | [course_offering.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/course_offering/course_offering.json) |
| `Course Schedule` | `program` | `Link` | Program | [course_schedule.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/course_schedule/course_schedule.json) |
| `Course Scheduling Tool` | `program` | `Link` | Program | [course_scheduling_tool.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/course_scheduling_tool/course_scheduling_tool.json) |
| `Curriculum` | `program` | `Link` | Program | [curriculum.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/curriculum/curriculum.json) |
| `Document Requirement Config` | `program` | `Link` | Program | [document_requirement_config.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/document_requirement_config/document_requirement_config.json) |
| `Eligibility Allowed Degree` | `degree_name` | `Link` | Degree Name | [eligibility_allowed_degree.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/eligibility_allowed_degree/eligibility_allowed_degree.json) |
| `Eligibility Evaluation` | `program` | `Link` | Programme | [eligibility_evaluation.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/eligibility_evaluation/eligibility_evaluation.json) |
| `Eligibility Program` | `program` | `Link` | Program  | [eligibility_program.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/eligibility_program/eligibility_program.json) |
| `Eligibility Result` | `program` | `Link` | Programme | [eligibility_result.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/eligibility_result/eligibility_result.json) |
| `Eligibility Rule Mapping` | `program` | `Link` | Programme | [eligibility_rule_mapping.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/eligibility_rule_mapping/eligibility_rule_mapping.json) |
| `Entrance Test Applicant` | `program` | `Link` | Programme | [entrance_test_applicant.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/entrance_test_applicant/entrance_test_applicant.json) |
| `Entrance Test Details` | `programme` | `Link` | Programme | [entrance_test_details.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/entrance_test_details/entrance_test_details.json) |
| `Entrance Test Seat Allocation` | `program` | `Link` | Programme | [entrance_test_seat_allocation.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/entrance_test_seat_allocation/entrance_test_seat_allocation.json) |
| `Fee Demand` | `program` | `Link` | Program | [fee_demand.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/fee_demand/fee_demand.json) |
| `Fee Invoice` | `program` | `Link` | Program | [fee_invoice.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/fee_invoice/fee_invoice.json) |
| `Fee Payment` | `program` | `Link` | Program | [fee_payment.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/fee_payment/fee_payment.json) |
| `Fee Structure` | `program` | `Link` | Programme | [fee_structure.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/fee_structure/fee_structure.json) |
| `HD Ticket Type Assignment Rule` | `programme` | `Link` | Programme | [hd_ticket_type_assignment_rule.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/hd_ticket_type_assignment_rule/hd_ticket_type_assignment_rule.json) |
| `ID Card Generation Tool` | `program` | `Link` | Program | [id_card_generation_tool.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/id_card_generation_tool/id_card_generation_tool.json) |
| `Interview Applicant` | `program` | `Link` | Programme | [interview_applicant.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/interview_applicant/interview_applicant.json) |
| `Interview Seat Allocation` | `program` | `Link` | Programme | [interview_seat_allocation.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/interview_seat_allocation/interview_seat_allocation.json) |
| `Merit Generation` | `program` | `Link` | Programme | [merit_generation.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/merit_generation/merit_generation.json) |
| `Merit List` | `program` | `Link` | Programme | [merit_list.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/merit_list/merit_list.json) |
| `Merit List Applicant` | `program` | `Link` | Programme | [merit_list_applicant.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/merit_list_applicant/merit_list_applicant.json) |
| `Offer Letter` | `program` | `Link` | Programme | [offer_letter.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/offer_letter/offer_letter.json) |
| `Office Hours Group` | `program` | `Link` | Program | [office_hours_group.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/office_hours_group/office_hours_group.json) |
| `Parent Login Invite Tool` | `programme` | `Link` | Programme | [parent_login_invite_tool.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/parent_login_invite_tool/parent_login_invite_tool.json) |
| `Portal Announcement` | `target_program` | `Link` | Target Program | [portal_announcement.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/portal_announcement/portal_announcement.json) |
| `Program Batch Section` | `program` | `Link` | Program | [program_batch_section.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/program_batch_section/program_batch_section.json) |
| `Program Mapping` | `program` | `Link` | Program | [program_mapping.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/program_mapping/program_mapping.json) |
| `Program Reservation Policy` | `program` | `Link` | Programme | [program_reservation_policy.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/program_reservation_policy/program_reservation_policy.json) |
| `Promotion Policy` | `program` | `Link` | Program | [promotion_policy.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/promotion_policy/promotion_policy.json) |
| `Quota Policy` | `program` | `Link` | Program | [quota_policy.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/quota_policy/quota_policy.json) |
| `Reservation Policy` | `program` | `Link` | Program | [reservation_policy.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/reservation_policy/reservation_policy.json) |
| `Reservation Rule` | `program` | `Link` | Program | [reservation_rule.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/reservation_rule/reservation_rule.json) |
| `Scholarship Application` | `program` | `Link` | Programme | [scholarship_application.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/scholarship_application/scholarship_application.json) |
| `Scholarship Scheme Mapping` | `program` | `Link` | Programme | [scholarship_scheme_mapping.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/scholarship_scheme_mapping/scholarship_scheme_mapping.json) |
| `Scholarship Utilization` | `program` | `Link` | Program | [scholarship_utilization.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/scholarship_utilization/scholarship_utilization.json) |
| `Seat Allocation` | `program` | `Link` | Programme | [seat_allocation.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/seat_allocation/seat_allocation.json) |
| `Seat Selection Applicant` | `program` | `Link` | Program | [seat_selection_applicant.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/seat_selection_applicant/seat_selection_applicant.json) |
| `Shortlisting Merit Candidate` | `program` | `Link` | Program | [shortlisting_merit_candidate.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/shortlisting_merit_candidate/shortlisting_merit_candidate.json) |
| `Shortlisting Merit List` | `program` | `Link` | Program | [shortlisting_merit_list.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/shortlisting_merit_list/shortlisting_merit_list.json) |
| `Student Attendance` | `program` | `Link` | Program | [student_attendance.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/student_attendance/student_attendance.json) |
| `Student Enrollment` | `program` | `Link` | Program | [student_enrollment.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/student_enrollment/student_enrollment.json) |
| `Student Fee Assignment` | `program` | `Link` | Program | [student_fee_assignment.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/student_fee_assignment/student_fee_assignment.json) |
| `Student Group` | `program` | `Link` | Program | [student_group.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/student_group/student_group.json) |
| `Student Master` | `programme_of_study` | `Link` | Programme Of Study | [student_master.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/student_master/student_master.json) |
| `Student Placement Profile` | `programme` | `Link` | Program | [student_placement_profile.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/student_placement_profile/student_placement_profile.json) |
| `Term Programme Mapping` | `programme` | `Link` | Programme | [term_programme_mapping.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/term_programme_mapping/term_programme_mapping.json) |

---

## 4. Indirect References in DocType Definitions
These are fields pointing to other doctypes that contain the word 'Program' (e.g. `Program Batch Section`, `Program Reservation Policy`). These will only need to be updated if those associated doctypes are also renamed:

| DocType | Field Name | Field Type | Target Options | File Path |
| :--- | :--- | :--- | :--- | :--- |
| `Admission Cancellation` | `cancellation_reason_type` | `Select` | `Financial Issues\nMedical Reasons\nPersonal Reasons\nBetter Offer Elsewhere\nProgram Change\nOther` | [admission_cancellation.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/admission_cancellation/admission_cancellation.json) |
| `Admission Cycle` | `programs` | `Table` | `Admission Cycle Program` | [admission_cycle.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/admission_cycle/admission_cycle.json) |
| `Admission Cycle Program` | `reservation_policy` | `Link` | `Program Reservation Policy` | [admission_cycle_program.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/admission_cycle_program/admission_cycle_program.json) |
| `Admission Cycle Program` | `program_media` | `Link` | `Program Media` | [admission_cycle_program.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/admission_cycle_program/admission_cycle_program.json) |
| `Attendance Session` | `section` | `Link` | `Program Batch Section` | [attendance_session.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/attendance_session/attendance_session.json) |
| `Attendance Summary` | `section` | `Link` | `Program Batch Section` | [attendance_summary.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/attendance_summary/attendance_summary.json) |
| `Bulk Fee Structure Update` | `target_scope` | `Select` | `Programme\nProgram` | [bulk_fee_structure_update.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/bulk_fee_structure_update/bulk_fee_structure_update.json) |
| `Class Schedule` | `section` | `Link` | `Program Batch Section` | [class_schedule.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/class_schedule/class_schedule.json) |
| `Course Management` | `section` | `Link` | `Program Batch Section` | [course_management.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/course_management/course_management.json) |
| `Office Hours Group` | `section` | `Link` | `Program Batch Section` | [office_hours_group.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/office_hours_group/office_hours_group.json) |
| `Program Reservation Policy` | `categories` | `Table` | `Program Reservation Category` | [program_reservation_policy.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/program_reservation_policy/program_reservation_policy.json) |
| `Program Reservation Policy` | `horizontal_reservations` | `Table` | `Program Reservation Sub Quota` | [program_reservation_policy.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/program_reservation_policy/program_reservation_policy.json) |
| `Program Reservation Policy` | `compartmental_reservations` | `Table` | `Program Reservation Sub Quota` | [program_reservation_policy.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/program_reservation_policy/program_reservation_policy.json) |
| `Reservation Rule` | `program_category` | `Link` | `Program Level` | [reservation_rule.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/admission/doctype/reservation_rule/reservation_rule.json) |
| `Student Announcement` | `target_audience` | `Select` | `All Students\nSpecific Programme(s)\nSpecific Batch Year(s)\nSpecific Student(s)` | [student_announcement.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/student_announcement/student_announcement.json) |
| `Student Announcement` | `target_programmes` | `Table` | `Announcement Programme Target` | [student_announcement.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/student_announcement/student_announcement.json) |
| `Student Attendance` | `section` | `Link` | `Program Batch Section` | [student_attendance.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/student_attendance/student_attendance.json) |
| `Student Attendance Tool` | `section` | `Link` | `Program Batch Section` | [student_attendance_tool.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/student_attendance_tool/student_attendance_tool.json) |
| `Student Group` | `section` | `Link` | `Program Batch Section` | [student_group.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/student_group/student_group.json) |
| `Term Configuration` | `programme_mapping` | `Table` | `Term Programme Mapping` | [term_configuration.json](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/slcm/doctype/term_configuration/term_configuration.json) |

---

## 5. Web Portal & Public Website Impact (`slcm/www`)
The portal and applicant interface in `slcm/www` is highly dependent on the `Program` doctype for pre-filling applicant forms, showing program listings, and validating selections. Below are the key files and how they are affected:

### File: [slcm/www/admission-status.html](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/www/admission-status.html)
Contains **2** occurrences of 'Program'. Key lines:
- Line 139: `<!-- Program & Cycle Card -->`
- Line 174: `>{{ _("Program") }}</span>`

### File: [slcm/www/admission/index.html](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/www/admission/index.html)
Contains **14** occurrences of 'Program'. Key lines:
- Line 147: `/* ── Program detail specific styles ── */`
- Line 725: `/* Program card hover lift */`
- Line 779: `{# ── Programme detail view ── #}`
- Line 781: `{% set _name = prog_name or 'Program' %}`
- Line 808: `Programme Not Found`

### File: [slcm/www/admission/index.py](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/www/admission/index.py)
Contains **7** occurrences of 'Program'. Key lines:
- Line 20: `"Program", {"program_slug": slug}, "name")`
- Line 29: `prog = frappe.get_doc("Program", prog_name)`
- Line 61: `# Media (child table "media" / Program Media)`
- Line 299: `"Admission Cycle Program",`
- Line 493: `context.title = (context.prog_name or "Program") + " — Admissions"`

### File: [slcm/www/admission/program_detail.html](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/www/admission/program_detail.html)
Contains **6** occurrences of 'Program'. Key lines:
- Line 4: `{% block title %}{{ prog_name or 'Programme' }} — Admissions{% endblock %}`
- Line 414: `{% set _name = prog_name or 'Programme' %}`
- Line 443: `Programme Not Found`
- Line 451: `← Back to Programmes`
- Line 826: `About This Programme`

### File: [slcm/www/admission/program_detail.py](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/www/admission/program_detail.py)
Contains **6** occurrences of 'Program'. Key lines:
- Line 46: `# ── Fetch Program by slug ─────────────────────────────────────`
- Line 48: `"Program", {"program_slug": slug}, "name")`
- Line 57: `prog = frappe.get_doc("Program", prog_name)`
- Line 89: `# Media (child table "media" / Program Media)`
- Line 245: `"Admission Cycle Program",`

### File: [slcm/www/application_form/index.html](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/www/application_form/index.html)
Contains **60** occurrences of 'Program'. Key lines:
- Line 2099: `<!-- ═══ Program applied for (information only) ─── -->`
- Line 2517: `<label>Programme <span class="req">*</span></label>`
- Line 2523: `onchange="onProgramChange(this.value)"`
- Line 2536: `>Programme is required</span>`
- Line 2540: `<label>Programme level</label>`

### File: [slcm/www/application_form/index.py](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/www/application_form/index.py)
Contains **28** occurrences of 'Program'. Key lines:
- Line 77: `"""Ordered campus names from Admission Cycle Program. Website Users often lack Campus read permission."""`
- Line 83: `"Admission Cycle Program",`
- Line 119: `"Admission Cycle Program",`
- Line 191: `"Admission Cycle Program",`
- Line 209: `"Admission Cycle Program",`

### File: [slcm/www/application_form/start/index.py](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/www/application_form/start/index.py)
Contains **1** occurrences of 'Program'. Key lines:
- Line 28: `"Admission Cycle Program",`

### File: [slcm/www/eligibility/entrance_test_seat_allocation.html](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/www/eligibility/entrance_test_seat_allocation.html)
Contains **3** occurrences of 'Program'. Key lines:
- Line 261: `<div class="data-label">Programme</div>`
- Line 766: `<div class="t2">Admission to ${doc.program_level ? esc(doc.program_level) : "the Programme"} &nbsp;|&nbsp; ${val(doc.academic_year)} &nbsp;|&nbsp; ${val(doc.admission_cycle)}</div>`
- Line 779: `<tr><td class="lb">Programme Applied</td><td class="sp">:</td><td class="vl">${val(doc.program)}</td></tr>`

### File: [slcm/www/my-applications/index.py](file:///home/n_l_s_i_u/frappe-bench/apps/slcm/slcm/www/my-applications/index.py)
Contains **7** occurrences of 'Program'. Key lines:
- Line 105: `program_name = frappe.db.get_value("Program", o.get("program"), "program_name") or o.get("program") or ""`
- Line 212: `JOIN 'tabProgram' p ON a.program = p.name`
- Line 379: `applicant.program_name = frappe.db.get_value("Program", applicant.program, "program_name") or applicant.program`
- Line 431: `program_doc = frappe.get_doc("Program", applicant.program, ignore_permissions=True)`

---

## 6. Risk Assessment & Side Effects of Renaming

Renaming a core DocType like `Program` in Frappe is a high-impact operation. Here are the key risks and areas that will be affected:

1. **Database Schema & Migrations**:
   - Running `bench migrate` will rename the table `tabProgram` to `tabProgramme`.
   - **Data Preservation**: Frappe automatically renames the table, but any custom raw SQL queries (using `frappe.db.sql`) referencing `tabProgram` or `tabProgram Batch Section` will immediately fail.
   
2. **API & Controller Code**:
   - Any calls to `frappe.get_doc("Program", ...)` or `frappe.get_all("Program", ...)` will throw errors unless updated.
   - Any client-side AJAX calls querying `/api/resource/Program` will fail.

3. **Portal Slug / URL Routing**:
   - In `slcm/www/admission/index.py` and `program_detail.py`, URL routing is determined by slug fields inside the `Program` doctype. If the doctype name changes, the ORM queries fetching the document based on the slug will break.

4. **Fixtures, Custom Fields, and Client Scripts**:
   - Any property setters, custom fields, or client scripts exported as fixtures referencing `Program` will fail to apply or will create duplicate fields on the new doctype.

---

## 7. Recommended Execution Plan (If renaming in future)

If you decide to proceed with the rename, follow this sequence to minimize downtime:

1. **Global Text Search & Replace**: Update references in code files (`.py`, `.js`, `.html`, `.json`) first in a development branch.
2. **Rename files and folders**: Rename the folder `slcm/slcm/doctype/program` to `slcm/slcm/doctype/programme`, and rename files inside it (e.g. `program.py` to `programme.py`, `program.json` to `programme.json`).
3. **Update DocType JSON**: Inside `programme.json`, change `"name": "Program"` to `"name": "Programme"`.
4. **Update Linked DocTypes**: Update all DocType JSON definitions that link to `Program` by replacing `"options": "Program"` with `"options": "Programme"`.
5. **Database Migration**: Run `bench migrate` on a staging environment first to verify that Frappe handles the table rename and data migration successfully.
6. **Thorough testing of Portal**: Run end-to-end tests on the applicant portal (`slcm/www`) and the admissions process, as these pages interact heavily with the program list.
