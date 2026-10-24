# COE SYNC 2026 — User & Technical Operations Guide
**BulSU College of Engineering • Academic Scheduling & Conflict Management System**
*Technical Lead & Documentation Engineering Release — Phase 4/5*

---

## 1. Executive Overview & System Architecture

### 1.1 Purpose
**COE SYNC 2026** is the centralized academic management, timetable scheduling, and conflict resolution platform engineered for the **Bulacan State University (BulSU) College of Engineering**. It eliminates scheduling overlaps across classrooms, laboratories, instructors, and student cohorts while maximizing facility utilization and ensuring balanced faculty teaching workloads.

### 1.2 Technology Stack
- **Backend Framework**: Python 3 with Flask, Flask-SQLAlchemy, and Flask-CORS.
- **Database Engine**: Local SQLite (`sqlite:///coe_sync.db`) with `PRAGMA foreign_keys = ON` for offline local parity, configurable to MySQL/MariaDB for enterprise deployments via `.env`.
- **Frontend Architecture**: Modular Vanilla HTML5, CSS3, and ES6 JavaScript.
- **Dependency Philosophy**: **Zero External CDN Dependencies**. All scripts, styles, icons, and visual analytics meters are bundled and served strictly from local static assets (`/static/css/`, `/static/js/`).
- **Visual Design Language**:
  - **Sidebar & Accent**: Official BulSU College of Engineering Maroon (`#4A1521`, `#3B111A`) with Warm Amber/Gold navigation pills (`#F5C26B`, `#E8A948`).
  - **Scheduled Class Status**: Mint / Soft Teal (`#D1FAE5`, border `#A7F3D0`, indicator `#059669`).
  - **Conflict / Clashing Status**: Amber / Warm Orange (`#FEF3C7`, border `#D97706`, indicator `#D97706`).
  - **Alternate Program / Lab**: Soft Rose / Pink (`#FFE4E6`, border `#FECDD3`, indicator `#E11D48`).

---

## 2. Live Hackathon Presentation & Demo Shortcuts

To facilitate live demonstration and judging, COE SYNC 2026 includes instant presentation accelerators embedded in the global UI header:

### 2.1 The Sticky "View As" Role Impersonator
Located in the upper right header on every page, the **View As** dropdown allows instant perspective swapping without logging out:
1. **Program Chair (`CHAIR`)**: Full administrative authority. Can create, edit, delete, generate drafts, resolve conflicts via the Radar drawer, manage master data, and execute batch publishing.
2. **Faculty Member (`FACULTY` — Prof. Santos)**: Instructors see their personal weekly timetable, teaching load meter (e.g., `10 / 21 units`), and availability windows. All draft generation, deletion, and batch publishing controls are hidden.
3. **Student (`STUDENT` — CpE 2A)**: Students view only official **`PUBLISHED`** schedules for their cohort. All draft schedules, admin toolbars, master data management tabs, and solver buttons are completely hidden from view.

### 2.2 The Global "Reset DB" Shortcut
- **Trigger**: Click the **"Reset DB"** button in the header (visible in `CHAIR` or `ADMIN` view).
- **Backend Action**: Sends `POST /api/seed`.
- **System Behavior**: Re-creates database tables and loads baseline mock data:
  - 6 Faculty members (with varying workload capacities).
  - 8 Classrooms and Laboratories (including Lecture Halls and Specialized Labs).
  - 6 Student Cohort Sections (CpE 1A, CpE 2A, CpE 3A, EE 1A, ME 1A, CE 1A).
  - 8 Engineering Subjects (Lecture and Lab classifications).
  - Pre-staged course schedules featuring intentional, realistic conflict scenarios (`ROOM_COLLISION`, `FACULTY_OVERLAP`, `SECTION_COLLISION`, `CAPACITY_OVERFLOW`) for immediate demonstration of the Conflict Radar.

---

## 3. Search & Filter Applicability & API Contract Reference

Instant search and filtering are systematically integrated across every primary view of the application:

