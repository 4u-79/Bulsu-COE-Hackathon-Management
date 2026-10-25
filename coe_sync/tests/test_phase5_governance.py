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
            cls.section = Section.query.filter(Section.name.in_(["CPE - 2A", "CpE 2A"])).first() or Section.query.first()

    def setUp(self):
        """Re-seed database before each test for clean test isolation."""
        with self.app.app_context():
            seed_database(self.app)
            chair = User.query.filter_by(role="CHAIR").first()
            fac_u = User.query.filter_by(role="FACULTY").first()
            stud = User.query.filter_by(role="STUDENT").first()
            sec = Section.query.filter(Section.name.in_(["CPE - 2A", "CpE 2A"])).first() or Section.query.first()
            other_sec = Section.query.filter(Section.id != sec.id).first()
            sub = Subject.query.filter_by(subject_type="LECTURE").first()
            room = Room.query.filter_by(room_type="LECTURE").first()
            fac = Faculty.query.first()

            self.chair_user_id = chair.id
            self.faculty_user_id = fac_u.id
            self.student_user_id = stud.id
            self.section_id = sec.id
            
            s1 = Schedule(
                subject_id=sub.id,
                section_id=sec.id,
                faculty_id=fac.id,
                room_id=room.id,
                day_of_week="MON",
                start_time=time(8, 0),
                end_time=time(10, 0),
                status="PUBLISHED",
            )
            s2 = Schedule(
                subject_id=sub.id,
                section_id=other_sec.id,
                faculty_id=fac.id,
                room_id=room.id,
                day_of_week="TUE",
                start_time=time(8, 0),
                end_time=time(10, 0),
                status="PUBLISHED",
            )
            db.session.add_all([s1, s2])
            db.session.commit()

    def test_01_chair_status_toggle_and_visibility_isolation(self):
        """Test Chair status toggle and verify that Student is restricted with 403."""
        # 1. Chair updates status to Inactive / Out of Office
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.chair_user_id
            sess["role"] = "CHAIR"
            sess["active_role"] = "CHAIR"

        res_toggle = self.client.post("/api/chair/status", json={"is_active": False})
        self.assertEqual(res_toggle.status_code, 200)
        self.assertEqual(res_toggle.get_json()["is_active"], False)

        # 2. Faculty views Chair status -> 200 OK
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.faculty_user_id
            sess["role"] = "FACULTY"
            sess["active_role"] = "FACULTY"

        res_fac = self.client.get("/api/chair/status")
        self.assertEqual(res_fac.status_code, 200)
        self.assertEqual(res_fac.get_json()["is_active"], False)

        # 3. Student attempts to view Chair status -> 403 Forbidden
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.student_user_id
            sess["role"] = "STUDENT"
            sess["active_role"] = "STUDENT"

        res_stud = self.client.get("/api/chair/status")
        self.assertEqual(res_stud.status_code, 403)
        self.assertIsNone(res_stud.get_json()["is_active"])

    def test_02_student_submit_reschedule_request_pipeline(self):
        """Test full multi-tier reschedule workflow: Student -> Faculty Review -> Chair Approval."""
        with self.app.app_context():
            # Find a schedule for CpE 2A
            sched = Schedule.query.filter_by(section_id=self.section_id).first()
            self.assertIsNotNone(sched)
            sched_id = sched.id
            initial_day = sched.day_of_week
            fac_id = sched.faculty_id

        # 1. Student submits a reschedule request for Friday 16:00 - 17:30
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.student_user_id
            sess["role"] = "STUDENT"
            sess["active_role"] = "STUDENT"
            sess["reference_id"] = self.section_id
            sess["active_reference_id"] = self.section_id

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
            sess["user_id"] = self.faculty_user_id
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
            sess["user_id"] = self.chair_user_id
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
            other_sec_sched = Schedule.query.filter(Schedule.section_id != self.section_id).first()
            self.assertIsNotNone(other_sec_sched)
            other_sched_id = other_sec_sched.id

        # Student is for CpE 2A
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.student_user_id
            sess["role"] = "STUDENT"
            sess["active_role"] = "STUDENT"
            sess["reference_id"] = self.section_id
            sess["active_reference_id"] = self.section_id

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


    def test_05_student_room_request_in_my_requests(self):
        """Test that room request submitted by student appears in their My Requests inbox."""
        with self.app.app_context():
            room = Room.query.first()
            room_id = room.id
            room_code = room.room_code

        with self.client.session_transaction() as sess:
            sess["user_id"] = self.student_user_id
            sess["role"] = "STUDENT"
            sess["active_role"] = "STUDENT"
            sess["username"] = "mayor_mee1a"
            sess["reference_id"] = self.section_id
            sess["active_reference_id"] = self.section_id

        # Submit room reservation request
        res = self.client.post("/api/rooms/request", json={
            "room_id": room_id,
            "day_of_week": "WED",
            "start_time": "13:00",
            "end_time": "15:00",
            "reason": "Robotics team assembly"
        })
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertEqual(data["status"], "success")
        req_id = data["data"]["id"]
        self.assertEqual(data["data"]["proposed_day"], "WED")
        self.assertIn("Robotics team assembly", data["data"]["reason"])

        # Fetch My Requests as student
        list_res = self.client.get("/api/reschedule/requests")
        self.assertEqual(list_res.status_code, 200)
        list_data = list_res.get_json()
        self.assertEqual(list_data["status"], "success")
        student_req_ids = [r["id"] for r in list_data["data"]]
        self.assertIn(req_id, student_req_ids)

        # Verify pending summary counts the request
        sum_res = self.client.get("/api/requests/pending-summary")
        self.assertEqual(sum_res.status_code, 200)
        sum_data = sum_res.get_json()
        self.assertGreaterEqual(sum_data["reschedule_count"], 1)


if __name__ == "__main__":
    unittest.main()
