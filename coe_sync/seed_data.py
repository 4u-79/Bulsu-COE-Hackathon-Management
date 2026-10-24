"""COE SYNC 2026 - Master Database Seeding & Migration Engine
Ingests data-2.sql as the Single Source of Truth for BulSU College of Engineering:
- 126 real BulSU COE faculty across 8 engineering departments + General Engineering
- 90 standardized Sections across 8 departments (CE - 1A to MEE - 4B)
- 267 normalized Subjects across all engineering curricula with LECTURE/LAB types
- Realistic COE 1 and COE 2 Rooms (Lecture halls and specialized labs)
- User accounts (admin, chair_cpe, chair, faculty, student)
- 1 Faculty blackout availability window (FRI 08:00-12:00)
- 0 pre-generated dummy schedules by default (clean slate for Smart Scheduler)
"""

import sys
from datetime import time
from pathlib import Path
from werkzeug.security import generate_password_hash

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from models import (
    db,
    User,
    Faculty,
    Section,
    Subject,
    Room,
    FacultyAvailability,
    Schedule,
    AuditLog,
    RescheduleRequest,
    Conflict,
)
from import_sql_dump import load_and_clean_sql_dump


def seed_database(app=None, stage_demo_schedules: bool = False):
    """
    Idempotent seeding function.
    Drops all existing tables, recreates schema, imports cleaned data-2.sql data,
    and initializes realistic BulSU COE master fixtures.
    """
    from app import create_app

    if app is None:
        app = create_app()

    with app.app_context():
        print("[COE SYNC 2026] Resetting and wiping database schema...")
        db.drop_all()
        db.create_all()
        print("[COE SYNC 2026] Schema recreated successfully.")

        # Load cleaned data from data-2.sql (Single Source of Truth)
        print("[COE SYNC 2026] Loading and cleaning data-2.sql...")
        dump_data = load_and_clean_sql_dump()

        # -------------------------------------------------------------
        # 1. Seed Faculty (126 real BulSU COE Faculty)
        # -------------------------------------------------------------
        print(f"[COE SYNC 2026] Seeding {len(dump_data['faculty'])} real BulSU COE Faculty members...")
        faculty_members = []
        for f in dump_data["faculty"]:
            faculty_members.append(
                Faculty(
                    id=f["id"],
                    name=f["name"],
                    email=f["email"],
                    program=f["program"],
                    max_units=f.get("max_units", 21),
                    current_units=0,
                )
            )
        db.session.add_all(faculty_members)
        db.session.flush()

        # -------------------------------------------------------------
        # 2. Seed Sections (90 Sections from CE - 1A to MEE - 4B)
        # -------------------------------------------------------------
        print(f"[COE SYNC 2026] Seeding {len(dump_data['sections'])} Section cohorts...")
        sections = []
        for s in dump_data["sections"]:
            sections.append(
                Section(
                    id=s["id"],
                    name=s["name"],
                    program=s["program"],
                    year_level=s["year_level"],
                    student_count=s.get("student_count", 40),
                )
            )
        db.session.add_all(sections)
        db.session.flush()

        # -------------------------------------------------------------
        # 3. Seed Subjects (267 Curricular Subjects from data-2.sql)
        # -------------------------------------------------------------
        print(f"[COE SYNC 2026] Seeding {len(dump_data['subjects'])} Subjects catalog...")
        subjects = []
        for s in dump_data["subjects"]:
            subjects.append(
                Subject(
                    id=s["id"],
                    code=s["code"],
                    title=s["title"],
                    program=s["program"],
                    units=s["units"],
                    subject_type=s["subject_type"],
                    hours_per_week=s["hours_per_week"],
                    year_level=s["year_level"],
                    semester=s["semester"],
                    split_preference=s["split_preference"],
                )
            )
        db.session.add_all(subjects)
        db.session.flush()

        # -------------------------------------------------------------
        # 4. Seed Realistic BulSU COE Rooms (COE 1 & COE 2 Buildings)
        # -------------------------------------------------------------
        print("[COE SYNC 2026] Seeding realistic BulSU COE Rooms (COE 1 & COE 2 Buildings)...")
        rooms = []

        # COE 1 Building: COE 101 - COE 107 (Lecture rooms)
        for room_num in range(101, 108):
            code = f"COE {room_num}"
            cap = 30 if room_num == 104 else 45  # COE 104 has capacity 30 for overcapacity test
            rooms.append(
                Room(
                    room_code=code,
                    room_type="LECTURE",
                    capacity=cap,
                    building="COE 1 Building",
                    equipment="Multimedia Projector, Whiteboard, Audio System" if room_num != 104 else "Whiteboard, TV Display",
                    is_available=True,
                )
            )

        # COE 1 Building: Specialized Laboratories
        coe1_labs = [
            ("CE Lab", "Civil Engineering Materials & Surveying Station"),
            ("EE Lab", "Electrical Machines & Power Systems Trainer"),
            ("MFGE Lab", "CNC Lathes, 3D Printers, CAD/CAM Workstations"),
            ("ME Lab", "Thermodynamics & Fluid Mechanics Apparatus"),
            ("Physics Lab", "Optics & Mechanics Experimental Benches"),
            ("Chem Lab", "Fume Hoods, Analytical Balances & Chemistry Benches"),
        ]
        for lab_code, equip in coe1_labs:
            rooms.append(
                Room(
                    room_code=lab_code,
                    room_type="LAB",
                    capacity=40,
                    building="COE 1 Building",
                    equipment=equip,
                    is_available=True,
                )
            )

        # COE 2 Building: COE 2 - 101 to COE 2 - 107
        for room_num in range(101, 108):
            rooms.append(
                Room(
                    room_code=f"COE 2 - {room_num}",
                    room_type="LECTURE",
                    capacity=45,
                    building="COE 2 Building",
                    equipment="Smart Display, Whiteboard, Podium",
                    is_available=True,
                )
            )

        # COE 2 Building: COE 2 - 201 to COE 2 - 206
        for room_num in range(201, 207):
            rooms.append(
                Room(
                    room_code=f"COE 2 - {room_num}",
                    room_type="LECTURE",
                    capacity=45,
                    building="COE 2 Building",
                    equipment="Multimedia Projector, Whiteboard",
                    is_available=True,
                )
            )

        # COE 2 Building: COE 2 - 301 to COE 2 - 306
        for room_num in range(301, 307):
            rooms.append(
                Room(
                    room_code=f"COE 2 - {room_num}",
                    room_type="LECTURE",
                    capacity=45,
                    building="COE 2 Building",
                    equipment="Smart TV, Whiteboard, Audio System",
                    is_available=True,
                )
            )

        # COE 2 Building: Specialized Laboratories
        coe2_labs = [
            ("CPE Lab", "Workstations, Gigabit Switch, Cisco Routers"),
            ("ECE Lab", "Oscilloscopes, Signal Generators, FPGA Kits"),
            ("IE Lab", "Human Factors & Ergonomics Workstations"),
            ("MEE Lab", "PLC Automation Trainers, Mechatronics Benches"),
        ]
        for lab_code, equip in coe2_labs:
            rooms.append(
                Room(
                    room_code=lab_code,
                    room_type="LAB",
                    capacity=40,
                    building="COE 2 Building",
                    equipment=equip,
                    is_available=True,
                )
            )

        db.session.add_all(rooms)
        db.session.flush()

        # -------------------------------------------------------------
        # 5. Seed Realistic User Accounts
        # -------------------------------------------------------------
        print("[COE SYNC 2026] Seeding User accounts with role-based reference IDs...")
        first_faculty = faculty_members[0]
        # Prefer a CPE faculty if available or first
        cpe_faculty = next((f for f in faculty_members if f.program == "CPE"), first_faculty)
        cpe_section = next((s for s in sections if "CPE" in s.name and "2" in s.name), sections[0])

        users = [
            User(
                username="admin",
                password_hash=generate_password_hash("admin123"),
                role="ADMIN",
                reference_id=None,
                must_change_credentials=False,
                is_active_status=True,
                demo_password="admin123",
            ),
            User(
                username="chair_cpe",
                password_hash=generate_password_hash("chair123"),
                role="CHAIR",
                reference_id=None,
                must_change_credentials=False,
                is_active_status=True,
                demo_password="chair123",
            ),
            User(
                username="chair",
                password_hash=generate_password_hash("chair123"),
                role="CHAIR",
                reference_id=None,
                must_change_credentials=False,
                is_active_status=True,
                demo_password="chair123",
            ),
            User(
                username="faculty",
                password_hash=generate_password_hash("faculty123"),
                role="FACULTY",
                reference_id=cpe_faculty.id,
                must_change_credentials=False,
                is_active_status=True,
                demo_password="faculty123",
            ),
            User(
                username="prof_santos",
                password_hash=generate_password_hash("faculty123"),
                role="FACULTY",
                reference_id=cpe_faculty.id,
                must_change_credentials=False,
                is_active_status=True,
                demo_password="faculty123",
            ),
            User(
                username="fac_santos",
                password_hash=generate_password_hash("faculty123"),
                role="FACULTY",
                reference_id=cpe_faculty.id,
                must_change_credentials=False,
                is_active_status=True,
                demo_password="faculty123",
            ),
            User(
                username="student",
                password_hash=generate_password_hash("student123"),
                role="STUDENT",
                reference_id=cpe_section.id,
                must_change_credentials=False,
                is_active_status=True,
                demo_password="student123",
            ),
            User(
                username="student_cpe2a",
                password_hash=generate_password_hash("student123"),
                role="STUDENT",
                reference_id=cpe_section.id,
                must_change_credentials=False,
                is_active_status=True,
                demo_password="student123",
            ),
        ]
        db.session.add_all(users)
        db.session.flush()

        # -------------------------------------------------------------
        # 6. Seed Faculty Availability (1 Blackout Window on Friday)
        # -------------------------------------------------------------
        print("[COE SYNC 2026] Seeding Faculty Availability Constraint...")
        unavailability = FacultyAvailability(
            faculty_id=cpe_faculty.id,
            day_of_week="FRI",
            start_time=time(8, 0, 0),
            end_time=time(12, 0, 0),
            is_preferred=False,
            split_preference="1.5_HOUR_SPLIT",
        )
        db.session.add(unavailability)
        db.session.flush()

        # -------------------------------------------------------------
        # 7. Schedules & Reschedule Requests: 0 by default
        # -------------------------------------------------------------
        schedules_data = []
        reschedule_requests = []

        if stage_demo_schedules:
            # Stage minimal schedules if explicitly requested
            subj_map = {s.code: s for s in subjects}
            room_map = {r.room_code: r for r in rooms}
            sec_target = cpe_section

            sample_subj = next((s for s in subjects if s.program in ("CPE", "GEN") and s.subject_type == "LECTURE"), subjects[0])
            sample_room = rooms[0]

            demo_sched = Schedule(
                subject_id=sample_subj.id,
                section_id=sec_target.id,
                faculty_id=cpe_faculty.id,
                room_id=sample_room.id,
                day_of_week="MON",
                start_time=time(8, 0),
                end_time=time(9, 30),
                status="PUBLISHED",
            )
            schedules_data.append(demo_sched)
            db.session.add_all(schedules_data)
            db.session.flush()

        # -------------------------------------------------------------
        # 8. Seed Audit Log Entry
        # -------------------------------------------------------------
        admin_user = next(u for u in users if u.username == "admin")
        audit_entry = AuditLog(
            user_id=admin_user.id,
            action="DATABASE_SEEDED",
            details=(
                f"data-2.sql ingestion complete: {len(faculty_members)} faculty, "
                f"{len(sections)} sections, {len(subjects)} subjects, {len(rooms)} rooms, "
                f"{len(schedules_data)} schedules."
            ),
        )
        db.session.add(audit_entry)

        db.session.commit()
        print(f"[COE SYNC 2026] Database successfully seeded with {len(faculty_members)} faculty, {len(sections)} sections, {len(subjects)} subjects, {len(rooms)} rooms, and {len(schedules_data)} schedules.")

        return {
            "users": len(users),
            "faculty": len(faculty_members),
            "sections": len(sections),
            "rooms": len(rooms),
            "subjects": len(subjects),
            "availabilities": 1,
            "schedules": len(schedules_data),
            "reschedule_requests": len(reschedule_requests),
        }


if __name__ == "__main__":
    seed_database()