| View & Route | Search / Filter Inputs | Client Debounce / Event | API Contract Query Params | DOM / State Impact |
| :--- | :--- | :--- | :--- | :--- |
| **Schedules**<br>`/schedules` | • Program (`#filter-program`)<br>• Year Level (`#filter-year`)<br>• Section (`#filter-section`)<br>• Faculty (`#filter-faculty`)<br>• Room (`#filter-room`)<br>• Status (`#filter-status`) | Immediate `change` listener on dropdowns; preserves state in URL query string | `GET /api/schedules`<br>`?program=BSCpE`<br>`&year_level=2`<br>`&section_id=2`<br>`&faculty_id=1`<br>`&room_id=1`<br>`&status=PUBLISHED` | Rerenders Timetable Grid (Mon–Sat 7am–7pm) showing only matching cards. Cards involved in clashes receive amber borders and collision tags. |
| **Conflict Radar**<br>`/schedules?radar=open` | Category Filter Bar (`#radar-category-nav`):<br>`ALL`, `ROOM`, `FACULTY`, `SECTION`, `CAPACITY` | Click event on category pills with dynamic count badges | In-memory evaluation against `detectConflictsLocally()` and preflight API validation | Filters the Radar slide-out drawer items by conflict type and highlights affected timetable slots. |
| **Master Data: Rooms**<br>`/manage?tab=rooms` | • Text search (`#search-rooms`)<br>• Room Type (`#filter-room-type`)<br>• Availability (`#filter-room-status`) | 300ms debounced input for room code (`Eng-104`); `change` on selects | `GET /api/rooms`<br>`?search=104`<br>`&type=LECTURE`<br>`&available=true` | Filters table rows dynamically in-memory or refetches records. |
| **Master Data: Faculty**<br>`/manage?tab=faculty` | • Text search (`#search-faculty`)<br>• Workload Status (`#filter-faculty-status`) | 300ms debounced text search (name/email); `change` for overload toggle | `GET /api/faculty`<br>`?search=Santos`<br>`&overloaded=true` | Shows normal vs. overloaded instructors (>21 units) and triggers availability modal. |
| **Master Data: Sections**<br>`/manage?tab=sections` | • Text search (`#search-sections`)<br>• Program (`#filter-section-prog`)<br>• Year Level (`#filter-section-year`) | 300ms debounced input; `change` on selects | `GET /api/sections`<br>`?search=CpE`<br>`&program=BSCpE`<br>`&year_level=2` | Filters section table and student counts. |
| **Master Data: Subjects**<br>`/manage?tab=subjects` | • Text search (`#search-subjects`)<br>• Subject Type (`#filter-subject-type`)<br>• Units (`#filter-subject-units`) | 300ms debounced code/title search; `change` on selects | `GET /api/subjects`<br>`?search=CPE211`<br>`&type=LAB`<br>`&units=3` | Filters subject records and required weekly contact hours. |
| **Dashboard**<br>`/` | • View Mode (Grid vs Table)<br>• Program Filter (`#dash-filter-program`)<br>• Section Filter (`#dash-filter-section`)<br>• Room Filter (`#dash-filter-room`) | Immediate `change` listener on selects; click listener on view pills | `GET /api/schedules` with clean query params | Toggles between interactive timetable grid and sortable data table. |
| **Reports**<br>`/reports` | • Academic Term (`#filter-term`)<br>• Section Scope (`#filter-section-scope`)<br>• Room Type (`#filter-room-type`)<br>• Utilization Threshold (`#filter-util-threshold`) | Immediate `change` listener | `GET /api/analytics/summary` + `GET /api/schedules?section_id=` | Recalculates visual CSS progress meters and detailed matrices without page reloads. |

---

## 4. The 7 Core End-to-End Workflows

---

### Workflow 1: Program Chair / Admin Master Schedule Generation & Publishing
**Audience**: Department Chair, Academic Head, System Administrator  
**Goal**: Generate, inspect, resolve, and publish a conflict-free semester schedule for the entire department.

#### Prerequisites
- Active role set to `CHAIR` or `ADMIN`.
- Master Data (Rooms, Faculty, Sections, Subjects) created or seeded via "Reset DB".

