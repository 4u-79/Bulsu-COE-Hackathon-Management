"""COE SYNC 2026 - Phase 5 Governance & Reschedule Pipeline Test Suite

Validates:
1. Program Chair active/inactive availability status toggle and role-based visibility isolation (CHAIR/FACULTY vs STUDENT 403)
2. Student submits a reschedule request for their class (POST /api/reschedule/request)
3. Faculty reviews and endorses student proposal (POST /api/reschedule/<id>/faculty-review)
4. Program Chair makes final authorization, atomically updating the Schedule timetable (POST /api/reschedule/<id>/chair-decision)
5. Analytics & reports endpoint (GET /api/analytics/reports) returns room utilization ranking, faculty workloads, and quality deductions
"""

import sys
import unittest
from pathlib import Path
from datetime import time

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
    RescheduleRequest,
)


class TestPhase5Governance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Initialize test app with isolated test configuration and fresh seed."""
        cls.app = create_app("testing")
        cls.client = cls.app.test_client()

        with cls.app.app_context():
            seed_database(cls.app)

            cls.chair_user = User.query.filter_by(role="CHAIR").first()
            cls.faculty_user = User.query.filter_by(role="FACULTY").first()
            cls.student_user = User.query.filter_by(role="STUDENT").first()
            cls.faculty_member = Faculty.query.first()
            cls.section = Section.query.filter_by(name="CpE 2A").first() or Section.query.first()

    def setUp(self):
        """Re-seed database before each test for clean test isolation."""
        with self.app.app_context():
            seed_database(self.app)

    def test_01_chair_status_toggle_and_visibility_isolation(self):
        """Test Chair status toggle and verify that Student is restricted with 403."""
        # 1. Chair updates status to Inactive / Out of Office
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.chair_user.id
            sess["role"] = "CHAIR"
            sess["active_role"] = "CHAIR"

        res_toggle = self.client.post("/api/chair/status", json={"is_active": False})
        self.assertEqual(res_toggle.status_code, 200)
        self.assertEqual(res_toggle.get_json()["is_active"], False)

        # 2. Faculty views Chair status -> 200 OK
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.faculty_user.id
            sess["role"] = "FACULTY"
            sess["active_role"] = "FACULTY"

        res_fac = self.client.get("/api/chair/status")
        self.assertEqual(res_fac.status_code, 200)
        self.assertEqual(res_fac.get_json()["is_active"], False)

        # 3. Student attempts to view Chair status -> 403 Forbidden
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.student_user.id
            sess["role"] = "STUDENT"
            sess["active_role"] = "STUDENT"

        res_stud = self.client.get("/api/chair/status")
        self.assertEqual(res_stud.status_code, 403)
        self.assertIsNone(res_stud.get_json()["is_active"])

    def test_02_student_submit_reschedule_request_pipeline(self):
        """Test full multi-tier reschedule workflow: Student -> Faculty Review -> Chair Approval."""
        with self.app.app_context():
            # Find a schedule for CpE 2A
            sched = Schedule.query.filter_by(section_id=self.section.id).first()
            self.assertIsNotNone(sched)
            sched_id = sched.id
            initial_day = sched.day_of_week
            fac_id = sched.faculty_id

        # 1. Student submits a reschedule request for Friday 16:00 - 17:30
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.student_user.id
            sess["role"] = "STUDENT"
            sess["active_role"] = "STUDENT"
            sess["reference_id"] = self.section.id
            sess["active_reference_id"] = self.section.id

        payload = {
            "schedule_id": sched_id,
            "proposed_day": "FRI",
            "proposed_start_time": "16:00",
            "proposed_end_time": "17:30",
            "reason": "Section cohort conflict with annual college-wide technical symposium.",
        }
        res_req = self.client.post("/api/reschedule/request", json=payload)
        self.assertEqual(res_req.status_code, 201)
        req_id = res_req.get_json()["data"]["id"]
        self.assertEqual(res_req.get_json()["data"]["status"], "PENDING_FACULTY")

        # 2. Faculty reviews and endorses proposal
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.faculty_user.id
            sess["role"] = "FACULTY"
            sess["active_role"] = "FACULTY"
            sess["reference_id"] = fac_id
            sess["active_reference_id"] = fac_id

        review_payload = {
            "approved": True,
            "feedback": "Approved. Friday late afternoon slot is compatible with lab schedule.",
        }
        res_review = self.client.post(f"/api/reschedule/{req_id}/faculty-review", json=review_payload)
        self.assertEqual(res_review.status_code, 200)
        self.assertEqual(res_review.get_json()["data"]["status"], "PENDING_CHAIR")

        # 3. Program Chair / Admin authorizes proposal -> Schedule updated atomically
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.chair_user.id
            sess["role"] = "CHAIR"
            sess["active_role"] = "CHAIR"

        chair_payload = {
            "approved": True,
            "feedback": "Final authorization granted. Timetable updated.",
        }
        res_chair = self.client.post(f"/api/reschedule/{req_id}/chair-decision", json=chair_payload)
        self.assertEqual(res_chair.status_code, 200)
        self.assertEqual(res_chair.get_json()["data"]["status"], "APPROVED")

        # 4. Verify Schedule database mutation
        with self.app.app_context():
            updated_sched = db.session.get(Schedule, sched_id)
            self.assertEqual(updated_sched.day_of_week, "FRI")
            self.assertEqual(updated_sched.start_time.strftime("%H:%M"), "16:00")
            self.assertEqual(updated_sched.end_time.strftime("%H:%M"), "17:30")

    def test_03_student_cannot_request_reschedule_for_other_section(self):
        """Test that a Student cannot request reschedule for a class belonging to another section."""
        with self.app.app_context():
            # Find a schedule belonging to section 1 (CpE 1A)
            other_sec_sched = Schedule.query.filter(Schedule.section_id != self.section.id).first()
            self.assertIsNotNone(other_sec_sched)
            other_sched_id = other_sec_sched.id

        # Student is for CpE 2A
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.student_user.id
            sess["role"] = "STUDENT"
            sess["active_role"] = "STUDENT"
            sess["reference_id"] = self.section.id
            sess["active_reference_id"] = self.section.id

        payload = {
            "schedule_id": other_sched_id,
            "proposed_day": "MON",
            "proposed_start_time": "14:00",
            "proposed_end_time": "15:30",
            "reason": "Unauthorized attempt.",
        }
        res = self.client.post("/api/reschedule/request", json=payload)
        self.assertEqual(res.status_code, 403)
        self.assertIn("unauthorized", res.get_json()["error"].lower())

    def test_04_analytics_reports_endpoint(self):
        """Test GET /api/analytics/reports returns room utilization ranking, workloads, and quality score."""
        res = self.client.get("/api/analytics/reports")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["data"]

        # 1. Room Utilization
        self.assertIn("room_utilization", data)
        self.assertEqual(data["room_utilization"]["weekly_capacity_benchmark_hours"], 72.0)
        self.assertIsInstance(data["room_utilization"]["rooms"], list)

        # 2. Faculty Workload
        self.assertIn("faculty_workload", data)
        self.assertEqual(data["faculty_workload"]["standard_max_units"], 21)
        self.assertIsInstance(data["faculty_workload"]["faculty"], list)

        # 3. Quality Score & Deductions
        self.assertIn("quality_score", data)
        self.assertIn("score", data["quality_score"])
        self.assertIn("deductions", data["quality_score"])


if __name__ == "__main__":
    unittest.main()
