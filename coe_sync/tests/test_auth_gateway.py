"""COE SYNC 2026 - Authentication Gateway & Credentials Management Test Suite

Validates:
1. Default Program Chair seed credentials (chair_cpe / chair123)
2. Login Required decorator on page views (redirects unauthenticated users to /login)
3. Login API authentication & session initialization
4. Credentials Management (Change Username / Password workflow)
5. Re-authentication with updated credentials and rejection of revoked credentials
"""

import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import create_app
from seed_data import seed_database
from models import db, User, AuditLog


class TestAuthGatewayAndCredentials(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Initialize test app with testing config and fresh database."""
        cls.app = create_app("testing")
        cls.client = cls.app.test_client()

        with cls.app.app_context():
            seed_database(cls.app)

    def setUp(self):
        """Re-seed database before each test for clean isolation."""
        with self.app.app_context():
            seed_database(self.app)
        # Fresh test client for isolated sessions
        self.client = self.app.test_client()

    def test_01_default_chair_seed_credentials(self):
        """Test default Program Chair seed account credentials and fields."""
        with self.app.app_context():
            chair = User.query.filter_by(username="chair_cpe").first()
            self.assertIsNotNone(chair, "Program Chair account should exist in seed data.")
            self.assertEqual(chair.username, "chair_cpe")
            self.assertTrue(chair.check_password("chair123"), "Default password must be 'chair123'.")
            self.assertFalse(chair.must_change_credentials)
            self.assertTrue(chair.is_active_status)
            self.assertIsNotNone(chair.created_at)

    def test_02_login_required_guards_redirect_unauthenticated_views(self):
        """Test that page views redirect unauthenticated users to /login."""
        # Clean client without session
        for path in ["/", "/manage", "/schedules", "/reports"]:
            res = self.client.get(path, follow_redirects=False)
            self.assertIn(
                res.status_code,
                [302, 401],
                f"Unauthenticated request to {path} must be redirected or denied.",
            )
            if res.status_code == 302:
                self.assertTrue(
                    res.location.endswith("/login") or "/login" in res.location,
                    f"Redirect location for {path} must lead to /login, got {res.location}",
                )

        # Login page itself should render 200
        res_login = self.client.get("/login")
        self.assertEqual(res_login.status_code, 200)
        self.assertIn(b"COE SYNC 2026", res_login.data)
        self.assertIn(b"chair_cpe", res_login.data)

    def test_03_login_api_authentication(self):
        """Test POST /api/auth/login with valid, invalid, and missing credentials."""
        # 1. Missing fields -> 400
        res_empty = self.client.post("/api/auth/login", json={})
        self.assertEqual(res_empty.status_code, 400)

        # 2. Invalid password -> 401
        res_bad_pw = self.client.post(
            "/api/auth/login",
            json={"username": "chair_cpe", "password": "wrongpassword"},
        )
        self.assertEqual(res_bad_pw.status_code, 401)

        # 3. Successful login -> 200
        res_ok = self.client.post(
            "/api/auth/login",
            json={"username": "chair_cpe", "password": "chair123"},
        )
        self.assertEqual(res_ok.status_code, 200)
        data = res_ok.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["user"]["username"], "chair_cpe")
        self.assertEqual(data["user"]["role"], "CHAIR")

        # Now protected dashboard should render 200 with session active
        res_dash = self.client.get("/")
        self.assertEqual(res_dash.status_code, 200)

    def test_04_credentials_management_change_workflow(self):
        """Test changing username and password for Program Chair."""
        # Step 1: Login as Program Chair
        login_res = self.client.post(
            "/api/auth/login",
            json={"username": "chair_cpe", "password": "chair123"},
        )
        self.assertEqual(login_res.status_code, 200)

        # Step 2: Attempt change with incorrect current password -> 400
        bad_change = self.client.post(
            "/api/auth/change-credentials",
            json={
                "current_password": "incorrect_pw",
                "new_username": "chair_eng_lead",
                "new_password": "newSecurePassword2026",
            },
        )
        self.assertEqual(bad_change.status_code, 400)
        self.assertIn("Current password is incorrect", bad_change.get_json()["error"])

        # Step 3: Attempt change with too short new password -> 400
        short_change = self.client.post(
            "/api/auth/change-credentials",
            json={
                "current_password": "chair123",
                "new_username": "chair_eng_lead",
                "new_password": "123",
            },
        )
        self.assertEqual(short_change.status_code, 400)
        self.assertIn("at least 6 characters", short_change.get_json()["error"])

        # Step 4: Valid credential update
        valid_change = self.client.post(
            "/api/auth/change-credentials",
            json={
                "current_password": "chair123",
                "new_username": "chair_eng_lead",
                "new_password": "newSecurePassword2026",
            },
        )
        self.assertEqual(valid_change.status_code, 200)
        res_data = valid_change.get_json()
        self.assertEqual(res_data["status"], "success")
        self.assertEqual(res_data["user"]["username"], "chair_eng_lead")
        self.assertFalse(res_data["user"]["must_change_credentials"])

        # Step 5: Verify database state
        with self.app.app_context():
            updated_user = User.query.filter_by(username="chair_eng_lead").first()
            self.assertIsNotNone(updated_user)
            self.assertTrue(updated_user.check_password("newSecurePassword2026"))
            self.assertFalse(updated_user.check_password("chair123"))

            # Check audit log
            audit = AuditLog.query.filter_by(action="CREDENTIALS_CHANGED").first()
            self.assertIsNotNone(audit)
            self.assertIn("chair_eng_lead", audit.details)

        # Step 6: Verify old credentials are now rejected
        fresh_client = self.app.test_client()
        old_login = fresh_client.post(
            "/api/auth/login",
            json={"username": "chair_cpe", "password": "chair123"},
        )
        self.assertEqual(old_login.status_code, 401)

        # Step 7: Verify new credentials successfully authenticate
        new_login = self.client.post(
            "/api/auth/login",
            json={"username": "chair_eng_lead", "password": "newSecurePassword2026"},
        )
        self.assertEqual(new_login.status_code, 200)
        self.assertEqual(new_login.get_json()["user"]["username"], "chair_eng_lead")


if __name__ == "__main__":
    unittest.main()
