# Requirements — Scalable Admission Management System

## v1.0 Requirements (Phases 1–5) — COMPLETE

REQ-01: Admission Year with single active year enforcement
REQ-02: Admission Cycle with workflow type and date validation
REQ-03: Admission Round with deadlines and locking
REQ-04: Admission Stage Config with enable/disable and sequencing
REQ-05: Reservation Policy with legal mandate enforcement
REQ-06: CLAT Rank Import via CSV
REQ-07: Admission Audit Log — immutable RTI-compliant trail
REQ-08: Campus Program Offering — campus + program + cycle mapping
REQ-09: Campus Seat Matrix — seats per campus/program/category
REQ-10: Applicant Campus Preference — max 3 preferences per applicant
REQ-11: Merit List — generate and publish with locking
REQ-12: Applicant — full application form with all NLSIU fields
REQ-13: Applicant Document — SHA-256 checksum and verification
REQ-14: Application Form Config — versioned form configuration
REQ-15: Form Condition Rule — conditional field visibility
REQ-16: Admission Report Config — RTI and compliance reports
REQ-17: Admission Dashboard Config — live admin stats
REQ-18: Applicant Dashboard — web portal for applicants
REQ-19: Notification Service — status-based email notifications
REQ-20: Auto Draft Service — periodic draft save

---

## v2.0 Requirements (Phases 6–12) — IN PROGRESS

### Phase 6 — Generic Foundation

REQ-V2-01: Institution Settings DocType
  - Master configuration per partner deployment
  - Fields: institution_name, institution_code, compliance_mode
    (India/International/Both), enable_multi_campus, max_campus_preferences,
    default_currency, payment_gateway (Razorpay/PayU/Stripe/Offline Only),
    razorpay_key, payU_key, smtp_configured (read only), allow_self_configuration,
    onboarding_complete (read only), logo, portal_theme_color, support_email
  - One record per site. Singleton DocType.
  - Controls entire system behaviour via flags

REQ-V2-02: Exam Type Config DocType
  - Replaces hardcoded CLAT/NLSAT/PACE workflow_type Select field
  - Fields: exam_name, exam_code, exam_category
    (National/State/Institution-Own/Merit-Based/International),
    score_import_method (CSV Upload/API Integration/Manual Entry/Not Applicable),
    api_endpoint, api_auth_type (API Key/OAuth2/Basic), api_credentials (Password),
    csv_field_mapping (JSON), score_fields (Table → Exam Score Field),
    has_rank (Check), has_category_rank (Check), is_external (Check),
    validity_years (Int)
  - Partner creates one record per exam type they use
  - Supported exams: CLAT, JEE Main, NEET, CAT, NLSAT, GRE, GMAT, IELTS,
    State CET, Institution Merit

REQ-V2-03: Quota Policy DocType (replaces hardcoded Reservation Policy)
  - Fully generic. Partner creates any categories they need.
  - Parent fields: policy_name, institution (Link→Institution Settings),
    program (Link→Program), academic_year (Link→Admission Year),
    is_legal_mandate (Check — locks on submit), quota_entries (Table)
  - Child table — Quota Policy Entry:
    category_name, category_code, mandated_percentage (Float),
    mandated_seats (Int, read only — calculated), legal_reference,
    requires_certificate (Check), certificate_label,
    is_income_based (Check), is_disability_based (Check), is_domicile_based (Check)
  - Locks permanently on submit if is_legal_mandate = 1

REQ-V2-10: Campus Mode Toggle
  - Institution Settings flag: enable_multi_campus
  - OFF: campus field hidden throughout system, no campus preferences,
    seat matrix at program level, simplified dashboard
  - ON: full campus selection UI, applicant selects up to N preferences
    (configurable via max_campus_preferences), seat matrix per campus per program

REQ-V2-18: Update Admission Cycle
  - Replace hardcoded workflow_type Select with exam_type Link → Exam Type Config
  - All existing CLAT/NLSAT/PACE cycles migrate to Exam Type records
  - No data loss. Backward compatible.

