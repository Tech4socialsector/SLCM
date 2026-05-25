# Fees Management Module — Complete Testing Guide

**App:** SLCM v16 | **Module:** SLCM | **Workspace:** `/desk/fees-management`

---

## Module Overview

| Phase | Area | Key Doctypes |
|-------|------|--------------|
| 1 | Fee Configuration | Fee Component, Fee Structure |
| 2 | Fee Notification & Demand Generation | Fee Notification, Fee Demand, Fee Demand Generation Log |
| 3 | Fee Collection | Fee Payment, Fee Receipt, Bulk Fee Collection |
| 4 | Event-Triggered Demands | Hostel Allocation, Course Reregistration, Re Exam Registration, Revaluation Request, Deferral Order, Discipline Order, Hostel Fine, Convocation Registration |
| 5 | Waivers & Concessions | Fee Concession, Fee Refund, Student Credit Note |
| 6 | Reports | Defaulter List, Collection Summary, Fee Demand Register, Receipt Register |
| 7 | Automation & Monitoring | Scheduler (Overdue Marking, Reminders), Scheduled Job Log, Error Log |

**Pre-requisite for all tests:** At least one active Student Master and one Academic Year marked as default must exist.

---

## Phase 1 — Fee Configuration

### 1A. Fee Component

**Path:** Fees Management → Fee Configuration → Fee Component

#### Test 1: Create a new Fee Component

1. Click **New**
2. Fill:
   - Component Name: `Tuition Fee 2026`
   - Component Type: `Tuition Fee`
   - Amount: `50000`
3. Save
4. **Expected:** Saved without error. Appears in Fee Component list.

#### Test 2: Component Type options

1. Open any Fee Component → click the Component Type field
2. **Expected:** Dropdown includes all types:
   - Standard: Tuition Fee, Library Fee, Lab Fee, Examination Fee, Hostel Fee, Transport Fee
   - Admission: Admission Fee, Application Fee, Re-admission Fee
   - Event: Revaluation Fee, Convocation Fee, Re-registration Tuition Fee
   - Special: Issue of Certificates, Provisional Degree Certificate, Objection Fee
   - Fine: Fine - Disciplinary, Fine - Hostel, Gap Year Fee
   - Other types as listed

#### Test 3: Missing required fields

1. Click **New**, leave Component Name blank
2. Click **Save**
3. **Expected:** Frappe throws mandatory field error.

---

### 1B. Fee Structure

**Path:** Fees Management → Fee Configuration → Fee Structure

#### Test 4: Create a Fee Structure

1. Click **New**
2. Fill:
   - Title: `BA LLB 2026-27 Tuition`
   - Academic Year: `2026-27`
   - Demand Type: `Academic`
   - Program Level: `BA LLB` (or relevant)
   - Batch Year: `2024`
   - Status: `Active`
   - Total Amount: `50000`
   - Due Offset Days: `30`
   - Auto Generate Demand: ✓ checked
3. Save
4. **Expected:** Saved. Status shows Active.

#### Test 5: Hostel Fee Structure

1. Create a Fee Structure with Demand Type = `Hostel`
2. **Expected:** Saved. This structure will be picked up when a Hostel Allocation is created for a student.

---

## Phase 2 — Fee Notification & Demand Generation

### 2A. Fee Notification

**Path:** Fees Management → Fee Configuration → Fee Notification

#### Test 6: Create and Publish Fee Notification

1. Click **New**
2. Fill:
   - Title: `Annual Fee — 2026-27`
   - Academic Year: `2026-27`
   - Issued Date: today
   - Effective From: today or future date
3. In the **Components** child table, add rows:
   - Fee Component: `Tuition Fee 2026`, Batch Year: `2024`, Program Level: `BA LLB`, Amount: `50000`
   - Fee Component: `Library Fee`, Batch Year: `2024`, Program Level: `BA LLB`, Amount: `5000`
4. Click **Save**
5. Click the **Publish** button
6. **Expected:** Status changes to `Published`. Success alert shown.

#### Test 7: Duplicate component validation

1. In the Components table, add the same Fee Component + Batch Year + Program Level twice
2. Click Save
3. **Expected:** Error — "Duplicate entry for Fee Component..."

