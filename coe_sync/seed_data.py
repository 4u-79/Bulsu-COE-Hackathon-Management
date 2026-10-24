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
)


def seed_database(app=None):
    """
    Idempotent seeding function.
    Drops all existing tables, recreates schema, and populates baseline mock data.
    """
    from app import create_app

    if app is None:
        app = create_app()

    with app.app_context():
        print("[COE SYNC 2026] Resetting and wiping database schema...")
        db.drop_all()
        db.create_all()
        print("[COE SYNC 2026] Schema recreated successfully.")

        print("[COE SYNC 2026] Seeding Faculty...")
        faculty_members = [
            Faculty(
                name="Prof. Juan Santos",
                email="juan.santos@bulsu.edu.ph",
                max_units=21,
                current_units=0,
            ),
            Faculty(
                name="Prof. Maria Rivera",
                email="maria.rivera@bulsu.edu.ph",
                max_units=21,
                current_units=0,
            ),
            Faculty(
                name="Engr. Alex Cruz",
                email="alex.cruz@bulsu.edu.ph",
                max_units=18,
                current_units=0,
            ),
            Faculty(
                name="Engr. Elena Bautista",
                email="elena.bautista@bulsu.edu.ph",
                max_units=21,
                current_units=0,
            ),
        ]
        db.session.add_all(faculty_members)
        db.session.flush()  # Populates IDs

        # Map faculty by name for relationship lookups
        faculty_map = {f.name: f for f in faculty_members}

        print("[COE SYNC 2026] Seeding Sections...")
        sections = [
            Section(
                name="CpE 1A",
                program="BSCpE",
                year_level=1,
                student_count=45,
            ),
            Section(
                name="CpE 2A",
                program="BSCpE",
                year_level=2,
                student_count=40,
            ),
            Section(
                name="CpE 2B",
                program="BSCpE",
                year_level=2,
                student_count=35,
            ),
            Section(
                name="CpE 3A",
                program="BSCpE",
                year_level=3,
                student_count=35,
            ),
        ]
        db.session.add_all(sections)
        db.session.flush()

        section_map = {s.name: s for s in sections}

        print("[COE SYNC 2026] Seeding Users with role-based reference IDs...")
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
                username="prof_santos",
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
        ]
        db.session.add_all(users)
        db.session.flush()

        print("[COE SYNC 2026] Seeding Rooms...")
        rooms = [
            Room(
                room_code="Eng-104",
                room_type="LECTURE",
                capacity=35,
                is_available=True,
            ),
            Room(
                room_code="Eng-201",
                room_type="LECTURE",
                capacity=50,
                is_available=True,
            ),
            Room(
                room_code="Eng-302",
                room_type="LECTURE",
                capacity=50,
                is_available=True,
            ),
            Room(
                room_code="Eng-Lab 1",
                room_type="LAB",
                capacity=40,
                is_available=True,
            ),
            Room(
                room_code="Eng-Lab 2",
                room_type="LAB",
                capacity=40,
                is_available=True,
            ),
        ]
        db.session.add_all(rooms)

        print("[COE SYNC 2026] Seeding Subjects...")
        subjects = [
            Subject(
                code="MATH 101",
                title="Calculus 1",
                units=3,
                subject_type="LECTURE",
                hours_per_week=3,
                split_preference="1.5_HOUR_SPLIT",
            ),
            Subject(
                code="CPE 211",
                title="Data Structures & Algorithms",
                units=3,
                subject_type="LECTURE",
                hours_per_week=3,
                split_preference="1.5_HOUR_SPLIT",
            ),
            Subject(
                code="CPE 211L",
                title="Data Structures Lab",
                units=1,
                subject_type="LAB",
                hours_per_week=3,
                split_preference="3_HOUR_BLOCK",
            ),
            Subject(
                code="CPE 312",
                title="Microprocessors",
                units=3,
                subject_type="LECTURE",
                hours_per_week=3,
                split_preference="1.5_HOUR_SPLIT",
            ),
            Subject(
                code="CPE 312L",
                title="Microprocessors Lab",
                units=1,
                subject_type="LAB",
                hours_per_week=3,
                split_preference="3_HOUR_BLOCK",
            ),
            Subject(
                code="CHEM 101",
                title="Chemistry for Engineers",
                units=3,
                subject_type="LECTURE",
                hours_per_week=3,
                split_preference="1.5_HOUR_SPLIT",
            ),
        ]
        db.session.add_all(subjects)

        print("[COE SYNC 2026] Seeding Faculty Availability Constraints...")
        # Mark Prof. Maria Rivera as unavailable on Friday (08:00:00 to 12:00:00)
        rivera = faculty_map["Prof. Maria Rivera"]
        unavailability = FacultyAvailability(
            faculty_id=rivera.id,
            day_of_week="FRI",
            start_time=time(8, 0, 0),
            end_time=time(12, 0, 0),
            is_preferred=False,
        )
        db.session.add(unavailability)
        db.session.flush()

        # Resolve FK IDs after flush
        santos  = faculty_map["Prof. Juan Santos"]
        rivera  = faculty_map["Prof. Maria Rivera"]
        cruz    = faculty_map["Engr. Alex Cruz"]
        bautista = faculty_map["Engr. Elena Bautista"]

        sec_1a = section_map["CpE 1A"]
        sec_2a = section_map["CpE 2A"]
        sec_3a = section_map["CpE 3A"]

        # Build subject & room maps from session
        db.session.flush()
        subj_map  = {s.code: s for s in subjects}
        room_map  = {r.room_code: r for r in rooms}

        print("[COE SYNC 2026] Seeding Schedule slots...")
        schedules_data = [
            # ── Monday ──────────────────────────────────────
            Schedule(
                subject=subj_map["MATH 101"], section=sec_1a,
                faculty=santos, room=room_map["Eng-104"],
                day_of_week="MON", start_time=time(7, 30), end_time=time(9, 0),
                status="PUBLISHED",
            ),
            Schedule(
                subject=subj_map["CPE 211"], section=sec_2a,
                faculty=cruz, room=room_map["Eng-201"],
                day_of_week="MON", start_time=time(9, 0), end_time=time(10, 30),
                status="PUBLISHED",
            ),
            Schedule(
                subject=subj_map["CPE 312"], section=sec_3a,
                faculty=bautista, room=room_map["Eng-302"],
                day_of_week="MON", start_time=time(13, 0), end_time=time(14, 30),
                status="DRAFT",
            ),
            # ── Tuesday ─────────────────────────────────────
            Schedule(
                subject=subj_map["CHEM 101"], section=sec_1a,
                faculty=rivera, room=room_map["Eng-201"],
                day_of_week="TUE", start_time=time(8, 0), end_time=time(9, 30),
                status="PUBLISHED",
            ),
            Schedule(
                subject=subj_map["CPE 211L"], section=sec_2a,
                faculty=cruz, room=room_map["Eng-Lab 1"],
                day_of_week="TUE", start_time=time(10, 0), end_time=time(13, 0),
                status="PUBLISHED",
            ),
            # ── Wednesday ───────────────────────────────────
            Schedule(
                subject=subj_map["CPE 312"], section=sec_2a,
                faculty=santos, room=room_map["Eng-104"],
                day_of_week="WED", start_time=time(10, 0), end_time=time(12, 0),
                status="PUBLISHED",
            ),
            # ⚠ DELIBERATE CONFLICT: same room Eng-104, same time, different section
            Schedule(
                subject=subj_map["MATH 101"], section=sec_3a,
                faculty=bautista, room=room_map["Eng-104"],
                day_of_week="WED", start_time=time(11, 0), end_time=time(12, 30),
                status="DRAFT",
            ),
            Schedule(
                subject=subj_map["CPE 312L"], section=sec_3a,
                faculty=bautista, room=room_map["Eng-Lab 2"],
                day_of_week="WED", start_time=time(13, 30), end_time=time(16, 30),
                status="PUBLISHED",
            ),
            # ── Thursday ────────────────────────────────────
            Schedule(
                subject=subj_map["MATH 101"], section=sec_2a,
                faculty=santos, room=room_map["Eng-201"],
                day_of_week="THU", start_time=time(7, 0), end_time=time(8, 30),
                status="PUBLISHED",
            ),
            Schedule(
                subject=subj_map["CHEM 101"], section=sec_3a,
                faculty=rivera, room=room_map["Eng-302"],
                day_of_week="THU", start_time=time(9, 30), end_time=time(11, 0),
                status="PUBLISHED",
            ),
            Schedule(
                subject=subj_map["CPE 211"], section=sec_1a,
                faculty=cruz, room=room_map["Eng-104"],
                day_of_week="THU", start_time=time(14, 0), end_time=time(15, 30),
                status="DRAFT",
            ),
            # ── Friday ──────────────────────────────────────
            Schedule(
                subject=subj_map["CPE 211L"], section=sec_1a,
                faculty=santos, room=room_map["Eng-Lab 1"],
                day_of_week="FRI", start_time=time(8, 0), end_time=time(11, 0),
                status="PUBLISHED",
            ),
            Schedule(
                subject=subj_map["CPE 312L"], section=sec_2a,
                faculty=cruz, room=room_map["Eng-Lab 2"],
                day_of_week="FRI", start_time=time(13, 0), end_time=time(16, 0),
                status="PUBLISHED",
            ),
            # ── Saturday ────────────────────────────────────
            Schedule(
                subject=subj_map["CHEM 101"], section=sec_2a,
                faculty=rivera, room=room_map["Eng-201"],
                day_of_week="SAT", start_time=time(7, 30), end_time=time(9, 0),
                status="DRAFT",
            ),
        ]
        db.session.add_all(schedules_data)
        db.session.flush()

        # Seed initial Reschedule Requests for Demonstration
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

        # Initial system audit log
        admin_user = next(u for u in users if u.username == "admin")
        audit_entry = AuditLog(
            user_id=admin_user.id,
            action="DATABASE_SEEDED",
            details="Initial baseline mock dataset seeded: Users, Faculty, Sections, Rooms, Subjects, Availability constraints, Schedules, and Reschedule Requests.",
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
            "reschedule_requests": len(reschedule_requests),
        }


if __name__ == "__main__":
    seed_database()
