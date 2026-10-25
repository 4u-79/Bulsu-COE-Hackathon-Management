"""COE SYNC 2026 - Smart Scheduler & Create Schedule Integration Tests (tests/test_smart_scheduler.py)

Tests:
1. View & Navigation Access Control for GET /schedules/create
2. Solver API: POST /api/scheduler/generate with parameter validation and heuristic satisfaction
3. Role-based security guards for smart scheduling
4. Pre-flight conflict validation for manual scheduling mode
5. Transactional manual schedule slot creation
"""

import sys
import unittest
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import create_app
from seed_data import seed_database
from models import db, User, Schedule, Section, Subject, Room, Faculty, AuditLog


class TestSmartSchedulerAndCreateSchedule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Initialize test app with testing config and fresh database."""
        cls.app = create_app("testing")
        cls.client = cls.app.test_client()

        with cls.app.app_context():
            seed_database(cls.app)

    def login_as(self, username, role="CHAIR"):
        """Helper to simulate authenticated session."""
        with self.app.app_context():
            user = User.query.filter_by(username=username).first()
            user_id = user.id if user else 999
            user_name = user.username if user else username
            user_role = user.role if user else role

        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = user_name
            sess["role"] = user_role
            sess["active_role"] = role
            sess["must_change_credentials"] = False

    def logout(self):
        with self.client.session_transaction() as sess:
            sess.clear()

    # 1. Access Control Tests for /schedules/create
    def test_01_unauthenticated_view_redirects_to_login(self):
        self.logout()
        res = self.client.get("/schedules/create")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers.get("Location", ""))

    def test_02_student_view_forbidden(self):
        self.login_as("student_cpe2a", role="STUDENT")
        res = self.client.get("/schedules/create")
        self.assertEqual(res.status_code, 403)

    def test_03_faculty_view_forbidden(self):
        self.login_as("fac_santos", role="FACULTY")
        res = self.client.get("/schedules/create")
        self.assertEqual(res.status_code, 403)

    def test_04_chair_view_accessible(self):
        self.login_as("chair_cpe", role="CHAIR")
        res = self.client.get("/schedules/create")
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        self.assertIn("Create Schedule", html)
        self.assertIn("Smart Generate", html)
        self.assertIn("Manual Scheduling", html)
        self.assertIn("tab-btn-smart", html)
        self.assertIn("tab-btn-manual", html)

    # 2. Smart Generate Solver API Tests
    def test_05_smart_generate_requires_chair_role(self):
        self.login_as("student_cpe2a", role="STUDENT")
        res = self.client.post("/api/scheduler/generate", json={})
        self.assertEqual(res.status_code, 403)

    def test_06_smart_generate_valid_execution(self):
        self.login_as("chair_cpe", role="CHAIR")

        with self.app.app_context():
            sections = Section.query.filter(Section.program.in_(["BSCpE", "CPE"]), Section.year_level == 2).all()
            sec_ids = [s.id for s in sections]
            rooms = Room.query.filter_by(is_available=True).all()
            room_ids = [r.id for r in rooms]

        payload = {
            "program": "CPE",
            "year_level": 2,
            "section_ids": sec_ids,
            "room_ids": room_ids,
            "faculty_ids": "all",
            "preferences": {
                "minimize_gaps": True,
                "balance_workload": True,
                "optimize_utilization": True,
            },
        }

        res = self.client.post("/api/scheduler/generate", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        self.assertEqual(data["status"], "success")
        self.assertGreater(data["placed_count"], 0)
        self.assertEqual(data["hard_conflicts"], 0)
        self.assertGreaterEqual(data["quality_score"], 50)
        self.assertIn("metrics", data)
        self.assertIn("classes_scheduled", data["metrics"])

        # Check Audit Log
        with self.app.app_context():
            audit = AuditLog.query.filter_by(action="SMART_SCHEDULE_GENERATED").first()
            self.assertIsNotNone(audit)
            self.assertIn("Smart generation completed", audit.details)

    def test_07_smart_generate_invalid_criteria_returns_400(self):
        self.login_as("chair_cpe", role="CHAIR")
        payload = {
            "program": "NonExistentProgram",
            "year_level": 99,
            "section_ids": [],
            "room_ids": [1],
            "faculty_ids": "all",
        }
        res = self.client.post("/api/scheduler/generate", json=payload)
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertEqual(data["status"], "error")

    # 3. Manual Pre-Flight Validation Tests
    def test_08_preflight_conflict_check_valid_slot(self):
        with self.app.app_context():
            sub = Subject.query.filter_by(code="COE 101").first() or Subject.query.first()
            sec = Section.query.filter_by(name="CPE - 1A").first() or Section.query.first()
            fac = Faculty.query.first()
            room = Room.query.filter_by(room_code="COE 101").first() or Room.query.first()

            payload = {
                "subject_id": sub.id,
                "section_id": sec.id,
                "faculty_id": fac.id,
                "room_id": room.id,
                "day_of_week": "SAT",
                "start_time": "14:00",
                "end_time": "15:30",
            }

        res = self.client.post("/api/conflicts/check", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["valid"])
        self.assertEqual(len(data["conflicts"]), 0)

    def test_09_preflight_temporal_inversion(self):
        payload = {
            "subject_id": 1,
            "section_id": 1,
            "faculty_id": 1,
            "room_id": 1,
            "day_of_week": "MON",
            "start_time": "11:00",
            "end_time": "10:00",
        }
        res = self.client.post("/api/conflicts/check", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertFalse(data["valid"])
        self.assertTrue(any("earlier than" in c for c in data["conflicts"]))

    # 4. Manual Schedule Slot Creation Test
    def test_10_save_manual_schedule_slot(self):
        self.login_as("chair_cpe", role="CHAIR")

        with self.app.app_context():
            sub = Subject.query.filter_by(code="COE 102").first() or Subject.query.first()
            sec = Section.query.filter_by(name="CPE - 1A").first() or Section.query.first()
            fac = Faculty.query.first()
            room = Room.query.filter_by(room_code="COE 101").first() or Room.query.first()

            payload = {
                "subject_id": sub.id,
                "section_id": sec.id,
                "faculty_id": fac.id,
                "room_id": room.id,
                "day_of_week": "SAT",
                "start_time": "16:00",
                "end_time": "17:30",
            }

        res = self.client.post("/api/schedules", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertEqual(data["status"], "success")
        self.assertIn("data", data)
        self.assertIn("id", data["data"])

    # 5. Smart Scheduler Major Subjects Only Filter Test
    def test_11_smart_generate_only_places_major_subjects(self):
        self.login_as("chair_cpe", role="CHAIR")

        with self.app.app_context():
            all_subjects = Subject.query.all()
            major_sub = next((s for s in all_subjects if s.classification == "MAJOR"), None)
            minor_sub = next((s for s in all_subjects if s.classification == "MINOR"), None)
            if not minor_sub:
                minor_sub = Subject(
                    code="MATH 101",
                    title="Mathematics in the Modern World",
                    units=3,
                    subject_type="LECTURE",
                    hours_per_week=3,
                    year_level=1,
                    semester=1,
                    program="GEN",
                )
                db.session.add(minor_sub)
                db.session.commit()

            sec = Section.query.filter_by(year_level=1).first() or Section.query.first()
            sec_ids = [sec.id]
            rooms = Room.query.filter_by(is_available=True).all()
            room_ids = [r.id for r in rooms]

        payload = {
            "program": sec.program,
            "year_level": sec.year_level,
            "section_ids": sec_ids,
            "room_ids": room_ids,
            "semester": 1,
            "save_to_database": True,
        }

        res = self.client.post("/api/scheduler/generate", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "success")

        # Check all placed schedules
        placed = data.get("placed", [])
        with self.app.app_context():
            for p in placed:
                s_obj = Subject.query.get(p["subject_id"])
                if s_obj:
                    self.assertEqual(
                        s_obj.classification,
                        "MAJOR",
                        f"Expected subject {s_obj.code} placed by Smart Scheduler to be MAJOR, but was {s_obj.classification}",
                    )

    # 6. Manual Scheduling of Minor Subjects Allowed
    def test_12_minor_subject_manual_scheduling_permitted(self):
        self.login_as("chair_cpe", role="CHAIR")

        with self.app.app_context():
            all_subjects = Subject.query.all()
            minor_sub = next((s for s in all_subjects if s.classification == "MINOR"), None)
            if not minor_sub:
                minor_sub = Subject(
                    code="ETH 101",
                    title="Ethics",
                    units=3,
                    subject_type="LECTURE",
                    hours_per_week=3,
                    year_level=1,
                    semester=1,
                    program="GEN",
                )
                db.session.add(minor_sub)
                db.session.commit()

            sec = Section.query.first()
            fac = Faculty.query.first()
            room = Room.query.first()

            payload = {
                "subject_id": minor_sub.id,
                "section_id": sec.id,
                "faculty_id": fac.id,
                "room_id": room.id,
                "day_of_week": "FRI",
                "start_time": "15:00",
                "end_time": "16:30",
            }

        res = self.client.post("/api/schedules", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertEqual(data["status"], "success")
        self.assertIn("id", data["data"])

    # 7. Drag-and-Drop Auto Adjustment and Warning Generation Test
    def test_13_drag_move_auto_adjusts_displaced_overlapping_class(self):
        self.login_as("chair_cpe", role="CHAIR")

        with self.app.app_context():
            from datetime import time
            sec = Section.query.first()
            fac = Faculty.query.first()
            room = Room.query.first()
            all_subjects = Subject.query.all()
            major_subs = [s for s in all_subjects if s.classification == "MAJOR"]
            sub1 = major_subs[0]
            sub2 = major_subs[1] if len(major_subs) > 1 else major_subs[0]

            # Create existing class at WED 09:00 - 10:30
            sched_existing = Schedule(
                section_id=sec.id,
                subject_id=sub1.id,
                faculty_id=fac.id,
                room_id=room.id,
                day_of_week="WED",
                start_time=time(9, 0),
                end_time=time(10, 30),
                status="DRAFT",
            )
            # Create another class at WED 14:00 - 15:30
            sched_to_drag = Schedule(
                section_id=sec.id,
                subject_id=sub2.id,
                faculty_id=fac.id,
                room_id=room.id,
                day_of_week="WED",
                start_time=time(14, 0),
                end_time=time(15, 30),
                status="DRAFT",
            )
            db.session.add_all([sched_existing, sched_to_drag])
            db.session.commit()
            existing_id = sched_existing.id
            drag_id = sched_to_drag.id

        # Drag sched_to_drag onto WED 09:00 (overlapping sched_existing)
        move_payload = {
            "target_day": "WED",
            "target_start_time": "09:00",
            "target_schedule_id": existing_id,
        }

        res = self.client.post(f"/api/schedules/{drag_id}/drag-move", json=move_payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "success")
        self.assertIn("Moved", data["message"])
        self.assertTrue(len(data.get("displaced_adjustments", [])) >= 1)
        self.assertTrue(len(data.get("warnings", [])) >= 1)

        # Verify the database state:
        with self.app.app_context():
            d_sched = Schedule.query.get(drag_id)
            e_sched = Schedule.query.get(existing_id)

            # Dragged schedule should now be at 09:00 - 10:30
            self.assertEqual(d_sched.start_time.strftime("%H:%M"), "09:00")
            self.assertEqual(d_sched.end_time.strftime("%H:%M"), "10:30")

            # Existing schedule should be shifted to start at the end of the dragged class (10:30)
            self.assertEqual(e_sched.start_time.strftime("%H:%M"), "10:30")
            self.assertEqual(e_sched.end_time.strftime("%H:%M"), "12:00")


if __name__ == "__main__":
    unittest.main()