### Phase 7 — Workflow Engine

REQ-V2-04: Admission Stage Template DocType
  - Partners build own admission flow by creating stage templates
  - Parent fields: template_name, institution (Link→Institution Settings),
    stages (Table → Stage Definition), is_default (Check),
    applicable_exam_type (Link → Exam Type Config)
  - Child table — Stage Definition:
    stage_name (Data — free text, partner names own stages),
    stage_type (Select: Application/Screening/Exam/Interview/Evaluation/
    Merit/Document/Fee/Enrollment — drives system behaviour),
    sequence (Int, Mandatory), is_mandatory (Check),
    is_enabled (Check, default 1), evaluation_config (Link → Evaluation Config),
    deadline_offset_days (Int), notify_applicant_on_entry (Check),
    notification_template (Link → Email Template Config),
    responsible_role (Link → Role), requires_approval_to_unlock (Check)
  - Drag-and-drop sequence reordering in UI
  - Stage Template drives Admission Stage Config (replaces hardcoded stage_name)

REQ-V2-05: Evaluation Config DocType
  - Generic evaluation framework for all interview and test formats
  - Fields: config_name, evaluation_type (Select: Panel Interview/Written Test/
    GD/Research Proposal/Portfolio Review/Automated Cutoff),
    scoring_components (Table → Score Component), min_evaluators (Int),
    max_evaluators (Int), allow_slot_booking (Check),
    slot_duration_minutes (Int), auto_shortlist_cutoff (Float),
    result_visibility (Select: Immediate/After All Complete/Admin Publishes)
  - Child table — Score Component: component_name, max_score, weightage (Float)

REQ-V2-12: Admission Cycle Deadline DocType
  - Dedicated deadline management at cycle level (gap from v1.0)
  - Fields: admission_cycle (Link), deadline_type (Select:
    Application/Evaluation/Interview/Offer/Acceptance/Payment),
    start_datetime (Datetime), end_datetime (Datetime), is_active (Check)
  - Validations: start < end, must fall within cycle dates,
    no overlapping deadlines of same type per cycle
  - Cannot edit after cycle is Active without Super Admin approval

REQ-V2-13: Admission Cycle Rule DocType
  - Cycle-level eligibility and screening rules (gap from v1.0)
  - Fields: admission_cycle (Link), rule_type (Select: submission_cutoff/
    modification_lock/evaluation_start_dependency/offer_validity_period),
    rule_value (Data), is_mandatory (Check)
  - Enforcement points: application submit, evaluation start, offer expiry

REQ-V2-16: validate_cycle_deadline() Utility
  - Central utility method: validate_cycle_deadline(action, cycle)
  - Actions: Apply, Edit Application, Evaluate, Interview, Offer, Accept
  - Called from: all DocType hooks, portal APIs, background jobs
  - Blocks action outside window with clear user-facing error message
  - Located in: admission/utils/deadline.py

REQ-V2-20: Update Admission Stage Config
  - Driven by Stage Template now instead of hardcoded stage_name Select
  - Links to Stage Definition from template
  - Preserves existing lock/unlock behaviour

### Phase 8 — Forms, Docs & Emails

REQ-V2-07: Document Requirement Config DocType
  - Partners define required documents per program and category combination
  - Parent fields: program (Link→Program), quota_category (Data — "All" or
    specific category code), document_requirements (Table)
  - Child table — Document Requirement Entry:
    document_name (Data, Mandatory), document_code (Data),
    is_mandatory (Check), allowed_formats (Data — e.g. pdf,jpg,png),
    max_size_mb (Float), verification_required (Check), help_text (Text)
  - Replaces hardcoded document types in Applicant Document

