# Admission Workflow

## Overview

The admission workflow manages the complete process of admitting students into the institution. It encompasses application submission, verification, evaluation, and final admission decision.

## Workflow Stages

### 1. Application Submission
- Applicant submits admission application
- Application form collection and initial data entry
- Document submission and verification

### 2. Application Review
- Initial eligibility check
- Document verification
- Completeness validation

### 3. Assessment & Evaluation
- Merit evaluation
- Interview/Test assessment
- Qualification verification

### 4. Decision Making
- Merit ranking
- Admission decision approval
- Waitlist assignment if required

### 5. Admission Confirmation
- Admission letter generation
- Fee acceptance
- Registration completion

### 6. Enrollment
- Final confirmation
- Document collection
- Student account creation

## Key Actors

- **Applicant**: Submits application and documents
- **Admission Officer**: Reviews and processes applications
- **Evaluation Committee**: Assesses merit and qualifications
- **Admission Manager**: Approves final decisions
- **Finance Officer**: Processes fees and payments

## Workflow Diagram

```mermaid
graph TD
    A[Applicant] -->|Submit Application| B[Application Submitted]
    B --> C{Initial Review}
    C -->|Incomplete| D[Request Missing Documents]
    D --> B
    C -->|Complete| E[Move to Entrance Exam]
    
    E --> F[Document Verification]
    F --> G{Verification Status}
    G -->|Failed| H[Reject Application]
    G -->|Passed| I[Schedule Entrance Exam]
    
    I --> J[Merit Evaluation]
    J --> K[Interview/Test]
    K --> L[Score Compilation]
    
    L --> M{Evaluation Result}
    M -->|Merit Pass| N[Generate Admit Card]
    M -->|Merit Fail| O[Provisional Admission]
    
    N --> P{Approval}
    O --> P
    P -->|Approved| Q[Generate Admit Letter]
    P -->|Rejected| H
    
    Q --> R[Awaiting Confirmation]
    R --> S{Applicant Decision}
    S -->|Accept| T[Scholarship & Process Payment]
    S -->|Decline| U[Admission Cancelled]
    
    T --> V{Payment Status}
    V -->|Paid| W[Registration Confirmation]
    V -->|Pending| X[Send Payment Reminder]
    X --> T
    
    W --> Y[Create Student Account]
    Y --> Z[Enrollment Complete]
    
    H --> AA[Application Closed]
    U --> AA
    
    Z --> AB[Active Student]
    AA --> AC[Admission Process Ends]
```

## Status Transitions

| Current Status | Next Status | Condition |
|---|---|---|
| Draft | Application Submitted | Application form completed |
| Application Submitted | Under Review | Initial eligibility met |
| Under Review | Assessment | All documents verified |
| Assessment | Decision Pending | Assessment completed |
| Decision Pending | Admission Offered | Merit criteria met |
| Admission Offered | Confirmed | Applicant accepts offer |
| Confirmed | Registered | Payment received |
| Registered | Enrolled | Registration finalized |
| Under Review | Rejected | Eligibility failed |
| Any | Cancelled | Applicant withdraws |

## Related DocTypes

- **Applicant**: Stores applicant information
- **Admission Application**: Main admission form
- **Assessment**: Evaluation records
- **Admission Decision**: Final decision document
- **Admission Letter**: Generated offer letter
- **Student**: Final enrolled student record

## Notes

- Applicants can track their application status in real-time
- Automated notifications sent at each stage transition
- Documents must meet specified criteria for verification
- Merit evaluation follows institution's defined criteria
- Payment must be completed within specified timeframe
- Waitlist management for oversubscribed programs
