# Project State

## Current Milestone
v2.0 — Scalable Multi-Partner Admission Platform

## Current Position
- Phases 1–5: COMPLETE (NLSIU v1.0 build)
- Phase 6: NEXT — Generic Foundation
- Phases 7–12: PENDING

## Codebase Location
/home/bsoft/slcm/apps/slcm/slcm/admission/

## Module Name
Admission (all DocTypes use "module": "Admission")

## Key Architecture Decisions
- One Frappe site per institution
- Three-layer: Core Engine / Config Layer / Operational Layer
- Campus mode: enable_multi_campus flag in Institution Settings
- compliance_mode: India / International / Both
- All partner config from UI — zero code changes per partner
- exam_type replaces hardcoded workflow_type in Admission Cycle

## What Phase 6 Must Build
1. Institution Settings DocType (singleton)
2. Exam Type Config DocType
3. Exam Score Field (child table of Exam Type Config)
4. Quota Policy DocType
5. Quota Policy Entry (child table of Quota Policy)
6. Update Admission Cycle: add exam_type Link → Exam Type Config
7. admission/utils/institution.py utility

## NLSIU Migration Notes
- NLSIU keeps working throughout v2.0 migration
- Each phase migrates one set of hardcoded items to config
- Phase 6: NLSIU creates CLAT, NLSAT, PACE as Exam Type records
- Phase 6: NLSIU creates SC/ST/OBC/EWS/PwD/Karnataka as Quota Policy entries
- No data loss at any phase

## Open Issues
- bench migrate error on tabApplicant (data truncation) — resolved by clearing
  NULL values before migration
- Two admission modules existed (admission + admission_managment) — resolved
  by merging into admission module

## Recent Completions
- Full gap analysis: 66% alignment with user stories
- Architecture document: Scalable_Admission_Architecture.docx
- GSD planning files created from architecture document

## Next Action
Run: /gsd:plan-phase 6
Then: /gsd:execute-phase 6
