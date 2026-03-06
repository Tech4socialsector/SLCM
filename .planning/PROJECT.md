# Scalable Admission Management System

## Product Vision

A fully configurable, partner-ready Admission Management Platform deployable
to any university worldwide. Each partner institution gets their own Frappe
site with a pre-built admission engine they can configure entirely from the
UI — no code changes required.

The core engine is generic. Everything institution-specific is configurable
data, not hardcoded logic.

## What Stays the Same Across All Partners (Core Engine)

- Core DocType structure and relationships
- Workflow engine and stage sequencing
- Merit generation and seat allocation engine
- Audit log and compliance framework
- Document integrity (SHA-256)
- Payment gateway integration
- Portal and dashboard framework

## What Each Partner Configures from UI (Zero Code)

- Reservation categories and percentages
- Exam types and score import methods
- Admission stages and their sequence
- Application form fields per program
- Document types required per category
- Fee structure and waiver rules
- Email templates and notification triggers

## Three-Layer Architecture

### Layer 1 — Core Engine
Generic DocTypes, workflow engine, merit generation, seat allocation,
audit framework, payment integration, portal framework.
Controlled by: Development team. Never changes per partner.

### Layer 2 — Config Layer
Institution Settings, Quota Policy, Exam Type Config, Stage Templates,
Form Builder, Fee Structure, Document Requirements, Email Templates.
Controlled by: Partner admin from UI. No code required. Setup Wizard guides.

### Layer 3 — Operational Layer
Admission Years, Cycles, Rounds, Applicants, Documents, Merit Lists,
Offers, Payments — day-to-day admission data.
Controlled by: Partner admission admin daily.

## Campus Mode

Controlled by single flag: Institution Settings → enable_multi_campus

- OFF = Single campus mode. Campus field hidden. Simplified UI.
- ON  = Multi campus mode. Full campus selection, preferences, seat matrix.

## Confirmed Requirements

| Area              | Requirement                                          | Decision                                              |
|-------------------|------------------------------------------------------|-------------------------------------------------------|
| Institution Type  | Universities only (v1.0)                             | Schema extensible for colleges in v2.0                |
| Deployment        | One Frappe site per institution                      | Isolated database. Partner owns their data            |
| Entrance Exams    | National, Own, Merit-based, State, International     | Generic Exam Type Config. Partner defines all         |
| Score Import      | Both CSV and API depending on exam                   | CSV upload or API endpoint per exam type              |
| Reservation       | Central govt + State + NRI + Custom + None           | Fully configurable Quota Policy                       |
| Workflow          | Fully configurable drag-and-drop stages              | Stage Template with drag-and-drop sequence in UI      |
| Campus Mode       | Single or Multi-campus, partner decides              | enable_multi_campus flag in Institution Settings      |
| Fee & Payment     | Application + Acceptance + Tuition, Razorpay/PayU    | Fee Structure Config per program. Gateway pluggable   |
| Evaluation        | Panel + Slot booking + Written + Research + Auto     | Evaluation Stage Config with type selector            |
| Partner Config    | All features configurable from UI                    | Zero-code onboarding. Setup Wizard                    |
| Compliance        | RTI + NAAC/UGC + GDPR + Reports + Dashboard          | compliance_mode = India / International / Both        |

## Version History

- v1.0: NLSIU-specific build (Phases 1-5) — COMPLETE
- v2.0: Multi-partner scalable platform (Phases 6-12) — IN PROGRESS