#### Step-by-Step User Actions
1. Open the **Dashboard** (`/`) or navigate to **Schedules** (`/schedules`).
2. Verify that master course offerings exist under `/manage` with valid relational bindings.
3. Click the **"Generate Drafts"** button in the header controls.
4. Review the heuristic solver report toast notification:
   - Total placed slots.
   - Any unplaced items (due to zero remaining room capacity or faculty blackout windows).
   - The updated **Schedule Quality Score** (starts at 100, penalized for idle student gaps > 2 hours and excessive seat waste > 50 seats).
5. Notice that conflicted schedules appear highlighted in amber with the `[CONFLICT]` badge.
6. Click any conflicted event or open the **Conflict Radar** sidebar button (`/schedules?radar=open`).
7. Inspect the detailed collision diagnostic (e.g., `Room double-booked with CpE 2A on Wed 11:00 AM`).
8. Apply suggested alternatives directly from the Conflict Radar drawer (see Workflow 5).
9. Make manual time or room adjustments using the "Edit Schedule" modal if specific faculty preferences apply.
10. Once all collisions are resolved (Unresolved Conflicts = 0), click the **"Publish All"** button.

#### System Response & Technical Flow
- `POST /api/schedules/generate-draft`: Iterates unassigned offerings, sorts by constraint tightness, and places conflict-free slots. Returns `HTTP 200` with placed and unplaced counts.
- `POST /api/schedules/publish-all`: Performs preflight verification across all draft schedules. If any hard conflict exists, returns `HTTP 409 Conflict` with a diagnostic list and refuses to lock. If conflict-free, updates all `DRAFT` schedules to `PUBLISHED` (`HTTP 200`).
- Global KPI cards reflect updated class counts and the Conflict Radar count drops to zero.

#### Completion Criteria
- Quality Score reaches 90–100%.
- Unresolved Conflicts KPI shows `0`.
- All schedule cards transition from `DRAFT` to `PUBLISHED`.
- Student view displays the newly finalized schedule.

---

### Workflow 2: Faculty Timetable & Availability Review
**Audience**: Faculty Members, Instructors, Department Teaching Staff  
**Goal**: Review assigned teaching workload, weekly timetable, and configure preferred/blackout availability windows.

#### Prerequisites
- Role set to `FACULTY` (e.g., Prof. Juan Santos).

#### Step-by-Step User Actions
1. In the top bar, switch **"View As"** to **"Faculty (Prof. Santos)"**.
2. Navigate to **Schedules** (`/schedules`):
   - Notice the timetable displays only classes assigned to Prof. Santos.
   - The administrative controls ("Generate Drafts", "Publish All", "Add Schedule") and row mutation buttons are hidden.
3. Navigate to **Reports** (`/reports`) or open the **Faculty Tab** in `/manage?tab=faculty`:
   - Inspect the **Faculty Workload Progress Bar**: shows assigned units against the standard 21-unit maximum limit (e.g., `10 / 21 units (48%)`).
   - Check the teaching hours per week (e.g., `8.0 hrs/wk`).
4. In `/manage?tab=faculty`, locate Prof. Santos and click **"Availability"**:
   - The **Faculty Availability Windows** modal slides open.
   - Review current preferred hours (green) and blackout windows (red).
5. To add a blackout constraint (e.g., attending graduate study on Friday 1:00 PM – 5:00 PM):
   - Select Day: `FRIDAY`.
   - Start Time: `13:00`, End Time: `17:00`.
   - Window Type: `Blackout / Unavailable`.
   - Click **"Add Window"**.
   *(Note: The current prototype allows authorized faculty and chair users to view and update availability records across faculty members for seamless demonstration).*

#### System Response & Technical Flow
- `GET /api/faculty/1/availability`: Returns list of preferred and blackout time spans (`HTTP 200`).
- `POST /api/faculty/1/availability`: Stores new `FacultyAvailability` record (`HTTP 201`).
- The conflict engine automatically registers this blackout as Hard Constraint 5 (HC5), flagging any scheduled class during this window as a violation.

#### Completion Criteria
- Timetable reflects instructor-specific teaching schedule.
- Availability modal displays the newly added blackout window.
- Administrative mutation buttons remain disabled/hidden.

---

