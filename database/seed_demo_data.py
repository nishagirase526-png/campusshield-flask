"""Idempotent, reversible demo-data seed for the existing CampusShield DB.

Run from the project root with CAMPUSSHIELD_DEMO_PASSWORD set, then pass
--apply. Use --remove to remove only rows marked with this seed's identifiers.
The script uses the configured application database connection and does not
create or alter any tables.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from werkzeug.security import generate_password_hash  # noqa: E402

from backend.app import get_db, valid_email  # noqa: E402


COLLEGE_CODE = "DEMO001"
DEMO_EMAIL_SUFFIX = "@campusshield.test"
STUDENT_EMAILS = [f"demo-student-{i:02d}{DEMO_EMAIL_SUFFIX}" for i in range(1, 8)]
FACULTY_EMAILS = [f"demo-faculty-{i:02d}{DEMO_EMAIL_SUFFIX}" for i in range(1, 9)]
STUDENT_NAMES = [
    "Aarav Deshmukh", "Anaya Kulkarni", "Ishaan Patil", "Meera Joshi",
    "Kabir Shah", "Riya More", "Advait Pawar",
]
FACULTY_NAMES = [
    "Dr Neha Kulkarni", "Prof Rahul Patil", "Prof Isha Naik",
    "Prof Kunal Deshmukh", "Prof Amruta Shah", "Prof Nikhil Joshi",
    "Prof Sagar Pawar", "Prof Rutuja More",
]

SUBJECTS = [
    ("Cloud Computing Fundamentals", "CSD501"),
    ("Data Analytics Essentials", "CSD502"),
    ("Secure Software Development", "CSD503"),
    ("Mobile Application Development", "CSD504"),
    ("IT Project Management", "CSD505"),
]

RESOURCE_DATA = [
    ("Java Language Learning Path", "Official Java learning guides and tutorials.", "https://dev.java/learn/", "Official tutorial"),
    ("Python Tutorial", "The official Python tutorial for core language concepts.", "https://docs.python.org/3/tutorial/", "Official documentation"),
    ("MDN HTML Learning Guide", "A structured guide to building accessible web pages with HTML.", "https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/Structuring_content", "Learning guide"),
    ("MDN CSS Learning Guide", "Practical lessons on styling responsive web interfaces.", "https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/Styling_basics", "Learning guide"),
    ("MySQL Reference Manual", "Official reference for relational database design and SQL usage.", "https://dev.mysql.com/doc/", "Official documentation"),
    ("Pro Git Book", "A free book covering Git fundamentals and collaborative workflows.", "https://git-scm.com/book/en/v2", "Online book"),
    ("OWASP Top 10", "A widely used awareness resource on common web application risks.", "https://owasp.org/www-project-top-ten/", "Security guide"),
    ("CISA Secure Our World", "Practical guidance on passwords, MFA, phishing, and software updates.", "https://www.cisa.gov/secure-our-world", "Cyber safety guide"),
    ("NIST Digital Identity Guidelines", "The official NIST guidance for digital identity and authentication.", "https://pages.nist.gov/800-63-4/", "Official standard"),
]

NOTICE_DATA = [
    ("BCA Practical Lab Schedule", "Review the current practical-lab timetable in your student portal and arrive with your lab record.", "high", "students"),
    ("Library Database Workshop", "The library team will demonstrate academic database search, citation, and source-evaluation techniques.", "normal", "all"),
    ("Student Identity Card Renewal", "Students who need an identity-card correction or replacement should contact the college office during working hours.", "normal", "students"),
    ("Internal Assessment Preparation", "Check subject-wise assessment instructions shared by faculty and contact the department for clarification.", "high", "students"),
    ("Campus Network Maintenance Window", "Routine network maintenance is planned outside teaching hours; save work before the announced window.", "normal", "all"),
    ("Cyber Safety Awareness Reminder", "Use multi-factor authentication where available and report suspicious links through the campus safety channel.", "high", "all"),
    ("Faculty Office Hours", "Faculty members should keep their current consultation availability updated for student queries.", "normal", "faculty"),
    ("Internship Orientation Session", "Students interested in internships can attend the orientation for guidance on applications and professional conduct.", "normal", "students"),
    ("Examination Hall Guidance", "Please follow the instructions issued with your examination timetable and bring the required college identity card.", "urgent", "students"),
]

EVENT_DATA = [
    ("BCA Student Project Showcase", "Student teams present working prototypes and explain their design choices.", "Seminar Hall", datetime(2026, 11, 14, 10, 0), datetime(2026, 11, 14, 15, 0)),
    ("Cyber Hygiene Awareness Session", "A practical session on phishing, account security, privacy, and incident reporting.", "Computer Lab 2", datetime(2026, 10, 17, 11, 0), datetime(2026, 10, 17, 12, 30)),
    ("Open Source Contribution Clinic", "Faculty mentors introduce version control, issue tracking, and responsible contributions.", "Computer Lab 1", datetime(2026, 10, 24, 10, 0), datetime(2026, 10, 24, 13, 0)),
    ("Data Structures Problem-Solving Workshop", "Guided practice with common data-structure problems and complexity discussion.", "Room B-204", datetime(2026, 10, 20, 14, 0), datetime(2026, 10, 20, 16, 0)),
    ("Web Accessibility Review", "Students review a sample interface using accessibility and usability principles.", "Design Studio", datetime(2026, 10, 29, 12, 0), datetime(2026, 10, 29, 14, 0)),
    ("Cloud Computing Fundamentals Talk", "An introductory talk on cloud service models and responsible cloud use.", "Seminar Hall", datetime(2026, 11, 7, 11, 0), datetime(2026, 11, 7, 12, 30)),
    ("Career Readiness and CV Clinic", "A guided review of CV structure, interview preparation, and professional communication.", "Placement Room", datetime(2026, 11, 21, 10, 0), datetime(2026, 11, 21, 13, 0)),
    ("Mobile App Design Review", "Teams share early mobile-app prototypes and receive peer and faculty feedback.", "Computer Lab 3", datetime(2026, 11, 26, 13, 0), datetime(2026, 11, 26, 15, 0)),
    ("Responsible Digital Citizenship Forum", "An open discussion on privacy, respectful communication, and reporting online harm.", "Auditorium", datetime(2026, 12, 5, 10, 30), datetime(2026, 12, 5, 12, 0)),
]

INCIDENT_DATA = [
    ("phishing", "Demo: Suspicious scholarship email", "A sample message requests a password after promising an unverified scholarship. No credentials were entered.", "under_review", "medium"),
    ("fake_account", "Demo: Impersonation profile reported", "A fictional student reports a social profile using a similar display name and copied campus imagery.", "submitted", "medium"),
    ("online_fraud", "Demo: Unverified event payment request", "A message requests payment to a personal account for a campus event; the sender has not been confirmed.", "investigating", "high"),
    ("suspicious_link", "Demo: Shortened link in group message", "A shortened URL was shared in a class group without a clear destination or trusted source.", "under_review", "medium"),
    ("cyberbullying", "Demo: Repeated unwanted messages", "A fictional report describes repeated hostile messages in a student discussion group.", "submitted", "high"),
    ("password_compromise", "Demo: Password reuse alert", "A student suspects a reused password may have been exposed and has started changing affected credentials.", "resolved", "medium"),
    ("suspicious_message", "Demo: Unexpected account verification request", "An unsolicited message asks the recipient to share a one-time verification code.", "submitted", "high"),
    ("malware", "Demo: Unexpected attachment warning", "A downloaded archive from an unknown sender triggered a device security warning and was not opened.", "closed", "low"),
]

REQUEST_DATA = [
    ("CampusShield Demo Partner College 01", "Nashik", "Demo Contact 01", f"contact01{DEMO_EMAIL_SUFFIX}"),
    ("CampusShield Demo Partner College 02", "Pune", "Demo Contact 02", f"contact02{DEMO_EMAIL_SUFFIX}"),
    ("CampusShield Demo Partner College 03", "Mumbai", "Demo Contact 03", f"contact03{DEMO_EMAIL_SUFFIX}"),
    ("CampusShield Demo Partner College 04", "Nagpur", "Demo Contact 04", f"contact04{DEMO_EMAIL_SUFFIX}"),
    ("CampusShield Demo Partner College 05", "Kolhapur", "Demo Contact 05", f"contact05{DEMO_EMAIL_SUFFIX}"),
    ("CampusShield Demo Partner College 06", "Aurangabad", "Demo Contact 06", f"contact06{DEMO_EMAIL_SUFFIX}"),
    ("CampusShield Demo Partner College 07", "Amravati", "Demo Contact 07", f"contact07{DEMO_EMAIL_SUFFIX}"),
    ("CampusShield Demo Partner College 08", "Satara", "Demo Contact 08", f"contact08{DEMO_EMAIL_SUFFIX}"),
    ("CampusShield Demo Partner College 09", "Jalgaon", "Demo Contact 09", f"contact09{DEMO_EMAIL_SUFFIX}"),
]


def one(cursor, sql, params=()):
    cursor.execute(sql, params)
    return cursor.fetchone()


def all_rows(cursor, sql, params=()):
    cursor.execute(sql, params)
    return cursor.fetchall()


def ensure_user(cursor, college_id, college_name, name, email, password_hash, role):
    if not valid_email(email):
        raise RuntimeError(f"Invalid demo email address: {email}")
    row = one(cursor, "SELECT id, college_id, role FROM users WHERE email = %s", (email,))
    if row:
        if row["college_id"] != college_id or row["role"] != role:
            raise RuntimeError(f"Demo email already belongs to a different account: {email}")
        return row["id"], False
    cursor.execute(
        """INSERT INTO users
            (college_id, college, name, full_name, email, password_hash, role,
             status, is_active, must_set_password)
           VALUES (%s, %s, %s, %s, %s, %s, %s, 'active', 1, 0)""",
        (college_id, college_name, name, name, email, password_hash, role),
    )
    return cursor.lastrowid, True


def ensure_student_profile(cursor, user_id, class_id, roll_number):
    row = one(cursor, "SELECT id FROM students WHERE user_id = %s", (user_id,))
    if row:
        return row["id"], False
    if one(cursor, "SELECT id FROM students WHERE class_id = %s AND roll_number = %s", (class_id, roll_number)):
        raise RuntimeError(f"Student roll number already exists: {roll_number}")
    cursor.execute(
        "INSERT INTO students (user_id, class_id, roll_number) VALUES (%s, %s, %s)",
        (user_id, class_id, roll_number),
    )
    return cursor.lastrowid, True


def ensure_faculty_profile(cursor, user_id, department_id, employee_number, designation="Lecturer"):
    row = one(cursor, "SELECT id FROM faculty WHERE user_id = %s", (user_id,))
    if row:
        return row["id"], False
    if one(cursor, "SELECT id FROM faculty WHERE employee_number = %s", (employee_number,)):
        raise RuntimeError(f"Faculty employee number already exists: {employee_number}")
    cursor.execute(
        """INSERT INTO faculty (user_id, department_id, employee_number, designation, joining_date)
           VALUES (%s, %s, %s, %s, %s)""",
        (user_id, department_id, employee_number, designation, date(2025, 6, 1)),
    )
    return cursor.lastrowid, True


def current_context(cursor):
    college = one(cursor, "SELECT id, name FROM colleges WHERE code = %s", (COLLEGE_CODE,))
    if not college:
        raise RuntimeError("The existing DEMO001 college record was not found; no data was changed.")
    department = one(cursor, "SELECT id FROM departments WHERE college_id = %s AND code = 'BCA'", (college["id"],))
    course = one(cursor, "SELECT id FROM courses WHERE college_id = %s AND code = 'BCA'", (college["id"],))
    if not department or not course:
        raise RuntimeError("Existing BCA department/course was not found; no data was changed.")
    class_row = one(
        cursor,
        """SELECT id FROM classes WHERE college_id = %s AND course_id = %s
           AND academic_year = '2026-2027' AND semester = 5
           AND year_level = 3 AND division = 'A' LIMIT 1""",
        (college["id"], course["id"]),
    )
    if not class_row:
        raise RuntimeError("Existing BCA 2026-2027 Semester 5, Year 3, Division A class was not found; no data was changed.")
    admin = one(
        cursor,
        "SELECT id FROM users WHERE college_id = %s AND role = 'admin' AND is_active = 1 AND status = 'active' ORDER BY id LIMIT 1",
        (college["id"],),
    )
    if not admin:
        raise RuntimeError("No active admin account exists for the demo college; no data was changed.")
    return college["id"], college["name"], department["id"], course["id"], class_row["id"], admin["id"]


def seed(cursor, password):
    college_id, college_name, department_id, course_id, class_id, admin_id = current_context(cursor)
    password_hash = generate_password_hash(password)
    counts = {}

    # Complete only missing profiles for existing college student accounts.
    existing_students = all_rows(
        cursor,
        """SELECT u.id FROM users u LEFT JOIN students s ON s.user_id = u.id
           WHERE u.college_id = %s AND u.role = 'student' AND s.id IS NULL
           ORDER BY u.id""",
        (college_id,),
    )
    profile_count = one(
        cursor,
        "SELECT COUNT(*) AS n FROM students s JOIN users u ON u.id = s.user_id WHERE u.college_id = %s AND u.role = 'student'",
        (college_id,),
    )["n"]
    for index, row in enumerate(existing_students, start=1):
        if profile_count >= 10:
            break
        _, created = ensure_student_profile(cursor, row["id"], class_id, f"CSD-LEGACY-{index:02d}")
        profile_count += int(created)
        counts["student_profiles_linked"] = counts.get("student_profiles_linked", 0) + int(created)

    demo_student_ids = []
    for index, email in enumerate(STUDENT_EMAILS, start=1):
        profile_count = one(
            cursor,
            "SELECT COUNT(*) AS n FROM students s JOIN users u ON u.id = s.user_id WHERE u.college_id = %s AND u.role = 'student'",
            (college_id,),
        )["n"]
        if profile_count >= 10:
            break
        user_id, created_user = ensure_user(
            cursor, college_id, college_name, STUDENT_NAMES[index - 1], email,
            password_hash, "student",
        )
        counts["student_accounts_added"] = counts.get("student_accounts_added", 0) + int(created_user)
        student_id, created_profile = ensure_student_profile(
            cursor, user_id, class_id, f"CSD-DEMO-{index:03d}",
        )
        counts["student_profiles_added"] = counts.get("student_profiles_added", 0) + int(created_profile)
        demo_student_ids.append(student_id)

    # Repair only the one existing faculty account that has no faculty profile.
    orphan_faculty = one(
        cursor,
        """SELECT u.id FROM users u LEFT JOIN faculty f ON f.user_id = u.id
           WHERE u.college_id = %s AND u.role = 'faculty' AND u.is_active = 1
             AND f.id IS NULL ORDER BY u.id LIMIT 1""",
        (college_id,),
    )
    if orphan_faculty:
        _, created = ensure_faculty_profile(
            cursor, orphan_faculty["id"], department_id, "CSD-LEGACY-FAC-01",
        )
        counts["faculty_profiles_linked"] = int(created)

    for index, email in enumerate(FACULTY_EMAILS, start=1):
        profile_count = one(
            cursor,
            "SELECT COUNT(*) AS n FROM faculty f JOIN users u ON u.id = f.user_id WHERE u.college_id = %s AND u.role = 'faculty'",
            (college_id,),
        )["n"]
        if profile_count >= 10:
            break
        user_id, created_user = ensure_user(
            cursor, college_id, college_name, FACULTY_NAMES[index - 1], email,
            password_hash, "faculty",
        )
        counts["faculty_accounts_added"] = counts.get("faculty_accounts_added", 0) + int(created_user)
        _, created_profile = ensure_faculty_profile(
            cursor, user_id, department_id, f"CSD-DEMO-FAC-{index:02d}",
            "Faculty Member",
        )
        counts["faculty_profiles_added"] = counts.get("faculty_profiles_added", 0) + int(created_profile)

    student_ids = all_rows(
        cursor,
        """SELECT s.id, s.user_id, s.roll_number, u.email FROM students s
           JOIN users u ON u.id = s.user_id
           WHERE u.college_id = %s AND u.role = 'student' AND s.class_id = %s
           ORDER BY s.id""",
        (college_id, class_id),
    )
    if len(student_ids) < 10:
        raise RuntimeError("Could not prepare ten valid student profiles for the selected class.")
    demo_student_ids = [row["id"] for row in student_ids if row["roll_number"].startswith("CSD-")]

    faculty_rows = all_rows(
        cursor,
        """SELECT f.id, f.user_id, u.email, f.employee_number
           FROM faculty f JOIN users u ON u.id = f.user_id
           WHERE u.college_id = %s AND u.role = 'faculty' AND u.is_active = 1
           ORDER BY f.id""",
        (college_id,),
    )
    if len(faculty_rows) < 10:
        raise RuntimeError("Could not prepare ten valid faculty profiles for the demo college.")
    demo_faculty_rows = [row for row in faculty_rows if row["email"] in FACULTY_EMAILS]
    faculty_by_id = {row["id"]: row for row in faculty_rows}
    new_faculty_ids = [row["id"] for row in demo_faculty_rows]
    legacy_faculty = next((row for row in faculty_rows if row["employee_number"] == "CSD-LEGACY-FAC-01"), None)

    # Add five semester-aligned BCA subjects and assignments without duplicating existing rows.
    subject_by_code = {}
    for name, code in SUBJECTS:
        row = one(cursor, "SELECT id, name FROM subjects WHERE course_id = %s AND code = %s AND semester = 5", (course_id, code))
        if row:
            if row["name"] != name:
                raise RuntimeError(f"Subject code {code} is already used for different content.")
            subject_id = row["id"]
        else:
            cursor.execute(
                "INSERT INTO subjects (college_id, course_id, name, code, semester) VALUES (%s, %s, %s, %s, 5)",
                (college_id, course_id, name, code),
            )
            subject_id = cursor.lastrowid
            counts["subjects_added"] = counts.get("subjects_added", 0) + 1
        subject_by_code[code] = subject_id

    existing_cs = all_rows(
        cursor,
        """SELECT cs.id, cs.subject_id, cs.faculty_id, s.code
           FROM class_subjects cs JOIN subjects s ON s.id = cs.subject_id
           WHERE cs.class_id = %s AND s.college_id = %s
             AND s.course_id = %s AND s.semester = 5 ORDER BY s.id""",
        (class_id, college_id, course_id),
    )
    if len(existing_cs) < 5:
        raise RuntimeError("The existing BCA class is missing expected subject assignments; stopping instead of guessing.")
    new_null_assignments = iter(new_faculty_ids)
    class_subjects_by_subject = {}
    for row in existing_cs:
        faculty_id = row["faculty_id"]
        if faculty_id is None:
            faculty_id = next(new_null_assignments, None)
            if faculty_id is not None:
                cursor.execute(
                    "UPDATE class_subjects SET faculty_id = %s WHERE id = %s AND faculty_id IS NULL",
                    (faculty_id, row["id"]),
                )
                counts["previously_unassigned_class_subjects_linked"] = counts.get("previously_unassigned_class_subjects_linked", 0) + cursor.rowcount
        class_subjects_by_subject[row["subject_id"]] = {
            "id": row["id"], "subject_id": row["subject_id"],
            "code": row["code"], "faculty_id": faculty_id,
        }

    new_subject_faculties = [legacy_faculty["id"] if legacy_faculty else new_faculty_ids[3], *new_faculty_ids[3:7]]
    for index, (name, code) in enumerate(SUBJECTS):
        subject_id = subject_by_code[code]
        row = one(cursor, "SELECT id, faculty_id FROM class_subjects WHERE class_id = %s AND subject_id = %s", (class_id, subject_id))
        if row:
            class_subject_id = row["id"]
            faculty_id = row["faculty_id"]
        else:
            faculty_id = new_subject_faculties[index]
            cursor.execute(
                "INSERT INTO class_subjects (class_id, subject_id, faculty_id) VALUES (%s, %s, %s)",
                (class_id, subject_id, faculty_id),
            )
            class_subject_id = cursor.lastrowid
            counts["class_subjects_added"] = counts.get("class_subjects_added", 0) + 1
        class_subjects_by_subject[subject_id] = {
            "id": class_subject_id, "subject_id": subject_id,
            "code": code, "faculty_id": faculty_id,
        }

    class_subjects = list(class_subjects_by_subject.values())
    class_subjects.sort(key=lambda item: item["subject_id"])
    if len(class_subjects) < 10:
        raise RuntimeError("Ten class-subject assignments could not be prepared.")

    # Ten non-overlapping, shared student/faculty timetable rows.
    slots = [
        ("Monday", time(9, 0), time(9, 50), "Demo Room A-201"),
        ("Monday", time(10, 0), time(10, 50), "Demo Room A-201"),
        ("Tuesday", time(9, 0), time(9, 50), "Demo Lab C-101"),
        ("Tuesday", time(10, 0), time(10, 50), "Demo Room A-202"),
        ("Wednesday", time(9, 0), time(9, 50), "Demo Room A-203"),
        ("Wednesday", time(10, 0), time(10, 50), "Demo Lab C-102"),
        ("Thursday", time(9, 0), time(9, 50), "Demo Room A-204"),
        ("Thursday", time(10, 0), time(10, 50), "Demo Lab C-103"),
        ("Friday", time(9, 0), time(9, 50), "Demo Room A-205"),
        ("Friday", time(10, 0), time(10, 50), "Demo Room A-206"),
    ]
    for item, (day, start, end, room) in zip(class_subjects[:10], slots):
        existing = one(
            cursor,
            "SELECT id FROM class_timetable WHERE class_id = %s AND subject_id = %s AND room LIKE 'Demo %' LIMIT 1",
            (class_id, item["subject_id"]),
        )
        if existing:
            continue
        cursor.execute(
            """INSERT INTO class_timetable
               (class_id, subject_id, faculty_id, day_of_week, start_time, end_time, room, created_by)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (class_id, item["subject_id"], item["faculty_id"], day, start, end, room, admin_id),
        )
        counts["timetable_rows_added"] = counts.get("timetable_rows_added", 0) + 1

    # Attendance for each of the nine newly completed demo profiles.
    if demo_student_ids:
        marker_faculty_user = demo_faculty_rows[0]["user_id"]
        demo_profiles = all_rows(
            cursor,
            """SELECT s.id, s.user_id FROM students s JOIN users u ON u.id = s.user_id
               WHERE u.college_id = %s AND u.role = 'student'
                 AND (u.email LIKE 'demo-student-%@campusshield.test'
                      OR s.roll_number LIKE 'CSD-LEGACY-%')
               ORDER BY s.id""",
            (college_id,),
        )
        for index, profile in enumerate(demo_profiles):
            cs_item = class_subjects[index % len(class_subjects)]
            attended_on = date(2026, 9, 14) + timedelta(days=index)
            if one(
                cursor,
                "SELECT id FROM attendance WHERE student_id = %s AND class_subject_id = %s AND attendance_date = %s AND marked_by = %s",
                (profile["id"], cs_item["id"], attended_on, marker_faculty_user),
            ):
                continue
            status = ("present", "present", "late", "present", "absent")[index % 5]
            cursor.execute(
                """INSERT INTO attendance (student_id, class_subject_id, attendance_date, status, marked_by)
                   VALUES (%s, %s, %s, %s, %s)""",
                (profile["id"], cs_item["id"], attended_on, status, marker_faculty_user),
            )
            counts["attendance_rows_added"] = counts.get("attendance_rows_added", 0) + 1

    # A few representative assessment marks; existing records are retained.
    class_marks = one(
        cursor,
        """SELECT COUNT(*) AS n FROM marks m JOIN students s ON s.id = m.student_id
           WHERE s.class_id = %s""",
        (class_id,),
    )["n"]
    mark_rows = [
        (0, "JAVA", 18, 20), (1, "FDS", 17, 20),
        (2, "FAI", 19, 20), (3, "WEB", 16, 20),
    ]
    for index, (student_index, code, obtained, maximum) in enumerate(mark_rows):
        if class_marks + counts.get("marks_added", 0) >= 10:
            break
        subject_id = subject_by_code.get(code)
        if subject_id is None:
            subject_id = one(cursor, "SELECT id FROM subjects WHERE course_id = %s AND code = %s AND semester = 5", (course_id, code))["id"]
        student_id = demo_profiles[student_index]["id"] if student_index < len(demo_profiles) else demo_student_ids[student_index]
        teacher = next((item for item in class_subjects if item["subject_id"] == subject_id), None)
        entered_by = faculty_by_id[teacher["faculty_id"]]["user_id"] if teacher and teacher["faculty_id"] in faculty_by_id else admin_id
        exam_type = f"DEMO: Internal Assessment {index + 1}"
        if one(cursor, "SELECT id FROM marks WHERE student_id = %s AND subject_id = %s AND exam_type = %s", (student_id, subject_id, exam_type)):
            continue
        cursor.execute(
            "INSERT INTO marks (student_id, subject_id, exam_type, marks_obtained, max_marks, entered_by) VALUES (%s, %s, %s, %s, %s, %s)",
            (student_id, subject_id, exam_type, obtained, maximum, entered_by),
        )
        counts["marks_added"] = counts.get("marks_added", 0) + 1

    # Add assignments only up to ten for this existing class.
    assignment_total = one(
        cursor,
        "SELECT COUNT(*) AS n FROM assignments a JOIN class_subjects cs ON cs.id = a.class_subject_id WHERE cs.class_id = %s",
        (class_id,),
    )["n"]
    assignment_data = [
        ("Java Collections Practice", "Implement a small collection-based task and explain the choice of data structure."),
        ("Data Structures Complexity Review", "Compare the time complexity of the selected search and sort operations."),
        ("AI Ethics Case Study", "Summarize a campus-relevant AI use case and identify privacy and fairness considerations."),
        ("Responsive Web Interface", "Build and document a responsive interface using semantic HTML and CSS."),
        ("Cyber Safety Reflection", "Describe safe handling of a suspicious campus email and the correct reporting steps."),
        ("Cloud Architecture Diagram", "Prepare a simple architecture diagram and explain the responsibility boundaries."),
        ("Data Analytics Mini Report", "Present a small analysis with clear assumptions, a chart, and a short interpretation."),
    ]
    for index, (title, description) in enumerate(assignment_data):
        if assignment_total + counts.get("assignments_added", 0) >= 10:
            break
        title = f"Campus Demo: {title}"
        if one(cursor, "SELECT id FROM assignments WHERE title = %s", (title,)):
            continue
        item = class_subjects[index]
        teacher_user = faculty_by_id[item["faculty_id"]]["user_id"]
        due = datetime(2026, 10, 20, 23, 59) + timedelta(days=index * 3)
        cursor.execute(
            "INSERT INTO assignments (class_subject_id, title, description, due_date, created_by) VALUES (%s, %s, %s, %s, %s)",
            (item["id"], title, description, due, teacher_user),
        )
        counts["assignments_added"] = counts.get("assignments_added", 0) + 1

    # Keep real submissions intact; fabricated submission URLs would make the UI misleading.
    notices_count = one(cursor, "SELECT COUNT(*) AS n FROM notices WHERE college_id = %s", (college_id,))["n"]
    for index, (title, description, priority, audience) in enumerate(NOTICE_DATA):
        if notices_count + counts.get("notices_added", 0) >= 10:
            break
        title = f"Campus Demo: {title}"
        if one(cursor, "SELECT id FROM notices WHERE college_id = %s AND title = %s", (college_id, title)):
            continue
        cursor.execute(
            """INSERT INTO notices (college_id, title, description, priority, audience, publish_at, expires_at, created_by)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (college_id, title, description, priority, audience, datetime(2026, 9, 1) + timedelta(days=index), datetime(2027, 1, 31), admin_id),
        )
        counts["notices_added"] = counts.get("notices_added", 0) + 1

    events_count = one(cursor, "SELECT COUNT(*) AS n FROM events WHERE college_id = %s", (college_id,))["n"]
    for index, (title, description, location, start, end) in enumerate(EVENT_DATA):
        if events_count + counts.get("events_added", 0) >= 10:
            break
        title = f"Campus Demo: {title}"
        if one(cursor, "SELECT id FROM events WHERE college_id = %s AND title = %s", (college_id, title)):
            continue
        cursor.execute(
            "INSERT INTO events (college_id, title, description, location, start_datetime, end_datetime, created_by) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (college_id, title, description, location, start, end, admin_id),
        )
        counts["events_added"] = counts.get("events_added", 0) + 1

    resources_count = one(cursor, "SELECT COUNT(*) AS n FROM resources WHERE college_id = %s", (college_id,))["n"]
    for index, (title, description, url, file_type) in enumerate(RESOURCE_DATA):
        if resources_count + counts.get("resources_added", 0) >= 10:
            break
        title = f"Campus Demo: {title}"
        if one(cursor, "SELECT id FROM resources WHERE college_id = %s AND title = %s", (college_id, title)):
            continue
        code = ("JAVA", "FDS", "WEB", "WEB", "CSD501", "CSD502", "CYBER", "CYBER", "CYBER")[index]
        subject_id = one(cursor, "SELECT id FROM subjects WHERE course_id = %s AND code = %s AND semester = 5", (course_id, code))["id"]
        cs_item = next((item for item in class_subjects if item["subject_id"] == subject_id), None)
        uploader = faculty_by_id[cs_item["faculty_id"]]["user_id"] if cs_item and cs_item["faculty_id"] in faculty_by_id else admin_id
        cursor.execute(
            "INSERT INTO resources (college_id, subject_id, title, description, file_url, file_type, uploaded_by) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (college_id, subject_id, title, description, url, file_type, uploader),
        )
        counts["resources_added"] = counts.get("resources_added", 0) + 1

    incidents_count = one(cursor, "SELECT COUNT(*) AS n FROM cyber_incidents WHERE college_id = %s", (college_id,))["n"]
    incident_profiles = demo_profiles[:]
    if not incident_profiles:
        raise RuntimeError("No demo student profiles are available for incident reports.")
    for index, (kind, title, description, status, priority) in enumerate(INCIDENT_DATA):
        if incidents_count + counts.get("incidents_added", 0) >= 10:
            break
        title = f"Campus Demo: {title.removeprefix('Demo: ')}"
        if one(cursor, "SELECT id FROM cyber_incidents WHERE college_id = %s AND title = %s", (college_id, title)):
            continue
        reporter = incident_profiles[index % len(incident_profiles)]["user_id"]
        cursor.execute(
            """INSERT INTO cyber_incidents
               (college_id, reported_by, incident_type, title, description, status, priority, assigned_to, resolution_notes)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (college_id, reporter, kind, title, description, status, priority, admin_id,
             "Demo record: follow the normal review and response process." if status in ("resolved", "closed") else None),
        )
        counts["incidents_added"] = counts.get("incidents_added", 0) + 1

    # College requests are a live admin workflow; keep all nine examples pending.
    request_count = one(cursor, "SELECT COUNT(*) AS n FROM college_requests")["n"]
    for index, (college, city, contact, email) in enumerate(REQUEST_DATA):
        if request_count + counts.get("college_requests_added", 0) >= 10:
            break
        if one(cursor, "SELECT id FROM college_requests WHERE college_name = %s", (college,)):
            continue
        cursor.execute(
            "INSERT INTO college_requests (college_name, city, requested_by, requested_email, status) VALUES (%s, %s, %s, %s, 'Pending')",
            (college, city, contact, email),
        )
        counts["college_requests_added"] = counts.get("college_requests_added", 0) + 1

    return {
        "college_id": college_id,
        "class_id": class_id,
        "admin_id": admin_id,
        "student_ids": demo_student_ids,
        "faculty_emails": [row["email"] for row in demo_faculty_rows],
        "student_emails": [row["email"] for row in student_ids if row["roll_number"].startswith("CSD-DEMO-")],
        "counts_added": counts,
    }


