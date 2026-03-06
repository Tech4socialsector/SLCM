# Roadmap — Scalable Admission Management System

## Milestone 1: NLSIU v1.0 — COMPLETE

### Phase 1: Regulatory Foundation ✅
DocTypes: Admission Year, Admission Cycle, Admission Round,
Admission Stage Config, Reservation Policy, Reservation Category,
CLAT Rank Import, Admission Audit Log
Requirements: REQ-01 to REQ-07

### Phase 2: Multi-Campus Management ✅
DocTypes: Campus Program Offering, Campus Seat Matrix,
Applicant Campus Preference, Merit List, Merit List Entry
Requirements: REQ-08 to REQ-11

### Phase 3: Application Portal & Forms ✅
DocTypes: Applicant, Applicant Document,
Application Form Config, Form Condition Rule
Requirements: REQ-12 to REQ-15

### Phase 4: Audit, Compliance & Publishing ✅
DocTypes: Admission Report Config
Utilities: regulatory.py (updated), events.py (updated)
Requirements: REQ-16

### Phase 5: Dashboard, Notifications & Recovery ✅
DocTypes: Admission Dashboard Config
Pages: applicant_dashboard
Utilities: notifications.py, auto_draft.py, error_handler.py
Requirements: REQ-17 to REQ-20

---

## Milestone 2: Scalable Multi-Partner Platform v2.0 — IN PROGRESS

### Phase 6: Generic Foundation 🔄
Sprint: 1 (Foundation)
Requirements: REQ-V2-01, REQ-V2-02, REQ-V2-03, REQ-V2-10, REQ-V2-18
Status: NOT STARTED

DocTypes to CREATE:
  - Institution Settings (singleton master config)
  - Exam Type Config (replaces hardcoded workflow_type)
  - Quota Policy (replaces hardcoded Reservation Policy)
  - Quota Policy Entry (child table)
  - Exam Score Field (child table of Exam Type Config)

DocTypes to UPDATE:
  - Admission Cycle: replace workflow_type Select with exam_type Link

Utilities to CREATE:
  - admission/utils/institution.py — get_institution_settings(), is_multi_campus()

Success Criteria:
  - Partner can create Institution Settings from UI
  - Partner can define any exam type (CLAT, JEE, custom) from UI
  - Partner can define any reservation categories from UI
  - Admission Cycle uses exam_type Link instead of hardcoded Select
  - enable_multi_campus flag hides/shows campus fields throughout system
  - NLSIU existing data continues to work

Dependencies: Phase 1-5 complete ✅

---

### Phase 7: Workflow Engine 🔄
Sprint: 2 (Workflow Engine)
Requirements: REQ-V2-04, REQ-V2-05, REQ-V2-12, REQ-V2-13, REQ-V2-16, REQ-V2-20
Status: NOT STARTED

DocTypes to CREATE:
  - Admission Stage Template (parent)
  - Stage Definition (child table)
  - Evaluation Config
  - Score Component (child table of Evaluation Config)
  - Admission Cycle Deadline
  - Admission Cycle Rule

DocTypes to UPDATE:
  - Admission Stage Config: driven by Stage Template instead of hardcoded Select

Utilities to CREATE:
  - admission/utils/deadline.py — validate_cycle_deadline(action, cycle)
  - admission/utils/stage.py — get_active_stages(), unlock_next_stage()

Success Criteria:
  - Partner can build any admission flow via drag-and-drop Stage Template
  - System blocks all actions outside configured deadline windows
  - Stage unlocks only when previous stage completes
  - Cycle-level rules enforced at submit/eval/offer
  - NLSIU stages migrated to Stage Template with same behaviour

Dependencies: Phase 6 complete

---

### Phase 8: Forms, Docs & Emails 🔄
Sprint: 3 (Forms & Docs)
Requirements: REQ-V2-07, REQ-V2-08, REQ-V2-19
Status: NOT STARTED

DocTypes to CREATE:
  - Document Requirement Config
  - Document Requirement Entry (child table)
  - Email Template Config
  - CC Role (child table of Email Template Config)
  - Application Form Field (child table of Application Form Config)

DocTypes to UPDATE:
  - Applicant Document: validate against Document Requirement Config
  - Application Form Config: add Application Form Field child table

Utilities to UPDATE:
  - admission/utils/documents.py — validate against Document Requirement Config
  - admission/events.py — use Email Template Config instead of hardcoded emails

Success Criteria:
  - Partner defines document requirements per program/category from UI
  - Partner writes all notification emails from UI with placeholders
  - Applicant Document enforces file type and size from config
  - Application Form Config supports dynamic field table
  - events.py reads Email Template Config instead of hardcoded strings
  - NLSIU documents and emails migrated to config with same behaviour

Dependencies: Phase 6-7 complete

---

### Phase 9: Fees & Payments 🔄
Sprint: 4 (Fees & Payments)
Requirements: REQ-V2-06
Status: NOT STARTED

