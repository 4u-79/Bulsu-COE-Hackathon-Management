"""COE SYNC 2026 - Master Database Seeding & Migration Engine
Unifies raw MySQL dump (coe-database.sql) into clean relational models:
- 32 cleaned Faculty members across CE, ECE, MEE, MFE + demo faculty
- 36 standardized Sections (CE-1A, ECE-1A, MEE-1A, MFE-1A) + demo sections
- 360+ normalized Subjects across departments with LECTURE/LAB types
- Realistic COE Rooms (Lecture 45 cap, small room 30 cap, specialized LABs)
- 4 Demo Users with hashed credentials (admin, chair, faculty, student)
- Availability constraints, conflict-staged schedules, and reschedule workflows
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


def seed_database(app=None):
    """
    Idempotent seeding function.
    Drops all existing tables, recreates schema, imports cleaned SQL dump data,
    and populates realistic demo fixtures.
    """
    from app import create_app

    if app is None:
        app = create_app()

    with app.app_context():
        print("[COE SYNC 2026] Resetting and wiping database schema...")
        db.drop_all()
        db.create_all()
        print("[COE SYNC 2026] Schema recreated successfully.")

        # Load cleaned data from raw coe-database.sql
        print("[COE SYNC 2026] Loading and cleaning raw MySQL dump (coe-database.sql)...")
        dump_data = load_and_clean_sql_dump()

        # -------------------------------------------------------------
        # 1. Seed Faculty (Baseline Test Fixtures + Cleaned SQL Dump)
        # -------------------------------------------------------------
        print("[COE SYNC 2026] Seeding Faculty members...")
        # Baseline demo faculty members for existing test compatibility (IDs 1-4)
        demo_faculty = [
            Faculty(
                name="Prof. Juan Santos",
                email="juan.santos@bulsu.edu.ph",
                program="ECE",
                max_units=21,
                current_units=0,
            ),
            Faculty(
                name="Prof. Maria Rivera",
                email="maria.rivera@bulsu.edu.ph",
                program="CE",
                max_units=21,
                current_units=0,
            ),
            Faculty(
                name="Engr. Alex Cruz",
                email="alex.cruz@bulsu.edu.ph",
                program="MEE",
                max_units=18,
                current_units=0,
            ),
            Faculty(
                name="Engr. Elena Bautista",
                email="elena.bautista@bulsu.edu.ph",
                program="MFE",
                max_units=21,
                current_units=0,
            ),
        ]
        faculty_members = list(demo_faculty)

        for f in dump_data["faculty"]:
            faculty_members.append(
                Faculty(
                    name=f["name"],
                    email=f["email"],
                    program=f["program"],
                    max_units=f["max_units"],
                    current_units=0,
                )
            )

        db.session.add_all(faculty_members)
        db.session.flush()

        faculty_map = {f.name: f for f in faculty_members}

        # -------------------------------------------------------------
        # 2. Seed Sections (Baseline Test Fixtures + Standardized SQL Dump)
        # -------------------------------------------------------------
        print("[COE SYNC 2026] Seeding Section cohorts...")
        # Baseline demo sections for existing test compatibility (IDs 1-4)
        demo_sections = [
            Section(name="CpE 1A", program="BSCpE", year_level=1, student_count=45),
            Section(name="CpE 2A", program="BSCpE", year_level=2, student_count=40),
            Section(name="CpE 2B", program="BSCpE", year_level=2, student_count=35),
            Section(name="CpE 3A", program="BSCpE", year_level=3, student_count=35),
        ]
        sections = list(demo_sections)

        for s in dump_data["sections"]:
            sections.append(
                Section(
                    name=s["name"],
                    program=s["program"],
                    year_level=s["year_level"],
                    student_count=s["student_count"],
                )
            )

        db.session.add_all(sections)
        db.session.flush()

        section_map = {s.name: s for s in sections}

        # -------------------------------------------------------------
        # 3. Seed Users (Admin, Chair, Faculty, Student + Aliases)
        # -------------------------------------------------------------
        print("[COE SYNC 2026] Seeding User accounts with role-based reference IDs...")
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
                username="prof_santos",
                password_hash=generate_password_hash("faculty123"),
                role="FACULTY",
                reference_id=faculty_map["Prof. Juan Santos"].id,
                must_change_credentials=False,
                is_active_status=True,
                demo_password="faculty123",
            ),
            User(
                username="faculty",
                password_hash=generate_password_hash("faculty123"),
                role="FACULTY",
                reference_id=faculty_map["Prof. Juan Santos"].id,
                must_change_credentials=False,
                is_active_status=True,
                demo_password="faculty123",
            ),
            User(
                username="student_cpe2a",
                password_hash=generate_password_hash("student123"),
                role="STUDENT",
                reference_id=section_map["CpE 2A"].id,
                must_change_credentials=False,
                is_active_status=True,
                demo_password="student123",
            ),
            User(
                username="student",
                password_hash=generate_password_hash("student123"),
                role="STUDENT",
                reference_id=section_map["CpE 2A"].id,
                must_change_credentials=False,
                is_active_status=True,
                demo_password="student123",
            ),
        ]
        db.session.add_all(users)
        db.session.flush()

        # -------------------------------------------------------------
        # 4. Seed Realistic COE Rooms
        # -------------------------------------------------------------
        print("[COE SYNC 2026] Seeding realistic COE Lecture Halls and Specialized Labs...")
        rooms = [
            # Standard Lecture Rooms (45-50 capacity)
            Room(
                room_code="Eng-201",
                room_type="LECTURE",
                capacity=50,
                equipment="Projector, Whiteboard, Audio System",
                is_available=True,
            ),
            Room(
                room_code="Eng-202",
                room_type="LECTURE",
                capacity=45,
                equipment="Projector, Whiteboard",
                is_available=True,
            ),
            Room(
                room_code="Eng-301",
                room_type="LECTURE",
                capacity=45,
                equipment="Smart TV, Whiteboard",
                is_available=True,
            ),
            Room(
                room_code="Eng-302",
                room_type="LECTURE",
                capacity=50,
                equipment="Projector, Whiteboard",
                is_available=True,
            ),
            Room(
                room_code="COE-101",
                room_type="LECTURE",
                capacity=45,
                equipment="Multimedia Podium, Whiteboard",
                is_available=True,
            ),
            # 1 Small Room (30 capacity) to test overcapacity warnings
            Room(
                room_code="Eng-104",
                room_type="LECTURE",
                capacity=30,
                equipment="Whiteboard, TV Display",
                is_available=True,
            ),
            # Specialized Laboratories for CE, ECE, MEE, MFE
            Room(
                room_code="CE-Lab 1",
                room_type="LAB",
                capacity=40,
                equipment="Civil Engineering Materials & Surveying Station",
                is_available=True,
            ),
            Room(
                room_code="ECE-Lab 1",
                room_type="LAB",
                capacity=40,
                equipment="Oscilloscopes, Signal Generators, FPGA Kits",
                is_available=True,
            ),
            Room(
                room_code="MEE-Lab 1",
                room_type="LAB",
                capacity=40,
                equipment="PLC Automation Trainers, Mechatronics Benches",
                is_available=True,
            ),
            Room(
                room_code="MFE-Lab 1",
                room_type="LAB",
                capacity=40,
                equipment="CNC Lathes, 3D Printers, CAD/CAM Workstations",
                is_available=True,
            ),
            Room(
                room_code="Eng-Lab 1",
                room_type="LAB",
                capacity=40,
                equipment="Workstations, Gigabit Switch, Cisco Routers",
                is_available=True,
            ),
            Room(
                room_code="Eng-Lab 2",
                room_type="LAB",
                capacity=40,
                equipment="Microcontroller Development Boards & Sensors",
                is_available=True,
            ),
        ]
        db.session.add_all(rooms)
        db.session.flush()

        room_map = {r.room_code: r for r in rooms}

        # -------------------------------------------------------------
        # 5. Seed Subjects (Baseline Test Fixtures + Cleaned SQL Dump)
        # -------------------------------------------------------------
        print("[COE SYNC 2026] Seeding Subjects catalog...")
        # Baseline demo subjects for test suite continuity (IDs 1-6)
        demo_subjects = [
            Subject(
                code="MATH 101",
                title="Calculus 1",
                program="BSCpE",
                units=3,
                subject_type="LECTURE",
                hours_per_week=3,
                year_level=1,
                semester=1,
                split_preference="1.5_HOUR_SPLIT",
            ),
            Subject(
                code="CHEM 101",
                title="Chemistry for Engineers",
                program="BSCpE",
                units=3,
                subject_type="LECTURE",
                hours_per_week=3,
                year_level=1,
                semester=1,
                split_preference="1.5_HOUR_SPLIT",
            ),
            Subject(
                code="CPE 211",
                title="Data Structures & Algorithms",
                program="BSCpE",
                units=3,
                subject_type="LECTURE",
                hours_per_week=3,
                year_level=2,
                semester=1,
                split_preference="1.5_HOUR_SPLIT",
            ),
            Subject(
                code="CPE 211L",
                title="Data Structures Lab",
                program="BSCpE",
                units=1,
                subject_type="LAB",
                hours_per_week=3,
                year_level=2,
                semester=1,
                split_preference="3_HOUR_BLOCK",
            ),
            Subject(
                code="CPE 312",
                title="Microprocessors",
                program="BSCpE",
                units=3,
                subject_type="LECTURE",
                hours_per_week=3,
                year_level=3,
                semester=1,
                split_preference="1.5_HOUR_SPLIT",
            ),
            Subject(
                code="CPE 312L",
                title="Microprocessors Lab",
                program="BSCpE",
                units=1,
                subject_type="LAB",
                hours_per_week=3,
                year_level=3,
                semester=1,
                split_preference="3_HOUR_BLOCK",
            ),
        ]
        subjects = list(demo_subjects)

        for s in dump_data["subjects"]:
            subjects.append(
                Subject(
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

        # Subject map helper
        subj_map = {}
        for s in subjects:
            subj_map[s.code] = s

        # -------------------------------------------------------------
        # 6. Seed Faculty Availability Constraints
        # -------------------------------------------------------------
        print("[COE SYNC 2026] Seeding Faculty Availability Constraints...")
        rivera = faculty_map["Prof. Maria Rivera"]
        unavailability = FacultyAvailability(
            faculty_id=rivera.id,
            day_of_week="FRI",
            start_time=time(8, 0, 0),
            end_time=time(12, 0, 0),
            is_preferred=False,
            split_preference="1.5_HOUR_SPLIT",
        )
        db.session.add(unavailability)
        db.session.flush()

        # -------------------------------------------------------------
        # 7. Seed Schedules (Staged with Realistic Demo Scenarios)
        # -------------------------------------------------------------
        print("[COE SYNC 2026] Seeding Schedule slots and staged conflict scenarios...")
        santos = faculty_map["Prof. Juan Santos"]
        cruz = faculty_map["Engr. Alex Cruz"]
        bautista = faculty_map["Engr. Elena Bautista"]

        sec_1a = section_map["CpE 1A"]
        sec_2a = section_map["CpE 2A"]
        sec_3a = section_map["CpE 3A"]

        schedules_data = [
            # Monday
            Schedule(
                subject=subj_map["MATH 101"],
                section=sec_1a,
                faculty=santos,
                room=room_map["Eng-104"],
                day_of_week="MON",
                start_time=time(7, 30),
                end_time=time(9, 0),
                status="PUBLISHED",
            ),
            Schedule(
                subject=subj_map["CPE 211"],
                section=sec_2a,
                faculty=cruz,
                room=room_map["Eng-201"],
                day_of_week="MON",
                start_time=time(9, 0),
                end_time=time(10, 30),
                status="PUBLISHED",
            ),
            Schedule(
                subject=subj_map["CPE 312"],
                section=sec_3a,
                faculty=bautista,
                room=room_map["Eng-302"],
                day_of_week="MON",
                start_time=time(13, 0),
                end_time=time(14, 30),
                status="DRAFT",
            ),
            # Tuesday
            Schedule(
                subject=subj_map["CHEM 101"],
                section=sec_1a,
                faculty=rivera,
                room=room_map["Eng-201"],
                day_of_week="TUE",
                start_time=time(8, 0),
                end_time=time(9, 30),
                status="PUBLISHED",
            ),
            Schedule(
                subject=subj_map["CPE 211L"],
                section=sec_2a,
                faculty=cruz,
                room=room_map["Eng-Lab 1"],
                day_of_week="TUE",
                start_time=time(10, 0),
                end_time=time(13, 0),
                status="PUBLISHED",
            ),
            # Wednesday (Includes Conflict for Conflict Radar Demo)
            Schedule(
                subject=subj_map["CPE 312"],
                section=sec_2a,
                faculty=santos,
                room=room_map["Eng-104"],
                day_of_week="WED",
                start_time=time(10, 0),
                end_time=time(12, 0),
                status="PUBLISHED",
            ),
            # Intentional Conflict: same room Eng-104, overlapping time slot
            Schedule(
                subject=subj_map["MATH 101"],
                section=sec_3a,
                faculty=bautista,
                room=room_map["Eng-104"],
                day_of_week="WED",
                start_time=time(11, 0),
                end_time=time(12, 30),
                status="DRAFT",
            ),
            Schedule(
                subject=subj_map["CPE 312L"],
                section=sec_3a,
                faculty=bautista,
                room=room_map["Eng-Lab 2"],
                day_of_week="WED",
                start_time=time(13, 30),
                end_time=time(16, 30),
                status="PUBLISHED",
            ),
            # Thursday
            Schedule(
                subject=subj_map["MATH 101"],
                section=sec_2a,
                faculty=santos,
                room=room_map["Eng-201"],
                day_of_week="THU",
                start_time=time(7, 0),
                end_time=time(8, 30),
                status="PUBLISHED",
            ),
            Schedule(
                subject=subj_map["CHEM 101"],
                section=sec_3a,
                faculty=rivera,
                room=room_map["Eng-302"],
                day_of_week="THU",
                start_time=time(9, 30),
                end_time=time(11, 0),
                status="PUBLISHED",
            ),
            Schedule(
                subject=subj_map["CPE 211"],
                section=sec_1a,
                faculty=cruz,
                room=room_map["Eng-104"],
                day_of_week="THU",
                start_time=time(14, 0),
                end_time=time(15, 30),
                status="DRAFT",
            ),
            # Friday
            Schedule(
                subject=subj_map["CPE 211L"],
                section=sec_1a,
                faculty=santos,
                room=room_map["Eng-Lab 1"],
                day_of_week="FRI",
                start_time=time(8, 0),
                end_time=time(11, 0),
                status="PUBLISHED",
            ),
            Schedule(
                subject=subj_map["CPE 312L"],
                section=sec_2a,
                faculty=cruz,
                room=room_map["Eng-Lab 2"],
                day_of_week="FRI",
                start_time=time(13, 0),
                end_time=time(16, 0),
                status="PUBLISHED",
            ),
            # Saturday
            Schedule(
                subject=subj_map["CHEM 101"],
                section=sec_2a,
                faculty=rivera,
                room=room_map["Eng-201"],
                day_of_week="SAT",
                start_time=time(7, 30),
                end_time=time(9, 0),
                status="DRAFT",
            ),
        ]
        db.session.add_all(schedules_data)
        db.session.flush()

        # Update faculty current_units based on assigned schedules
        for s in schedules_data:
            if s.faculty and s.subject:
                s.faculty.current_units += s.subject.units
        db.session.flush()

        # -------------------------------------------------------------
        # 8. Seed Reschedule Requests (Multi-tier Workflow Demonstration)
        # -------------------------------------------------------------
        sample_schedule = schedules_data[0]
        sample_schedule_2 = schedules_data[2]
        reschedule_requests = [
            RescheduleRequest(
                schedule_id=sample_schedule.id,
                student_section_id=sec_2a.id,
                proposed_day="THU",
                proposed_start_time=time(14, 0),
                proposed_end_time=time(15, 30),
                reason="Section conflict with university-wide college assembly on Monday morning.",
                status="PENDING_FACULTY",
            ),
            RescheduleRequest(
                schedule_id=sample_schedule_2.id,
                student_section_id=sec_2a.id,
                proposed_day="FRI",
                proposed_start_time=time(10, 0),
                proposed_end_time=time(11, 30),
                reason="Laboratory maintenance scheduled during original slot.",
                status="PENDING_CHAIR",
                faculty_feedback="Endorsed. Friday 10:00 AM is suitable for instructor timetable.",
            ),
        ]
        db.session.add_all(reschedule_requests)

        # -------------------------------------------------------------
        # 9. Seed Audit Log Entry
        # -------------------------------------------------------------
        admin_user = next(u for u in users if u.username == "admin")
        audit_entry = AuditLog(
            user_id=admin_user.id,
            action="DATABASE_SEEDED",
            details=(
                f"Unified migration complete: {len(faculty_members)} faculty, "
                f"{len(sections)} sections, {len(subjects)} subjects, {len(rooms)} rooms, "
                f"{len(schedules_data)} schedules, {len(reschedule_requests)} requests."
            ),
        )
        db.session.add(audit_entry)

        db.session.commit()
        print("[COE SYNC 2026] Database successfully seeded!")

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