def remove(cursor):
    college_id, _, _, course_id, class_id, _ = current_context(cursor)
    student_users = all_rows(
        cursor,
        """SELECT id FROM users WHERE college_id = %s AND role = 'student'
           AND (email LIKE 'demo-student-%@campusshield.test' OR id IN
                (SELECT user_id FROM students WHERE class_id = %s AND roll_number LIKE 'CSD-LEGACY-%'))""",
        (college_id, class_id),
    )
    student_user_ids = [row["id"] for row in student_users]
    faculty_users = all_rows(
        cursor,
        """SELECT id FROM users WHERE college_id = %s AND role = 'faculty'
           AND (email LIKE 'demo-faculty-%@campusshield.test' OR id IN
                (SELECT user_id FROM faculty WHERE employee_number = 'CSD-LEGACY-FAC-01'))""",
        (college_id,),
    )
    faculty_user_ids = [row["id"] for row in faculty_users]
    faculty_ids = []
    if faculty_user_ids:
        marks = ",".join(["%s"] * len(faculty_user_ids))
        faculty_ids = [row["id"] for row in all_rows(cursor, f"SELECT id FROM faculty WHERE user_id IN ({marks})", tuple(faculty_user_ids))]

    # Remove dependent demo rows before their referenced demo accounts.
    cursor.execute("DELETE FROM class_timetable WHERE class_id = %s AND room LIKE 'Demo %'", (class_id,))
    cursor.execute("DELETE FROM assignment_submissions WHERE assignment_id IN (SELECT id FROM assignments WHERE title LIKE 'Campus Demo: %')")
    cursor.execute("DELETE FROM assignments WHERE title LIKE 'Campus Demo: %'")
    cursor.execute("DELETE FROM notices WHERE college_id = %s AND title LIKE 'Campus Demo: %'", (college_id,))
    cursor.execute("DELETE FROM events WHERE college_id = %s AND title LIKE 'Campus Demo: %'", (college_id,))
    cursor.execute("DELETE FROM resources WHERE college_id = %s AND title LIKE 'Campus Demo: %'", (college_id,))
    cursor.execute("DELETE FROM cyber_incidents WHERE college_id = %s AND title LIKE 'Campus Demo: %'", (college_id,))
    cursor.execute("DELETE FROM college_requests WHERE college_name LIKE 'CampusShield Demo Partner College %'")
    cursor.execute("DELETE FROM marks WHERE exam_type LIKE 'DEMO: %'")
    if faculty_ids:
        marks = ",".join(["%s"] * len(faculty_ids))
        cursor.execute(
            f"""UPDATE class_subjects SET faculty_id = NULL
                WHERE class_id = %s AND subject_id NOT IN
                    (SELECT id FROM subjects WHERE course_id = %s AND code LIKE 'CSD50%')
                  AND faculty_id IN ({marks})""",
            (class_id, course_id, *faculty_ids),
        )
    cursor.execute("DELETE FROM class_subjects WHERE class_id = %s AND subject_id IN (SELECT id FROM subjects WHERE course_id = %s AND code LIKE 'CSD50%')", (class_id, course_id))
    cursor.execute("DELETE FROM subjects WHERE college_id = %s AND course_id = %s AND code LIKE 'CSD50%'", (college_id, course_id))

    if student_user_ids:
        marks = ",".join(["%s"] * len(student_user_ids))
        cursor.execute(
            f"DELETE a FROM attendance a JOIN students s ON s.id = a.student_id WHERE s.user_id IN ({marks})",
            tuple(student_user_ids),
        )
    cursor.execute("DELETE FROM students WHERE class_id = %s AND roll_number LIKE 'CSD-LEGACY-%'", (class_id,))
    if student_user_ids:
        marks = ",".join(["%s"] * len(student_user_ids))
        cursor.execute(f"DELETE FROM users WHERE id IN ({marks}) AND email LIKE 'demo-student-%@campusshield.test'", tuple(student_user_ids))
    if faculty_user_ids:
        marks = ",".join(["%s"] * len(faculty_user_ids))
        cursor.execute(f"DELETE FROM users WHERE id IN ({marks}) AND email LIKE 'demo-faculty-%@campusshield.test'", tuple(faculty_user_ids))
    cursor.execute("DELETE FROM faculty WHERE employee_number = 'CSD-LEGACY-FAC-01'")