#### Test 8: Effective From before Issued Date

1. Set Effective From to a date earlier than Issued Date
2. Save
3. **Expected:** Error — "Effective From cannot be earlier than Issued Date."

---

### 2B. Fee Demand Generation

**Path:** Fee Notification → click **Generate Demands** button

#### Test 9: Generate demands from notification

1. Open a Published Fee Notification
2. Click **Generate Demands**
3. **Expected:** Background job enqueued. Wait ~30 seconds.
4. Go to **Fee Demand Generation Log** → open the latest log
5. **Expected:** Log shows:
   - Status: `Completed`
   - Total Students, Success Count, Skipped Count, Error Count filled
   - Result Rows shows each student with status Created/Skipped/Error
6. Go to **All Fee Demands**
7. **Expected:** New demands exist for each eligible student with status `Pending`

#### Test 10: Idempotency — run Generate Demands again

1. Click **Generate Demands** on the same notification again
2. Wait for the job to finish
3. Open the new Generation Log
4. **Expected:** All rows show status `Skipped` — "Demand already exists". No duplicate demands created.

#### Test 11: Fee Demand fields

1. Open any created Fee Demand
2. **Expected:**
   - Original Amount = amount from notification
   - Net Payable = Original Amount − Waiver Amount (0 initially)
   - Outstanding Amount = Net Payable (nothing paid)
   - Status = `Pending`
   - Trigger Ref Doctype = `Fee Notification`

---

## Phase 3 — Fee Collection

### 3A. Fee Payment

**Path:** Fees Management → Collections & Receipts → Fee Payment

#### Test 12: Create a Fee Payment (single demand)

1. Click **New**
2. Fill:
   - Student: pick any student with a Pending demand
   - Payment Date: today
   - Payment Mode: `Cash`
3. In the **Fee Demands** child table, click **Add Row**:
   - Fee Demand: pick the student's pending demand (demand name auto-filters to that student)
   - Amount Allocated: enter the outstanding amount (e.g. `50000`)
4. Total Payment Amount auto-fills
5. Click **Save** → **Submit**
6. **Expected:**
   - Payment status → `Submitted`
   - Fee Demand status → `Paid`
   - Fee Receipt auto-created and linked in the `Receipt` field
   - Click the receipt link → Receipt opens with all details filled

#### Test 13: Over-allocation validation

1. Create a Fee Payment
2. In Fee Demands table, set Amount Allocated > outstanding amount on that demand
3. Submit
4. **Expected:** Error — "Amount Allocated exceeds outstanding amount..."

#### Test 14: Mismatched total validation

1. Add two demand rows totalling ₹70,000 but set total Amount to ₹50,000
2. Submit
3. **Expected:** Error — "Total allocated amount must equal the payment amount."

#### Test 15: Multi-demand payment

1. Create a Fee Payment for a student who has 2 pending demands
2. Add both demands in the Fee Demands table, split the amount between them
3. Submit
4. **Expected:** Both demands updated — each shows paid_amount matching their allocation. One receipt created covering both demands.

#### Test 16: Cancel a Fee Payment

1. Open a Submitted Fee Payment
2. Click **Cancel**
3. **Expected:**
   - Payment status → `Cancelled`
   - Fee Demand paid_amount reversed (back to 0)
   - Fee Demand status → `Pending` again
   - Linked Fee Receipt cancelled

---

### 3B. Fee Receipt

**Path:** Fees Management → Collections & Receipts → Fee Receipt

#### Test 17: Verify auto-created receipt

