# COE SYNC 2026 — College of Engineering Academic & Schedule Conflict Management System

## Phase 1, 2 & 3: Conflict Engine, Master Data Management & Wireframe Frontend Shell

### 1. Overview
**COE SYNC 2026** is the official academic management and schedule conflict management system engineered for the BulSU College of Engineering (COE). Phase 3 establishes:
- **Wireframe 1 Implementation (Dashboard)**:
  - Deep maroon/burgundy sidebar (`#4A1521` / `#3B111A`) with warm gold/amber active navigation pills (`#F5C26B`).
  - Warm light-gray/off-white background (`#F9F9F8`).
  - Hero banner container with engineering term branding (`[Campus photo]`).
  - 4 KPI summary cards (Schedules, Rooms, Faculty, Conflicts · needs review).
  - Conflict Radar summary table with "View all" trigger.
- **Wireframe 2 Implementation (Schedules)**:
  - Weekly navigation controls (`<`, `>`, `Today`, `Week` toggle).
  - 4 Dropdown filters: `[All Programs]`, `[All Sections]`, `[All Faculty]`, `[All Rooms]`.
  - Timetable matrix with color-coded event cards (Scheduled mint/teal, Alternate program rose, Conflict amber/orange border).
- **Master Data Management Interface (`/manage`)**:
  - Horizontal tab bar: `[Rooms]` | `[Faculty]` | `[Sections]` | `[Subjects]` with live counts.
  - Full CRUD operations with standard action modals, client-side validation, and instant updates.
- **Sticky "View As" Role Impersonator**:
  - Top bar dropdown for `[ Program Chair | Faculty | Student ]`.
  - Instantly calls `POST /api/auth/impersonate` and updates active UI permissions (e.g. hiding edit/delete controls for Student/Faculty).
- **Easy-to-Tweak Separation**:
  - Centralized design tokens in `static/css/theme.css`.
  - Reusable fetch client in `static/js/api.js`.
  - Modular scripts for Master Data (`manage.js`), Dashboard (`dashboard.js`), and Timetable (`schedules_view.js`).

---

### 2. Architecture & File Structure
```text
coe_sync/
├── .env                  # Active local environment variables
├── .env.example          # Environment configuration template
├── requirements.txt      # Python dependencies
├── config.py             # App & Database configuration
├── app.py                # Flask entrypoint & Blueprint registration
├── models.py             # SQLAlchemy models with cascading foreign keys
├── seed_data.py          # Idempotent database wipe & seed script
├── coe_sync.db           # Local SQLite database (enforces PRAGMA foreign_keys = ON)
├── services/
│   ├── __init__.py
│   └── conflict_detector.py # Hard Constraint checks & 3-step recommendation heuristics
├── routes/
│   ├── __init__.py
│   ├── auth.py           # Authentication, RBAC guards & presentation pitch bar
│   ├── schedules.py      # CRUD endpoints & pre-flight conflict check
│   ├── analytics.py      # Room utilization %, quality score & workloads
│   ├── master_data.py    # CRUD endpoints for Rooms, Faculty, Sections, Subjects
│   └── views.py          # Frontend template page routes (/, /manage, /schedules)
├── tests/
│   ├── __init__.py
│   └── test_conflict_engine.py # Automated test suite (8 assertions passed)
├── static/
│   ├── css/
│   │   ├── theme.css     # Centralized design tokens (colors, radii, spacing)
│   │   └── styles.css    # Layout shell, dashboard, manage tables, schedules grid
│   └── js/
│       ├── api.js        # Reusable API fetch client with error handling
│       ├── app.js        # Shell logic, sticky View As selector, notifications
│       ├── dashboard.js  # Dashboard metrics & Conflict Radar controller
│       ├── manage.js     # Master Data 4-tab CRUD & modal controller
│       └── schedules_view.js # Timetable grid & filter controller
└── templates/
    ├── base.html         # Persistent sidebar, sticky topbar, modal injection shell
    ├── dashboard.html    # Wireframe 1: Hero, 4 KPI cards, Conflict Radar
    ├── manage.html       # Section 7: Master Data 4-tab CRUD interface
    └── schedules.html    # Wireframe 2: Weekly timetable grid shell
```