REQ-V2-08: Email Template Config DocType
  - Partners write own notification emails from UI
  - Replaces hardcoded email messages in events.py
  - Fields: template_name, trigger_event (Select: Application Submitted/
    Status Changed/Offer Sent/Document Rejected/Deadline Reminder/
    Interview Scheduled/Payment Confirmed), subject (Data),
    body (Text Editor), available_placeholders (Text, Read Only),
    is_active (Check), cc_roles (Table → CC Role)
  - Placeholders: {{candidate_name}}, {{program}}, {{campus}},
    {{application_id}}, {{status}}, {{deadline}}, {{offer_amount}}

REQ-V2-19: Update Applicant Document
  - Validate uploaded documents against Document Requirement Config
  - Enforce allowed_formats and max_size_mb from config
  - Show help_text from config to applicant during upload

### Phase 9 — Fees & Payments

REQ-V2-06: Fee Structure Config DocType
  - Fully configurable fee setup per program
  - Parent fields: program (Link→Program), academic_year (Link→Admission Year),
    fee_components (Table → Fee Component), payment_gateway
    (Select: Razorpay/PayU/Offline), allow_offline_payment (Check),
    waiver_policy (Table → Fee Waiver Rule)
  - Child table — Fee Component:
    fee_type (Select: Application/Acceptance/Seat Booking/Tuition/Other),
    label (Data), amount (Currency), due_at_stage (Link → Stage Definition),
    is_mandatory (Check), is_refundable (Check), refund_policy_text (Text)
  - Child table — Fee Waiver Rule:
    quota_category (Data), waiver_type (Select: Full/Percentage/Fixed),
    waiver_value (Float)
  - Razorpay + PayU integration
  - Offline payment with receipt upload

### Phase 10 — Merit & Seat Allocation

REQ-V2-15: Seat Allocation Engine
  - Preference-based automated seat allocation
  - Allocation order: Merit rank → Category → Preference order → Seat availability
  - Allocates first eligible preference, locks others
  - One seat per applicant global enforcement
  - One accepted offer only safeguard
  - Campus cut-off per campus + program + category
  - Applicant marked Not Eligible (Campus) if cut-off not met
  - Background job for allocation run
  - Transaction-safe atomic seat updates

REQ-V2-14: Campus Decision Log DocType
  - Multi-campus audit trail (gap from v1.0)
  - Fields: applicant (Link), campus (Link), action (Select:
    Preference Added/Preference Changed/Seat Allocated/Cut-off Applied/
    Offer Generated/Offer Accepted/Offer Rejected/Waitlisted),
    old_value (JSON), new_value (JSON), performed_by (Link→User), timestamp
  - Only active if enable_multi_campus = ON

### Phase 11 — Setup Wizard & Partner Onboarding

REQ-V2-09: Setup Wizard — 10-step onboarding for new partners
  - Step 1: Institution Profile → Institution Settings
  - Step 2: Campus Mode → Institution Settings + Company
  - Step 3: Exam Types → Exam Type Config
  - Step 4: Quota / Reservation → Quota Policy + Quota Policy Entry
  - Step 5: Admission Stages → Admission Stage Template + Stage Definition
  - Step 6: Document Requirements → Document Requirement Config
  - Step 7: Fee Structure → Fee Structure Config + Fee Component
  - Step 8: Email Templates → Email Template Config
  - Step 9: Application Form → Application Form Config + Form Condition Rule
  - Step 10: Review & Activate → Institution Settings (onboarding_complete = 1)
  - Validation checks before activation
  - Cannot go live until onboarding_complete = 1

REQ-V2-11: Exam Score Import Framework
  - CSV import flow: upload → read csv_field_mapping → validate → import → audit
  - API integration flow: configure endpoint → schedule/on-demand → map → audit
  - Retry mechanism for API failures
  - Credential rotation without code change
  - Audit log entry for every import

### Phase 12 — Compliance & Reporting