### Workflow 3: Student Published Timetable & Section Schedule Export
**Audience**: Engineering Students, Section Representatives  
**Goal**: View official published section timetable and export a clean, printable PDF copy.

#### Prerequisites
- Role set to `STUDENT` (e.g., CpE 2A).

#### Step-by-Step User Actions
1. In the top bar, select **"View As: Student (CpE 2A)"**.
2. Navigate to **Schedules** (`/schedules`):
   - The section filter defaults to `CpE 2A`.
   - Notice that **only PUBLISHED schedules** are visible. Any tentative draft schedules created by the department chair are completely hidden by the backend query filter.
   - Administrative controls ("Generate Drafts", "Publish All", "Add Class", "Delete") and master management tabs are hidden from the UI.
3. Click the **"Print / PDF"** button in the top controls bar.
4. The browser's native print preview dialog opens:
   - Dedicated print stylesheet (`@media print`) activates.
   - The maroon sidebar, top bar, search dropdowns, and buttons are automatically hidden.
   - The weekly timetable renders cleanly onto a standard single-page landscape layout with complete subject titles, faculty names, room codes, and timeslots.
5. Select "Save as PDF" or send to the physical printer.

#### System Response & Technical Flow
- `GET /api/schedules?section_id=2`: The server-side route checks `session["active_role"] == "STUDENT"` and injects `filter(Schedule.status == "PUBLISHED")`.
- HTTP 200 returns only finalized, published courses.
- `window.print()` executes formatted print output.

#### Completion Criteria
- Student sees only official published courses for their section.
- Draft items and editing tools are completely inaccessible.
- Clean PDF export without extraneous web UI chrome.

---

### Workflow 4: Master Data Relational Lifecycle Management
**Audience**: Department Chair, Academic Records Administrator  
**Goal**: Maintain integrity of core academic resources: Rooms, Faculty, Sections, Subjects, and Offerings.

#### Prerequisites
- Role set to `CHAIR` or `ADMIN`.
- Access to `/manage`.

#### Step-by-Step User Actions
1. Navigate to **Master Data Management** (`/manage`).
2. **Rooms Tab**:
   - Filter by type (`LECTURE` vs `LAB`) or search `Eng-104`.
   - Click **"+ Add Room"**: enter Room Code (`Eng-305`), Type (`LAB`), Capacity (`40`), Status (`Available`).
   - Click **"Save Changes"**.
3. **Faculty Tab**:
   - Search by faculty name or toggle "Overloaded Only".
   - Click **"+ Add Faculty"**: enter Name (`Engr. Patricia Gomez`), Email (`patricia.gomez@bulsu.edu.ph`), Max Units (`21`).
4. **Sections Tab**:
   - Filter by Program (`BSCpE`) and Year Level (`3`).
   - Click **"+ Add Section"**: Name (`CpE 3B`), Program (`BSCpE`), Year (`3`), Student Count (`38`).
5. **Subjects Tab**:
   - Search by code or filter by units.
   - Click **"+ Add Subject"**: Code (`CPE 312`), Title (`Embedded Systems Design`), Units (`3`), Type (`LAB`), Contact Hours (`5`).
6. **Relational Constraints Enforcement**:
   - Every scheduled class requires valid foreign key relationships: `room_id`, `faculty_id`, `section_id`, and `subject_id`.
   - The database enforces `PRAGMA foreign_keys = ON`, preventing orphaned schedule records.

#### System Response & Technical Flow
- `POST /api/rooms`, `POST /api/faculty`, `POST /api/sections`, `POST /api/subjects`: Return `HTTP 201 Created` with the newly serialized entity.
- Audit logs record entity creation with timestamp and user reference.
- Dynamic count badges on tabs (`Rooms (9)`, `Faculty (7)`, etc.) update immediately.

#### Completion Criteria
- Entities appear in their respective data tables.
- Entities are immediately available in the dropdown selectors of the Schedules view.

---

### Workflow 5: Real-Time Conflict Radar & 1-Click Alternative Resolution
**Audience**: Department Chair, Academic Schedulers  
**Goal**: Detect schedule clashes and execute 1-click automated resolution via the Conflict Radar.