def counts_for_report(cursor):
    names = (
        "colleges", "departments", "courses", "classes", "users", "students", "faculty",
        "subjects", "class_subjects", "class_timetable", "attendance", "marks", "assignments",
        "assignment_submissions", "notices", "events", "resources", "cyber_incidents",
        "college_requests", "notifications", "auth_otps", "password_resets", "activity_logs",
    )
    result = {}
    for table in names:
        result[table] = one(cursor, f"SELECT COUNT(*) AS n FROM `{table}`")["n"]
    return result


def main():
    parser = argparse.ArgumentParser(description="Seed/remove CampusShield faculty-demo data.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--apply", action="store_true", help="Add only missing demo data in the configured development database.")
    group.add_argument("--remove", action="store_true", help="Remove rows created by this seed and restore its profile links.")
    args = parser.parse_args()

    from backend import app as application
    if application.IS_PRODUCTION:
        raise SystemExit("Refusing to seed a production-configured database.")
    if application.DB_NAME.casefold() != "campusshield":
        raise SystemExit("Refusing unexpected configured database name; expected campusshield.")
    password = os.environ.get("CAMPUSSHIELD_DEMO_PASSWORD", "")
    if args.apply and len(password) < 8:
        raise SystemExit("Set CAMPUSSHIELD_DEMO_PASSWORD to a demo-only password of at least 8 characters before --apply.")

    connection = get_db()
    cursor = connection.cursor(dictionary=True)
    try:
        before = counts_for_report(cursor)
        connection.commit()
        connection.start_transaction()
        if args.apply:
            result = seed(cursor, password)
        else:
            remove(cursor)
            result = {"removed": True}
        connection.commit()
        after = counts_for_report(cursor)
        print({"result": result, "database_counts_before": before, "database_counts_after": after})
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


if __name__ == "__main__":
    main()
