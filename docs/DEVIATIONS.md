# Deviations from the Submitted Documents

This log records every place where the implementation differs from the documents we
submitted, so each one can be explained at the final demo (Deliverables Part-2, item 2i).

**Documents compared:** Software Requirements Specification (`Team3_Hostel_Management_System_SRS.pdf`),
Software Architecture and Design (`HMS_SASD_Deliverable-3.docx`), Software Test Plan
(`Hostel_Management_System_Test_Plan.pdf`) and the Functional and Non-Functional
Requirements document (`FR_NFR.pdf`).

**Status values:** *Accepted* (a deliberate change we are keeping) · *Planned* (will be
brought in line, tracked by an issue) · *Open* (a decision is still needed).

_Last updated: 27 Oct 2026, end of Sprint 1._

## Summary

| ID | Area | Deviation | Status | Tracking |
|---|---|---|---|---|
| D-01 | Login | Users log in with their SRN, not a username | Accepted | #3 |
| D-02 | Requirement IDs | FR numbering differs between the SRS and the FR/NFR document | Accepted | — |
| D-03 | Fees | Fee due is entered by an Admin, not taken from the room fee | Planned | #14 |
| D-04 | Fees | No receipts yet | Planned | #17 |
| D-05 | Fees | Payment route and service function differ from the SAD API design | Accepted | #8 |
| D-06 | Rooms | Blocks and rooms are managed only through the Django admin site | Planned | #29 |
| D-07 | Rooms | Known defects merged: blank-field crash, occupied room can be deleted, no tests | Planned | #29 |
| D-08 | Rooms | Extra "Dormitory" room type not in the SRS | Open | #29 |
| D-09 | Rooms | Room fee stored as `monthly_fee`; fees are tracked per term | Open | #29, #14 |
| D-10 | Testing | Automated tests are not labelled with Test Plan case IDs (TC-xx) | Planned | — |
| D-11 | Testing | CI runs on SQLite only, not also on PostgreSQL | Planned | — |
| D-12 | Schedule | Sprint 1 work finished late, and one Sprint 1 story moved out | Accepted | #9 |
| D-13 | Tracking | Jira is used alongside the GitHub Project backlog | Accepted | — |
| D-14 | Complaints | Complaints are not yet tagged with the student's room | Planned | #4, #15 |

## Details

### D-01 · Login uses SRN instead of a username

- **Documents say:** FR/NFR FR-1.1 and SRS §3.1 (Login screen): log in with "username and password". SAD §4.3: `POST /login {username, password}`.
- **Implemented:** a custom user model whose login identifier is the college SRN (`accounts.User.USERNAME_FIELD = "srn"`), stored uppercase and unique. The login form is labelled "SRN".
- **Reason:** every student already has a unique SRN, so a separate username would be one more thing to remember and keep unique. Django's built-in authentication is still used, as SAD ADR-2 requires.
- **Impact:** none on the requirements; the generic wrong-credentials error and role redirects work as specified.

### D-02 · Requirement numbering differs between the SRS and the FR/NFR document

- **Documents say:** the SRS and the FR/NFR document number some requirements differently. For example, fees are FR-5.1 to FR-5.6 in the SRS but FR-5.1 to FR-5.4 in the FR/NFR document, and the FR/NFR document lists search as FR-9 with items numbered FR-10.1 to FR-10.4. The SRS also adds details the FR/NFR document leaves out, such as "fee due comes from the room's assigned fee".
- **Decision:** the **SRS numbering is the reference**, as the SAD (§3.8) and Test Plan already use it. Issues and PRs created before this was noticed may quote FR/NFR numbers.

### D-03 · Fee due is entered by an Admin, not derived from the room fee

