"""COE SYNC 2026 - Phase 4 & 5 Core Workflows Test Suite

Validates:
1. Search and filter query contract for /api/schedules (program, year_level, status)
2. Student role row-level security: only PUBLISHED schedules returned
3. Automated draft schedule generation endpoint (POST /api/schedules/generate-draft)
4. Batch publish-all endpoint with conflict preflight guard (POST /api/schedules/publish-all)
5. Faculty availability endpoints (GET/POST /api/faculty/<id>/availability)
6. Institutional reports view (GET /reports) and analytics summary breakdown
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
from models import (
    db,
    User,
    Faculty,
    Section,
    Room,
    Subject,
    Schedule,
    FacultyAvailability,
)


class TestPhase4Workflows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Initialize test app with isolated test configuration and fresh seed."""
        cls.app = create_app("testing")
        cls.client = cls.app.test_client()

        with cls.app.app_context():
            seed_database(cls.app)

            cls.chair_user = User.query.filter_by(username="chair_cpe").first()
            cls.faculty_user = User.query.filter_by(role="FACULTY").first()
            cls.student_user = User.query.filter_by(role="STUDENT").first()
            cls.faculty_member = Faculty.query.first()
            cls.section = Section.query.first()
            cls.room = Room.query.filter_by(room_type="LECTURE").first()
            cls.subject = Subject.query.filter_by(subject_type="LECTURE").first()

    def setUp(self):
        """Reset session and re-seed database before each test."""
        with self.app.app_context():
            seed_database(self.app)

    def test_01_search_and_filter_schedules_contract(self):
        """Test querying /api/schedules with program, year_level, and status."""
        from datetime import time as dt_time
        with self.app.app_context():
            sec2 = Section.query.filter_by(program="CPE", year_level=2).first() or self.section
            adequate_room = Room.query.filter(Room.capacity >= sec2.student_count).first()
            s = Schedule(
                section_id=sec2.id,
                subject_id=self.subject.id,
                faculty_id=self.faculty_member.id,
                room_id=adequate_room.id,
                day_of_week="MON",
                start_time=dt_time(8, 0),
                end_time=dt_time(10, 0),
                status="DRAFT",
            )
            db.session.add(s)
            db.session.commit()
            expected_sec_name = sec2.name

        with self.client.session_transaction() as sess:
            sess["user_id"] = self.chair_user.id
            sess["role"] = "CHAIR"
            sess["active_role"] = "CHAIR"

        # Query all for BSCpE Year 2
        res = self.client.get("/api/schedules?program=BSCpE&year_level=2")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["data"]
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        for s in data:
            self.assertIn("section_name", s)
            self.assertEqual(s["section_name"], expected_sec_name)

    def test_02_student_role_row_level_isolation(self):
        """Verify that Student view isolates only PUBLISHED schedules, hiding DRAFTs."""
        from datetime import time as dt_time
        with self.app.app_context():
            sec2 = Section.query.filter_by(program="CPE", year_level=2).first() or self.section
            adequate_room = Room.query.filter(Room.capacity >= sec2.student_count).first()
            s1 = Schedule(
                section_id=sec2.id,
                subject_id=self.subject.id,
                faculty_id=self.faculty_member.id,
                room_id=adequate_room.id,
                day_of_week="MON",
                start_time=dt_time(8, 0),
                end_time=dt_time(10, 0),
                status="DRAFT",
            )
            s2 = Schedule(
                section_id=sec2.id,
                subject_id=self.subject.id,
                faculty_id=self.faculty_member.id,
                room_id=adequate_room.id,
                day_of_week="TUE",
                start_time=dt_time(8, 0),
                end_time=dt_time(10, 0),
                status="PUBLISHED",
            )
            db.session.add_all([s1, s2])
            db.session.commit()
            sec2_id = sec2.id

        # 2. Impersonate Student
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.student_user.id
            sess["role"] = "STUDENT"
            sess["active_role"] = "STUDENT"
            sess["reference_id"] = sec2_id

        # Query schedules as Student
        res = self.client.get(f"/api/schedules?section_id={sec2_id}")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["data"]
        # Must only see PUBLISHED
        self.assertGreater(len(data), 0)
        for s in data:
            self.assertEqual(s["status"], "PUBLISHED", f"Student saw non-published schedule {s['id']}")

    def test_03_generate_draft_heuristic_solver(self):
        """Verify POST /api/schedules/generate-draft places offerings and returns metrics."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.chair_user.id
            sess["role"] = "CHAIR"
            sess["active_role"] = "CHAIR"

        res = self.client.post("/api/schedules/generate-draft")
        self.assertEqual(res.status_code, 200)
        payload = res.get_json()
        self.assertEqual(payload["status"], "success")
        self.assertIn("placed_count", payload)
        self.assertIn("unplaced_count", payload)

    def test_04_publish_all_blocks_on_conflict_and_succeeds_when_clean(self):
        """Verify POST /api/schedules/publish-all returns 409 if conflict exists, 200 when clean."""
        from datetime import time as dt_time
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.chair_user.id
            sess["role"] = "CHAIR"
            sess["active_role"] = "CHAIR"

        # Create two conflicting schedules
        with self.app.app_context():
            adequate_room = Room.query.filter(Room.capacity >= self.section.student_count).first()
            c1 = Schedule(
                section_id=self.section.id,
                subject_id=self.subject.id,
                faculty_id=self.faculty_member.id,
                room_id=adequate_room.id,
                day_of_week="MON",
                start_time=dt_time(8, 0),
                end_time=dt_time(10, 0),
                status="DRAFT",
            )
            other_sec = Section.query.filter(Section.id != self.section.id).first()
            other_fac = Faculty.query.filter(Faculty.id != self.faculty_member.id).first()
            c2 = Schedule(
                section_id=other_sec.id,
                subject_id=self.subject.id,
                faculty_id=other_fac.id,
                room_id=adequate_room.id,
                day_of_week="MON",
                start_time=dt_time(9, 0),
                end_time=dt_time(11, 0),
                status="DRAFT",
            )
            db.session.add_all([c1, c2])
            db.session.commit()

        # Should return 409 Conflict because seed has room collisions
        res_conflict = self.client.post("/api/schedules/publish-all")
        self.assertEqual(res_conflict.status_code, 409)
        self.assertIn("error", res_conflict.get_json())

        # Now clear conflicts by keeping a clean single schedule
        with self.app.app_context():
            Schedule.query.delete()
            adequate_room = Room.query.filter(Room.capacity >= self.section.student_count).first()
            clean_s = Schedule(
                section_id=self.section.id,
                subject_id=self.subject.id,
                faculty_id=self.faculty_member.id,
                room_id=adequate_room.id,
                day_of_week="MON",
                start_time=dt_time(8, 0),
                end_time=dt_time(10, 0),
                status="DRAFT",
            )
            db.session.add(clean_s)
            db.session.commit()

        # Try publish-all on clean schedule
        res_clean = self.client.post("/api/schedules/publish-all")
        self.assertEqual(res_clean.status_code, 200)
        self.assertEqual(res_clean.get_json()["published_count"], 1)

    def test_05_faculty_availability_endpoints(self):
        """Test GET and POST on /api/faculty/<id>/availability."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.chair_user.id
            sess["role"] = "CHAIR"
            sess["active_role"] = "CHAIR"

        # GET availability
        res_get = self.client.get(f"/api/faculty/{self.faculty_member.id}/availability")
        self.assertEqual(res_get.status_code, 200)
        self.assertIsInstance(res_get.get_json()["data"], list)

        # POST new availability
        payload = {
            "day_of_week": "SAT",
            "start_time": "13:00",
            "end_time": "17:00",
            "is_preferred": False,
        }
        res_post = self.client.post(
            f"/api/faculty/{self.faculty_member.id}/availability",
            json=payload,
        )
        self.assertEqual(res_post.status_code, 201)
        created_id = res_post.get_json()["data"]["id"]

        # Delete availability
        res_del = self.client.delete(f"/api/availabilities/{created_id}")
        self.assertEqual(res_del.status_code, 200)

    def test_06_reports_view_and_summary_breakdown(self):
        """Test GET /reports renders 200 and GET /api/analytics/summary returns breakdowns."""
        # 1. HTML View
        res_view = self.client.get("/reports")
        self.assertEqual(res_view.status_code, 200)
        self.assertIn(b"Institutional Analytics", res_view.data)

        # 2. Analytics Summary API
        res_api = self.client.get("/api/analytics/summary")
        self.assertEqual(res_api.status_code, 200)
        data = res_api.get_json()["data"]
        self.assertIn("room_breakdown", data)
        self.assertIn("faculty_workloads", data)
        self.assertIn("section_breakdown", data)
        self.assertIn("room_utilization", data)
        self.assertIn("schedule_quality_score", data)


if __name__ == "__main__":
    unittest.main()
