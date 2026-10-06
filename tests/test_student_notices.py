import unittest
from datetime import datetime
from unittest.mock import patch

from backend import app as campus_app


class NoticesCursor:
    def __init__(self, state):
        self.state = state
        self.result = None
        self.rows = []
        self.lastrowid = 41
        self.executed = []

    def execute(self, query, params=()):
        normalized = " ".join(query.lower().split())
        self.executed.append((normalized, params))
        self.result = None
        self.rows = []

        if "from faculty f" in normalized:
            self.result = {
                "faculty_id": 7,
                "user_id": 30,
                "college_id": 1,
            }
        elif "insert into notices" in normalized:
            self.state["insert"] = (normalized, params)
            college_id, title, description, publish_at, _created_by = params
            notice = make_notice(
                self.lastrowid,
                college_id,
                title,
                future=True,
            )
            notice["description"] = description
            notice["publish_at"] = publish_at.isoformat(sep=" ")
            notice["created_at"] = datetime.now().isoformat(sep=" ")
            self.state["notices"].append(notice)
        elif "inner join notices n" in normalized:
            user_id = params[0]
            student = self.state["students"].get(user_id)
            if student is None:
                return

            scoped = "n.college_id = u.college_id" in normalized
            immediate_faculty_notices = "notice_author.role = 'faculty'" in normalized
            for notice in self.state["notices"]:
                if scoped and notice["college_id"] != student["college_id"]:
                    continue
                if notice["audience"] not in ("all", "students"):
                    continue
                if notice["expired"]:
                    continue
                if notice["future"] and not (
                    immediate_faculty_notices and notice["author_role"] == "faculty"
                ):
                    continue
                self.rows.append({
                    key: notice[key]
                    for key in (
                        "id", "title", "description", "priority", "audience",
                        "publish_at", "expires_at", "attachment_url", "created_at"
                    )
                })
        elif "inner join events e" in normalized:
            self.rows = list(self.state["events"])

    def fetchone(self):
        result = self.result
        self.result = None
        return result

    def fetchall(self):
        rows = self.rows
        self.rows = []
        return rows

    def close(self):
        pass


class NoticesConnection:
    def __init__(self, state):
        self.state = state
        self.cursor_instance = NoticesCursor(state)

    def cursor(self, dictionary=True):
        return self.cursor_instance

    def commit(self):
        self.state["committed"] = True

    def rollback(self):
        pass

    def close(self):
        pass


def make_notice(notice_id, college_id, title, author_role="faculty", future=True):
    return {
        "id": notice_id,
        "college_id": college_id,
        "title": title,
        "description": "Notice details",
        "priority": "normal",
        "audience": "students",
        "publish_at": "2026-10-21T00:00:00",
        "expires_at": None,
        "attachment_url": None,
        "created_at": "2026-10-02T09:58:25",
        "author_role": author_role,
        "future": future,
        "expired": False,
    }


class StudentNoticesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_before_request = campus_app.app.before_request_funcs[None][:]
        campus_app.app.before_request_funcs[None] = [
            function
            for function in cls.original_before_request
            if function.__name__ != "enforce_request_security"
        ]

    @classmethod
    def tearDownClass(cls):
        campus_app.app.before_request_funcs[None] = cls.original_before_request

    def setUp(self):
        self.state = {
            "students": {
                10: {"college_id": 1},
                20: {"college_id": 2},
            },
            "notices": [
                make_notice(1, 1, "Internal Exam Schedule"),
                make_notice(2, 2, "Other College Notice"),
                make_notice(3, 1, "Scheduled Admin Notice", author_role="admin"),
            ],
            "events": [{
                "id": 50,
                "title": "Campus Tech Fest 2026",
                "description": "Existing event",
                "venue": "Main Hall",
                "start_datetime": datetime(2026, 10, 25, 10, 0),
                "end_datetime": datetime(2026, 10, 25, 16, 0),
                "created_at": datetime(2026, 10, 2, 9, 0),
            }],
            "insert": None,
            "committed": False,
        }
        self.connection = NoticesConnection(self.state)
        self.db_patch = patch.object(
            campus_app,
            "get_db",
            return_value=self.connection,
        )
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.client = campus_app.app.test_client()

    def set_session(self, user_id, role):
        with self.client.session_transaction() as session:
            session["user_id"] = user_id
            session["role"] = role

    def test_same_college_student_sees_faculty_notice_with_future_notice_date(self):
        self.set_session(10, "student")

        response = self.client.get("/api/student/notices")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [notice["title"] for notice in response.get_json()["notices"]],
            ["Internal Exam Schedule"],
        )
        query, params = self.connection.cursor_instance.executed[-1]
        self.assertIn("n.college_id = u.college_id", query)
        self.assertIn("where u.id = %s and u.role = 'student'", query)
        self.assertEqual(params, (10,))

    def test_same_college_faculty_publish_is_visible_to_student(self):
        self.set_session(30, "faculty")
        publish_response = self.client.post("/api/faculty/notices", json={
            "title": "Published During Test",
            "description": "Published now with a future notice date.",
            "publish_date": "2099-12-31",
        })
        self.assertEqual(publish_response.status_code, 201)

        self.set_session(10, "student")
        student_response = self.client.get("/api/student/notices")

        self.assertEqual(student_response.status_code, 200)
        self.assertIn(
            "Published During Test",
            [notice["title"] for notice in student_response.get_json()["notices"]],
        )

    def test_student_from_another_college_cannot_see_notice(self):
        self.set_session(20, "student")

        response = self.client.get("/api/student/notices")

        self.assertEqual(response.status_code, 200)
        titles = [notice["title"] for notice in response.get_json()["notices"]]
        self.assertNotIn("Internal Exam Schedule", titles)
        self.assertEqual(titles, ["Other College Notice"])

    def test_no_notices_returns_empty_list(self):
        self.set_session(10, "student")
        self.state["notices"] = []

        response = self.client.get("/api/student/notices")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["notices"], [])

    def test_unauthenticated_student_gets_json_401(self):
        response = self.client.get("/api/student/notices")

        self.assertEqual(response.status_code, 401)
        self.assertTrue(response.is_json)
        self.assertFalse(response.get_json()["success"])

    def test_non_student_role_gets_json_403(self):
        self.set_session(30, "faculty")

        response = self.client.get("/api/student/notices")

        self.assertEqual(response.status_code, 403)
        self.assertTrue(response.is_json)
        self.assertFalse(response.get_json()["success"])

    def test_database_failure_returns_json_500(self):
        self.set_session(10, "student")

        with patch.object(
            campus_app,
            "get_db",
            side_effect=campus_app.mysql.connector.Error("test database failure"),
        ):
            response = self.client.get("/api/student/notices")

        self.assertEqual(response.status_code, 500)
        self.assertTrue(response.is_json)
        self.assertFalse(response.get_json()["success"])

    def test_faculty_publish_uses_authenticated_college_and_succeeds(self):
        self.set_session(30, "faculty")

        response = self.client.post("/api/faculty/notices", json={
            "title": "New Exam Notice",
            "description": "Details",
            "publish_date": "2026-10-21",
        })

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.get_json()["success"])
        self.assertEqual(response.get_json()["message"], "Notice published successfully.")
        self.assertTrue(self.state["committed"])
        query, params = self.state["insert"]
        self.assertIn("(college_id, title, description, audience, publish_at, created_by)", query)
        self.assertEqual(params[0], 1)
        self.assertEqual(params[1], "New Exam Notice")
        self.assertEqual(params[4], 30)

    def test_student_events_response_remains_unchanged(self):
        self.set_session(10, "student")

        response = self.client.get("/api/student/events")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["events"][0]["title"],
            "Campus Tech Fest 2026",
        )


if __name__ == "__main__":
    unittest.main()