REQ-V2-17: Compliance Mode
  - compliance_mode = India: RTI audit export, NAAC/UGC report templates
  - compliance_mode = International: GDPR data export and deletion
  - compliance_mode = Both: all of the above
  - Custom report builder for admin
  - Real-time dashboard per institution
  - Data export: Excel and PDF
  - Compliance mode switching without data loss

---

## DocType Classification

### GENERIC (same structure, same engine logic for all partners)
Institution Settings, Admission Year, Admission Cycle (updated),
Admission Round, Admission Cycle Deadline (new), Admission Cycle Rule (new),
Admission Stage Config (updated), Campus Program Offering,
Campus Seat Matrix, Applicant (updated), Applicant Campus Preference,
Applicant Document (updated), Merit List, Admission Audit Log,
Campus Decision Log (optional), Admission Report Config,
Admission Dashboard Config

### CONFIGURABLE (same structure, partner fills data from UI)
Exam Type Config, Quota Policy, Quota Policy Entry,
Admission Stage Template, Stage Definition, Evaluation Config,
Score Component, Fee Structure Config, Fee Component,
Document Requirement Config, Document Requirement Entry,
Email Template Config, Application Form Config, Form Condition Rule

---

## Exam Score Integration

### CSV Import (CLAT, JEE, NEET, CAT, GRE, GMAT, IELTS, State CET)
1. Partner downloads file from exam body portal
2. Admin uploads CSV in Exam Score Import DocType
3. System reads csv_field_mapping from Exam Type Config
4. Maps CSV columns to system fields automatically
5. Validates: required fields, score range, applicant email match
6. Imports matched records. Reports unmatched rows.
7. Audit log entry created for every import.

### API Integration (JEE via NTA, GRE via ETS)
1. Partner configures api_endpoint, api_auth_type, api_credentials
2. System calls API on schedule or on-demand
3. Response mapped using score_fields configuration
4. Same validation and audit logic as CSV
5. API errors logged with retry mechanism
6. Credential rotation supported without code change

### Supported Exams
| Exam             | Category         | Import Method      | Score Fields                        |
|------------------|------------------|--------------------|-------------------------------------|
| CLAT             | National         | CSV from Consortium| AIR Rank, Category Rank, Total Score|
| JEE Main         | National         | CSV or API (NTA)   | Score, Percentile, Category Rank    |
| NEET             | National         | CSV from NTA       | Score, AIR Rank, Category Rank      |
| CAT              | National         | CSV from IIMs      | Overall Score, Section Scores, %ile |
| NLSAT            | Institution-Own  | Manual Entry       | Exam Score, Section Scores          |
| GRE              | International    | CSV or API (ETS)   | Verbal, Quant, AWA Scores           |
| GMAT             | International    | CSV                | Total Score, Section Scores         |
| IELTS            | International    | CSV                | Overall Band, Section Bands         |
| State CET        | State            | CSV                | Score, State Rank, Category Rank    |
| Institution Merit| Merit-Based      | Not Applicable     | Class XII %, UG %                   |

---

## Migration: NLSIU v1.0 → Generic v2.0

| Current (NLSIU-specific)                     | Change To (Generic)                     | Priority |
|----------------------------------------------|-----------------------------------------|----------|
| workflow_type = CLAT/NLSAT/PACE hardcoded    | exam_type = Link → Exam Type Config     | HIGH     |
| Reservation Policy with hardcoded categories | Quota Policy with configurable categories| HIGH    |
| Admission Stage Config hardcoded stage_name  | Stage Definition child table free text  | HIGH     |
| Hardcoded document types in Applicant Doc    | Document Requirement Config             | MEDIUM   |
| Hardcoded email messages in events.py        | Email Template Config DocType           | MEDIUM   |
| Hardcoded CLAT CSV field mapping in clat.py  | csv_field_mapping JSON in Exam Type Config| MEDIUM  |
| campus field always visible                  | Hidden when enable_multi_campus = 0     | LOW      |
| Applicant fixed fields only                  | Core fields + dynamic via Form Builder  | MEDIUM   |