---

### 3. Master Data Management (`/manage`)

The `/manage` route implements the Section 7 master data console:
1. **Rooms**:
   - Fields: Code, Type (`LECTURE` / `LAB`), Capacity, Availability Status.
   - Operations: Add, Edit, Delete, filter by type.
2. **Faculty**:
   - Fields: Name, Email, Max Units, Current Assigned Units (with progress bar), Availability.
   - Operations: Add, Edit, Delete, workload tracking.
3. **Sections**:
   - Fields: Section Name (e.g. `CpE 2A`), Degree Program, Year Level, Enrolled Student Count.
   - Operations: Add, Edit, Delete.
4. **Subjects**:
   - Fields: Course Code, Descriptive Title, Credit Units, Delivery Type (`LECTURE` / `LAB`), Contact Hours/Week.
   - Operations: Add, Edit, Delete.

All modals perform real-time client validation (e.g. `capacity > 0`, `units > 0`, valid email formats) before dispatching to the backend.

---

### 4. Running and Testing
Start the server:
```bash
python app.py
```
Visit in your browser:
- **Dashboard**: `http://127.0.0.1:5000/`
- **Master Data**: `http://127.0.0.1:5000/manage`
- **Schedules**: `http://127.0.0.1:5000/schedules`
- **Reports & Institutional Analytics**: `http://127.0.0.1:5000/reports`
- **User & Technical Operations Guide**: [docs/USER_OPERATIONS_GUIDE.md](file:///c:/Users/Marcus%20Andrei%20Guinto/Documents/Bulsu_Unified_Management/coe_sync/docs/USER_OPERATIONS_GUIDE.md)

---

### 5. Phase 5 Governance, Role Portals & Features
1. **Multi-tier Student Reschedule Pipeline**:
   - `POST /api/reschedule/request`: Students submit slot change proposals for their section with preflight conflict checking.
   - `GET /api/reschedule/requests`: Role-scoped requests queue (`STUDENT`, `FACULTY`, `CHAIR`, `ADMIN`).
   - `POST /api/reschedule/<id>/faculty-review`: Faculty reviews & endorses (`PENDING_CHAIR`) or rejects (`REJECTED`) with feedback.
   - `POST /api/reschedule/<id>/chair-decision`: Program Chair authorizes with zero-conflict validation, atomically mutating the timetable.
2. **Program Chair Active/Inactive Status**:
   - `POST /api/chair/status`: Program Chair toggles "Active" vs. "Out of Office / Inactive" with audit logging.
   - `GET /api/chair/status`: Strict visibility isolation (visible to Faculty, Chair, Admin; HTTP 403 / hidden from Students).
3. **Role-Specific Portals**:
   - **Faculty Portal**: Displays Chair availability badge, Teaching Load progress meter vs. 21 max units with overload warning, personal timetable, and student reschedule approval controls.
   - **Student Portal**: Strict UI lockdown (Chair status and `/manage` hidden), cohort timetable filter, `✎ Reschedule` card buttons, and visual request status tracker stepper.
4. **Analytics & Schedule Quality Scoring (`/reports`)**:
   - Evaluates schedule quality score out of 100 with itemized deductions (-5 for idle gaps > 2h, -5 for unassigned seats > 30).
   - Room utilization ranking vs. 72-hour weekly capacity benchmark.
   - Faculty teaching workload distribution vs. 21-unit cap with CSV export.

---

### 6. Automated Test Suites
Run the complete automated test suite (18 assertions):
```bash
# Phase 2: Conflict Engine & RBAC Constraints (8 tests)
python tests/test_conflict_engine.py

# Phase 4: Core Workflows & Timetable Interactions (6 tests)
python tests/test_phase4_workflows.py

# Phase 5: Multi-tier Reschedule, Chair Status & Analytics (4 tests)
python tests/test_phase5_governance.py
```

