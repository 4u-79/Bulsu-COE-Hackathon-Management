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
    InterDepartmentRequest,
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

        # Load cleaned data from data-final.sql (Single Source of Truth)
        print("[COE SYNC 2026] Loading and cleaning data-final.sql...")
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
                    preferred_session_type=f.get("preferred_session_type", "SPLIT"),
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
                    class_mayor=s.get("class_mayor"),
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
                    split_preference=s.get("split_preference", "1.5_HOUR_SPLIT"),
                    is_general=s.get("is_general", False),
                    requires_grouping=s.get("requires_grouping", False),
                    preferred_session_type=s.get("preferred_session_type", "SPLIT"),
                )
            )
        db.session.add_all(subjects)
        db.session.flush()

        # -------------------------------------------------------------
        # 4. Seed Realistic BulSU COE Rooms (COE 1 & COE 2 Buildings)
        # Allocated across the 8 Engineering Departments + GEN Pool
        # -------------------------------------------------------------
        print("[COE SYNC 2026] Seeding department-allocated BulSU COE Rooms (COE 1 & COE 2 Buildings)...")
        rooms = []

        # Department room assignment mapping for lecture halls
        coe1_lecture_depts = {
            101: "CE",
            102: "CE",
            103: "EE",
            104: "EE",
            105: "MFGE",
            106: "MFGE",
            107: "ME",
        }

        # COE 1 Building: COE 101 - COE 107 (Lecture rooms)
        for room_num in range(101, 108):
            code = f"COE {room_num}"
            cap = 30 if room_num == 104 else 45  # COE 104 has capacity 30 for overcapacity test
            dept = coe1_lecture_depts.get(room_num, "GEN")
            rooms.append(
                Room(
                    room_code=code,
                    room_type="LECTURE",
                    capacity=cap,
                    building="COE 1 Building",
                    equipment="Multimedia Projector, Whiteboard, Audio System" if room_num != 104 else "Whiteboard, TV Display",
                    is_available=True,
                    department=dept,
                    booked_by_label=None,
                )
            )

        # COE 1 Building: Specialized Laboratories
        coe1_labs = [
            ("CE Lab", "Civil Engineering Materials & Surveying Station", "CE"),
            ("EE Lab", "Electrical Machines & Power Systems Trainer", "EE"),
            ("MFGE Lab", "CNC Lathes, 3D Printers, CAD/CAM Workstations", "MFGE"),
            ("ME Lab", "Thermodynamics & Fluid Mechanics Apparatus", "ME"),
            ("Physics Lab", "Optics & Mechanics Experimental Benches", "GEN"),
            ("Chem Lab", "Fume Hoods, Analytical Balances & Chemistry Benches", "GEN"),
        ]
        for lab_code, equip, dept in coe1_labs:
            rooms.append(
                Room(
                    room_code=lab_code,
                    room_type="LAB",
                    capacity=40,
                    building="COE 1 Building",
                    equipment=equip,
                    is_available=True,
                    department=dept,
                    booked_by_label=None,
                )
            )

        # COE 2 Building: COE 2 - 101 to COE 2 - 107
        coe2_floor1_depts = {
            101: "ME",
            102: "CPE",
            103: "CPE",
            104: "ECE",
            105: "ECE",
            106: "IE",
            107: "IE",
        }
        for room_num in range(101, 108):
            dept = coe2_floor1_depts.get(room_num, "GEN")
            rooms.append(
                Room(
                    room_code=f"COE 2 - {room_num}",
                    room_type="LECTURE",
                    capacity=45,
                    building="COE 2 Building",
                    equipment="Smart Display, Whiteboard, Podium",
                    is_available=True,
                    department=dept,
                    booked_by_label=None,
                )
            )

        # COE 2 Building: COE 2 - 201 to COE 2 - 206
        coe2_floor2_depts = {
            201: "MEE",
            202: "MEE",
            203: "GEN",
            204: "GEN",
            205: "GEN",
            206: "GEN",
        }
        for room_num in range(201, 207):
            dept = coe2_floor2_depts.get(room_num, "GEN")
            rooms.append(
                Room(
                    room_code=f"COE 2 - {room_num}",
                    room_type="LECTURE",
                    capacity=45,
                    building="COE 2 Building",
                    equipment="Multimedia Projector, Whiteboard",
                    is_available=True,
                    department=dept,
                    booked_by_label=None,
                )
            )

        # COE 2 Building: COE 2 - 301 to COE 2 - 306 (General COE Lecture Halls)
        for room_num in range(301, 307):
            rooms.append(
                Room(
                    room_code=f"COE 2 - {room_num}",
                    room_type="LECTURE",
                    capacity=45,
                    building="COE 2 Building",
                    equipment="Smart TV, Whiteboard, Audio System",
                    is_available=True,
                    department="GEN",
                    booked_by_label=None,
                )
            )

        # COE 2 Building: Specialized Laboratories
        coe2_labs = [
            ("CPE Lab", "Workstations, Gigabit Switch, Cisco Routers", "CPE"),
            ("ECE Lab", "Oscilloscopes, Signal Generators, FPGA Kits", "ECE"),
            ("IE Lab", "Human Factors & Ergonomics Workstations", "IE"),
            ("MEE Lab", "PLC Automation Trainers, Mechatronics Benches", "MEE"),
        ]
        for lab_code, equip, dept in coe2_labs:
            rooms.append(
                Room(
                    room_code=lab_code,
                    room_type="LAB",
                    capacity=40,
                    building="COE 2 Building",
                    equipment=equip,
                    is_available=True,
                    department=dept,
                    booked_by_label=None,
                )
            )

        # Ingest rooms from data-final.sql if present
        if "rooms" in dump_data and dump_data["rooms"]:
            existing_room_codes = {r.room_code for r in rooms}
            for rd in dump_data["rooms"]:
                rcode = rd["room_code"]
                if rcode not in existing_room_codes:
                    existing_room_codes.add(rcode)
                    rooms.append(
                        Room(
                            room_code=rcode,
                            room_type=rd.get("room_type", "LECTURE"),
                            capacity=rd.get("capacity", 45),
                            building=rd.get("building", "College of Engineering"),
                            equipment=rd.get("equipment", "Standard Classroom Amenities"),
                            is_available=True,
                            department=rd.get("department", "GEN"),
                            booked_by_label=None,
                        )
                    )

        db.session.add_all(rooms)
        db.session.flush()

        # -------------------------------------------------------------
        # 5. Seed Authoritative Ground-Truth Users & Aliases
        # -------------------------------------------------------------
        print("[COE SYNC 2026] Seeding User accounts with role-based reference IDs...")
        first_faculty = faculty_members[0]
        cpe_faculty = next((f for f in faculty_members if f.program == "CPE"), first_faculty)
        cpe_section = next((s for s in sections if "CPE" in s.name and "2" in s.name), sections[0])

        tullao_fac = next((f for f in faculty_members if "TULLAO" in f.name.upper()), first_faculty)
        bugayong_fac = next((f for f in faculty_members if "BUGAYONG" in f.name.upper()), first_faculty)
        roque_fac = next((f for f in faculty_members if "ROQUE" in f.name.upper()), first_faculty)

        mee_section = next((s for s in sections if "MEE" in s.name and "1A" in s.name.replace(" ", "")), sections[0])
        ce_section = next((s for s in sections if "CE" in s.name and "1A" in s.name.replace(" ", "")), sections[0])

        default_pwd_hash = generate_password_hash("password")
        seeded_usernames = set()
        user_objects = []

        # 5a. Seed 129 Authoritative Users from data-final.sql
        if "users" in dump_data:
            print(f"[COE SYNC 2026] Ingesting {len(dump_data['users'])} authoritative users from SQL dump...")
            for u in dump_data["users"]:
                uname = u["username"]
                seeded_usernames.add(uname)
                user_objects.append(
                    User(
                        id=u["id"],
                        username=uname,
                        password_hash=default_pwd_hash,
                        role=u["role"],
                        program=u.get("program"),
                        reference_id=u.get("reference_id"),
                        must_change_credentials=False,
                        is_active_status=True,
                        demo_password="password",
                    )
                )

        # 5b. Seed Backward-Compatible Aliases (if username not already registered)
        alias_accounts = [
            ("dean", "DEAN", None, None),
            ("admin", "ADMIN", None, None),
            ("chair_cpe", "CHAIR", "CPE", None),
            ("chair_mee", "CHAIR", "MEE", None),
            ("chair_ce", "CHAIR", "CE", None),
            ("chair_ee", "CHAIR", "EE", None),
            ("chair_ece", "CHAIR", "ECE", None),
            ("chair_ie", "CHAIR", "IE", None),
            ("chair_mfge", "CHAIR", "MFGE", None),
            ("chair_me", "CHAIR", "ME", None),
            ("chair", "CHAIR", "CPE", None),
            ("tullao", "FACULTY", "MEE", tullao_fac.id),
            ("bugayong", "FACULTY", "MEE", bugayong_fac.id),
            ("roque", "FACULTY", "CE", roque_fac.id),
            ("faculty", "FACULTY", "CPE", cpe_faculty.id),
            ("prof_santos", "FACULTY", "CPE", cpe_faculty.id),
            ("fac_santos", "FACULTY", "CPE", cpe_faculty.id),
            ("student_mee1a", "STUDENT", "MEE", mee_section.id),
            ("mayor_mee1a", "STUDENT", "MEE", mee_section.id),
            ("student_ce1a", "STUDENT", "CE", ce_section.id),
            ("student", "STUDENT", "CPE", cpe_section.id),
            ("student_cpe2a", "STUDENT", "CPE", cpe_section.id),
        ]

        for uname, urole, uprog, uref in alias_accounts:
            if uname not in seeded_usernames:
                seeded_usernames.add(uname)
                user_objects.append(
                    User(
                        username=uname,
                        password_hash=default_pwd_hash,
                        role=urole,
                        program=uprog,
                        reference_id=uref,
                        must_change_credentials=False,
                        is_active_status=True,
                        demo_password="nexus2026",
                    )
                )

        db.session.add_all(user_objects)
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
        admin_user = next(u for u in user_objects if u.username == "admin")
        audit_entry = AuditLog(
            user_id=admin_user.id,
            action="DATABASE_SEEDED",
            details=(
                f"data-final.sql ingestion complete: {len(faculty_members)} faculty, "
                f"{len(sections)} sections, {len(subjects)} subjects, {len(rooms)} rooms, "
                f"{len(user_objects)} users."
            ),
        )
        db.session.add(audit_entry)

        db.session.commit()
        print(f"[COE SYNC 2026] Database successfully seeded with {len(faculty_members)} faculty, {len(sections)} sections, {len(subjects)} subjects, {len(rooms)} rooms, and {len(user_objects)} users.")

        return {
            "users": len(user_objects),
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