1. After submitting a Fee Payment, go to **Fee Receipt**
2. Open the receipt linked to that payment
3. **Expected:**
   - Receipt No (NLS-RPT-##### format or configured autoname)
   - Student, Programme, Academic Year, Year of Study filled
   - Payment Mode, Reference Number from the payment
   - Demands Paid child table lists each demand and amount
   - Receipt Date = Payment Date

---

### 3C. Bulk Fee Collection

**Path:** Fees Management → Collections & Receipts → Bulk Fee Collection

#### Test 18: Fetch students with pending dues

1. Click **New**
2. Fill:
   - Academic Year: `2026-27`
   - Batch Year: `2024` (optional filter)
3. Click **Fetch Students**
4. **Expected:** Students child table fills with all students who have pending/overdue demands, showing their outstanding amount.

#### Test 19: Collect fees in bulk

1. After fetching students, review the amounts
2. Click **Submit**
3. **Expected:** Fee Payments created for each student in the list. Fee Demands updated accordingly.

---

## Phase 4 — Event-Triggered Demands

### 4A. Hostel Allocation → Housing and Mess Fee

**Pre-requisite:** Active Hostel Fee Structure exists with Demand Type = `Hostel`.

#### Test 20: Hostel allocation creates fee demand

1. Go to **Hostel Allocation** → New
2. Fill: Student, Hostel, Room, Bed. Save.
3. Go to **All Fee Demands**
4. **Expected:** New demand created for the student:
   - Fee Component type = `Housing and Mess Fee`
   - Demand Type = `Hostel`
   - Trigger Ref Doctype = `Hostel Allocation`
   - Due Date = today + 30 days

#### Test 21: Delete hostel allocation cancels demand

1. Open the Hostel Allocation just created
2. Click **Delete**
3. Go to Fee Demands and check the demand created in Test 20
4. **Expected:** Demand status → `Cancelled`

---

### 4B. Course Reregistration → Re-registration Tuition Fee

**Pre-requisite:** Fee Component with type `Re-registration Tuition Fee` must exist.

#### Test 22: Submit course reregistration creates demand

1. Go to **Course Reregistration** → New
2. Fill: Student, Academic Year, Number of Courses: `3`, Fee Per Course: `1500`
3. Save → Submit
4. Go to **All Fee Demands**
5. **Expected:** Demand created:
   - Amount = `3 × 1500 = ₹4,500`
   - Description: "Re-registration Tuition Fee (3 course(s) × ₹1,500)"
   - Trigger = `Course Reregistration`

#### Test 23: Cancel reregistration cancels demand

1. Cancel the Course Reregistration
2. **Expected:** Linked demand → `Cancelled`

---

### 4C. Re Exam Registration → Examination Fee

**Pre-requisite:** Fee Component with type `Examination Fee` must exist.

#### Test 24: Re Exam Registration with status Registered

1. Go to **Re Exam Registration** → New
2. Fill: Student, Course, Re Exam Fee: `500`, Status: `Registered`
3. Save
4. **Expected:** Fee Demand created with amount ₹500, type Examination.

#### Test 25: Re Exam with status other than Registered

1. Create Re Exam Registration with Status: `Applied` (not Registered)
2. Save
3. **Expected:** No fee demand created.

---

### 4D. Revaluation Request → Revaluation Fee

**Pre-requisite:** Fee Component with type `Revaluation Fee` must exist.

#### Test 26: Submit revaluation request creates demand

1. Go to **Revaluation Request** → New
2. Fill: Student, Academic Year, Number of Papers: `2`, Fee Per Paper: `500`
3. Save → Submit
4. **Expected:** Demand created with amount `₹1,000` (2 × 500). Trigger = `Revaluation Request`.

#### Test 27: Cancel reverses demand

1. Cancel the Revaluation Request
2. **Expected:** Linked demand → `Cancelled`

---

### 4E. Deferral Order → Gap Year Fee

**Pre-requisite:** Fee Component with type `Gap Year Fee` must exist.

#### Test 28: Submit deferral order creates demand

1. Go to **Deferral Order** → New
2. Fill: Student, Academic Year, Gap Year Fee: `10000`
3. Save → Submit
4. **Expected:** Demand created with amount ₹10,000. Type = Academic.

---

### 4F. Discipline Order → Fine - Disciplinary

**Pre-requisite:** Fee Component with type `Fine - Disciplinary` must exist.

#### Test 29: Submit discipline order creates fine demand

1. Go to **Discipline Order** → New
2. Fill: Student, Fine Amount: `2000`, Reason: `Misconduct`, Academic Year
3. Save → Submit
4. **Expected:** Demand created with amount ₹2,000. Due Date = today + 15 days. Type = Fine.

---

### 4G. Hostel Fine → Fine - Hostel

**Pre-requisite:** Fee Component with type `Fine - Hostel` must exist.

#### Test 30: Create hostel fine creates demand

1. Go to **Hostel Fine** → New
2. Fill: Student, Amount: `500`, Reason: `Room damage`
3. Save
4. **Expected:** Demand created with amount ₹500. Due Date = today + 15 days. Type = Fine.

---

### 4H. Convocation Registration → Convocation Fee

**Pre-requisite:** Fee Component with type `Convocation Fee` must exist (e.g., base amount ₹1,500).

#### Test 31: In-Person convocation demand

1. Go to **Convocation Registration** → New
2. Fill: Student, Academic Year, Convocation Year, Convocation Type: `In-Person`
3. Save → **Expected:** Amount field = ₹1,500 (base)
4. Submit
5. **Expected:**
   - Fee Demand created with ₹1,500
   - `Convocation Fee Demand` field filled on the registration form
   - Trigger = `Convocation Registration`

#### Test 32: In-Absentia convocation demand

1. Create Convocation Registration with Type: `In-Absentia`
2. Save → **Expected:** Amount = ₹2,000 (base + 500)
3. Submit → **Expected:** Demand created for ₹2,000

#### Test 33: Cancel convocation registration

1. Cancel a submitted Convocation Registration
2. **Expected:** Linked demand → `Cancelled`. `Convocation Fee Demand` field cleared.

#### Test 34: Missing fee component throws error

1. Temporarily ensure no Fee Component of type `Convocation Fee` exists
2. Try to submit a Convocation Registration
3. **Expected:** Error — "Fee Component 'Convocation Fee' not found. Create a Fee Component with type 'Convocation Fee' first."

---

## Phase 5 — Waivers & Concessions

### 5A. Fee Concession (Waiver)

**Path:** Fees Management → Waivers & Concessions → Fee Concession

#### Test 35: Percentage waiver

1. Click **New**
2. Fill:
   - Student: pick student with a Pending demand
   - Fee Demand: pick the demand (Original Amount auto-fills)
   - Waiver Mode: `Percentage`
   - Waiver Value: `50`
   - Reason: `Merit Scholarship`
3. Save → **Expected:** Waiver Amount calculates as 50% of original
4. Submit
5. **Expected:**
   - Concession status → `Approved`
   - Approved By + Approved On filled
   - Fee Demand: waiver_amount updated, outstanding_amount recalculated
   - If waiver = 100% → demand status → `Waived`

#### Test 36: Fixed amount waiver

1. Create Fee Concession, Waiver Mode: `Fixed`, Waiver Value: `10000`
2. Submit
3. **Expected:** Demand outstanding reduced by ₹10,000

#### Test 37: Waiver exceeds original amount

1. Set Waiver Value to more than the original amount
2. Save
3. **Expected:** Error — "Waiver Amount cannot exceed Original Amount."

#### Test 38: Duplicate concession blocked

1. Submit a concession on demand X
2. Create a second concession on the same demand X
3. Submit the second one
4. **Expected:** Error — "Fee Demand X already has an approved concession."

#### Test 39: Cancel concession reverses waiver

1. Cancel an approved Fee Concession
2. **Expected:**
   - Concession status → `Reversed`
   - Fee Demand waiver_amount → 0, outstanding restored

---

### 5B. Fee Refund

**Path:** Fees Management → Waivers & Concessions → Fee Refund

**Pre-requisite:** Student must have a Paid or Partially Paid demand (paid_amount > 0).

#### Test 40: Create a refund

1. Click **New** (autoname: REF-.YYYY.-.#####)
2. Fill:
   - Student: pick student with a paid demand
   - Fee Demand: pick a demand where paid_amount > 0
   - Refund Type: `Overpayment`
   - Refund Amount: ₹5,000
   - Refund Date: today
   - Refund Mode: `Bank Transfer`
   - Bank Name, Account Number, IFSC Code, UTR Number
3. Save → Submit
4. **Expected:**
   - Status → `Approved`, Approved By + Approved On filled
   - Fee Demand: paid_amount reduced by ₹5,000, outstanding_amount increased
   - If demand was `Paid` and now has outstanding → status → `Partially Paid`

#### Test 41: Refund exceeds paid amount

1. Set Refund Amount > paid_amount on the demand
2. Save
3. **Expected:** Error — "Refund Amount cannot exceed the amount already paid."

#### Test 42: Duplicate refund blocked

1. Submit a refund on demand X
2. Create a second refund on the same demand
3. Submit
4. **Expected:** Error — "Fee Demand X already has an approved refund."

#### Test 43: Cancel refund reverses it

1. Cancel an approved Fee Refund
2. **Expected:**
   - Status → `Reversed`
   - Fee Demand paid_amount restored, demand status → `Paid` again

---

### 5C. Student Credit Note

**Path:** Fees Management → Waivers & Concessions → Student Credit Note

#### Test 44: Create and submit credit note

1. Click **New** (autoname: CRN-.YYYY.-.#####)
2. Fill:
   - Student: pick any student
   - Credit Type: `Advance Deposit`
   - Academic Year
   - Credit Amount: `20000`
3. Save → Submit
4. **Expected:**
   - Status → `Active`
   - Available Credit = ₹20,000
   - Used Credit = ₹0

#### Test 45: Apply credit to a demand

1. Open a Submitted (Active) Student Credit Note
2. Click **Apply Credit to Demand** button (visible only when docstatus=1 and status=Active)
3. Dialog opens → fill:
   - Fee Demand: pick a Pending demand for the same student
   - Amount: ₹5,000
4. Click Apply
5. **Expected:**
   - Available Credit → ₹15,000
   - Used Credit → ₹5,000
   - Adjustments child table: new row with fee_demand, amount_adjusted=₹5,000, adjusted_on, adjusted_by
   - Fee Demand: credit_adjusted = ₹5,000, outstanding_amount reduced by ₹5,000

#### Test 46: Apply full credit — status becomes Exhausted

1. Apply credit equal to the full available credit amount
2. **Expected:** Credit Note status → `Exhausted`. Button no longer visible.

#### Test 47: Credit note for wrong student blocked

1. Attempt to apply credit note of Student A to a demand belonging to Student B
2. **Expected:** Error — "This credit note belongs to a different student."

#### Test 48: Credit exceeds available balance

1. Try to apply amount greater than available_credit
2. **Expected:** Error — "Amount exceeds available credit."

#### Test 49: Cancel credit note with used credit blocked

1. Partially use a credit note (some credit applied)
2. Try to cancel the credit note
3. **Expected:** Error — "Cannot cancel — ₹X of this credit has already been applied. Reverse the adjustments first."

---

## Phase 6 — Reports

**Path:** Fees Management → Reports section

### 6A. Defaulter List

**Path:** Fees Management → Defaulter List

#### Test 50: Run defaulter list

1. Open **Defaulter List** report
2. Set filters: Academic Year = `2026-27`
3. Click **Run**
4. **Expected:** Lists all students with demands where:
   - Status is `Pending`, `Overdue`, or `Partially Paid`
   - Outstanding Amount > 0
   - Due date is past

---

### 6B. Collection Summary

**Path:** Fees Management → Collection Summary

#### Test 51: Run collection summary

1. Open **Collection Summary** report
2. Set filters: Academic Year, optionally date range
3. Click **Run**
4. **Expected:** Grouped totals of amount collected by Fee Component/type. Matches actual Fee Receipts issued.

---

### 6C. Fee Demand Register

**Path:** Fees Management → Fee Demand Register

#### Test 52: Run demand register

1. Open **Fee Demand Register** report
2. Set filters: Academic Year = `2026-27`
3. Click **Run**
4. **Expected:** Full ledger of all demands — columns include student, fee component, demand date, due date, original amount, waiver, outstanding, status.

---

### 6D. Receipt Register

**Path:** Fees Management → Receipt Register

#### Test 53: Run receipt register

1. Open **Receipt Register** report
2. Set filters: date range (this month)
3. Click **Run**
4. **Expected:** All receipts issued in the period with payment mode, amount, student details.

---

## Phase 7 — Automation & Monitoring

### 7A. Overdue Marking (Scheduled Job)

**Scheduler function:** `slcm.slcm.fee.scheduler.mark_overdue_demands` (runs daily at midnight)

#### Test 54: Manual trigger — mark overdue

1. Create a Fee Demand with due_date = yesterday, status = `Pending`
2. Run via Frappe console or bench:
   ```
   bench --site slcm.local execute slcm.slcm.fee.scheduler.mark_overdue_demands
   ```
3. **Expected:** The demand's status → `Overdue`

#### Test 55: Verify via workspace number card

1. Go to **Fees Management** workspace
2. Check **Overdue Fee Demands** number card
3. **Expected:** Count reflects the newly overdue demand

---

### 7B. Reminder Emails (Scheduled Job)

**Scheduler function:** `slcm.slcm.fee.scheduler.send_due_reminders` (runs daily at midnight)

#### Test 56: T-7 reminder

1. Create a demand with due_date = today + 7 days, status = `Pending`, reminder_1_sent = 0
2. Run:
   ```
   bench --site slcm.local execute slcm.slcm.fee.scheduler.send_due_reminders
   ```
3. **Expected:** Email sent to student's registered email. `reminder_1_sent` flag set to 1 on the demand.

#### Test 57: Idempotency — reminder not sent twice

1. Run send_due_reminders again on the same day
2. **Expected:** Email NOT sent again (flag = 1 blocks resend).

---

### 7C. Scheduled Job Log & Error Log

**Path:** Fees Management → Automation & Monitoring → Scheduled Job Log / Error Log

#### Test 58: Verify scheduled job log

1. Go to **Scheduled Job Log**
2. **Expected:** Entries showing recent scheduler runs (overdue marking, reminders) with status Completed/Failed.

#### Test 59: Verify error log

1. Go to **Error Log**
2. After triggering any operation that should log errors (e.g., missing fee component), check here
3. **Expected:** Error entry appears with title and traceback.

---

## Workspace Verification

**Path:** `/desk/fees-management`

#### Test 60: Number cards load correctly

1. Open Fees Management workspace
2. **Expected:** 4 number cards visible and showing counts:
   - Total Fee Demands
   - Pending Fee Demands
   - Overdue Fee Demands
   - Fee Receipts This Month

#### Test 61: Charts load correctly

1. Scroll to the Charts section
2. **Expected:** 3 charts render:
   - Demand Status Distribution
   - Demands by Fee Component
   - Monthly Fee Collection

#### Test 62: Shortcuts filter correctly

1. Click **Pending Demands** shortcut
2. **Expected:** Fee Demand list opens filtered to Status = Pending only
3. Click **Overdue Demands** shortcut
4. **Expected:** Fee Demand list opens filtered to Status = Overdue only
5. Click **Waived Demand** → Status = Waived; **Cancelled Demand** → Status = Cancelled; **Partially Paid Demand** → Status = Partially Paid

#### Test 63: Workspace edit does not break routing

1. Click the ⋯ menu → **Edit**
2. Make a minor change (e.g., reorder a shortcut)
3. Click **Save**
4. **Expected:** URL stays at `/desk/fees-management` (no redirect to `/desk/fees%20management`). No "Page not found" error.

---

## Quick Smoke Test Sequence

Run this end-to-end to verify the full fee lifecycle in ~15 minutes:

```
1. Create Fee Component: "Tuition Fee Test" (type: Tuition Fee, amount: 10000)
2. Create Fee Structure: Active, Academic, auto_generate_demand=1, amount=10000, due_offset=30
3. Create Fee Notification → add component row → Publish → Generate Demands
4. Verify demand created for student (status: Pending)
5. Create Fee Payment → allocate to that demand → Submit
6. Verify demand status → Paid; verify Fee Receipt created
7. Create Fee Concession on a different Pending demand → Submit → verify outstanding reduced
8. Create Convocation Registration (In-Person) → Submit → verify ₹1500 demand created
9. Run mark_overdue_demands (set a demand due_date to yesterday first) → verify Overdue status
10. Open workspace → verify all 4 number cards and 3 charts show data
```

---

*Document generated: 2026-05-23 | SLCM v16 Fees Management Module*
