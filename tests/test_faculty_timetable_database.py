"""Opt-in MySQL/MariaDB integration test for the real faculty timetable flow.

Run with CAMPUSSHIELD_RUN_DB_TESTS=1 after starting the configured development
database. The test creates uniquely named temporary records and removes them.
"""

import os
import re
import secrets
import unittest
from unittest.mock import patch

import mysql.connector
from werkzeug.security import generate_password_hash

from backend import app as campus_app


@unittest.skipUnless(
    os.environ.get("CAMPUSSHIELD_RUN_DB_TESTS") == "1",
    "Set CAMPUSSHIELD_RUN_DB_TESTS=1 to run against the configured MySQL/MariaDB database.",
)
class FacultyTimetableDatabaseTest(unittest.TestCase):
    def test_login_authorization_assigned_and_empty_timetable(self):
        token = secrets.token_hex(6)
        test_password = secrets.token_urlsafe(24)
        email = f"timetable.test.{token}@campusshield.local"
        identifiers = {}
        db = campus_app.get_db()
        cursor = db.cursor()

        def insert(sql, values):
            cursor.execute(sql, values)
            return cursor.lastrowid

        try:
            campus_app.ensure_timetable_table(cursor)

            identifiers["college"] = insert(
                "INSERT INTO colleges (name, code) VALUES (%s, %s)",
                (f"DEV TEST CampusShield {token}", f"DEVTT{token}"),
            )
            identifiers["department"] = insert(
                "INSERT INTO departments (college_id, name, code) VALUES (%s, %s, %s)",
                (identifiers["college"], f"DEV TEST Department {token}", f"TT{token}"),
            )
            identifiers["course"] = insert(
                "INSERT INTO courses (college_id, department_id, name, code) VALUES (%s, %s, %s, %s)",
                (identifiers["college"], identifiers["department"], f"DEV TEST Course {token}", f"T{token}"),
            )
            identifiers["class"] = insert(
                """INSERT INTO classes
                   (college_id, course_id, academic_year, semester, year_level, division)
                   VALUES (%s, %s, '2026-2027', 1, 1, %s)""",
                (identifiers["college"], identifiers["course"], f"DEV-{token}"),
            )
            identifiers["subject"] = insert(
                """INSERT INTO subjects (college_id, course_id, name, code, semester)
                   VALUES (%s, %s, %s, %s, 1)""",
                (identifiers["college"], identifiers["course"], f"DEV TEST Subject {token}", f"SUB{token}"),
            )
            identifiers["user"] = insert(
                """INSERT INTO users
                   (college_id, full_name, name, email, password_hash, role, status, is_active)
                   VALUES (%s, %s, %s, %s, %s, 'faculty', 'active', TRUE)""",
                (
                    identifiers["college"], f"DEV TEST Faculty {token}",
                    f"DEV TEST Faculty {token}", email,
                    generate_password_hash(test_password),
                ),
            )
            for role in ("student", "admin"):
                identifiers[role] = insert(
                    """INSERT INTO users
                       (college_id, full_name, name, email, password_hash, role, status, is_active)
                       VALUES (%s, %s, %s, %s, %s, %s, 'active', TRUE)""",
                    (
                        identifiers["college"], f"DEV TEST {role.title()} {token}",
                        f"DEV TEST {role.title()} {token}",
                        f"timetable.{role}.{token}@campusshield.local",
                        generate_password_hash(test_password), role,
                    ),
                )
            identifiers["faculty"] = insert(
                "INSERT INTO faculty (user_id, department_id, employee_number, designation) VALUES (%s, %s, %s, %s)",
                (identifiers["user"], identifiers["department"], f"DEVTT{token}", "Development Test Faculty"),
            )
            identifiers["timetable"] = insert(
                """INSERT INTO class_timetable
                   (class_id, subject_id, faculty_id, day_of_week, start_time, end_time, room, created_by)
                   VALUES (%s, %s, %s, 'Tuesday', '10:00:00', '11:00:00', %s, %s)""",
                (
                    identifiers["class"], identifiers["subject"], identifiers["faculty"],
                    f"DEV TEST Room {token}", identifiers["user"],
                ),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            cursor.close()
            db.close()

        try:
            faculty_client = campus_app.app.test_client()
            login = faculty_client.post(
                "/api/login",
                json={
                    "loginType": "email",
                    "identifier": email,
                    "password": test_password,
                    "role": "faculty",
                },
                headers={"Origin": "http://localhost"},
            )
            self.assertEqual(login.status_code, 200, login.get_data(as_text=True))
            self.assertTrue(login.get_json()["success"])

            dashboard = faculty_client.get("/faculty-dashboard.html")
            self.assertEqual(dashboard.status_code, 200)
            self.assertIn(b"faculty-timetable.html", dashboard.data)

            timetable_page = faculty_client.get("/faculty-timetable.html")
            self.assertEqual(timetable_page.status_code, 200)
            self.assertIn(b"Loading timetable...", timetable_page.data)

            response = faculty_client.get("/api/faculty/timetable")
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
            entries = response.get_json()["timetable"]
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["day_of_week"], "Tuesday")
            self.assertEqual(entries[0]["subject_name"], f"DEV TEST Subject {token}")
            self.assertEqual(entries[0]["room"], f"DEV TEST Room {token}")

            for role in ("student", "admin"):
                client = campus_app.app.test_client()
                role_login = client.post(
                    "/api/login",
                    json={
                        "loginType": "email",
                        "identifier": f"timetable.{role}.{token}@campusshield.local",
                        "password": test_password,
                        "role": role,
                    },
                    headers={"Origin": "http://localhost"},
                )
                self.assertEqual(role_login.status_code, 200, role_login.get_data(as_text=True))
                denied = client.get("/api/faculty/timetable")
                self.assertEqual(denied.status_code, 403)
                if role == "student":
                    cyber_page = client.get("/Cyber-safety.html")
                    self.assertEqual(cyber_page.status_code, 200)
                    video_ids = re.findall(
                        rb'\{ id: "([A-Za-z0-9_-]{11})", title:',
                        cyber_page.data,
                    )
                    self.assertEqual(len(video_ids), 20)
                    self.assertEqual(len(set(video_ids)), 20)

            cleanup_db = campus_app.get_db()
            cleanup_cursor = cleanup_db.cursor()
            cleanup_cursor.execute(
                "DELETE FROM class_timetable WHERE id = %s",
                (identifiers["timetable"],),
            )
            cleanup_db.commit()
            cleanup_cursor.close()
            cleanup_db.close()

            empty = faculty_client.get("/api/faculty/timetable")
            self.assertEqual(empty.status_code, 200, empty.get_data(as_text=True))
            self.assertEqual(empty.get_json()["timetable"], [])
        finally:
            cleanup_db = campus_app.get_db()
            cleanup_cursor = cleanup_db.cursor()
            if "timetable" in identifiers:
                cleanup_cursor.execute("DELETE FROM class_timetable WHERE id = %s", (identifiers["timetable"],))
            if "faculty" in identifiers:
                cleanup_cursor.execute("DELETE FROM faculty WHERE id = %s", (identifiers["faculty"],))
            if "user" in identifiers:
                cleanup_cursor.execute("DELETE FROM users WHERE id = %s", (identifiers["user"],))
            for role in ("student", "admin"):
                if role in identifiers:
                    cleanup_cursor.execute("DELETE FROM users WHERE id = %s", (identifiers[role],))
            if "class" in identifiers:
                cleanup_cursor.execute("DELETE FROM classes WHERE id = %s", (identifiers["class"],))
            if "subject" in identifiers:
                cleanup_cursor.execute("DELETE FROM subjects WHERE id = %s", (identifiers["subject"],))
            if "course" in identifiers:
                cleanup_cursor.execute("DELETE FROM courses WHERE id = %s", (identifiers["course"],))
            if "department" in identifiers:
                cleanup_cursor.execute("DELETE FROM departments WHERE id = %s", (identifiers["department"],))
            if "college" in identifiers:
                cleanup_cursor.execute("DELETE FROM colleges WHERE id = %s", (identifiers["college"],))
            cleanup_db.commit()
            cleanup_cursor.close()
            cleanup_db.close()


class FacultyTimetableFailureTest(unittest.TestCase):
    def test_database_failure_returns_friendly_service_unavailable(self):
        client = campus_app.app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 1
            session["role"] = "faculty"

        callbacks = campus_app.app.before_request_funcs[None]
        original_callbacks = list(callbacks)
        callbacks[:] = [
            callback for callback in callbacks
            if callback is not campus_app.enforce_request_security
        ]
        try:
            with patch.object(
                campus_app,
                "get_db",
                side_effect=mysql.connector.Error("private database diagnostic"),
            ):
                response = client.get("/api/faculty/timetable")
        finally:
            callbacks[:] = original_callbacks

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.get_json()["message"],
            "Unable to load timetable. Please try again.",
        )
        self.assertNotIn(b"private database diagnostic", response.data)


if __name__ == "__main__":
    unittest.main()