#### Prerequisites
- Role set to `CHAIR` or `ADMIN`.
- A schedule with an existing conflict (e.g., pre-seeded room double-booking on Wednesday 11:00 AM).

#### Step-by-Step User Actions
1. Open **Schedules** (`/schedules`).
2. Identify a card rendered with an amber background and orange border with the label `[CONFLICT]`.
3. Click the conflicted class card or click **"Conflict Radar"** in the sidebar.
4. The **Real-Time Conflict Radar slide-out drawer** opens from the right side of the screen.
5. In the drawer header, observe the category filters with dynamic counts:
   - `ALL (5)`
   - `ROOM (2)`
   - `FACULTY (1)`
   - `SECTION (1)`
   - `CAPACITY (1)`
6. Click the `ROOM` filter to isolate room double-bookings.
7. Click the specific conflict card:
   - Diagnostic explanation: *"Room Eng-104 is double-booked on WED 11:00 AM - 12:30 PM with CPE 211 (CpE 2A) and ECE 201 (ECE 2A)"*.
8. Under **Recommended Resolution Alternatives**:
   - **Alternative 1 (Alt Room)**: Move to `Eng-201 (Lecture Hall - Capacity: 50)`.
   - **Alternative 2 (Alt Slot)**: Move to `Thursday 1:00 PM – 2:30 PM in Eng-104`.
9. Click the green **"Apply Alternative (Eng-201)"** button.
10. The Conflict Radar drawer automatically updates, recalculates overlaps, and decreases the conflict count.

#### System Response & Technical Flow
- `POST /api/conflicts/check`: Pre-flight endpoint validates the proposed alternative against all 6 Hard Constraints.
- `PUT /api/schedules/<id>`: Updates the schedule record with the new `room_id`.
- The timetable grid dynamically recolors the card from amber (`--event-conflict-bg`) to mint (`--event-scheduled-bg`).
- The Conflict Radar counter in the sidebar and dashboard KPI decrements by 1.

#### Completion Criteria
- Conflict card disappears from the Conflict Radar list.
- Timetable card status badge transitions to green "Scheduled".
- Database reflects the updated room assignment.

---

### Workflow 6: Executive Dashboard & Operational Monitoring
**Audience**: College Dean, Associate Dean, Department Chairs  
**Goal**: Monitor college-wide academic scheduling KPIs, switch visualization modes, and export summary datasets.

#### Prerequisites
- Access to `/`.

#### Step-by-Step User Actions
1. Open the **Dashboard** (`/`).
2. Review the **4 Top KPI Cards**:
   - **Total Schedules**: Total active class offerings (e.g., `14 Classes`).
   - **Active Rooms**: Total available instructional rooms (e.g., `8 Available`).
   - **Faculty Members**: Total registered teaching staff (e.g., `6 Instructors`).
   - **Conflicts Needing Review**: Live count of unresolved collisions (highlighted in amber).
3. Under the **Schedule Overview** section:
   - Use the **View Toggle** pills to switch between **"Table View"** and **"Timetable Grid"**.
4. Apply Quick Filters:
   - Select Program: `BSCpE`.
   - Select Section: `CpE 2A`.
   - Select Room: `Eng-104`.
   - Table rows update immediately to reflect the filtered criteria.
5. Click **"Export CSV"**:
   - Browser downloads `BulSU_COE_Schedules_<timestamp>.csv` containing columns: Schedule ID, Day, Time, Section, Subject Code, Subject Title, Faculty, Room, Status.
6. Click **"Print / PDF"** to produce an executive briefing report.

#### System Response & Technical Flow
- `GET /api/analytics/summary`: Supplies live metric aggregates for the KPI cards.
- `GET /api/schedules`: Loads the schedule dataset.
- Pure client-side CSV generator converts dataset into an RFC 4180-compliant CSV and triggers browser download.

#### Completion Criteria
- KPI metrics accurately reflect database records.
- View toggle smoothly switches between table and grid without state loss.
- Downloaded CSV matches the active schedule data.

---

### Workflow 7: Institutional Analytics & Term Workload Reporting
**Audience**: College Dean, Department Chair, Curriculum Committee  
**Goal**: Analyze room utilization efficiency against weekly operating hours and audit faculty workload distribution against university policies.

