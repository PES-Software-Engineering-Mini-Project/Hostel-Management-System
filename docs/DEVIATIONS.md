# Deviations from the Submitted Documents

This log records every place where the implementation differs from the documents we
submitted, so each one can be explained at the final demo (Deliverables Part-2, item 2i).

**Documents compared:** Software Requirements Specification (`Team3_Hostel_Management_System_SRS.pdf`),
Software Architecture and Design (`HMS_SASD_Deliverable-3.docx`), Software Test Plan
(`Hostel_Management_System_Test_Plan.pdf`) and the Functional and Non-Functional
Requirements document (`FR_NFR.pdf`).

**Status values:** *Accepted* (a deliberate change we are keeping) · *Planned* (will be
brought in line, tracked by an issue) · *Open* (a decision is still needed).

_Last updated: 1 Nov 2026, end of Sprint 2 (rooms, allocation, dashboard, profiles, NFR tests, fees from room fee, receipts, search)._

## Summary

| ID | Area | Deviation | Status | Tracking |
|---|---|---|---|---|
| D-01 | Login | Users log in with their SRN, not a username | Accepted | #3 |
| D-02 | Requirement IDs | FR numbering differs between the SRS and the FR/NFR document | Accepted | — |
| D-03 | Fees | Fee due was entered by an Admin, not taken from the room fee | **Resolved** | #14, PR #47 |
| D-04 | Fees | No receipts | **Resolved** | #17, PR #47 |
| D-05 | Fees | Payment route and service function differ from the SAD API design | Accepted | #8 |
| D-06 | Rooms | Blocks and rooms were managed only through the Django admin site | **Resolved** | #29, PR #36 |
| D-07 | Rooms | Known defects merged: blank-field crash, occupied room can be deleted, no tests | **Resolved** | #29, PR #36 |
| D-08 | Rooms | Extra "Dormitory" room type not in the SRS | **Resolved** | #29, PR #36 |
| D-09 | Rooms | Room fee stored as `monthly_fee`; fees are tracked per term | **Resolved** | #14, PR #47 |
| D-10 | Testing | Automated tests are not labelled with Test Plan case IDs (TC-xx) | Planned | — |
| D-11 | Testing | CI ran on SQLite only, not also on PostgreSQL | **Resolved** | #23, PR #45 → #52 |
| D-12 | Schedule | Sprints ran late; visitors and complaint room tags move to Sprint 3 | Accepted | #5, #49 |
| D-13 | Tracking | Jira is used alongside the GitHub Project backlog | Accepted | — |
| D-14 | Complaints | Complaints are not yet tagged with the student's room | Planned | #49 (Sprint 3) |
| D-15 | Rooms | Application and allocation routes differ from the SAD API design | Accepted | #15, PR #38 |
| D-16 | Fees | Room fee changes and moves don't change an existing term's fee | Accepted | #14, PR #47 |

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
- **Resolved (PR #47, Sprint 2):** the Admin picks only the student and term. The fee record stores the allotted room, and the amount due is the room's monthly fee × `HMS_MONTHS_PER_TERM` (see D-09). Students without an allotted room can't be billed.

### D-04 · No fee receipts yet

- **Documents say:** SRS §5.5 FR-5.5 and FR-5.6 (receipt per payment; students download their own); SAD §3.9 (receipts carry a receipt number) and §4.3 (`/fees/receipts/<id>`; payment returns a printable receipt).
- **Implemented (Sprint 1):** payments are recorded and listed with history, but no receipt is generated.
- **Plan:** issue #17, Sprint 2.
- **Resolved (PR #47, Sprint 2):** every payment has a receipt at `/fees/receipts/<id>/` (the SAD route) with a 10-digit receipt number, student, SRN, room, term, date, amount and balance after the payment. It can be printed or downloaded as an HTML file. Admins can open any receipt; a student only their own (others get 404).

### D-05 · Fee payment route and service function

- **SAD says:** §4.3: `POST /fees/<student>/pay {amount, payment_date}` returning a printable receipt; service `record_payment(student, amount, date)`.
- **Implemented:** `POST /fees/manage/<fee_record_id>/payments/new/` redirecting to the fee list, and `FeeRecord.record_payment(amount=..., paid_on=..., recorded_by=...)`.
- **Reason:** a student can owe fees for more than one term, so a payment has to name the term's fee record, not just the student. Recording who took the payment also supports the SAD's repudiation control (§3.9). The SAD notes that route names "may change slightly during coding".
- **Impact:** none on the rules: overpayment, zero and negative amounts are rejected, and the save runs in a transaction with a row lock.
- **Update (PR #47):** recording a payment now opens its printable receipt, as the SAD describes. Fee due is set by the fee record form from the allotted room, rather than by a separate `create_fee_due` service function.

### D-06 · Rooms are managed only through the Django admin site

- **Documents say:** SRS §3.1 Room management screen for the Admin; SAD §4.3 `/rooms` list with filters; SAD §3.4: the Django admin site is "not the warden's daily tool".
- **Implemented (Sprint 1):** `Block` and `Room` models registered in the Django admin site only. The Django admin needs `is_staff`, which HMS Admin-role users do not have, so the warden cannot manage rooms yet.
- **Plan:** Admin-only HMS pages for blocks and rooms — issue #29, Sprint 2.
- **Resolved (PR #36, Sprint 2):** Admin-only pages at `/rooms/`, `/rooms/blocks/add/` and `/rooms/add/`, linked from the admin navigation (PR #46). The room list has the block, floor, type and status filters from SAD §4.3 (PR #48).

### D-07 · Room module merged with known defects

- **Documents say:** SRS §5.3 FR-3.5 / FR/NFR FR-3.4 (a room with an occupant can't be deleted); SAD §4.4 and NFR-8 (plain error page, form errors next to the field); NFR-6 and the Test Plan (each app has its own tests, TC-04).
- **Implemented (Sprint 1, #28):** the review found that blank numeric fields crash validation with a `TypeError` (a 500 instead of a form error), an occupied room can be deleted, and there are no tests for the rooms rules.
- **Reason:** #28 was approved to close Sprint 1 on time, with the defects tracked rather than blocking the merge.
- **Plan:** issue #29, Sprint 2, High priority.
- **Resolved (PR #36, Sprint 2):** blank fields give form errors, occupied rooms can't be deleted from the model, a queryset or the Django admin, and the rooms app has its own tests (`rooms/tests/`). The remaining template polish (#44) was finished in PR #52, which also added an admin Reject action for pending applications. FR-4 does not require Reject, but `RoomApplication.Status.REJECTED` existed and nothing could set it.

### D-08 · Extra "Dormitory" room type

- **SRS says:** §5.3 FR-3.2: room type is single, double or triple.
- **Implemented:** a fourth type, `Dormitory`, with no fixed capacity.
- **Open decision:** remove it, or keep it and update the SRS — tracked in #29.
- **Resolved (PR #36):** `Dormitory` was removed; room types are Single, Double and Triple as in the SRS.

### D-09 · Room fee is monthly; fees are per term

- **SRS says:** FR-3.2 gives each room a "fee"; FR-5.1 stores fee due "per student per term" from that fee.
- **Implemented:** `Room.monthly_fee`, while `fees.FeeRecord` is per term.
- **Open decision:** store a per-term room fee, or define how monthly converts to a term, before #14 derives fee due from it — tracked in #29 and #14.
- **Resolved (PR #47):** the room keeps a monthly fee, and a term's fee due is `monthly_fee × HMS_MONTHS_PER_TERM`. The setting defaults to 6 (one semester) and can be changed in the environment without code changes.

### D-10 · Tests are not labelled with Test Plan case IDs

- **Documents say:** the SAD §3.8 traceability table maps requirements to Test Plan cases TC-01 to TC-13.
- **Implemented:** unit and integration tests exist (accounts, fees), but their names and docstrings do not reference TC IDs, so the traceability matrix can't be followed from the code.
- **Plan:** add the TC ID to each test class docstring as apps are completed, and keep the Requirements Traceability Matrix in step.

### D-11 · CI does not run the tests on PostgreSQL

- **SAD says:** §3.7: "Run the tests on PostgreSQL as well before release" (SQLite and PostgreSQL behave differently).
- **Implemented:** the GitHub Actions pipeline runs the full suite on SQLite (Python 3.10 and 3.12).
- **Plan:** add a PostgreSQL service job to CI before the final release.
- **Resolved (PR #45, landed on `main` through PR #52, Sprint 2):** each CI job runs the full suite twice, on SQLite (as used locally) and on a PostgreSQL 17 service. The concurrent-allotment test (NFR-4) needs real row locks, so it runs only on PostgreSQL and is skipped on SQLite.

### D-12 · Sprint schedule

- **Deliverables say:** Sprint 1 runs 19–23 Oct 2026.
- **Actual:** Sprint 1 development and reviews happened on 26–27 Oct, after the planned window. All planned Sprint 1 stories were delivered: project setup (#1), CI pipeline (#7), login and roles (#3), student registration (#9), fee records and payments (#8), blocks and rooms (#10), and complaints (#4). Known defects in blocks and rooms carry over to Sprint 2 (see D-07).
- **Plan change:** the course has three sprints, not four. Most of the project is to be finished by Sprint 2 (26–30 Oct), and Sprint 3 (2–6 Nov) only has a few extras and NFR polish.
- **Sprint 2 actual:** reviews and merges ran until 1 Nov. Delivered: room setup fixes (#29), room application and allocation (#15), safe concurrent allotment (#23), admin dashboard (#18), student profile and admin student records (#16), usability, performance and security NFR work (#20, #21, #22), fee due from the room fee (#14), receipts (#17) and search and filter (#6). **Moved to Sprint 3:** visitor logging (#5) and tagging complaints with the room (#49, see D-14).

### D-13 · Jira is used alongside the GitHub Project

- **Deliverables say:** item 1 — create the backlog in a GitHub Project.
- **Actual:** the backlog, story points, sprints and priorities are in the GitHub Project "Hostel Management Backlog". The team also tracks the same stories in Jira (SCRUM-6 to SCRUM-16), and issues and PRs reference both. The GitHub Project is the reference for the deliverable.

### D-14 · Complaints are not yet tagged with the student's room

- **Documents say:** SRS §5.6 FR-6.2: "The complaint auto-tags the student's room and the time it was submitted." SAD §4.3: a new complaint is saved "as Open, with room and time".
- **Implemented (Sprint 1, #32):** the complaint stores the student and the submission time, but not the room.
- **Reason:** room allocation does not exist yet, so a student has no room to tag.
- **Plan:** add the room link once allocation (#15) is merged, in Sprint 2.
- **Update:** allocation was merged in Sprint 2 (PR #38), but the complaint room link was not built in time. It is tracked in #49 for Sprint 3.

### D-15 · Room application and allocation routes

- **SAD says:** §4.3: `POST /applications/apply`, `POST /allocations/allot {application_id, room_id}`, `POST /allocations/<id>/deallocate`, `POST /allocations/<id>/reassign {room_id}`; service `allot(student, room)`.
- **Implemented (PR #38):** the same actions under the rooms app: `/rooms/apply/`, `/rooms/applications/`, `/rooms/application/<id>/allot/`, `/rooms/allocations/`, `/rooms/allocation/<id>/move/` and `/rooms/allocation/<id>/deallocate/`. Allotment runs in the view inside a transaction, not in a separate `allot` service function.
- **Reason:** keeping every room URL under `/rooms/` matches how the other apps are routed (`/fees/`, `/complaints/`). The SAD notes that route names "may change slightly during coding".
- **Impact:** none on the rules: capacity (FR-4.4), one room per student (FR-4.5) and updating the count and record together (FR-4.6) are enforced and tested, including under concurrent requests on PostgreSQL (#23).

### D-16 · A term's fee is fixed when it is created

- **Documents say:** SRS FR-5.1 takes fee due from the room's fee; FR-4.7 lets the Admin reassign a student. Neither says what happens to fee due when a student moves, or a room's fee changes, partway through a term.
- **Implemented (PR #47):** a fee record stores the room and amount when it is created and does not change afterwards. The next term's record uses the student's room at that time.
- **Reason:** the bill may already be part-paid and receipts quote it, so changing it silently would make balances and receipts disagree.
- **Impact:** tested in `fees/tests/test_models.py` (`RoomChangeMidTermTests`).

## How to update this log

Add a row and a details section whenever code is merged that differs from the SRS, SAD,
Test Plan or FR/NFR document, or when a deviation is resolved. When one is resolved, change
its status to **Resolved**, name the PR that fixed it, and keep the entry so the history is
visible at the final demo.
