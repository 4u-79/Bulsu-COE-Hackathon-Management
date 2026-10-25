"""COE SYNC 2026 - Comprehensive Tests for UI/UX Enhancements, Role Lockdown,
Dynamic Demo Credentials, and 1.5-Hour Split Solver
"""

import os
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
    FacultyAvailability,
    Schedule,
)
from services.conflict_detector import validate_split_schedule_pair
from services.scheduler import run_smart_scheduler


class TestEnhancementsAndFixes(unittest.TestCase):
    """Test suite covering the 4 critical bug fixes and functional enhancements."""

    def setUp(self):
        self.app = create_app("testing")
        self.app.config["SHOW_DEMO_CREDENTIALS"] = True
        self.client = self.app.test_client()

        with self.app.app_context():
            db.drop_all()
            db.create_all()

            # Seed base test accounts
            self.chair_user = User(
                username="chair_cpe",
                role="CHAIR",
                demo_password="chair123",
                must_change_credentials=False,
            )
            self.chair_user.set_password("chair123")

            self.admin_user = User(
                username="admin",
                role="ADMIN",
                demo_password="admin123",
                must_change_credentials=False,
            )
            self.admin_user.set_password("admin123")

            self.faculty_user = User(
                username="prof_santos",
                role="FACULTY",
                reference_id=1,
                demo_password="faculty123",
                must_change_credentials=False,
            )
            self.faculty_user.set_password("faculty123")

            self.student_user = User(
                username="student_cpe2a",
                role="STUDENT",
                reference_id=1,
                demo_password="student123",
                must_change_credentials=False,
            )
            self.student_user.set_password("student123")

            # Seed section
            self.section = Section(
                id=1,
                name="CpE 2A",
                program="BSCpE",
                year_level=2,
                student_count=40,
            )

            # Seed faculty
            self.faculty = Faculty(
                id=1,
                name="Prof. Juan Santos",
                email="santos@bulsu.edu.ph",
                max_units=21,
                current_units=0,
            )

            # Seed rooms
            self.room_lec = Room(
                id=1,
                room_code="COE-101",
                room_type="LECTURE",
                capacity=50,
                is_available=True,
            )
            self.room_lab = Room(
                id=2,
                room_code="LAB-201",
                room_type="LAB",
                capacity=45,
                is_available=True,
            )

            # Seed subjects: 3-unit lecture course with 1.5_HOUR_SPLIT
            self.sub_split = Subject(
                id=1,
                code="CPE 211",
                title="Data Structures and Algorithms",
                units=3,
                subject_type="LECTURE",
                hours_per_week=3,
                split_preference="1.5_HOUR_SPLIT",
            )
            # 3-unit course with 3_HOUR_BLOCK
            self.sub_block = Subject(
                id=2,
                code="CPE 222",
                title="Microprocessors Lab",
                units=3,
                subject_type="LAB",
                hours_per_week=3,
                split_preference="3_HOUR_BLOCK",
            )

            db.session.add_all([
                self.chair_user,
                self.admin_user,
                self.faculty_user,
                self.student_user,
                self.section,
                self.faculty,
                self.room_lec,
                self.room_lab,
                self.sub_split,
                self.sub_block,
            ])
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    # =========================================================================
    # 1. Role-Based Navigation & UI Lockdown Tests
    # =========================================================================
    def test_view_as_dropdown_hidden_and_forbidden_for_student_and_faculty(self):
        """Verify Student and Faculty cannot use /api/auth/impersonate and receive 403."""
        # 1. Faculty login
        res = self.client.post("/api/auth/login", json={"username": "prof_santos", "password": "faculty123"})
        self.assertEqual(res.status_code, 200)

        # Faculty attempts impersonation
        imp_res = self.client.post("/api/auth/impersonate", json={"role": "CHAIR"})
        self.assertEqual(imp_res.status_code, 403)
        self.assertIn("Access denied", imp_res.get_json()["error"])

        # Check rendered page omits #view-as-container
        sched_res = self.client.get("/schedules")
        self.assertEqual(sched_res.status_code, 200)
        self.assertNotIn('id="view-as-select"', sched_res.get_data(as_text=True))

        # Logout
        self.client.post("/api/auth/logout")

        # 2. Student login
        res = self.client.post("/api/auth/login", json={"username": "student_cpe2a", "password": "student123"})
        self.assertEqual(res.status_code, 200)

        # Student attempts impersonation
        imp_res = self.client.post("/api/auth/impersonate", json={"role": "ADMIN"})
        self.assertEqual(imp_res.status_code, 403)
        self.assertIn("Access denied", imp_res.get_json()["error"])

        # Check rendered page omits #view-as-container
        sched_res = self.client.get("/schedules")
        self.assertEqual(sched_res.status_code, 200)
        self.assertNotIn('id="view-as-select"', sched_res.get_data(as_text=True))

    def test_view_as_dropdown_rendered_and_allowed_for_chair(self):
        """Verify Chair can use /api/auth/impersonate and sees the View As control."""
        res = self.client.post("/api/auth/login", json={"username": "chair_cpe", "password": "chair123"})
        self.assertEqual(res.status_code, 200)

        # Check rendered page includes #view-as-select
        sched_res = self.client.get("/schedules")
        self.assertEqual(sched_res.status_code, 200)
        self.assertIn('id="view-as-select"', sched_res.get_data(as_text=True))

        # Impersonate faculty
        imp_res = self.client.post("/api/auth/impersonate", json={"role": "FACULTY", "reference_id": 1})
        self.assertEqual(imp_res.status_code, 200)
        self.assertEqual(imp_res.get_json()["active_role"], "FACULTY")

    def test_strict_student_redirect_and_sidebar_simplification(self):
        """Verify Student navigating to /, /manage, or /reports is redirected to /schedules."""
        self.client.post("/api/auth/login", json={"username": "student_cpe2a", "password": "student123"})

        # Navigation redirects
        for restricted_path in ["/", "/manage", "/reports"]:
            res = self.client.get(restricted_path, follow_redirects=False)
            self.assertEqual(res.status_code, 302, f"Expected redirect on {restricted_path}")
            self.assertIn("/schedules", res.headers.get("Location", ""))

        # Landing on /schedules succeeds
        res = self.client.get("/schedules")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        # Verify non-student items have .non-student class or are omitted
        self.assertIn("non-student", html)

    # =========================================================================
    # 2. Dynamic Demo Credentials, Password Update & Toggle Feature Flag Tests
    # =========================================================================
    def test_feature_flag_shows_or_hides_demo_credentials_badge(self):
        """Verify SHOW_DEMO_CREDENTIALS flag controls demo badge rendering on /login."""
        # When True
        res = self.client.get("/login")
        self.assertEqual(res.status_code, 200)
        self.assertIn('id="demo-credentials-badge"', res.get_data(as_text=True))

        # When False
        self.app.config["SHOW_DEMO_CREDENTIALS"] = False
        res = self.client.get("/login")
        self.assertEqual(res.status_code, 200)
        self.assertNotIn('id="demo-credentials-badge"', res.get_data(as_text=True))
        # Reset back to True
        self.app.config["SHOW_DEMO_CREDENTIALS"] = True

    def test_demo_credentials_endpoint_returns_live_db_values(self):
        """Verify GET /api/auth/demo-credentials returns current database accounts."""
        res = self.client.get("/api/auth/demo-credentials")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["show_demo_credentials"])
        self.assertEqual(data["chair"]["username"], "chair_cpe")
        self.assertEqual(data["chair"]["password"], "chair123")
        self.assertEqual(data["faculty"]["username"], "prof_santos")
        self.assertEqual(data["student"]["username"], "student_cpe2a")

    def test_credential_update_pipeline_syncs_with_db_and_invalidates_old(self):
        """Verify POST /api/auth/update-credentials updates DB, session, and demo endpoint."""
        # 1. Login as chair
        self.client.post("/api/auth/login", json={"username": "chair_cpe", "password": "chair123"})

        # 2. Update credentials to new username and password
        update_res = self.client.post(
            "/api/auth/update-credentials",
            json={
                "current_password": "chair123",
                "new_username": "chair_eng_lead",
                "new_password": "leadPassword2026",
            },
        )
        self.assertEqual(update_res.status_code, 200)

        # 3. Check demo-credentials endpoint immediately reflects updated info
        demo_res = self.client.get("/api/auth/demo-credentials")
        self.assertEqual(demo_res.status_code, 200)
        demo_data = demo_res.get_json()
        self.assertEqual(demo_data["chair"]["username"], "chair_eng_lead")
        self.assertEqual(demo_data["chair"]["password"], "leadPassword2026")

        # 4. Logout and verify old credentials are completely invalidated
        self.client.post("/api/auth/logout")

        old_login = self.client.post(
            "/api/auth/login",
            json={"username": "chair_cpe", "password": "chair123"},
        )
        self.assertEqual(old_login.status_code, 401)

        # 5. Login with new credentials succeeds
        new_login = self.client.post(
            "/api/auth/login",
            json={"username": "chair_eng_lead", "password": "leadPassword2026"},
        )
        self.assertEqual(new_login.status_code, 200)
        self.assertEqual(new_login.get_json()["user"]["username"], "chair_eng_lead")

    # =========================================================================
    # 3. Faculty 1.5-Hour Slot Split Preference & Solver Tests
    # =========================================================================
    def test_validate_split_schedule_pair_logic(self):
        """Verify validate_split_schedule_pair checks non-consecutive days, duration, and matching entities."""
        with self.app.app_context():
            slot1 = {
                "subject_id": 1,
                "section_id": 1,
                "faculty_id": 1,
                "room_id": 1,
                "day_of_week": "MON",
                "start_time": "09:00:00",
                "end_time": "10:30:00",
            }
            # Valid non-consecutive pair (MON & THU)
            slot2_valid = {
                "subject_id": 1,
                "section_id": 1,
                "faculty_id": 1,
                "room_id": 1,
                "day_of_week": "THU",
                "start_time": "09:00:00",
                "end_time": "10:30:00",
            }
            val_res = validate_split_schedule_pair(slot1, slot2_valid)
            self.assertTrue(val_res["valid"], f"Expected valid pair, got conflicts: {val_res['conflicts']}")

            # Invalid: Consecutive days (MON & TUE)
            slot2_consecutive = dict(slot2_valid, day_of_week="TUE")
            val_res2 = validate_split_schedule_pair(slot1, slot2_consecutive)
            self.assertFalse(val_res2["valid"])
            self.assertTrue(any("non-consecutive" in c for c in val_res2["conflicts"]))

            # Invalid: Mismatched rooms
            slot2_diff_room = dict(slot2_valid, room_id=2)
            val_res3 = validate_split_schedule_pair(slot1, slot2_diff_room)
            self.assertFalse(val_res3["valid"])
            self.assertTrue(any("same room" in c for c in val_res3["conflicts"]))

    def test_smart_scheduler_places_1_5_hour_split_on_non_consecutive_days(self):
        """Verify smart scheduler allocates two 1.5h sessions on non-consecutive days with same room/fac."""
        with self.app.app_context():
            config = {
                "program": "BSCpE",
                "year_level": 2,
                "section_ids": [1],
                "room_ids": [1, 2],
                "faculty_ids": [1],
                "preferences": {"minimize_gaps": True, "balance_workload": True, "optimize_utilization": True},
            }
            res = run_smart_scheduler(config, user_id=1)
            self.assertEqual(res["status"], "success")

            # Check generated schedules in DB
            schedules = Schedule.query.filter_by(section_id=1, subject_id=1).all()
            # 1.5_HOUR_SPLIT subject must generate exactly 2 half-session records
            self.assertEqual(len(schedules), 2, "Expected 2 split sessions for CPE 211")

            s1, s2 = schedules[0], schedules[1]
            self.assertEqual(s1.room_id, s2.room_id, "Both halves must share the same room")
            self.assertEqual(s1.faculty_id, s2.faculty_id, "Both halves must share the same faculty")
            self.assertEqual(s1.split_preference, "1.5_HOUR_SPLIT")
            self.assertEqual(s2.split_preference, "1.5_HOUR_SPLIT")

            # Verify non-consecutive days
            days = {s1.day_of_week, s2.day_of_week}
            valid_pairs = [{"MON", "THU"}, {"TUE", "FRI"}, {"WED", "SAT"}, {"MON", "FRI"}, {"TUE", "SAT"}]
            self.assertTrue(
                any(days == p for p in valid_pairs),
                f"Generated days {days} were not a recognized non-consecutive pair.",
            )

    # =========================================================================
    # 4. BulSU Building Campus Photo Replacement Tests
    # =========================================================================
    def test_bulsu_campus_photo_asset_and_template_markup(self):
        """Verify campus photo asset exists and is referenced in dashboard.html."""
        img_path = os.path.join(self.app.root_path, "static", "img", "bulsu_building.jpg")
        self.assertTrue(os.path.exists(img_path), f"Campus photo missing at {img_path}")
        self.assertGreater(os.path.getsize(img_path), 50000, "Image asset is too small or corrupt")

        # Login and render dashboard
        self.client.post("/api/auth/login", json={"username": "chair_cpe", "password": "chair123"})
        dash_res = self.client.get("/")
        self.assertEqual(dash_res.status_code, 200)
        html = dash_res.get_data(as_text=True)

        # Check markup
        self.assertIn("hero-banner-container", html)
        self.assertIn("bulsu_building.jpg", html)
        self.assertIn("Bulacan State University — College of Engineering", html)
        self.assertIn("COE SYNC Master Timetable &amp; Conflict Engine", html)

    # =========================================================================
    # 5. Role Redundancy, Chair Scoping & 2-Tier Approval Tests
    # =========================================================================
    def test_chair_and_prog_cha_role_equivalence_and_normalization(self):
        """Verify PROG_CHA and CHAIR normalize identically and provide full chair privileges."""
        with self.app.app_context():
            prog_cha_user = User(
                username="CHAIR-MVillena-Test",
                role="PROG_CHA",
                program="CPE",
                demo_password="password",
                must_change_credentials=False,
            )
            prog_cha_user.set_password("password")
            db.session.add(prog_cha_user)
            db.session.commit()

        # Login as PROG_CHA
        res = self.client.post("/api/auth/login", json={"username": "CHAIR-MVillena-Test", "password": "password"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["active_role"], "CHAIR")

        # Session profile /api/auth/me should return normalized CHAIR
        me_res = self.client.get("/api/auth/me")
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.get_json()["active_role"], "CHAIR")

    def test_program_chair_sections_scoped_strictly_to_department(self):
        """Verify Program Chair in /api/sections strictly receives only sections for their department."""
        with self.app.app_context():
            sec_cpe = Section(name="CPE - 2A", program="CPE", year_level=2, student_count=35)
            sec_ce = Section(name="CE - 2A", program="CE", year_level=2, student_count=35)
            sec_ee = Section(name="EE - 2A", program="EE", year_level=2, student_count=35)
            chair = User(
                username="chair_cpe_scoped",
                role="CHAIR",
                program="CPE",
                demo_password="password",
                must_change_credentials=False,
            )
            chair.set_password("password")
            db.session.add_all([sec_cpe, sec_ce, sec_ee, chair])
            db.session.commit()

        # Login as CPE Chair
        self.client.post("/api/auth/login", json={"username": "chair_cpe_scoped", "password": "password"})

        # Call /api/sections without program parameter
        res = self.client.get("/api/sections")
        self.assertEqual(res.status_code, 200)
        sections = res.get_json()["data"]
        self.assertTrue(len(sections) > 0)
        for s in sections:
            self.assertEqual(s["program"], "CPE", f"Chair received non-CPE section: {s}")

    def test_two_tier_reschedule_faculty_and_chair_approval_pipeline(self):
        """Verify student reschedule proposal flow: Student -> Faculty Endorse -> Chair Approve."""
        with self.app.app_context():
            cpe_sec = Section(name="CPE - 2A", program="CPE", year_level=2, student_count=30)
            fac = Faculty(name="Engr. Test Faculty", email="testfac@bulsu.edu.ph", program="CPE", max_units=21, current_units=15)
            subj = Subject(code="CPE 201", title="Logic Circuits", units=3, hours_per_week=3, subject_type="LECTURE", program="CPE", year_level=2, semester=1)
            room1 = Room(room_code="COE 101", room_type="LECTURE", capacity=40, building="COE 1", department="CPE")
            room2 = Room(room_code="COE 102", room_type="LECTURE", capacity=40, building="COE 1", department="CPE")
            db.session.add_all([cpe_sec, fac, subj, room1, room2])
            db.session.flush()

            sched = Schedule(
                section_id=cpe_sec.id,
                subject_id=subj.id,
                faculty_id=fac.id,
                room_id=room1.id,
                day_of_week="MON",
                start_time=time(8, 0),
                end_time=time(10, 0),
                status="PUBLISHED",
            )
            stu_user = User(username="student_cpe", role="STUDENT", program="CPE", reference_id=cpe_sec.id)
            stu_user.set_password("password")
            fac_user = User(username="faculty_cpe", role="FACULTY", program="CPE", reference_id=fac.id)
            fac_user.set_password("password")
            chair_user = User(username="chair_cpe_approver", role="CHAIR", program="CPE")
            chair_user.set_password("password")

            db.session.add_all([sched, stu_user, fac_user, chair_user])
            db.session.commit()
            sched_id = sched.id
            fac_id = fac.id

        # 1. Student submits reschedule proposal
        self.client.post("/api/auth/login", json={"username": "student_cpe", "password": "password"})
        req_res = self.client.post("/api/reschedule/request", json={
            "schedule_id": sched_id,
            "proposed_day": "WED",
            "proposed_start_time": "10:00",
            "proposed_end_time": "12:00",
            "reason": "Class consensus",
        })
        self.assertEqual(req_res.status_code, 201)
        req_id = req_res.get_json()["data"]["id"]
        self.assertEqual(req_res.get_json()["data"]["status"], "PENDING_FACULTY")

        # 2. Faculty logs in and endorses proposal
        self.client.post("/api/auth/login", json={"username": "faculty_cpe", "password": "password"})
        fac_rev = self.client.post(f"/api/reschedule/{req_id}/approve", json={"feedback": "Looks good to me"})
        self.assertEqual(fac_rev.status_code, 200)
        self.assertEqual(fac_rev.get_json()["data"]["status"], "PENDING_CHAIR")

        # 3. Chair logs in and sees proposal in pending requests
        self.client.post("/api/auth/login", json={"username": "chair_cpe_approver", "password": "password"})
        chair_list = self.client.get("/api/reschedule/requests?status=PENDING_CHAIR")
        self.assertEqual(chair_list.status_code, 200)
        items = chair_list.get_json()["data"]
        self.assertTrue(any(r["id"] == req_id for r in items), "Chair must see PENDING_CHAIR request")

        # 4. Chair authorizes and updates timetable
        chair_dec = self.client.post(f"/api/reschedule/{req_id}/approve", json={"feedback": "Approved by Chair"})
        self.assertEqual(chair_dec.status_code, 200)
        self.assertEqual(chair_dec.get_json()["data"]["status"], "APPROVED")

        # Verify timetable updated in DB
        with self.app.app_context():
            updated_sched = db.session.get(Schedule, sched_id)
            self.assertEqual(updated_sched.day_of_week, "WED")
            self.assertEqual(updated_sched.start_time, time(10, 0))
            self.assertEqual(updated_sched.end_time, time(12, 0))


if __name__ == "__main__":
    unittest.main()
