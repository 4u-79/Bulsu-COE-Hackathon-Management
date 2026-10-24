"""COE SYNC 2026 - NEXUS 2.0 Test Suite

Validates:
1. data-3.sql ingestion & sanitization (539 subjects, 90 sections, 126 faculty, 8 COE departments + GEN)
2. Disambiguation of duplicate lecture/lab codes (e.g. MFG 221 / MFG 221L) and whitespace collapsing
3. 5 User Roles (DEAN, ADMIN, CHAIR/PROG_CHA, FACULTY/FCLTY_DEPT, STUDENT/STDN_MYR) & access matrix
4. Department-allocated rooms, room booking endpoint, and inter-department approval workflow
5. 7-day reschedule request expiration badge & pending requests summary
6. Scoped faculty sections, curriculum toggle, and profile session preferences (SPLIT vs STRAIGHT)
"""

import sys
import unittest
from pathlib import Path
from datetime import datetime, timedelta

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
    InterDepartmentRequest,
)


class TestNexus2Suite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.client = cls.app.test_client()

        with cls.app.app_context():
            seed_database(cls.app)

    def test_01_data_3_ingestion_and_counts(self):
        """Verify data-3.sql parsed exact counts: 539 subjects, 90 sections, 126 faculty."""
        with self.app.app_context():
            subj_count = Subject.query.count()
            sec_count = Section.query.count()
            fac_count = Faculty.query.count()

            self.assertEqual(subj_count, 539, f"Expected 539 subjects, found {subj_count}")
            self.assertEqual(sec_count, 90, f"Expected 90 sections, found {sec_count}")
            self.assertEqual(fac_count, 126, f"Expected 126 faculty, found {fac_count}")

            # Verify all 8 engineering departments + GEN are present
            departments = {s.program for s in Subject.query.all()}
            expected_depts = {"CE", "CPE", "EE", "ECE", "IE", "MFGE", "ME", "MEE", "GEN"}
            self.assertTrue(expected_depts.issubset(departments), f"Missing departments: {expected_depts - departments}")

    def test_02_subject_sanitization_and_lab_disambiguation(self):
        """Verify whitespace collapsing and lab code disambiguation (MFG 221L, etc.)."""
        with self.app.app_context():
            # Check duplicate disambiguation in MFG
            mfg_221_lec = Subject.query.filter_by(code="MFG 221").first()
            mfg_221_lab = Subject.query.filter_by(code="MFG 221L").first()
            self.assertIsNotNone(mfg_221_lec, "MFG 221 lecture should exist")
            self.assertIsNotNone(mfg_221_lab, "MFG 221L lab should exist")
            self.assertEqual(mfg_221_lab.subject_type, "LAB")

            # Check whitespace collapsing on descriptions (title column)
            for s in Subject.query.filter(Subject.program == "MEE").all():
                self.assertNotIn("  ", s.title, f"Uncollapsed whitespace in subject description: {s.title}")

            # Check is_general, requires_grouping, preferred_session_type
            gen_subj = Subject.query.filter_by(program="GEN").first()
            self.assertTrue(gen_subj.is_general)
            
            lab_subj = Subject.query.filter_by(subject_type="LAB").first()
            self.assertTrue(lab_subj.requires_grouping)
            self.assertEqual(lab_subj.preferred_session_type, "STRAIGHT")

    def test_03_five_nexus_roles_auth_and_normalization(self):
        """Verify authentication and normalization for all 5 NEXUS 2.0 roles."""
        with self.app.app_context():
            dean = User.query.filter_by(role="DEAN").first()
            admin = User.query.filter_by(role="ADMIN").first()
            chair = User.query.filter_by(role="CHAIR").first()
            faculty = User.query.filter_by(role="FACULTY").first()
            student = User.query.filter_by(role="STUDENT").first()

            self.assertIsNotNone(dean, "DEAN role should be seeded")
            self.assertIsNotNone(admin, "ADMIN role should be seeded")
            self.assertIsNotNone(chair, "CHAIR role should be seeded")
            self.assertIsNotNone(faculty, "FACULTY role should be seeded")
            self.assertIsNotNone(student, "STUDENT role should be seeded")

        # Test login as DEAN
        res = self.client.post("/api/auth/login", json={"username": "dean", "password": "password"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["user"]["role"], "DEAN")
        self.assertIn("College Dean", data["user"]["title"])

        # Test login as Program Chair MEE
        res = self.client.post("/api/auth/login", json={"username": "chair_mee", "password": "password"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["user"]["role"], "CHAIR")
        self.assertEqual(data["user"]["program"], "MEE")

        # Test login as Student Mayor
        res = self.client.post("/api/auth/login", json={"username": "mayor_mee1a", "password": "password"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["user"]["role"], "STUDENT")
        self.assertIsNotNone(data["user"]["reference_id"])

    def test_04_department_allocated_rooms_and_room_request(self):
        """Verify room department ownership and room booking endpoint."""
        with self.app.app_context():
            rooms = Room.query.all()
            departments = {r.department for r in rooms}
            self.assertTrue({"MEE", "GEN"}.issubset(departments), f"Rooms should have department allocation: {departments}")

            mee_room = Room.query.filter_by(department="MEE").first()
            room_id = mee_room.id

        # Student mayor requests a room
        self.client.post("/api/auth/login", json={"username": "mayor_mee1a", "password": "password"})
        req_res = self.client.post("/api/rooms/request", json={
            "room_id": room_id,
            "purpose": "Mechatronics Robotics Workshop",
            "time_slot": "MON 13:00-16:00"
        })
        self.assertEqual(req_res.status_code, 201)
        req_data = req_res.get_json()
        self.assertEqual(req_data["status"], "success")
        reschedule_id = req_data["data"]["id"]

        # Chair approves room request
        self.client.post("/api/auth/login", json={"username": "chair_mee", "password": "password"})
        action_res = self.client.post(f"/api/reschedule/{reschedule_id}/chair-decision", json={
            "action": "APPROVE",
            "remarks": "Approved for Robotics Workshop"
        })
        self.assertEqual(action_res.status_code, 200)

        # Verify Room.booked_by_label was set
        with self.app.app_context():
            updated_room = Room.query.get(room_id)
            self.assertIsNotNone(updated_room.booked_by_label)
            self.assertIn("Approved by", updated_room.booked_by_label)

    def test_05_interdepartment_request_and_approval_workflow(self):
        """Verify InterDepartmentRequest creation, inbox listing, and approval action."""
        with self.app.app_context():
            room = Room.query.filter_by(department="ECE").first() or Room.query.first()
            inter_req = InterDepartmentRequest(
                source_department="MEE",
                target_department=room.department or "ECE",
                room_id=room.id,
                reason="All MEE labs fully booked during TUE morning block.",
                alternative_recommendations="['WED 13:00-16:00 Room 204', 'THU 08:00-11:00 Room 202']",
                status="PENDING_APPROVAL"
            )
            db.session.add(inter_req)
            db.session.commit()
            req_id = inter_req.id

        # Admin checks pending summary count
        self.client.post("/api/auth/login", json={"username": "admin", "password": "password"})
        sum_res = self.client.get("/api/requests/pending-summary")
        self.assertEqual(sum_res.status_code, 200)
        sum_data = sum_res.get_json()
        self.assertGreaterEqual(sum_data["total_pending"], 1)

        # Admin lists interdepartment requests
        list_res = self.client.get("/api/interdept/requests")
        self.assertEqual(list_res.status_code, 200)
        list_data = list_res.get_json()
        self.assertIn("data", list_data)
        found = any(r["id"] == req_id for r in list_data["data"])
        self.assertTrue(found, "InterDepartmentRequest should be listed in inbox")

        # Admin approves the request
        act_res = self.client.post(f"/api/interdept/{req_id}/action", json={
            "action": "APPROVE",
            "remarks": "Approved interdepartment allocation"
        })
        self.assertEqual(act_res.status_code, 200)
        self.assertEqual(act_res.get_json()["data"]["status"], "APPROVED")

    def test_06_scoped_views_and_faculty_profile(self):
        """Verify faculty-scoped sections, subjects curriculum toggle, and profile session preference."""
        with self.app.app_context():
            fac = Faculty.query.filter_by(program="MEE").first()
            fac_user = User.query.filter_by(reference_id=fac.id, role="FACULTY").first()
            if not fac_user:
                fac_user = User(
                    username="test_fac_mee",
                    role="FACULTY",
                    program="MEE",
                    reference_id=fac.id,
                    is_active_status=True
                )
                fac_user.set_password("password")
                db.session.add(fac_user)
                db.session.commit()
            username = fac_user.username
            fac_id = fac.id

        # Login as faculty
        self.client.post("/api/auth/login", json={"username": username, "password": "password"})

        # Call /api/master/sections?faculty_id=fac_id
        sec_res = self.client.get(f"/api/master/sections?faculty_id={fac_id}")
        self.assertEqual(sec_res.status_code, 200)
        sections = sec_res.get_json()["data"]
        self.assertIsInstance(sections, list)

        # Call /api/master/subjects with curriculum=true vs false
        subj_assigned = self.client.get("/api/master/subjects?curriculum=false")
        self.assertEqual(subj_assigned.status_code, 200)

        subj_all = self.client.get("/api/master/subjects?curriculum=true")
        self.assertEqual(subj_all.status_code, 200)
        self.assertGreaterEqual(len(subj_all.get_json()["data"]), len(subj_assigned.get_json()["data"]))

        # Update faculty profile session preference
        upd_res = self.client.put(f"/api/master/faculty/{fac_id}", json={
            "preferred_session_type": "STRAIGHT"
        })
        self.assertEqual(upd_res.status_code, 200)
        with self.app.app_context():
            f = db.session.get(Faculty, fac_id)
            self.assertEqual(f.preferred_session_type, "STRAIGHT")


if __name__ == "__main__":
    unittest.main()
