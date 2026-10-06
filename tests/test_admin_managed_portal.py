import unittest
from unittest.mock import patch

from flask import session

from backend import app as campus_app


def _account(user_id, role, name):
    return {
        "id": user_id,
        "role": role,
        "is_active": 1,
        "status": "active",
        "college_id": 7,
        "full_name": name,
        "email": f"{role}{user_id}@example.test",
        "mobile": "9000000000",
        "password_hash": "hashed-password",
        "updated_at": None,
        "college": "Test College",
    }


class _AccountCursor:
    def __init__(self, accounts):
        self.accounts = accounts
        self.row = None

    def execute(self, query, params=None):
        if query.startswith("SHOW COLUMNS"):
            self.row = ("column",)
        elif "FROM users u LEFT JOIN colleges c" in query:
            self.row = self.accounts.get(params[0])
        else:
            raise AssertionError(f"Unexpected SQL in test: {query}")

    def fetchone(self):
        row, self.row = self.row, None
        return row

    def close(self):
        pass


class _AccountDatabase:
    def __init__(self, accounts):
        self.cursor_instance = _AccountCursor(accounts)

    def cursor(self, **_kwargs):
        return self.cursor_instance

    def close(self):
        pass


class AdminManagedPortalTest(unittest.TestCase):
    def test_admin_can_open_and_return_from_selected_role_portal(self):
        accounts = {
            10: _account(10, "admin", "Admin User"),
            21: _account(21, "student", "Student User"),
        }

        with campus_app.app.test_request_context(
            "/api/admin/manage-user",
            method="POST",
            json={"user_id": 21, "role": "student"},
        ):
            session["user_id"] = 10
            session["role"] = "admin"
            with patch.object(campus_app, "get_db", return_value=_AccountDatabase(accounts)), \
                 patch.object(campus_app, "record_admin_management_action", return_value=True):
                response = campus_app.admin_manage_user()

            self.assertEqual(response.status_code, 200)
            self.assertEqual(session["user_id"], 21)
            self.assertEqual(session["role"], "student")
            self.assertEqual(session["admin_management"]["admin_user_id"], 10)

        with campus_app.app.test_request_context(
            "/api/admin/stop-managing",
            method="POST",
            json={},
        ):
            session["user_id"] = 21
            session["role"] = "student"
            session["admin_management"] = {
                "admin_user_id": 10,
                "admin_college_id": 7,
                "admin_account_updated_at": campus_app.account_session_version(accounts[10]),
                "target_user_id": 21,
                "target_role": "student",
            }
            with patch.object(campus_app, "get_db", return_value=_AccountDatabase(accounts)), \
                 patch.object(campus_app, "record_admin_management_action", return_value=True):
                response = campus_app.admin_stop_managing_user()

            self.assertEqual(response.status_code, 200)
            self.assertEqual(session["user_id"], 10)
            self.assertEqual(session["role"], "admin")
            self.assertNotIn("admin_management", session)

    def test_managed_portal_is_blocked_when_audit_cannot_be_written(self):
        with campus_app.app.test_request_context("/api/faculty/attendance", method="GET"):
            session["admin_management"] = {
                "admin_user_id": 10,
                "target_user_id": 21,
                "target_role": "faculty",
            }
            with patch.object(campus_app, "record_admin_management_action", return_value=False):
                response, status = campus_app.audit_admin_managed_api_access()

            self.assertEqual(status, 503)
            self.assertFalse(response.get_json()["success"])


if __name__ == "__main__":
    unittest.main()