- **SRS says:** §5.5 FR-5.1: "Fee due comes from the room's assigned fee." SAD §4.3 lists a `create_fee_due(student, fee)` service.
- **Implemented (Sprint 1):** an Admin creates a fee record per student per term and types the amount due.
- **Reason:** rooms were only just added and room allocation does not exist yet, so there is no allotted room to read the fee from.
- **Plan:** link fee records to the allotted room once allocation (#15) is merged — issue #14, Sprint 2.

### D-04 · No fee receipts yet

- **Documents say:** SRS §5.5 FR-5.5 and FR-5.6 (receipt per payment; students download their own); SAD §3.9 (receipts carry a receipt number) and §4.3 (`/fees/receipts/<id>`; payment returns a printable receipt).
- **Implemented (Sprint 1):** payments are recorded and listed with history, but no receipt is generated.
- **Plan:** issue #17, Sprint 2.

### D-05 · Fee payment route and service function

- **SAD says:** §4.3: `POST /fees/<student>/pay {amount, payment_date}` returning a printable receipt; service `record_payment(student, amount, date)`.
- **Implemented:** `POST /fees/manage/<fee_record_id>/payments/new/` redirecting to the fee list, and `FeeRecord.record_payment(amount=..., paid_on=..., recorded_by=...)`.
- **Reason:** a student can owe fees for more than one term, so a payment has to name the term's fee record, not just the student. Recording who took the payment also supports the SAD's repudiation control (§3.9). The SAD notes that route names "may change slightly during coding".
- **Impact:** none on the rules: overpayment, zero and negative amounts are rejected, and the save runs in a transaction with a row lock.

### D-06 · Rooms are managed only through the Django admin site

- **Documents say:** SRS §3.1 Room management screen for the Admin; SAD §4.3 `/rooms` list with filters; SAD §3.4: the Django admin site is "not the warden's daily tool".
- **Implemented (Sprint 1):** `Block` and `Room` models registered in the Django admin site only. The Django admin needs `is_staff`, which HMS Admin-role users do not have, so the warden cannot manage rooms yet.
- **Plan:** Admin-only HMS pages for blocks and rooms — issue #29, Sprint 2.

### D-07 · Room module merged with known defects

- **Documents say:** SRS §5.3 FR-3.5 / FR/NFR FR-3.4 (a room with an occupant can't be deleted); SAD §4.4 and NFR-8 (plain error page, form errors next to the field); NFR-6 and the Test Plan (each app has its own tests, TC-04).
- **Implemented (Sprint 1, #28):** the review found that blank numeric fields crash validation with a `TypeError` (a 500 instead of a form error), an occupied room can be deleted, and there are no tests for the rooms rules.
- **Reason:** #28 was approved to close Sprint 1 on time, with the defects tracked rather than blocking the merge.
- **Plan:** issue #29, Sprint 2, High priority.

### D-08 · Extra "Dormitory" room type

- **SRS says:** §5.3 FR-3.2: room type is single, double or triple.
- **Implemented:** a fourth type, `Dormitory`, with no fixed capacity.
- **Open decision:** remove it, or keep it and update the SRS — tracked in #29.

### D-09 · Room fee is monthly; fees are per term

- **SRS says:** FR-3.2 gives each room a "fee"; FR-5.1 stores fee due "per student per term" from that fee.
- **Implemented:** `Room.monthly_fee`, while `fees.FeeRecord` is per term.
- **Open decision:** store a per-term room fee, or define how monthly converts to a term, before #14 derives fee due from it — tracked in #29 and #14.

### D-10 · Tests are not labelled with Test Plan case IDs

- **Documents say:** the SAD §3.8 traceability table maps requirements to Test Plan cases TC-01 to TC-13.
- **Implemented:** unit and integration tests exist (accounts, fees), but their names and docstrings do not reference TC IDs, so the traceability matrix can't be followed from the code.
- **Plan:** add the TC ID to each test class docstring as apps are completed, and keep the Requirements Traceability Matrix in step.

### D-11 · CI does not run the tests on PostgreSQL

- **SAD says:** §3.7: "Run the tests on PostgreSQL as well before release" (SQLite and PostgreSQL behave differently).
- **Implemented:** the GitHub Actions pipeline runs the full suite on SQLite (Python 3.10 and 3.12).
- **Plan:** add a PostgreSQL service job to CI before the final release.

### D-12 · Sprint 1 schedule

- **Deliverables say:** Sprint 1 runs 19–23 Oct 2026.
- **Actual:** Sprint 1 development and reviews happened on 26–27 Oct. Delivered in Sprint 1: project setup (#1), CI pipeline (#7), login and roles (#3), fee records and payments (#8), blocks and rooms (#10), and complaints (#4). **Not delivered in Sprint 1:** student registration (#9); it moves to Sprint 2.

### D-13 · Jira is used alongside the GitHub Project

- **Deliverables say:** item 1 — create the backlog in a GitHub Project.
- **Actual:** the backlog, story points, sprints and priorities are in the GitHub Project "Hostel Management Backlog". The team also tracks the same stories in Jira (SCRUM-6 to SCRUM-16), and issues and PRs reference both. The GitHub Project is the reference for the deliverable.

### D-14 · Complaints are not yet tagged with the student's room

- **Documents say:** SRS §5.6 FR-6.2: "The complaint auto-tags the student's room and the time it was submitted." SAD §4.3: a new complaint is saved "as Open, with room and time".
- **Implemented (Sprint 1, #32):** the complaint stores the student and the submission time, but not the room.
- **Reason:** room allocation does not exist yet, so a student has no room to tag.
- **Plan:** add the room link once allocation (#15) is merged, in Sprint 2.

## How to update this log

Add a row and a details section whenever code is merged that differs from the SRS, SAD,
Test Plan or FR/NFR document, or when a deviation is resolved. When one is resolved, change
its status to **Resolved**, name the PR that fixed it, and keep the entry so the history is
visible at the final demo.