#### Prerequisites
- Access to **Reports** (`/reports`).

#### Step-by-Step User Actions
1. Navigate to **Reports** (`/reports`) via the sidebar navigation.
2. Review the **Institutional KPI Cards**:
   - **Average Room Utilization %**: Calculated against standard operating capacity (6 days × 12 hours = 72 hours/week).
   - **Faculty Overload Status**: Count of instructors exceeding the 21-unit policy cap.
   - **Schedule Quality Score**: Comprehensive metric penalizing student gap hours and room seat waste.
   - **Total Scheduled Classes**: Active class offerings.
3. Configure the **Reports Filter Toolbar**:
   - Academic Term: `1st Semester AY 2026–2027`.
   - Section Scope: Select `CpE 2A` to isolate facilities and faculty involved with this cohort.
   - Room Type: Filter between `Lecture Rooms Only` and `Laboratories Only`.
   - Utilization Threshold: Select `> 75% High Utilization` to inspect congested facilities.
4. Inspect the **Zero-CDN Visual Progress Meters**:
   - **Room Utilization & Facility Load**:
     - Visual bar meters for each room displaying scheduled hours vs. 72-hour operating capacity (e.g., `Eng-104: 6.5h / 72.0h (9.0%)`).
     - Color-coded: Blue (<50% safe), Amber (50–75% moderate), Purple (>75% peak).
   - **Faculty Workload Distribution**:
     - Visual bar meters for each instructor displaying assigned units vs. 21-unit maximum limit (e.g., `Prof. Santos: 10 / 21 units (48%)`).
     - Status badges: Mint `NORMAL`, Amber `NEAR MAX`, Crimson `OVERLOADED`.
5. Review the **Detailed Matrix Tables**:
   - **Room Capacity & Hours Matrix**: Room Code, Type, Capacity, Scheduled Hours, Weekly Max (72h), Utilization %, Status.
   - **Faculty Workload Matrix**: Faculty Member, Email, Teaching Hours, Assigned Units, Max Limit, Load %, Status.
6. Click **"Export CSV"** (`#btn-export-reports`) to generate the full institutional utilization CSV.
7. Click **"Print / PDF"** (`#btn-print-reports`) to generate a formal accreditation-ready report.

#### System Response & Technical Flow
- `GET /api/analytics/summary`: Returns precomputed `room_breakdown`, `faculty_workloads`, and `section_breakdown`.
- In-memory reactive filtering dynamically updates both the visual meter cards and data tables.
- `@media print` rules format the page for executive presentation.

#### Completion Criteria
- Utilization metrics align with weekly 72-hour operating capacity.
- Overloaded instructors (>21 units) are clearly flagged with crimson indicators.
- CSV export and print preview generate clean, verified reports.

---

## 5. Constraint Engine & Technical Rule Specification

The COE SYNC 2026 deterministic validation engine enforces constraints categorized into Hard and Soft rules:

### 5.1 Hard Constraints (Zero Tolerance — Strictly Blocked)
| Code | Rule Name | Description | Conflict Type |
| :--- | :--- | :--- | :--- |
| **HC1** | **Room Collision** | A room cannot host two overlapping classes on the same day. | `ROOM_COLLISION` |
| **HC2** | **Faculty Overlap** | An instructor cannot teach two classes simultaneously. | `FACULTY_OVERLAP` |
| **HC3** | **Section Collision** | A student cohort cannot be scheduled for two classes at the same time. | `SECTION_COLLISION` |
| **HC4** | **Room Capacity** | Room capacity must equal or exceed the section's student count. | `CAPACITY_OVERFLOW` |
| **HC5** | **Faculty Availability** | Classes cannot be scheduled during a faculty member's blackout window. | `FACULTY_BLACKOUT` |
| **HC6** | **Room Type Match** | Laboratory subjects must be assigned to laboratory rooms (`room_type = 'LAB'`). | `ROOM_TYPE_MISMATCH` |