DocTypes to CREATE:
  - Fee Structure Config
  - Fee Component (child table)
  - Fee Waiver Rule (child table)
  - Fee Payment (operational DocType)
  - Payment Receipt (operational DocType)

Utilities to CREATE:
  - admission/utils/fees.py — get_applicable_fee(), apply_waiver(), process_payment()
  - admission/utils/payment_gateway.py — razorpay_init(), payU_init(), verify_payment()

Success Criteria:
  - Partner defines all fee types from UI per program
  - Partner configures fee waivers per category from UI
  - Online payment via Razorpay or PayU works end to end
  - Offline payment with receipt upload works
  - Fee due at correct stage (linked via Stage Definition)
  - Payment receipt auto-generated on success

Dependencies: Phase 6-7 complete

---

### Phase 10: Merit & Seat Allocation 🔄
Sprint: 5 (Merit & Allocation)
Requirements: REQ-V2-15, REQ-V2-14
Status: NOT STARTED

DocTypes to CREATE:
  - Campus Decision Log (optional, only if multi-campus ON)

DocTypes to UPDATE:
  - Merit List: use Exam Type Config scores in calculation
  - Campus Seat Matrix: enforce cut-off per campus+program+category

Utilities to CREATE:
  - admission/utils/merit.py (rewrite) — generic_merit_generate(cycle, exam_type)
  - admission/utils/allocation.py — allocate_seats(), check_conflicts(),
    release_expired_offers(), promote_waitlist()

Background Jobs to CREATE:
  - allocation_engine — runs on demand and on schedule
  - conflict_checker — runs hourly to ensure one seat per applicant

Success Criteria:
  - Merit generated correctly for any exam type (CLAT/NLSAT/PACE/JEE/custom)
  - Seat allocation follows merit rank → category → preference → availability
  - Campus cut-offs enforced, Not Eligible (Campus) status set
  - One seat per applicant enforced globally
  - One accepted offer only enforced
  - Campus Decision Log captures every allocation event

Dependencies: Phase 6-9 complete

---

### Phase 11: Setup Wizard & Partner Onboarding 🔄
Sprint: 6 (Setup Wizard)
Requirements: REQ-V2-09, REQ-V2-11
Status: NOT STARTED

Pages to CREATE:
  - admission/page/setup_wizard/ — 10-step guided onboarding UI
  - admission/page/exam_score_import/ — CSV upload + API trigger UI

Utilities to CREATE:
  - admission/utils/wizard.py — validate_step(), complete_onboarding()
  - admission/utils/exam_import.py — csv_import(), api_sync(), map_scores()

Success Criteria:
  - New partner completes onboarding via 10-step wizard without developer help
  - All 10 steps covered: institution, campus, exams, quota, stages,
    documents, fees, emails, forms, activation
  - Validation runs before marking onboarding_complete = 1
  - CSV import works for all supported exam types
  - API sync works for JEE (NTA) and GRE (ETS) endpoints
  - Import audit log created for every import

Dependencies: Phase 6-10 complete

---

### Phase 12: Compliance & Reporting 🔄
Sprint: 7 (Compliance)
Requirements: REQ-V2-17
Status: NOT STARTED

DocTypes to CREATE:
  - Compliance Report Config
  - GDPR Data Request

Utilities to CREATE:
  - admission/utils/compliance.py — rti_export(), naac_report(),
    gdpr_export(), gdpr_delete()

Reports to CREATE:
  - RTI Response Export (India mode)
  - NAAC/UGC Admission Summary (India mode)
  - GDPR Data Export (International mode)
  - Custom Report Builder (All modes)

Success Criteria:
  - India compliance mode: RTI export, NAAC/UGC templates available
  - International mode: GDPR export and deletion available
  - Custom report builder allows admin to create own reports
  - All reports exportable as Excel and PDF
  - compliance_mode can be switched without data loss

Dependencies: Phase 6-11 complete

---

## Summary

| Phase | Sprint          | Requirements         | Status      |
|-------|-----------------|----------------------|-------------|
| 1     | —               | REQ-01 to 07         | ✅ COMPLETE |
| 2     | —               | REQ-08 to 11         | ✅ COMPLETE |
| 3     | —               | REQ-12 to 15         | ✅ COMPLETE |
| 4     | —               | REQ-16               | ✅ COMPLETE |
| 5     | —               | REQ-17 to 20         | ✅ COMPLETE |
| 6     | Foundation      | V2-01,02,03,10,18    | 🔄 NEXT     |
| 7     | Workflow Engine | V2-04,05,12,13,16,20 | ⏳ PENDING  |
| 8     | Forms/Docs/Email| V2-07,08,19          | ⏳ PENDING  |
| 9     | Fees & Payments | V2-06                | ⏳ PENDING  |
| 10    | Merit/Alloc     | V2-15,14             | ⏳ PENDING  |
| 11    | Setup Wizard    | V2-09,11             | ⏳ PENDING  |
| 12    | Compliance      | V2-17                | ⏳ PENDING  |
