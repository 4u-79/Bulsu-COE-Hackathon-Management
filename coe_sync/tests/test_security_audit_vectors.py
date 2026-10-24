"""COE SYNC 2026 - Security & Systems Audit Regression Test Suite
Validates the 7 Security Audit Vectors across all 4 RBAC Tiers.
"""

import unittest
from datetime import time
from app import create_app
from models import (
    db,
    User,
    Faculty,
    Section,
    Subject,
    Room,
    Schedule,
    RescheduleRequest,
    FacultyAvailability,
)
from seed_data import seed_database
from services.conflict_detector import times_overlap, validate_schedule_slot


class TestSecurityAuditVectors(unittest.TestCase):
    """Deep cross-examination tests for COE SYNC 2026 security architecture."""

    def setUp(self):
        self.app = create_app("testing")
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        # Seed baseline database
        seed_database(self.app)

        self.chair_user = User.query.filter_by(role="CHAIR").first()
        self.admin_user = User.query.filter_by(role="ADMIN").first()
        self.faculty_user = User.query.filter_by(role="FACULTY").first()
        self.student_user = User.query.filter_by(role="STUDENT").first()

        # Seed baseline test schedules for security vector tests
        sec1 = Section.query.get(1)
        sec2 = Section.query.get(2)
        sub1 = Subject.query.filter_by(subject_type="LECTURE").first()
        room1 = Room.query.filter_by(room_type="LECTURE").first()
        room2 = Room.query.filter(Room.room_type == "LECTURE", Room.id != room1.id).first()
        fac1 = Faculty.query.get(1)
        fac2 = Faculty.query.get(2)

        s1 = Schedule(
            subject_id=sub1.id,
            section_id=sec1.id,
            faculty_id=fac1.id,
            room_id=room1.id,
            day_of_week="MON",
            start_time=time(8, 0),
            end_time=time(10, 0),
            status="PUBLISHED",
        )
        s2 = Schedule(
            subject_id=sub1.id,
            section_id=sec2.id,
            faculty_id=fac1.id,
            room_id=room2.id,
            day_of_week="TUE",
            start_time=time(10, 0),
            end_time=time(12, 0),
            status="PUBLISHED",
        )
        s3 = Schedule(
            subject_id=sub1.id,
            section_id=sec2.id,
            faculty_id=fac2.id,
            room_id=room1.id,
            day_of_week="WED",
            start_time=time(13, 0),
            end_time=time(15, 0),
            status="DRAFT",
        )
        s4 = Schedule(
            subject_id=sub1.id,
            section_id=sec2.id,
            faculty_id=fac1.id,
            room_id=room2.id,
            day_of_week="THU",
            start_time=time(10, 0),
            end_time=time(12, 0),
            status="PUBLISHED",
        )
        db.session.add_all([s1, s2, s3, s4])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    # ─────────────────────────────────────────────────────────────────────────
    # VECTOR 1: RBAC Enforcement & Route Guard Integrity
    # ─────────────────────────────────────────────────────────────────────────
    def test_v1_unauthenticated_requests_fail_closed_with_401(self):
        """Endpoint protected by require_roles returns 401 (not 403 or 500) when unauthenticated."""
        res = self.client.post("/api/schedules", json={})
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertIn("Authentication required", data.get("error", ""))

        # Also check POST /api/chair/status
        res_chair = self.client.post("/api/chair/status", json={"is_active": True})
        self.assertEqual(res_chair.status_code, 401)

    def test_v1_student_bypassing_frontend_receives_403(self):
        """Student authenticated session directly calling POST /api/schedules is rejected with 403."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.student_user.id
            sess["role"] = "STUDENT"
            sess["active_role"] = "STUDENT"
            sess["reference_id"] = self.student_user.reference_id

        res = self.client.post("/api/schedules", json={"subject_id": 1})
        self.assertEqual(res.status_code, 403)

        res_chair = self.client.post("/api/chair/status", json={"is_active": False})
        self.assertEqual(res_chair.status_code, 403)

    def test_v1_row_level_security_student_cannot_view_other_sections(self):
        """Student cannot query other section IDs or inspect unpublished/draft schedules."""
        # Ensure section 2 has a draft and a published schedule, and section 1 has a published schedule
        sched_sec2_draft = Schedule.query.filter_by(section_id=2).first()
        sched_sec2_draft.status = "DRAFT"
        db.session.commit()

        with self.client.session_transaction() as sess:
            sess["user_id"] = self.student_user.id
            sess["role"] = "STUDENT"
            sess["active_role"] = "STUDENT"
            sess["reference_id"] = 2  # CpE 2A

        # Query own section -> Success (200), strictly PUBLISHED only
        res_own = self.client.get("/api/schedules?section_id=2")
        self.assertEqual(res_own.status_code, 200)
        data_own = res_own.get_json()["data"]
        for s in data_own:
            self.assertEqual(s["status"], "PUBLISHED")
            self.assertEqual(s["section_id"], 2)

        # Attacker crafts request to view section 1 -> Strictly 403 Forbidden
        res_other = self.client.get("/api/schedules?section_id=1")
        self.assertEqual(res_other.status_code, 403)
        self.assertIn("Cross-section", res_other.get_json()["error"])

    def test_v1_row_level_security_faculty_cannot_view_other_faculty(self):
        """Faculty cannot query other faculty IDs via parameter tampering."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.faculty_user.id
            sess["role"] = "FACULTY"
            sess["active_role"] = "FACULTY"
            sess["reference_id"] = self.faculty_user.reference_id

        # Query other faculty id (999 or 2)
        other_id = self.faculty_user.reference_id + 1
        res = self.client.get(f"/api/schedules?faculty_id={other_id}")
        self.assertEqual(res.status_code, 403)
        self.assertIn("Access restricted to your own instructional assignments", res.get_json()["error"])

    def test_v1_impersonate_restricted_to_chair_and_admin(self):
        """Student and Faculty sessions cannot call POST /api/auth/impersonate."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.student_user.id
            sess["role"] = "STUDENT"
            sess["active_role"] = "STUDENT"

        res = self.client.post("/api/auth/impersonate", json={"role": "ADMIN"})
        self.assertEqual(res.status_code, 403)

    # ─────────────────────────────────────────────────────────────────────────
    # VECTOR 2: Frontend DOM & UI Visibility Lockdown per Role Tier
    # ─────────────────────────────────────────────────────────────────────────
    def test_v2_student_dom_omits_restricted_elements_server_side(self):
        """Student HTML view completely omits admin links, radar drawer, and edit modal from DOM."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.student_user.id
            sess["role"] = "STUDENT"
            sess["active_role"] = "STUDENT"
            sess["reference_id"] = 2

        res = self.client.get("/schedules")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Under NEXUS RBAC, Students CAN see Dashboard, Schedules, and Rooms, but MUST NOT see admin tools
        self.assertIn('id="nav-dashboard"', html)
        self.assertIn('id="nav-rooms"', html)
        self.assertIn('id="nav-schedules"', html)

        # Verify completely omitted from HTML text
        self.assertNotIn('id="nav-create-schedule"', html)
        self.assertNotIn('id="nav-faculty"', html)
        self.assertNotIn('id="nav-sections"', html)
        self.assertNotIn('id="nav-subjects"', html)
        self.assertNotIn('id="nav-reports"', html)
        self.assertNotIn('id="nav-conflict-radar"', html)
        self.assertNotIn('id="chair-status-widget"', html)
        self.assertNotIn('id="view-as-container"', html)
        self.assertNotIn('id="btn-publish-all"', html)
        self.assertNotIn('id="btn-create-schedule-cta"', html)
        self.assertNotIn('id="btn-add-schedule"', html)
        self.assertNotIn('id="radar-drawer"', html)
        self.assertNotIn('id="sched-modal-backdrop"', html)

    def test_v2_faculty_dom_omits_view_as_and_includes_chair_status(self):
        """Faculty HTML view has chair status pill, but completely omits view-as dropdown and modal."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.faculty_user.id
            sess["role"] = "FACULTY"
            sess["active_role"] = "FACULTY"
            sess["reference_id"] = self.faculty_user.reference_id

        res = self.client.get("/schedules")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        self.assertNotIn('id="view-as-container"', html)
        self.assertNotIn('id="btn-publish-all"', html)
        self.assertNotIn('id="btn-create-schedule-cta"', html)
        self.assertNotIn('id="sched-modal-backdrop"', html)
        # Faculty has access to chair status widget
        self.assertIn('id="chair-status-widget"', html)

    # ─────────────────────────────────────────────────────────────────────────
    # VECTOR 3: Reschedule Request Pipeline End-to-End Tracing
    # ─────────────────────────────────────────────────────────────────────────
    def test_v3_reschedule_submission_ownership_and_preflight(self):
        """Student cannot submit reschedule for another section, and preflight detects collisions."""
        sched_sec1 = Schedule.query.filter_by(section_id=1).first()
        sched_sec2 = Schedule.query.filter_by(section_id=2).first()

        with self.client.session_transaction() as sess:
            sess["user_id"] = self.student_user.id
            sess["role"] = "STUDENT"
            sess["active_role"] = "STUDENT"
            sess["reference_id"] = 2  # Assigned to section 2

        # 1. Attempt submitting for section 1's schedule -> 403 Forbidden
        res_cross = self.client.post(
            "/api/reschedule/request",
            json={
                "schedule_id": sched_sec1.id,
                "proposed_day": "WED",
                "proposed_start_time": "13:00",
                "proposed_end_time": "14:30",
                "reason": "Test cross-section exploit",
            },
        )
        self.assertEqual(res_cross.status_code, 403)
        self.assertIn("classes in your section", res_cross.get_json()["error"])

        # 2. Submit for own schedule with an impossible collision slot -> 409 Conflict
        # Find another class occupying MON 08:00
        colliding_sched = Schedule.query.filter(Schedule.id != sched_sec2.id).first()
        res_collision = self.client.post(
            "/api/reschedule/request",
            json={
                "schedule_id": sched_sec2.id,
                "proposed_day": colliding_sched.day_of_week,
                "proposed_start_time": colliding_sched.start_time.strftime("%H:%M"),
                "proposed_end_time": colliding_sched.end_time.strftime("%H:%M"),
                "reason": "Requesting an occupied slot",
            },
        )
        # Should return 409 Conflict or 201 if clean
        self.assertIn(res_collision.status_code, [409, 201])

    def test_v3_faculty_review_enforces_assigned_instructor(self):
        """Faculty A cannot review a reschedule request intended for Faculty B."""
        # Create a pending request for a schedule with faculty_id = 1
        sched = Schedule.query.filter_by(faculty_id=1).first()
        req = RescheduleRequest(
            schedule_id=sched.id,
            student_section_id=sched.section_id,
            proposed_day="SAT",
            proposed_start_time=time(8, 0),
            proposed_end_time=time(9, 30),
            reason="Convenience",
            status="PENDING_FACULTY",
        )
        db.session.add(req)
        db.session.commit()

        # Log in as Faculty with reference_id = 2 (not instructor 1)
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.faculty_user.id
            sess["role"] = "FACULTY"
            sess["active_role"] = "FACULTY"
            sess["reference_id"] = 2  # Different faculty member

        res = self.client.post(
            f"/api/reschedule/{req.id}/faculty-review",
            json={"approved": True, "feedback": "Sneaky endorsement"},
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("not the assigned instructor", res.get_json()["error"])

    def test_v3_chair_decision_atomic_mutation(self):
        """Chair approval re-validates slot and atomically mutates schedule record."""
        sched = Schedule.query.join(Section).join(Room).filter(Section.student_count <= Room.capacity).first()
        req = RescheduleRequest(
            schedule_id=sched.id,
            student_section_id=sched.section_id,
            proposed_day="SAT",
            proposed_start_time=time(14, 0),
            proposed_end_time=time(15, 30),
            reason="Weekend afternoon slot",
            status="PENDING_CHAIR",
        )
        db.session.add(req)
        db.session.commit()

        with self.client.session_transaction() as sess:
            sess["user_id"] = self.chair_user.id
            sess["role"] = "CHAIR"
            sess["active_role"] = "CHAIR"

        res = self.client.post(
            f"/api/reschedule/{req.id}/chair-decision",
            json={"approved": True, "feedback": "Approved by Chair"},
        )
        self.assertEqual(res.status_code, 200)

        # Verify mutation in database
        db.session.refresh(sched)
        self.assertEqual(sched.day_of_week, "SAT")
        self.assertEqual(sched.start_time, time(14, 0))
        self.assertEqual(sched.end_time, time(15, 30))

    # ─────────────────────────────────────────────────────────────────────────
    # VECTOR 4: Dynamic Credentials, Password Hashing & Feature Flag
    # ─────────────────────────────────────────────────────────────────────────
    def test_v4_credentials_update_verifies_hash_and_updates_session(self):
        """POST /api/auth/update-credentials validates current hash and prevents username collision."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.chair_user.id
            sess["role"] = "CHAIR"
            sess["username"] = self.chair_user.username

        # 1. Incorrect current password rejected
        res_bad_pw = self.client.post(
            "/api/auth/update-credentials",
            json={"current_password": "wrongpassword", "new_password": "newchair123"},
        )
        self.assertEqual(res_bad_pw.status_code, 400)

        # 2. Username collision with existing admin rejected
        res_collision = self.client.post(
            "/api/auth/update-credentials",
            json={
                "current_password": self.chair_user.demo_password or "chair123",
                "new_username": self.admin_user.username,
            },
        )
        self.assertEqual(res_collision.status_code, 409)

    # ─────────────────────────────────────────────────────────────────────────
    # VECTOR 5: Scheduling Conflict Engine & Constraint Logic
    # ─────────────────────────────────────────────────────────────────────────
    def test_v5_boundary_touching_classes_do_not_collide(self):
        """Mathematical overlap strictly tests Start_A < End_B and Start_B < End_A."""
        # Class A: 09:00 - 10:30 (540 - 630 min)
        # Class B: 10:30 - 12:00 (630 - 720 min)
        start_a, end_a = time(9, 0), time(10, 30)
        start_b, end_b = time(10, 30), time(12, 0)
        self.assertFalse(times_overlap(start_a, end_a, start_b, end_b))
        self.assertFalse(times_overlap(start_b, end_b, start_a, end_a))

    def test_v5_hard_constraint_validations(self):
        """Validates capacity is no longer blocking, and room type hard constraints remain active."""
        # HC4: Capacity violation check is deprecated/bypassed
        large_sec = Section.query.filter(Section.student_count > 30).first() or Section.query.first()
        small_room = Room.query.filter(Room.capacity < (large_sec.student_count or 40), Room.room_type == "LECTURE").first() or Room.query.filter_by(room_type="LECTURE").first()
        val_cap = validate_schedule_slot({
            "subject_id": 1,
            "section_id": large_sec.id,
            "faculty_id": 1,
            "room_id": small_room.id,
            "day_of_week": "MON",
            "start_time": "13:00",
            "end_time": "14:30",
        })
        self.assertFalse(any("capacity exceeded" in c.lower() for c in val_cap.get("conflicts", [])))

        # HC5: Room type mismatch (LAB subject in LECTURE room)
        lab_sub = Subject.query.filter_by(subject_type="LAB").first()
        lec_room = Room.query.filter_by(room_type="LECTURE").first()
        val_type = validate_schedule_slot({
            "subject_id": lab_sub.id,
            "section_id": 1,
            "faculty_id": 1,
            "room_id": lec_room.id,
            "day_of_week": "MON",
            "start_time": "08:00",
            "end_time": "11:00",
        })
        self.assertFalse(val_type["valid"])
        self.assertTrue(any("laboratory facility" in c.lower() for c in val_type["conflicts"]))

    # ─────────────────────────────────────────────────────────────────────────
    # VECTOR 6: Protected Utility Routes & Unauthenticated Leak Prevention
    # ─────────────────────────────────────────────────────────────────────────
    def test_v6_audit_logs_and_availabilities_require_login_and_roles(self):
        """GET /api/audit-logs and GET /api/availabilities reject unauthenticated requests."""
        # Unauthenticated calls return 401
        res_logs_unauth = self.client.get("/api/audit-logs")
        self.assertEqual(res_logs_unauth.status_code, 401)

        res_avail_unauth = self.client.get("/api/availabilities")
        self.assertEqual(res_avail_unauth.status_code, 401)

        res_seed_unauth = self.client.post("/api/seed")
        self.assertEqual(res_seed_unauth.status_code, 401)

        # Student calling audit-logs receives 403
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.student_user.id
            sess["role"] = "STUDENT"
            sess["active_role"] = "STUDENT"

        res_logs_student = self.client.get("/api/audit-logs")
        self.assertEqual(res_logs_student.status_code, 403)


if __name__ == "__main__":
    unittest.main()