### 5.2 Soft Constraints (Optimization Heuristics — Scored)
| Code | Rule Name | Optimization Target | Penalty |
| :--- | :--- | :--- | :--- |
| **SC1** | **Section Idle Gaps** | Avoid gap windows > 2 hours between classes in a section's daily timetable. | -5 points per violation |
| **SC2** | **Seat Overcapacity Waste** | Avoid assigning large rooms (>50 seats excess) to small student sections. | -5 points per violation |
| **SC3** | **Faculty Load Balance** | Distribute teaching units evenly without exceeding 21 units. | Flagged in analytics |

---

## 6. Scope Guard: Current Prototype vs. Future Roadmap

To ensure technical transparency during hackathon evaluation, the table below strictly demarcates operational prototype capabilities from planned post-hackathon integrations:

| Functional Area | Current Working Prototype (Phase 4/5) | Future University Integration Roadmap (Post-Hackathon) |
| :--- | :--- | :--- |
| **Conflict Detection** | Deterministic pairwise overlap detection across all 6 Hard Constraints in Python/SQLAlchemy. | Asynchronous event-driven conflict worker with Celery & Redis. |
| **Alternative Recommendation** | Heuristic ranking of vacant rooms and time slots in 30-minute intervals. | Genetic / Integer Linear Programming (ILP) solver for full-semester timetable synthesis. |
| **User Roles & Impersonation** | Sticky "View As" presentation switcher with session-backed role enforcement. | BulSU Active Directory / LDAP / OAuth2 Single Sign-On (SSO) with MFA. |
| **Student Access** | Row-level isolation displaying only `PUBLISHED` schedules for the student's cohort. | Student Mobile App (React Native/PWA) with enrollment cart sync. |
| **Notifications** | Real-time in-app visual toast notifications and Conflict Radar drawer. | Automated SMS (Twilio/Telco gateway) and Email/Push schedule change alerts. |
| **Faculty Availability** | Direct interactive window editor in `/manage` with full schedule constraint linkage. | Self-service Faculty Portal with official Dean approval workflows. |
| **Ad-Hoc Rebooking** | Standard CRUD schedule modification with preflight conflict checking. | Real-time ad-hoc classroom rebooking with QR code door-reader check-ins. |
| **Curriculum Intelligence** | Relational Subject-Section-Offering links with contact hours and unit limits. | Automated syllabus submission tracking, grading deadline sync, and AI academic advisor. |
| **Analytics & Reporting** | Zero-CDN CSS/SVG progress meters, CSV export, and print stylesheets. | Institutional BI dashboard with historical trend forecasting and accreditation audit exports. |

---

## 7. Troubleshooting & Operational FAQ

### Q1: Why is the "Publish All" button disabled or returning an error?
**A**: The system enforces absolute schedule integrity. If any unresolved hard conflict exists in the schedule dataset, `POST /api/schedules/publish-all` returns `HTTP 409 Conflict`. Open the Conflict Radar drawer, apply suggested alternatives until conflicts equal zero, and publish will succeed.

### Q2: Why cannot a student view draft classes?
**A**: By design, `routes/schedules.py` enforces row-level security: when `active_role == 'STUDENT'`, only records with `status == 'PUBLISHED'` are queried. Drafts remain strictly confidential to academic chairs until formally published.

### Q3: How do I test with a fresh dataset during live judging?
**A**: Click the **"Reset DB"** button in the top navigation bar. It invokes `POST /api/seed`, resetting all tables and populating realistic faculty, rooms, sections, and pre-staged conflict scenarios in under two seconds.

---

## 8. Phase 5 Governance Features & Role-Specific Portals

Phase 5 establishes enterprise-grade academic governance workflows and personalized portal views for Faculty and Students:

### 8.1 Multi-Tier Student Reschedule Request Pipeline
Students can initiate schedule adjustment proposals directly from published classes on their section timetable. The request follows a strict two-tier approval lifecycle:

```
[Student Submission]
       │
       ▼
[Faculty Endorsement] ──(Rejected)──► [REJECTED (with feedback)]
       │ (Approved)
       ▼
[Program Chair Decision] ──(Rejected)──► [REJECTED (with feedback)]
       │ (Approved)
       ▼
[APPROVED & Timetable Atomically Mutated]
```

