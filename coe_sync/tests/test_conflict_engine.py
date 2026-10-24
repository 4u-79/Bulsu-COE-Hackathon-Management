"""COE SYNC 2026 - Conflict Detection Engine & Phase 2 Test Suite

Validates:
1. Room collision raises HTTP 409 with actionable alternative suggestions
2. Overcapacity class assignment is rejected (student_count > room.capacity)
3. Lab subject assigned to a lecture room is rejected (Room type mismatch)
4. Student attempting POST /api/schedules receives HTTP 403
5. Inverted time (start_time >= end_time) receives HTTP 400
6. Faculty availability blackout on Friday 08:00-12:00 is enforced
7. Locked schedule edit (status=PUBLISHED) is rejected with HTTP 400
8. Analytics summary endpoint returns utilization, workload, and quality score
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


class TestConflictEngineAndRBAC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Initialize test app with isolated test configuration and fresh seed."""
        cls.app = create_app("testing")
        cls.client = cls.app.test_client()

        with cls.app.app_context():
            seed_database(cls.app)

            # Cache lookup dictionaries
            cls.users = {u.username: u for u in User.query.all()}
            cls.faculty = {f.name: f for f in Faculty.query.all()}
            cls.sections = {s.name: s for s in Section.query.all()}
            cls.rooms = {r.room_code: r for r in Room.query.all()}
            cls.subjects = {s.code: s for s in Subject.query.all()}

    def setUp(self):
        """Reset session and re-seed for clean test isolation."""
        with self.app.app_context():
            # Clear schedules while keeping master seed data
            Schedule.query.delete()
            db.session.commit()

        # Login as CHAIR by default for administrative endpoints
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.users["chair_cpe"].id
            sess["username"] = "chair_cpe"
            sess["role"] = "CHAIR"
            sess["active_role"] = "CHAIR"
            sess["reference_id"] = None
            sess["active_reference_id"] = None

    def test_01_room_collision_raises_409_with_suggestions(self):
        """Test: A room collision raises HTTP 409 with alternative suggestions."""
        math101 = self.subjects["MATH 101"]
        cpe2a = self.sections["CpE 2A"]
        santos = self.faculty["Prof. Juan Santos"]
        eng201 = self.rooms["Eng-201"]

        # Step A: Create initial schedule slot
        payload_1 = {
            "subject_id": math101.id,
            "section_id": cpe2a.id,
            "faculty_id": santos.id,
            "room_id": eng201.id,
            "day_of_week": "MON",
            "start_time": "08:00:00",
            "end_time": "10:00:00",
        }
        res1 = self.client.post("/api/schedules", json=payload_1)
        self.assertEqual(res1.status_code, 201)

        # Step B: Attempt overlapping booking in the exact same room with different faculty & section
        chem101 = self.subjects["CHEM 101"]
        cpe3a = self.sections["CpE 3A"]
        cruz = self.faculty["Engr. Alex Cruz"]

        payload_2 = {
            "subject_id": chem101.id,
            "section_id": cpe3a.id,
            "faculty_id": cruz.id,
            "room_id": eng201.id,  # Colliding room
            "day_of_week": "MON",
            "start_time": "09:00:00",  # Overlaps 08:00-10:00
            "end_time": "11:00:00",
        }
        res2 = self.client.post("/api/schedules", json=payload_2)
        self.assertEqual(res2.status_code, 409)

        data = res2.get_json()
        self.assertIn("conflicts", data)
        self.assertTrue(
            any("already occupied" in c for c in data["conflicts"]),
            f"Expected room occupation conflict, got: {data['conflicts']}",
        )
        self.assertIn("suggestions", data)
        self.assertGreater(
            len(data["suggestions"]),
            0,
            "Expected recommendation heuristics to provide alternative suggestions.",
        )

    def test_02_overcapacity_assignment_rejected(self):
        """Test: An overcapacity class assignment is rejected."""
        math101 = self.subjects["MATH 101"]
        cpe1a = self.sections["CpE 1A"]  # 45 students
        santos = self.faculty["Prof. Juan Santos"]
        eng104 = self.rooms["Eng-104"]  # Capacity: 35 seats

        payload = {
            "subject_id": math101.id,
            "section_id": cpe1a.id,
            "faculty_id": santos.id,
            "room_id": eng104.id,
            "day_of_week": "TUE",
            "start_time": "08:00:00",
            "end_time": "10:00:00",
        }
        res = self.client.post("/api/schedules", json=payload)
        self.assertEqual(res.status_code, 409)

        data = res.get_json()
        self.assertTrue(
            any("Room capacity exceeded" in c for c in data["conflicts"]),
            f"Expected capacity overflow message, got: {data['conflicts']}",
        )

    def test_03_lab_subject_assigned_to_lecture_room_rejected(self):
        """Test: A lab subject assigned to a lecture room is rejected."""
        cpe211l = self.subjects["CPE 211L"]  # LAB subject
        cpe2a = self.sections["CpE 2A"]  # 40 students
        santos = self.faculty["Prof. Juan Santos"]
        eng201 = self.rooms["Eng-201"]  # LECTURE room

        payload = {
            "subject_id": cpe211l.id,
            "section_id": cpe2a.id,
            "faculty_id": santos.id,
            "room_id": eng201.id,
            "day_of_week": "WED",
            "start_time": "13:00:00",
            "end_time": "16:00:00",
        }
        res = self.client.post("/api/schedules", json=payload)
        self.assertEqual(res.status_code, 409)

        data = res.get_json()
        self.assertTrue(
            any(
                "Subject requires a specialized Laboratory facility" in c
                for c in data["conflicts"]
            ),
            f"Expected lab facility mismatch error, got: {data['conflicts']}",
        )

    def test_04_student_cannot_post_schedules(self):
        """Test: A Student attempting POST /api/schedules receives HTTP 403."""
        # Impersonate / authenticate as STUDENT
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.users["student_cpe2a"].id
            sess["username"] = "student_cpe2a"
            sess["role"] = "STUDENT"
            sess["active_role"] = "STUDENT"
            sess["reference_id"] = self.sections["CpE 2A"].id
            sess["active_reference_id"] = self.sections["CpE 2A"].id

        payload = {
            "subject_id": self.subjects["MATH 101"].id,
            "section_id": self.sections["CpE 2A"].id,
            "faculty_id": self.faculty["Prof. Juan Santos"].id,
            "room_id": self.rooms["Eng-201"].id,
            "day_of_week": "THU",
            "start_time": "08:00:00",
            "end_time": "10:00:00",
        }
        res = self.client.post("/api/schedules", json=payload)
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertIn("error", data)
        self.assertIn("Insufficient permissions", data["error"])

    def test_05_inverted_time_rejected_with_400(self):
        """Test: Inverted time (start_time >= end_time) receives HTTP 400."""
        payload = {
            "subject_id": self.subjects["MATH 101"].id,
            "section_id": self.sections["CpE 2A"].id,
            "faculty_id": self.faculty["Prof. Juan Santos"].id,
            "room_id": self.rooms["Eng-201"].id,
            "day_of_week": "FRI",
            "start_time": "11:00:00",  # Inverted: start is later than end
            "end_time": "09:00:00",
        }
        res = self.client.post("/api/schedules", json=payload)
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertIn("error", data)
        self.assertIn("start_time must be strictly earlier than end_time", data["error"])

    def test_06_faculty_unavailability_blackout_enforced(self):
        """Test: Prof. Maria Rivera unavailable on Friday 08:00-12:00."""
        rivera = self.faculty["Prof. Maria Rivera"]
        cpe3a = self.sections["CpE 3A"]
        eng201 = self.rooms["Eng-201"]
        math101 = self.subjects["MATH 101"]

        payload = {
            "subject_id": math101.id,
            "section_id": cpe3a.id,
            "faculty_id": rivera.id,
            "room_id": eng201.id,
            "day_of_week": "FRI",
            "start_time": "09:00:00",  # Inside 08:00 - 12:00 blackout
            "end_time": "11:00:00",
        }
        res = self.client.post("/api/schedules", json=payload)
        self.assertEqual(res.status_code, 409)
        data = res.get_json()
        self.assertTrue(
            any("marked as unavailable" in c for c in data["conflicts"]),
            f"Expected faculty blackout error, got: {data['conflicts']}",
        )

    def test_07_locked_schedule_edit_rejected(self):
        """Test: Updating a locked (PUBLISHED) schedule receives HTTP 400."""
        # Create schedule
        math101 = self.subjects["MATH 101"]
        cpe2a = self.sections["CpE 2A"]
        santos = self.faculty["Prof. Juan Santos"]
        eng201 = self.rooms["Eng-201"]

        payload = {
            "subject_id": math101.id,
            "section_id": cpe2a.id,
            "faculty_id": santos.id,
            "room_id": eng201.id,
            "day_of_week": "SAT",
            "start_time": "08:00:00",
            "end_time": "10:00:00",
            "status": "PUBLISHED",
        }
        res = self.client.post("/api/schedules", json=payload)
        self.assertEqual(res.status_code, 201)
        sched_id = res.get_json()["data"]["id"]

        # Attempt to edit the published schedule
        update_payload = {"end_time": "11:00:00"}
        edit_res = self.client.put(f"/api/schedules/{sched_id}", json=update_payload)
        self.assertEqual(edit_res.status_code, 400)
        self.assertIn("Must unpublish before editing", edit_res.get_json()["error"])

    def test_08_analytics_summary_endpoint(self):
        """Test: Analytics summary endpoint returns valid metrics."""
        # Create a valid schedule to populate analytics
        payload = {
            "subject_id": self.subjects["MATH 101"].id,
            "section_id": self.sections["CpE 2A"].id,
            "faculty_id": self.faculty["Prof. Juan Santos"].id,
            "room_id": self.rooms["Eng-201"].id,
            "day_of_week": "MON",
            "start_time": "08:00:00",
            "end_time": "11:00:00",  # 3 hours
        }
        self.client.post("/api/schedules", json=payload)

        res = self.client.get("/api/analytics/summary")
        self.assertEqual(res.status_code, 200)

        data = res.get_json()["data"]
        self.assertGreaterEqual(data["total_classes"], 1)
        self.assertGreater(data["room_utilization"], 0.0)
        self.assertEqual(data["unresolved_conflicts"], 0)
        self.assertLessEqual(data["schedule_quality_score"], 100)
        self.assertEqual(len(data["faculty_workloads"]), len(self.faculty))


if __name__ == "__main__":
    unittest.main(verbosity=2)
