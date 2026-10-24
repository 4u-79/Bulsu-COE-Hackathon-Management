# BulSU COE Hackathon Management — COE SYNC 2026

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Flask 3.0](https://img.shields.io/badge/flask-3.0+-green.svg)](https://palletsprojects.com/p/flask/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Test Suite](https://img.shields.io/badge/tests-55%20passed-brightgreen.svg)]()

> **Centralized Academic Timetable Scheduling, Multi-Constraint Conflict Engine, and Master Data Management System** engineered for the **Bulacan State University (BulSU) College of Engineering**.

---

## 🌟 Key Features

- **⚡ Real-Time Multi-Constraint Conflict Detection Engine**:
  - Automatically identifies **Room Collisions**, **Faculty Double-Booking**, **Section Overlaps**, and **Capacity Overflows**.
  - Provides preflight conflict verification before any schedule is saved or committed.
  - Interactive **Conflict Radar** slide-out drawer with 1-click intelligent resolution suggestions.

- **📅 Interactive Weekly Timetable Matrix**:
  - Color-coded schedule cards with status indicators (Mint: Scheduled, Amber: Conflict / Needs Review, Rose: Alternate Program / Lab).
  - Multi-dimensional filters (Program, Year Level, Section, Faculty, Room, Status).
  - Time slot grid from Monday to Saturday, 7:00 AM – 7:00 PM.

- **🛠️ Master Data Management Console (`/manage`)**:
  - Full CRUD operations with modal validation for **Rooms**, **Faculty**, **Sections**, and **Subjects**.
  - Dynamic faculty workload tracking with unit caps and overload prevention.
  - Section enrollment sizing and lab/lecture room capacity compliance.

- **🎭 Sticky Role Impersonator ("View As") & RBAC**:
  - Seamlessly switch between **Program Chair (`CHAIR`)**, **Faculty (`FACULTY`)**, and **Student (`STUDENT`)** roles without re-logging.
  - Instant client-side permission adaptations (students see published schedules only; faculty view personal teaching loads; chairs access admin controls).

- **📊 Visual Analytics & Reporting (`/reports`)**:
  - Room utilization rate metrics.
  - Faculty workload distribution meters.
  - Printable/exportable term schedule matrices.

- **🚀 Smart Schedule Optimizer & Reschedule Workflow**:
  - Heuristic-based slot recommendation engine for clash-free automated rescheduling.
  - Audit logging for governance and tracking schedule changes.

- **🌐 Zero CDN Dependencies**:
  - Pure Vanilla HTML5, CSS3, and ES6 JavaScript. Runs 100% offline with zero external network dependencies.

---

## 🏗️ Architecture & Project Structure

```text
Bulsu_Unified_Management/
├── .env.example              # Environment configuration example
├── .gitignore                # Git ignore rules (bytecode, db, secrets)
├── README.md                 # Root repository overview and setup guide
├── requirements.txt          # Python dependencies
├── run.py                    # Root entrypoint launcher
└── coe_sync/                 # Core application package
    ├── app.py                # Flask application factory & blueprint registry
    ├── config.py             # App configurations (Development, Testing, Production)
    ├── models.py             # SQLAlchemy models (User, Faculty, Room, Schedule, etc.)
    ├── seed_data.py          # Idempotent database wiping and seeding script
    ├── requirements.txt      # Module dependencies
    ├── docs/
    │   └── USER_OPERATIONS_GUIDE.md # Comprehensive Technical & Operations manual
    ├── routes/
    │   ├── analytics.py      # Room utilization & workload analytics endpoints
    │   ├── auth.py           # Authentication, RBAC, and impersonation API
    │   ├── chair.py          # Program Chair batch operations & publishing
    │   ├── master_data.py    # CRUD endpoints for Rooms, Faculty, Sections, Subjects
    │   ├── reschedule.py     # Reschedule request workflow
    │   ├── schedules.py      # Schedule CRUD & preflight conflict engine
    │   └── views.py          # HTML template page renderers
    ├── services/
    │   ├── conflict_detector.py # Hard constraint checking & heuristics
    │   └── scheduler.py      # Smart scheduling & recommendation engine
    ├── static/
    │   ├── css/
    │   │   ├── styles.css    # Shell layouts, cards, modals, and tables
    │   │   ├── theme.css     # Centralized BulSU maroon & amber design tokens
    │   │   └── timetable.css # Weekly timetable grid formatting
    │   ├── img/              # University branding & campus imagery
    │   └── js/
    │       ├── api.js        # Centralized fetch client & error handling
    │       ├── app.js        # Global shell logic & impersonator controller
    │       ├── create_schedule.js # Schedule creation & preflight checks
    │       ├── dashboard.js  # Dashboard charts & KPI counters
    │       ├── manage.js     # Master data 4-tab CRUD modal controller
    │       ├── reports.js    # Visual utilization meters & filters
    │       └── schedules_view.js # Timetable rendering & filter listeners
    ├── templates/            # Jinja2 HTML templates
    └── tests/                # Automated test suite (55 unit & integration tests)
```

---

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.10 or higher
- `git`
- `pip`

### 1. Clone the Repository
```bash
git clone https://github.com/4u-79/Bulsu-COE-Hackathon-Management.git
cd Bulsu-COE-Hackathon-Management
```

### 2. Set Up Virtual Environment (Recommended)
```bash
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
Copy `.env.example` to `coe_sync/.env`:
```bash
# Windows (PowerShell)
Copy-Item coe_sync\.env.example coe_sync\.env

# Linux / macOS
cp coe_sync/.env.example coe_sync/.env
```

### 5. Seed the Database
Initialize SQLite database with full mock data (6 faculty members, 8 rooms, 6 sections, 8 subjects, and staged conflict scenarios):
```bash
python coe_sync/seed_data.py
```

### 6. Run the Application
You can run the server directly from the root directory:
```bash
python run.py
```
*(Alternatively, `cd coe_sync && python app.py`)*

Open your browser and navigate to:
👉 **`http://127.0.0.1:5000`**

---

## 🔑 Demo & Test Credentials

The database comes pre-populated with accounts for evaluation and role testing:

| Role | Username | Password | Access Scope |
| :--- | :--- | :--- | :--- |
| **System Admin** | `admin` | `admin123` | Full system governance, audit logs, configuration |
| **Program Chair** | `chair_cpe` | `chair123` | Timetable authoring, conflict resolution, master data |
| **Faculty Member** | `prof_santos` | `faculty123` | Personal schedule view, teaching workload tracker |
| **Student (CpE 2A)** | `student_cpe2a` | `student123` | Published section schedule viewer only |

> 💡 **Hackathon Tip**: You can also use the **"View As"** dropdown in the navigation bar to instantly switch roles on the fly without logging in or out!

---

## 🧪 Running Automated Tests

The codebase includes an automated test suite with **55 unit and integration tests** covering RBAC, the conflict detection engine, smart scheduling heuristics, and security vectors:

```bash
python -m unittest discover -s coe_sync/tests
```

All 55 tests pass without external service requirements.

---

## 📄 License
This project was developed for the **BulSU College of Engineering Hackathon 2026** and is licensed under the [MIT License](LICENSE).