#### API Endpoints:
- `POST /api/reschedule/request` (`@require_roles('STUDENT')`):
  - Validates section ownership of `schedule_id`.
  - Runs preflight conflict check via `validate_schedule_slot()`. If the proposed slot collides with active bookings, returns `HTTP 409` with conflict diagnostics and alternative suggestions.
  - Creates `RescheduleRequest` with status `PENDING_FACULTY`.
- `GET /api/reschedule/requests`:
  - Scoped by role: `STUDENT` receives requests submitted by their section; `FACULTY` receives proposals for their assigned courses; `CHAIR`/`ADMIN` receives all proposals or those awaiting final decision (`PENDING_CHAIR`).
- `POST /api/reschedule/<id>/faculty-review` (`@require_roles('FACULTY', 'CHAIR', 'ADMIN')`):
  - Transitions proposal from `PENDING_FACULTY` to `PENDING_CHAIR` (if approved) or `REJECTED` (with feedback).
- `POST /api/reschedule/<id>/chair-decision` (`@require_roles('CHAIR', 'ADMIN')`):
  - If approved, re-verifies that zero conflicts exist at execution time, atomically mutates `Schedule.day_of_week`, `Schedule.start_time`, and `Schedule.end_time`, and marks the request `APPROVED`.

### 8.2 Program Chair Active / Out-of-Office Availability
Enables the Program Chair to broadcast real-time availability to instructional staff while strictly preserving privacy isolation from students:
- `POST /api/chair/status` (`@require_roles('CHAIR', 'ADMIN')`):
  - Toggles `is_active_status` boolean on the Program Chair account and records an entry in `AuditLog`.
- `GET /api/chair/status`:
  - **Role Isolation**:
    - For `CHAIR`, `ADMIN`, and `FACULTY`: Returns `{ "chair_name": "...", "is_active": true/false }`.
    - For `STUDENT`: Returns `HTTP 403 Forbidden` with `{ "is_active": null }`. The frontend completely hides the widget from the student DOM.

### 8.3 Faculty Portal View
Activated when "View As" is set to `FACULTY`:
1. **Chair Status Badge**: Displays "Program Chair: ● Active" or "● Out of Office" in read-only pill format.
2. **Faculty Teaching Load Bar**: Shows current assigned teaching units against the 21-unit cap (e.g., `18 / 21 Teaching Units`) with a live progress meter and amber overload badge if exceeded.
3. **Weekly Personal Timetable**: Filtered strictly to classes assigned to the logged-in instructor.
4. **Reschedules Modal Tab**: Quick-action interface to endorse or reject pending student proposals with feedback.

### 8.4 Student Portal View
Activated when "View As" is set to `STUDENT`:
1. **Strict UI Lockdown**:
   - Chair status badge is completely removed.
   - Master Data Management (`/manage`), Conflict Radar drawer, and DRAFT schedules are inaccessible.
2. **Cohort Timetable**: Filtered strictly to their enrolled section (e.g., CpE 2A).
3. **Reschedule Action Trigger**: Each published class card renders a clean `✎ Reschedule` button, opening the proposal modal with day/time inputs and reason textarea.
4. **Reschedule Status Tracker**: Multi-step visual stepper tracking submissions from `Pending Faculty Review` ➔ `Pending Program Chair Approval` ➔ `Approved / Rejected`.
5. **Clean Print Export**: Formatted for browser-native PDF export and printing.

### 8.5 Analytics & Schedule Quality Scoring
Available at `GET /api/analytics/reports` and rendered in the `/reports` view:
- **Room Utilization %**: Weekly scheduled hours per room evaluated against the 72-hour operating benchmark (Mon–Sat, 7:00 AM – 7:00 PM).
- **Faculty Workload**: Tracks teaching units against 21 max units, highlighting overload conditions.
- **Schedule Quality Score (out of 100)**:
  - Base: 100 points.
  - `-5` deduction per section daily idle gap exceeding 2 hours.
  - `-5` deduction per room assignment where unassigned seats exceed 30.
  - Itemized deduction breakdown table returned in the API and rendered in `/reports`.

---
*COE SYNC 2026 — Engineering Academic Excellence through Synchronized Scheduling.*

