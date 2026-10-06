from flask import Flask, request, jsonify, render_template, session, redirect
from flask_cors import CORS

import mysql.connector
import re
import os
import secrets
import hashlib
import hmac
import smtplib
import base64
import urllib.parse
import urllib.request
import threading
import time
import math
from pathlib import Path
from urllib.error import HTTPError, URLError

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from datetime import datetime, timedelta
from email.message import EmailMessage

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


def _load_env_files():

    if load_dotenv is None:
        return

    configured_environment = (
        os.environ.get("CAMPUSSHIELD_ENV")
        or os.environ.get("FLASK_ENV")
        or "development"
    ).strip().lower()
    if configured_environment in {"production", "prod"}:
        return

    backend_dir = Path(__file__).resolve().parent
    project_root = backend_dir.parent

    for env_path in (
        backend_dir / ".env",
        project_root / ".env"
    ):

        if env_path.is_file():
            load_dotenv(env_path, override=False)


_load_env_files()


# ============================================================
# APP CONFIGURATION
# ============================================================

app = Flask(
    __name__,
    template_folder="../frontend",
    static_folder="../frontend",
    static_url_path=""
)


@app.errorhandler(404)
def handle_not_found(error):
    if request.path.startswith("/api/"):
        return error_response("API endpoint not found.", 404)
    return error


@app.errorhandler(405)
def handle_method_not_allowed(error):
    if request.path.startswith("/api/"):
        return error_response("HTTP method not allowed for this API endpoint.", 405)
    return error

APP_ENV = (
    os.environ.get("CAMPUSSHIELD_ENV")
    or os.environ.get("FLASK_ENV")
    or "development"
).strip().lower()
IS_PRODUCTION = APP_ENV in {"production", "prod"}
DEBUG_MODE = (
    not IS_PRODUCTION
    and (os.environ.get("CAMPUSSHIELD_DEBUG", "false") or "false").strip().lower() == "true"
)

configured_secret = os.environ.get("CAMPUSSHIELD_SECRET_KEY")
if not configured_secret:
    if IS_PRODUCTION:
        raise RuntimeError("CAMPUSSHIELD_SECRET_KEY must be configured in production.")
    configured_secret = secrets.token_urlsafe(32)
elif IS_PRODUCTION and (
    len(configured_secret) < 32
    or configured_secret.strip().lower() in {"change-this-in-production", "secret", "development"}
):
    raise RuntimeError("CAMPUSSHIELD_SECRET_KEY must be a strong production secret.")
app.secret_key = configured_secret

configured_cors_origins = [
    origin.strip()
    for origin in os.environ.get("CAMPUSSHIELD_CORS_ORIGINS", "").split(",")
    if origin.strip()
]
if "*" in configured_cors_origins:
    raise RuntimeError("CAMPUSSHIELD_CORS_ORIGINS must list exact trusted origins.")
local_cors_origins = [
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:5000",
    "http://127.0.0.1:5000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
render_frontend_origin_pattern = r"^https://[a-z0-9-]+\.onrender\.com$"
railway_frontend_origin_pattern = r"^https://[a-z0-9-]+\.up\.railway\.app$"
CORS(
    app,
    resources={r"/api/*": {"origins": configured_cors_origins + local_cors_origins + [render_frontend_origin_pattern, railway_frontend_origin_pattern]}},
    supports_credentials=True
)

# Session security
app.config["SESSION_COOKIE_HTTPONLY"] = True
cookie_samesite = (os.environ.get("CAMPUSSHIELD_COOKIE_SAMESITE", "Lax") or "Lax").strip().capitalize()
if cookie_samesite not in {"Lax", "Strict", "None"}:
    cookie_samesite = "Lax"
secure_default = "true" if IS_PRODUCTION else "false"
app.config["SESSION_COOKIE_SAMESITE"] = cookie_samesite
configured_cookie_secure = (
    (os.environ.get("CAMPUSSHIELD_COOKIE_SECURE", secure_default) or secure_default).strip().lower() == "true"
)
app.config["SESSION_COOKIE_SECURE"] = IS_PRODUCTION or configured_cookie_secure
if cookie_samesite == "None" and not app.config["SESSION_COOKIE_SECURE"]:
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(
    seconds=max(300, int(os.environ.get("CAMPUSSHIELD_SESSION_LIFETIME_SECONDS", "28800")))
)
app.config["SESSION_REFRESH_EACH_REQUEST"] = False


# ============================================================
# AUTH CONFIGURATION
# ============================================================

OTP_LENGTH = 6

OTP_EXPIRY_MINUTES = 5

MAX_OTP_ATTEMPTS = 5

OTP_RESEND_SECONDS = 60

PASSWORD_MIN_LENGTH = 8

SESSION_COOKIE_HTTPONLY = True


# ============================================================
# DATABASE CONNECTION
# ============================================================

DB_HOST = os.environ.get("CAMPUSSHIELD_DB_HOST", "localhost")
DB_PORT = int(os.environ.get("CAMPUSSHIELD_DB_PORT", "3306"))
DB_USER = os.environ.get("CAMPUSSHIELD_DB_USER", "root")
DB_PASSWORD = os.environ.get("CAMPUSSHIELD_DB_PASSWORD", "")
DB_NAME = os.environ.get("CAMPUSSHIELD_DB_NAME", "campusshield")

if IS_PRODUCTION:
    missing_database_settings = [
        name
        for name in (
            "CAMPUSSHIELD_DB_HOST",
            "CAMPUSSHIELD_DB_NAME",
            "CAMPUSSHIELD_DB_USER",
            "CAMPUSSHIELD_DB_PASSWORD"
        )
        if not os.environ.get(name, "").strip()
    ]
    if missing_database_settings:
        raise RuntimeError(
            "Production database host, name, user, and password must be configured."
        )
    if DB_USER.strip().lower() == "root":
        raise RuntimeError("A non-root production database user must be configured.")

def get_db():

    if IS_PRODUCTION and (not DB_PASSWORD or DB_USER.strip().lower() == "root"):
        raise RuntimeError("Production database credentials must be configured securely.")

    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )


def ensure_timetable_table(cursor):

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS class_timetable (
            id INT AUTO_INCREMENT PRIMARY KEY,
            class_id INT NOT NULL,
            subject_id INT NOT NULL,
            faculty_id INT NULL,
            day_of_week ENUM('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday') NOT NULL,
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,
            room VARCHAR(100) NULL,
            created_by INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE,
            FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
            FOREIGN KEY (faculty_id) REFERENCES faculty(id) ON DELETE SET NULL,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
            UNIQUE (class_id, subject_id, day_of_week, start_time)
        )
    """)


# ============================================================
# COMMON RESPONSE
# ============================================================

def success_response(message, **extra):

    response = {
        "success": True,
        "message": message
    }

    response.update(extra)

    return jsonify(response)


def error_response(message, status=400):

    return jsonify({
        "success": False,
        "message": message
    }), status


def session_role():

    return (
        session.get("role")
        or ""
    ).strip().lower()


def api_require_admin():

    if "user_id" not in session:

        return error_response(
            "Login required.",
            401
        )

    if session_role() != "admin":

        return error_response(
            "Access denied.",
            403
        )

    return None


def audit_admin_managed_api_access():
    management = session.get("admin_management")
    if (
        not management
        or not request.path.startswith("/api/")
        or request.path == "/api/auth/me"
        or request.path == "/api/admin/manage-user"
        or request.path == "/api/admin/stop-managing"
    ):
        return None

    description = (
        f"Admin {management.get('admin_user_id')} accessed "
        f"{management.get('target_role')} account "
        f"{management.get('target_user_id')} via "
        f"{request.method} {request.path}"
    )
    if not record_admin_management_action(
        management,
        "Admin managed portal access",
        description
    ):
        return error_response(
            "Admin audit logging is unavailable. No module access was allowed.",
            503
        )
    return None


@app.after_request
def add_admin_management_banner(response):
    if (
        session.get("admin_management")
        and response.status_code == 200
        and response.mimetype == "text/html"
    ):
        body = response.get_data(as_text=True)
        script_tag = '<script src="/admin-management.js" defer></script>'
        if script_tag not in body:
            closing_body = body.lower().rfind("</body>")
            if closing_body >= 0:
                body = body[:closing_body] + script_tag + body[closing_body:]
                response.set_data(body)
        response.headers["Cache-Control"] = "private, no-store"
    return response


def insert_user_account(cursor, college_id, name, email, mobile, password_hash, role):

    cursor.execute("SHOW COLUMNS FROM users")
    columns = {row[0] for row in cursor.fetchall()}

    values = {
        "college_id": college_id,
        "name": name,
        "full_name": name,
        "email": email,
        "mobile": mobile,
        "password_hash": password_hash,
        "is_active": True,
        "role": role,
    }
    insert_columns = [column for column in values if column in columns]

    if not {"college_id", "role"}.issubset(insert_columns):
        raise RuntimeError("The users table is missing required account columns.")
    if not ({"name", "full_name"} & set(insert_columns)):
        raise RuntimeError("The users table is missing a name column.")
    if "password_hash" not in insert_columns:
        raise RuntimeError("The users table is missing the password_hash column.")

    placeholders = ", ".join(["%s"] * len(insert_columns))
    column_sql = ", ".join(f"`{column}`" for column in insert_columns)
    cursor.execute(
        f"INSERT INTO users ({column_sql}) VALUES ({placeholders})",
        tuple(values[column] for column in insert_columns)
    )
    return cursor.lastrowid


def account_session_version(account):

    updated_at = account.get("updated_at")
    if updated_at:
        return updated_at.isoformat(sep=" ")

    version_fields = (
        "id",
        "college_id",
        "full_name",
        "email",
        "mobile",
        "password_hash",
        "role",
        "is_active",
        "status",
    )
    payload = "\x1f".join(
        "" if account.get(field) is None else str(account.get(field))
        for field in version_fields
    )
    return hmac.new(
        str(app.secret_key).encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def load_session_account(cursor, user_id):
    """Load the fields used to validate a live user session."""
    cursor.execute("SHOW COLUMNS FROM users LIKE 'updated_at'")
    has_updated_at = cursor.fetchone() is not None
    cursor.execute("SHOW COLUMNS FROM users LIKE 'password'")
    has_legacy_password = cursor.fetchone() is not None
    updated_at_select = "u.updated_at" if has_updated_at else "NULL"
    password_hash_select = (
        "COALESCE(NULLIF(u.password_hash, ''), NULLIF(u.password, ''))"
        if has_legacy_password else "u.password_hash"
    )
    cursor.execute(
        f"SELECT u.id, u.role, u.is_active, u.status, u.college_id, "
        f"COALESCE(NULLIF(u.full_name, ''), NULLIF(u.name, '')) AS full_name, "
        f"u.email, u.mobile, {password_hash_select} AS password_hash, "
        f"{updated_at_select} AS updated_at, c.name AS college "
        "FROM users u LEFT JOIN colleges c ON c.id = u.college_id "
        "WHERE u.id = %s LIMIT 1",
        (user_id,)
    )
    return cursor.fetchone()


def record_admin_management_action(context, action, description):
    """Persist an admin-managed portal access/action before allowing it."""
    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO activity_logs "
            "(college_id, user_id, action, description, ip_address, user_agent) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (
                context.get("admin_college_id"),
                context.get("admin_user_id"),
                action[:100],
                description,
                request.remote_addr,
                request.headers.get("User-Agent", "")[:1000],
            )
        )
        db.commit()
        return True
    except Exception as error:
        if db:
            db.rollback()
        app.logger.error("Admin management audit write failed: %s", error)
        return False
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


def create_user_profile(
    cursor,
    user_id,
    college_id,
    role,
    department_id=None,
    class_id=None,
    roll_number=None
):

    if role == "student":
        if not class_id or not roll_number:
            return "Please select a class and enter the student's roll number.", 400

        cursor.execute("""
            SELECT id
            FROM classes
            WHERE id = %s
              AND college_id = %s
            LIMIT 1
        """, (class_id, college_id))
        if cursor.fetchone() is None:
            return "Selected class does not belong to this college.", 400

        cursor.execute(
            "SELECT id FROM students WHERE user_id = %s LIMIT 1",
            (user_id,)
        )
        if cursor.fetchone():
            return "A student profile already exists for this user.", 409

        cursor.execute("""
            INSERT INTO students (user_id, class_id, roll_number)
            VALUES (%s, %s, %s)
        """, (user_id, class_id, roll_number))
        return None

    if role == "faculty":
        cursor.execute(
            "SELECT id FROM faculty WHERE user_id = %s LIMIT 1",
            (user_id,)
        )
        if cursor.fetchone():
            return "A faculty profile already exists for this user.", 409

        cursor.execute("""
            INSERT INTO faculty (user_id, department_id)
            VALUES (%s, %s)
        """, (user_id, department_id))
        return None

    return "Unsupported profile role.", 400


def page_require_role(*roles):

    if "user_id" not in session:

        return redirect(
            "/login.html"
        )

    if session_role() not in roles:

        return "Access Denied", 403

    return None


PROTECTED_HTML_BY_LOWER = {}

PROTECTED_HTML_ROLES = {}


def register_protected_html_pages():

    pages = [
        ("student-dashboard.html", ("student",)),
        ("attendance.html", ("student",)),
        ("Notes.html", ("student",)),
        ("assignment.html", ("student",)),
        ("timetable.html", ("student",)),
        ("notices.html", ("student",)),
        ("Cyber-safety.html", ("student",)),
        ("password-checker.html", ("student",)),
        ("digital-score.html", ("student",)),
        ("website-checker.html", ("student",)),
        ("cyber-quiz.html", ("student",)),
        ("safety-tips.html", ("student",)),
        ("safety-report.html", ("student",)),
        ("faculty-dashboard.html", ("faculty",)),
        ("faculty-attendence.html", ("faculty",)),
        ("faculty-assignment.html", ("faculty",)),
        ("faculty-notes.html", ("faculty",)),
        ("marks.html", ("faculty",)),
        ("faculty-notices.html", ("faculty",)),
        ("faculty-events.html", ("faculty",)),
        ("faculty-timetable.html", ("faculty",)),
        ("faculty-student.html", ("faculty",)),
        ("admin-notes.html", ("admin",)),
        ("admin-notices.html", ("admin",)),
        ("admin-events.html", ("admin",)),
        ("admin-cyber-safety.html", ("admin",)),
        ("admin-reports.html", ("admin",)),
        ("admin-assignments.html", ("admin",)),
        ("admin-profile.html", ("admin",)),
        ("admin-classes.html", ("admin",)),
    ]

    # These already have dedicated Flask routes.
    extra_protected = [
        ("admin-dashboard.html", ("admin",)),
        ("admin-users.html", ("admin",)),
    ]

    for filename, roles in pages:

        def make_view(page_name, allowed_roles):

            def view():

                blocked = page_require_role(
                    *allowed_roles
                )

                if blocked is not None:

                    return blocked

                return render_template(
                    page_name
                )

            return view

        view = make_view(
            filename,
            roles
        )

        view.__name__ = (
            "protected_"
            + filename.replace(".", "_").replace("-", "_")
        )

        app.add_url_rule(
            "/" + filename,
            endpoint=view.__name__,
            view_func=view
        )

        PROTECTED_HTML_BY_LOWER[filename.lower()] = filename

        PROTECTED_HTML_ROLES[filename] = roles

    for filename, roles in extra_protected:

        PROTECTED_HTML_BY_LOWER[filename.lower()] = filename

        PROTECTED_HTML_ROLES[filename] = roles


register_protected_html_pages()


@app.before_request
def enforce_protected_html_canonical():

    # Static serving uses the same folder as templates, so a
    # differently-cased URL (for example /cyber-safety.html)
    # can miss the protected route and return HTML with no auth.
    # Send those requests to the canonical protected URL.

    if request.method not in [
        "GET",
        "HEAD"
    ]:

        return None

    path = request.path

    if (
        not path.startswith("/")
        or "/" in path[1:]
    ):

        return None

    requested = path[1:]

    if not requested.lower().endswith(".html"):

        return None

    canonical = PROTECTED_HTML_BY_LOWER.get(
        requested.lower()
    )

    if not canonical:

        return None

    if requested != canonical:

        return redirect(
            "/" + canonical
        )

    if request.endpoint == "static":

        blocked = page_require_role(
            *PROTECTED_HTML_ROLES[canonical]
        )

        if blocked is not None:

            return blocked

        return render_template(
            canonical
        )

    return None


RATE_LIMITS = {
    "login": (10, 300),
    "register_send_otp": (5, 300),
    "register_verify_otp": (10, 300),
    "register_user": (10, 3600),
    "forgot_password": (5, 300),
    "verify_otp": (10, 300),
    "reset_password": (5, 300),
    "student_cyber_incidents": (10, 3600),
}
_rate_limit_state = {}
_rate_limit_lock = threading.Lock()


def _rate_limit_request(endpoint):
    limit, window = RATE_LIMITS[endpoint]
    now = time.monotonic()
    key = (endpoint, request.remote_addr or "unknown")
    with _rate_limit_lock:
        started, count = _rate_limit_state.get(key, (now, 0))
        if now - started >= window:
            started, count = now, 0
        if count >= limit:
            return max(1, int(window - (now - started)))
        _rate_limit_state[key] = (started, count + 1)
        if len(_rate_limit_state) > 10000:
            cutoff = now - 3600
            for state_key, (state_started, _) in list(_rate_limit_state.items()):
                if state_started < cutoff:
                    _rate_limit_state.pop(state_key, None)
    return 0


@app.before_request
def enforce_request_security():
    if request.endpoint == "static":
        return None

    endpoint = request.endpoint or ""
    if endpoint in RATE_LIMITS and (
        endpoint != "student_cyber_incidents" or request.method == "POST"
    ):
        retry_after = _rate_limit_request(endpoint)
        if retry_after:
            response, status = error_response("Too many requests. Please try again later.", 429)
            response.headers["Retry-After"] = str(retry_after)
            return response, status

    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        fetch_site = request.headers.get("Sec-Fetch-Site", "").lower()
        if fetch_site and fetch_site != "same-origin":
            return error_response("Cross-site request blocked.", 403)

        origin = request.headers.get("Origin")
        source = origin or request.headers.get("Referer")
        if not source:
            return error_response("Request origin could not be verified.", 403)
        try:
            parsed_source = urllib.parse.urlsplit(source)
        except ValueError:
            return error_response("Request origin could not be verified.", 403)
        if (
            parsed_source.scheme.lower() not in {"http", "https"}
            or parsed_source.netloc.lower() != request.host.lower()
        ):
            return error_response("Cross-origin request blocked.", 403)

    if (
        "user_id" in session
        and endpoint not in {"logout", "logout_and_redirect"}
        and endpoint not in {"login_page", "register_page", "forgot_password_page"}
    ):
        db = cursor = None
        try:
            db = get_db()
            cursor = db.cursor(dictionary=True)
            account = load_session_account(cursor, session.get("user_id"))
            account_version = account_session_version(account) if account else None
            management = session.get("admin_management")
            valid_session = not (
                not account
                or not account.get("is_active")
                or account.get("status") != "active"
                or (account.get("role") or "").strip().lower() != session_role()
                or session.get("account_updated_at") != account_version
            )

            if management:
                admin_account = load_session_account(
                    cursor,
                    management.get("admin_user_id")
                )
                admin_version = (
                    account_session_version(admin_account)
                    if admin_account else None
                )
                valid_session = valid_session and not (
                    management.get("target_user_id") != session.get("user_id")
                    or management.get("target_role") != session_role()
                    or not admin_account
                    or not admin_account.get("is_active")
                    or admin_account.get("status") != "active"
                    or (admin_account.get("role") or "").strip().lower() != "admin"
                    or admin_version != management.get("admin_account_updated_at")
                )

            if not valid_session:
                session.clear()
                if request.path.lower().endswith(".html"):
                    return redirect("/login.html")
                return error_response("Session expired. Please login again.", 401)
        except Exception:
            return error_response("Unable to verify your session. Please retry.", 503)
        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    return audit_admin_managed_api_access()


# ============================================================
# IDENTIFIER HELPERS
# ============================================================

def normalize_email(email):

    return (email or "").strip().lower()


def normalize_mobile(mobile):

    return re.sub(
        r"[\s\-()]",
        "",
        (mobile or "").strip()
    )


def format_mobile_for_sms(mobile):

    # Twilio needs E.164, for example +91XXXXXXXXXX.
    # Stored login numbers are not rewritten.

    number = normalize_mobile(
        mobile
    )

    if number.startswith("+"):

        digits = number[1:]

        if digits.isdigit() and 10 <= len(digits) <= 15:

            return "+" + digits

        return number

    if number.isdigit() and len(number) == 10:

        return "+91" + number

    if (
        number.isdigit()
        and len(number) == 12
        and number.startswith("91")
    ):

        return "+" + number

    if number.isdigit():

        return "+" + number

    return number


def valid_email(email):

    return re.fullmatch(
        r"[^@\s]+@[^@\s]+\.[^@\s]+",
        email
    ) is not None


def valid_mobile(mobile):

    return re.fullmatch(
        r"\+?[0-9]{10,15}",
        mobile
    ) is not None


# ============================================================
# PASSWORD HELPERS
# ============================================================

def valid_password(password):

    if not password:
        return False

    return len(password) >= PASSWORD_MIN_LENGTH


def password_is_hashed(password):

    if not password:
        return False

    return (
        password.startswith("pbkdf2:")
        or password.startswith("scrypt:")
        or password.startswith("argon2:")
    )


def verify_user_password(stored_password, entered_password):

    if not stored_password:
        return False, False

    # New secure password
    if password_is_hashed(stored_password):

        try:

            valid = check_password_hash(
                stored_password,
                entered_password
            )

            return valid, False

        except Exception:

            return False, False

    # Existing old plaintext password
    if stored_password == entered_password:

        return True, True

    return False, False


# ============================================================
# OTP HELPERS
# ============================================================

def generate_otp():

    return "".join(
        secrets.choice("0123456789")
        for _ in range(OTP_LENGTH)
    )


def hash_otp(otp):
    return hmac.new(
        str(app.secret_key).encode("utf-8"),
        otp.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


# ============================================================
# OTP DELIVERY CONFIGURATION
# ============================================================

EMAIL_ADDRESS = (
    os.environ.get("EMAIL_ADDRESS")
    or ""
).strip()

EMAIL_APP_PASSWORD = (
    os.environ.get("EMAIL_APP_PASSWORD")
    or ""
).strip()

_legacy_smtp_host = (
    os.environ.get("CAMPUSSHIELD_SMTP_HOST")
    or ""
).strip()

_legacy_smtp_user = (
    os.environ.get("CAMPUSSHIELD_SMTP_USERNAME")
    or ""
).strip()

_legacy_smtp_password = (
    os.environ.get("CAMPUSSHIELD_SMTP_PASSWORD")
    or ""
)

_legacy_smtp_from = (
    os.environ.get("CAMPUSSHIELD_SMTP_FROM")
    or ""
).strip()

_gmail_ready = bool(
    EMAIL_ADDRESS
    and EMAIL_APP_PASSWORD
)

SMTP_HOST = _legacy_smtp_host or (
    "smtp.gmail.com"
    if _gmail_ready
    else ""
)

SMTP_PORT = int(
    os.environ.get(
        "CAMPUSSHIELD_SMTP_PORT",
        "587"
    )
    or "587"
)

SMTP_USERNAME = _legacy_smtp_user or EMAIL_ADDRESS

SMTP_PASSWORD = _legacy_smtp_password or EMAIL_APP_PASSWORD

SMTP_FROM = _legacy_smtp_from or SMTP_USERNAME

SMS_PROVIDER = (
    os.environ.get(
        "CAMPUSSHIELD_SMS_PROVIDER",
        ""
    )
    or ""
).strip().lower()

TWILIO_ACCOUNT_SID = os.environ.get(
    "CAMPUSSHIELD_TWILIO_ACCOUNT_SID",
    ""
)

TWILIO_AUTH_TOKEN = os.environ.get(
    "CAMPUSSHIELD_TWILIO_AUTH_TOKEN",
    ""
)

TWILIO_FROM_NUMBER = os.environ.get(
    "CAMPUSSHIELD_TWILIO_FROM_NUMBER",
    ""
)


# ============================================================
# DEVELOPMENT MODE
# ============================================================

DEV_MODE = (
    not IS_PRODUCTION
    and (os.environ.get("CAMPUSSHIELD_DEV_MODE", "false") or "false").strip().lower() == "true"
)


def smtp_configured():

    return bool(
        SMTP_HOST
        and SMTP_USERNAME
        and SMTP_PASSWORD
    )


def resend_cooldown_remaining(last_created_at):

    if not last_created_at:
        return 0

    try:
        elapsed = (
            datetime.now() - last_created_at
        ).total_seconds()
    except TypeError:
        return 0

    remaining = OTP_RESEND_SECONDS - elapsed

    if remaining <= 0:
        return 0

    return max(1, int(remaining))


def sms_configured():

    if SMS_PROVIDER == "twilio":

        return bool(
            TWILIO_ACCOUNT_SID
            and TWILIO_AUTH_TOKEN
            and TWILIO_FROM_NUMBER
        )

    return False


def print_dev_otp(channel, destination, otp):

    if IS_PRODUCTION or not DEV_MODE:
        return

    print("", flush=True)
    print("=" * 60, flush=True)
    print("CAMPUSSHIELD DEVELOPMENT OTP", flush=True)
    print("Channel     :", channel, flush=True)
    print("Destination :", destination, flush=True)
    print("OTP         :", otp, flush=True)
    print("=" * 60, flush=True)
    print("", flush=True)


def otp_delivery_payload(otp, delivery_method=None):

    payload = {}

    method = (
        delivery_method
        or ""
    ).strip().lower()

    real_delivery = False

    if method in [
        "sms",
        "mobile"
    ]:

        real_delivery = sms_configured()

    elif method == "email":

        real_delivery = smtp_configured()

    else:

        real_delivery = (
            smtp_configured()
            or sms_configured()
        )

    # Never return the OTP in the API when a real
    # provider is sending it.
    if DEV_MODE and not real_delivery:

        payload["developmentOtp"] = otp
        payload["developmentHint"] = (
            "Development mode: OTP is also printed in the Flask terminal."
        )

    return payload


# ============================================================
# SEND EMAIL OTP
# ============================================================

def send_email_otp(email, otp, purpose="verification"):

    if smtp_configured():

        try:

            subject = "CampusShield verification OTP"

            if purpose == "password_reset":

                subject = "CampusShield Password Reset OTP"

            elif purpose == "registration":

                subject = "CampusShield registration OTP"

            message = EmailMessage()

            message["Subject"] = subject

            message["From"] = SMTP_FROM or SMTP_USERNAME

            message["To"] = email

            message.set_content(
                f"""
CampusShield

Your OTP is:

{otp}

This OTP will expire in {OTP_EXPIRY_MINUTES} minutes.

If you did not request this code, please ignore this email.

CampusShield Security Team
"""
            )

            gmail_host = (
                SMTP_HOST
                or ""
            ).lower() in (
                "smtp.gmail.com",
                "smtp.googlemail.com",
            )

            if gmail_host:

                with smtplib.SMTP_SSL(
                    SMTP_HOST,
                    465
                ) as server:

                    server.login(
                        SMTP_USERNAME,
                        SMTP_PASSWORD
                    )

                    server.send_message(message)

            else:

                with smtplib.SMTP(
                    SMTP_HOST,
                    SMTP_PORT
                ) as server:

                    server.starttls()

                    server.login(
                        SMTP_USERNAME,
                        SMTP_PASSWORD
                    )

                    server.send_message(message)

            return True

        except Exception as error:

            if DEV_MODE:
                print("Email OTP delivery error:", error)
            else:
                print("Email OTP delivery failed.")

            return False

    if DEV_MODE:

        print_dev_otp("email", email, otp)

        return True

    print(
        "SMTP is not configured."
    )

    return False


# ============================================================
# SEND MOBILE OTP
# ============================================================

def send_twilio_sms(mobile, otp):

    url = (
        "https://api.twilio.com/2010-04-01/Accounts/"
        + TWILIO_ACCOUNT_SID
        + "/Messages.json"
    )

    form = urllib.parse.urlencode({
        "To": format_mobile_for_sms(mobile),
        "From": TWILIO_FROM_NUMBER,
        "Body": (
            "CampusShield OTP: "
            + otp
            + ". Expires in "
            + str(OTP_EXPIRY_MINUTES)
            + " minutes."
        )
    }).encode("utf-8")

    request_obj = urllib.request.Request(
        url,
        data=form,
        method="POST"
    )

    credentials = (
        TWILIO_ACCOUNT_SID
        + ":"
        + TWILIO_AUTH_TOKEN
    )

    auth_header = base64.b64encode(
        credentials.encode("utf-8")
    ).decode("ascii")

    request_obj.add_header(
        "Authorization",
        "Basic " + auth_header
    )

    request_obj.add_header(
        "Content-Type",
        "application/x-www-form-urlencoded"
    )

    with urllib.request.urlopen(
        request_obj,
        timeout=20
    ) as response:

        response.read()

    return True


def send_mobile_otp(mobile, otp):

    if sms_configured() and SMS_PROVIDER == "twilio":

        try:

            return send_twilio_sms(
                mobile,
                otp
            )

        except (HTTPError, URLError, TimeoutError, Exception) as error:

            if DEV_MODE:
                print("SMS OTP delivery error:", error)
            else:
                print("SMS OTP delivery failed.")

            return False

    if DEV_MODE:

        print_dev_otp("sms", mobile, otp)

        return True

    print(
        "SMS provider is not configured."
    )

    return False


# ============================================================
# COLLEGE REQUEST TABLE
# ============================================================

def create_college_requests_table():

    db = None
    cursor = None

    try:

        db = get_db()

        cursor = db.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS college_requests (

                id INT AUTO_INCREMENT PRIMARY KEY,

                college_name VARCHAR(255) NOT NULL,

                city VARCHAR(100) NOT NULL,

                requested_by VARCHAR(255) NOT NULL,

                requested_email VARCHAR(255),

                status ENUM(
                    'Pending',
                    'Approved',
                    'Rejected'
                ) DEFAULT 'Pending',

                college_code VARCHAR(50),

                created_at TIMESTAMP
                    DEFAULT CURRENT_TIMESTAMP,

                approved_at TIMESTAMP NULL

            )
        """)

        db.commit()

        print(
            "College requests table ready."
        )

    except Exception as error:

        print(
            "College Request Table Error:",
            error
        )

    finally:

        if cursor:
            cursor.close()

        if db:
            db.close()


# ============================================================
# AUTH OTP TABLES
# ============================================================

def ensure_auth_tables():

    db = None
    cursor = None

    try:

        db = get_db()

        cursor = db.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS password_resets (

                id INT AUTO_INCREMENT PRIMARY KEY,

                user_id INT NOT NULL,

                identifier VARCHAR(150) NOT NULL,

                otp_hash VARCHAR(255) NOT NULL,

                expires_at DATETIME NOT NULL,

                attempts INT NOT NULL DEFAULT 0,

                used TINYINT(1) NOT NULL DEFAULT 0,

                created_at TIMESTAMP
                    DEFAULT CURRENT_TIMESTAMP,

                INDEX idx_password_resets_user (user_id),

                INDEX idx_password_resets_identifier (identifier)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auth_otps (

                id INT AUTO_INCREMENT PRIMARY KEY,

                identifier VARCHAR(150) NOT NULL,

                full_name VARCHAR(150) NULL,

                purpose VARCHAR(50) NOT NULL,

                delivery_method VARCHAR(20) NOT NULL,

                otp_hash VARCHAR(255) NOT NULL,

                expires_at DATETIME NOT NULL,

                attempts INT NOT NULL DEFAULT 0,

                verified_at DATETIME NULL,

                used TINYINT(1) NOT NULL DEFAULT 0,

                created_at TIMESTAMP
                    DEFAULT CURRENT_TIMESTAMP,

                INDEX idx_auth_otps_identifier (identifier),

                INDEX idx_auth_otps_purpose (purpose)
            )
        """)

        db.commit()

        print(
            "Auth OTP tables ready."
        )

    except Exception as error:

        print(
            "Auth OTP Table Error:",
            error
        )

    finally:

        if cursor:
            cursor.close()

        if db:
            db.close()


# ============================================================
# LOGIN PAGE
# ============================================================

@app.route("/login.html")
def login_page():

    return render_template(
        "login.html"
    )


@app.route("/register.html")
def register_page():

    return render_template(
        "register.html"
    )


@app.route("/forgot-password.html")
def forgot_password_page():

    return render_template(
        "forgot-password.html"
    )


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@app.route("/admin-dashboard.html")
def admin_dashboard():

    if "user_id" not in session:

        return redirect(
            "/login.html"
        )

    if session.get("role") != "admin":

        return "Access Denied", 403

    return render_template(
        "admin-dashboard.html"
    )


# ============================================================
# ADMIN USERS PAGE
# ============================================================

@app.route("/admin-users.html")
def admin_users():

    if "user_id" not in session:

        return redirect(
            "/login.html"
        )

    if session.get("role") != "admin":

        return "Access Denied", 403

    return render_template(
        "admin-users.html"
    )


@app.route("/api/admin/manage-user", methods=["POST"])
def admin_manage_user():
    denied = api_require_admin()
    if denied:
        return denied

    data = request.get_json(silent=True) or {}
    if isinstance(data.get("user_id"), bool):
        return error_response("Please select a valid Student or Faculty account.")
    try:
        target_user_id = int(data.get("user_id"))
    except (TypeError, ValueError):
        return error_response("Please select a valid Student or Faculty account.")

    requested_role = (data.get("role") or "").strip().lower()
    if target_user_id <= 0 or requested_role not in {"student", "faculty"}:
        return error_response("Choose an active Student or Faculty account.")

    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        admin_account = load_session_account(cursor, session.get("user_id"))
        target_account = load_session_account(cursor, target_user_id)

        if (
            not admin_account
            or (admin_account.get("role") or "").strip().lower() != "admin"
            or not target_account
            or (target_account.get("role") or "").strip().lower() != requested_role
            or not target_account.get("is_active")
            or target_account.get("status") != "active"
        ):
            return error_response("That active Student or Faculty account could not be found.", 404)

        management = {
            "admin_user_id": int(admin_account["id"]),
            "admin_college_id": admin_account.get("college_id"),
            "admin_account_updated_at": account_session_version(admin_account),
            "target_user_id": int(target_account["id"]),
            "target_role": requested_role,
        }
        target_name = target_account.get("full_name") or ""
        audit_description = (
            f"Admin {management['admin_user_id']} opened {requested_role} "
            f"portal for account {management['target_user_id']} ({target_name})"
        )
        if not record_admin_management_action(
            management,
            "Admin opened role portal",
            audit_description
        ):
            return error_response(
                "Admin audit logging is unavailable. Portal access was not started.",
                503
            )

        session["admin_management"] = management
        session["user_id"] = management["target_user_id"]
        session["user_name"] = target_name
        session["email"] = target_account.get("email")
        session["mobile"] = target_account.get("mobile")
        session["role"] = requested_role
        session["college"] = target_account.get("college")
        session["account_updated_at"] = account_session_version(target_account)
        session.permanent = True

        return success_response(
            f"Admin access started for the selected {requested_role} account.",
            redirect=f"/{requested_role}-dashboard.html"
        )
    except Exception as error:
        print("Admin Managed Portal Error:", error)
        return error_response("Unable to open the selected role portal.", 500)
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@app.route("/api/admin/stop-managing", methods=["POST"])
def admin_stop_managing_user():
    management = session.get("admin_management")
    if not management:
        return error_response("No Admin-managed portal is active.", 409)

    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        admin_account = load_session_account(
            cursor,
            management.get("admin_user_id")
        )
        if (
            not admin_account
            or (admin_account.get("role") or "").strip().lower() != "admin"
            or not admin_account.get("is_active")
            or admin_account.get("status") != "active"
            or account_session_version(admin_account)
            != management.get("admin_account_updated_at")
        ):
            session.clear()
            return error_response("The Admin account changed. Please sign in again.", 401)

        record_admin_management_action(
            management,
            "Admin returned to own portal",
            f"Admin {management['admin_user_id']} ended managed access to "
            f"{management['target_role']} account {management['target_user_id']}"
        )

        session.pop("admin_management", None)
        session["user_id"] = int(admin_account["id"])
        session["user_name"] = admin_account.get("full_name") or ""
        session["email"] = admin_account.get("email")
        session["mobile"] = admin_account.get("mobile")
        session["role"] = "admin"
        session["college"] = admin_account.get("college")
        session["account_updated_at"] = account_session_version(admin_account)
        session.permanent = True
        return success_response("Admin access restored.")
    except Exception as error:
        print("Admin Stop Managed Portal Error:", error)
        return error_response("Unable to restore the Admin account.", 500)
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


# ============================================================
# COLLEGES API
# ============================================================

@app.route("/api/colleges")
def get_colleges():

    db = None
    cursor = None

    try:

        db = get_db()

        cursor = db.cursor(
            buffered=True
        )

        cursor.execute("""
            SELECT id, name, code
            FROM colleges
            WHERE is_active = 1
            ORDER BY name ASC
        """)

        colleges = cursor.fetchall()

        return jsonify([

            {
                "id": college[0],
                "name": college[1],
                "code": college[2]
            }

            for college in colleges

        ])

    except Exception as error:

        print(
            "College API Error:",
            error
        )

        return error_response(
            "Unable to load colleges.",
            500
        )

    finally:

        if cursor:
            cursor.close()

        if db:
            db.close()


@app.route("/api/classes", methods=["GET", "POST"])
def get_college_classes():
    if "user_id" not in session:
        return error_response("Login required.", 401)

    if request.method == "POST":
        denied = api_require_admin()
        if denied:
            return denied

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return error_response("Invalid class data.")

        try:
            college_id = int(data.get("college_id", ""))
        except (TypeError, ValueError):
            return error_response("Please select a valid college.")

        if college_id <= 0:
            return error_response("Please select a valid college.")

        course_name = (data.get("course_name") or data.get("course") or "").strip()
        course_code = (data.get("course_code") or course_name or "").strip().upper()
        academic_year = (data.get("academic_year") or "").strip()
        division = (data.get("division") or "").strip()

        try:
            semester = int(data.get("semester", 0))
            year_level = int(data.get("year_level", 0))
        except (TypeError, ValueError):
            return error_response("Semester and year level must be valid numbers.")

        if not course_name:
            return error_response("Course name is required.")
        if not course_code:
            return error_response("Course code is required.")
        if not academic_year:
            return error_response("Academic year is required.")
        if not division:
            return error_response("Division is required.")
        if semester <= 0:
            return error_response("Semester must be greater than zero.")
        if year_level <= 0:
            return error_response("Year level must be greater than zero.")

        db = cursor = None
        try:
            db = get_db()
            cursor = db.cursor(dictionary=True)

            cursor.execute("""
                SELECT id, name, code, is_active
                FROM colleges
                WHERE id = %s
                  AND is_active = 1
                LIMIT 1
            """, (college_id,))
            college = cursor.fetchone()
            if college is None:
                return error_response("Selected college is not active.")

            normalized_course_name = course_name.strip()
            normalized_course_code = course_code.strip()[:30] or normalized_course_name[:30]
            department_name = normalized_course_name
            department_code = normalized_course_code

            cursor.execute("""
                SELECT id
                FROM departments
                WHERE college_id = %s
                  AND (LOWER(code) = LOWER(%s) OR LOWER(name) = LOWER(%s))
                ORDER BY id
                LIMIT 1
            """, (college_id, department_code, department_name))
            department = cursor.fetchone()
            if department is None:
                cursor.execute("""
                    INSERT INTO departments (college_id, name, code, is_active)
                    VALUES (%s, %s, %s, 1)
                """, (college_id, department_name, department_code))
                department_id = cursor.lastrowid
            else:
                department_id = department["id"]

            cursor.execute("""
                SELECT id
                FROM courses
                WHERE college_id = %s
                  AND (LOWER(code) = LOWER(%s) OR LOWER(name) = LOWER(%s))
                LIMIT 1
            """, (college_id, normalized_course_code, normalized_course_name))
            existing_course = cursor.fetchone()
            if existing_course is None:
                cursor.execute("""
                    INSERT INTO courses (college_id, department_id, name, code, duration_years, is_active)
                    VALUES (%s, %s, %s, %s, %s, 1)
                """, (
                    college_id,
                    department_id,
                    normalized_course_name,
                    normalized_course_code,
                    max(1, int(year_level))
                ))
                course_id = cursor.lastrowid
            else:
                course_id = existing_course["id"]

            cursor.execute("""
                SELECT id
                FROM classes
                WHERE college_id = %s
                  AND course_id = %s
                  AND academic_year = %s
                  AND semester = %s
                  AND year_level = %s
                  AND division = %s
                LIMIT 1
            """, (college_id, course_id, academic_year, semester, year_level, division))
            existing_class = cursor.fetchone()
            if existing_class is not None:
                return error_response("This class already exists for this college.", 409)

            cursor.execute("""
                INSERT INTO classes (
                    college_id,
                    course_id,
                    academic_year,
                    semester,
                    year_level,
                    division
                )
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (college_id, course_id, academic_year, semester, year_level, division))
            class_id = cursor.lastrowid
            db.commit()
            return success_response(
                "Class created successfully.",
                class_id=class_id,
                class_info={
                    "id": class_id,
                    "course_id": course_id,
                    "course": normalized_course_name,
                    "academic_year": academic_year,
                    "semester": semester,
                    "year_level": year_level,
                    "division": division,
                }
            ), 201
        except mysql.connector.Error as error:
            if db:
                db.rollback()
            print("Class Creation Database Error:", error)
            return error_response("Unable to create class right now.", 500)
        except Exception as error:
            if db:
                db.rollback()
            print("Class Creation Error:", error)
            return error_response("Unable to create class right now.", 500)
        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    try:
        college_id = int(request.args.get("college_id", ""))
    except (TypeError, ValueError):
        return error_response("Please select a valid college.")

    if college_id <= 0:
        return error_response("Please select a valid college.")

    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT college_id, role
            FROM users
            WHERE id = %s
            LIMIT 1
        """, (session.get("user_id"),))
        account = cursor.fetchone()
        if account is None:
            return error_response("Authentication required.", 401)

        if account.get("role") != "admin" and int(account.get("college_id") or 0) != college_id:
            return error_response("You can only view classes for your college.", 403)

        cursor.execute("""
            SELECT
                c.id,
                c.college_id,
                c.course_id,
                co.name AS course,
                co.code AS course_code,
                c.academic_year,
                c.semester,
                c.year_level,
                c.division
            FROM classes c
            INNER JOIN courses co
                ON co.id = c.course_id
               AND co.college_id = c.college_id
            WHERE c.college_id = %s
              AND co.is_active = 1
            ORDER BY co.name, c.year_level, c.semester, c.division, c.academic_year
        """, (college_id,))
        return success_response("Classes loaded successfully.", classes=cursor.fetchall())
    except mysql.connector.Error as error:
        print("College Classes Database Error:", error)
        return error_response("Unable to load classes right now.", 500)
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@app.route("/api/departments", methods=["GET", "POST"])
def get_departments():

    denied = api_require_admin()
    if denied:
        return denied

    db = None
    cursor = None
    try:
        db = get_db()
        cursor = db.cursor(buffered=True)

        if request.method == "POST":
            data = request.get_json(silent=True)
            if not isinstance(data, dict):
                return error_response("Invalid department data.")

            college_code = data.get("college_code")
            name = data.get("name")
            code = data.get("code")
            is_active = data.get("is_active", True)

            if not isinstance(college_code, str) or not college_code.strip():
                return error_response("Please select a college.")
            if not isinstance(name, str) or not isinstance(code, str):
                return error_response("Department name and code must be text.")
            college_code = college_code.strip()
            name = name.strip()
            code = code.strip().upper()
            if not name or len(name) > 120:
                return error_response("Department name is required and must be 120 characters or fewer.")
            if not code or len(code) > 30:
                return error_response("Department code is required and must be 30 characters or fewer.")
            if not isinstance(is_active, bool):
                return error_response("Department active status must be true or false.")

            cursor.execute("""
                SELECT id
                FROM colleges
                WHERE code = %s
                  AND is_active = 1
                LIMIT 1
            """, (college_code,))
            college = cursor.fetchone()
            if college is None:
                return error_response("Selected college is not registered.")

            cursor.execute("""
                SELECT id
                FROM departments
                WHERE college_id = %s
                  AND code = %s
                LIMIT 1
            """, (college[0], code))
            if cursor.fetchone():
                return error_response(
                    "A department with this code already exists for the selected college.",
                    409
                )

            cursor.execute("""
                INSERT INTO departments (college_id, name, code, is_active)
                VALUES (%s, %s, %s, %s)
            """, (college[0], name, code, is_active))
            department_id = cursor.lastrowid
            db.commit()
            return success_response(
                "Department created successfully.",
                department={
                    "id": department_id,
                    "college_id": college[0],
                    "name": name,
                    "code": code,
                    "is_active": is_active
                }
            ), 201

        college_code = (request.args.get("college_code") or "").strip()
        if not college_code:
            return error_response("Please select a college.")

        cursor.execute("""
            SELECT id
            FROM colleges
            WHERE code = %s
              AND is_active = 1
            LIMIT 1
        """, (college_code,))
        college = cursor.fetchone()
        if college is None:
            return error_response("Selected college is not registered.")

        include_inactive = request.args.get("include_inactive") == "1"
        cursor.execute("""
            SELECT id, name, code, is_active
            FROM departments
            WHERE college_id = %s
              AND (%s = 1 OR is_active = 1)
            ORDER BY name, id
        """, (college[0], int(include_inactive)))
        departments = cursor.fetchall()
        return success_response(
            "Departments loaded successfully.",
            departments=[
                {
                    "id": item[0],
                    "name": item[1],
                    "code": item[2],
                    "is_active": bool(item[3])
                }
                for item in departments
            ]
        )
    except Exception as error:
        if db and request.method == "POST":
            db.rollback()
        if getattr(error, "errno", None) == 1062:
            return error_response(
                "A department with this code already exists for the selected college.",
                409
            )
        print("Departments API Error:", error)
        message = (
            "Unable to save department."
            if request.method == "POST"
            else "Unable to load departments."
        )
        return error_response(message, 500)
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


# ============================================================
# COLLEGE REQUEST - CREATE
# ============================================================

@app.route(
    "/api/college-requests",
    methods=["POST"]
)
def create_college_request():

    denied = api_require_admin()

    if denied:
        return denied

    data = request.get_json()

    if not data:

        return error_response(
            "Invalid request."
        )

    college_name = (
        data.get("collegeName")
        or ""
    ).strip()

    city = (
        data.get("city")
        or ""
    ).strip()

    requested_by = (
        data.get("requestedBy")
        or "Admin"
    ).strip()

    requested_email = (
        data.get("requestedEmail")
        or ""
    ).strip()

    if not college_name or not city:

        return error_response(
            "College name and city are required."
        )

    db = None
    cursor = None

    try:

        db = get_db()

        cursor = db.cursor(
            buffered=True
        )

        cursor.execute("""
            SELECT id
            FROM colleges
            WHERE LOWER(name) = LOWER(%s)
        """, (
            college_name,
        ))

        existing_college = cursor.fetchone()

        if existing_college:

            return error_response(
                "This college is already registered.",
                409
            )

        cursor.execute("""
            SELECT id
            FROM college_requests
            WHERE LOWER(college_name) = LOWER(%s)
            AND LOWER(city) = LOWER(%s)
            AND status = 'Pending'
        """, (
            college_name,
            city
        ))

        existing_request = cursor.fetchone()

        if existing_request:

            return error_response(
                "A request for this college is already pending.",
                409
            )

        cursor.execute("""
            INSERT INTO college_requests
            (
                college_name,
                city,
                requested_by,
                requested_email,
                status
            )
            VALUES (%s, %s, %s, %s, 'Pending')
        """, (
            college_name,
            city,
            requested_by,
            requested_email
        ))

        db.commit()

        return success_response(
            "College registration request sent to admin."
        )

    except Exception as error:

        if db:
            db.rollback()

        print(
            "College Request Error:",
            error
        )

        return error_response(
            "Unable to send college request.",
            500
        )

    finally:

        if cursor:
            cursor.close()

        if db:
            db.close()


# ============================================================
# COLLEGE REQUESTS - ADMIN LIST
# ============================================================

@app.route(
    "/api/college-requests",
    methods=["GET"]
)
def get_college_requests():

    if "user_id" not in session:

        return error_response(
            "Login required.",
            401
        )

    if session.get("role") != "admin":

        return error_response(
            "Access denied.",
            403
        )

    db = None
    cursor = None

    try:

        db = get_db()

        cursor = db.cursor(
            buffered=True
        )

        cursor.execute("""
            SELECT
                id,
                college_name,
                city,
                requested_by,
                requested_email,
                status,
                college_code,
                created_at
            FROM college_requests
            ORDER BY id DESC
        """)

        requests_data = cursor.fetchall()

        return jsonify([

            {
                "id": item[0],
                "collegeName": item[1],
                "city": item[2],
                "requestedBy": item[3],
                "requestedEmail": item[4],
                "status": item[5],
                "collegeCode": item[6],
                "createdAt": (
                    item[7].strftime(
                        "%d %b %Y, %I:%M %p"
                    )
                    if item[7]
                    else ""
                )
            }

            for item in requests_data

        ])

    except Exception as error:

        print(
            "College Requests Error:",
            error
        )

        return error_response(
            "Unable to load college requests.",
            500
        )

    finally:

        if cursor:
            cursor.close()

        if db:
            db.close()


# ============================================================
# APPROVE COLLEGE REQUEST
# ============================================================

@app.route(
    "/api/college-requests/<int:request_id>/approve",
    methods=["POST"]
)
def approve_college_request(request_id):

    if "user_id" not in session:

        return error_response(
            "Login required.",
            401
        )

    if session.get("role") != "admin":

        return error_response(
            "Access denied.",
            403
        )

    db = None
    cursor = None

    try:

        db = get_db()

        cursor = db.cursor(
            buffered=True
        )

        cursor.execute("""
            SELECT
                college_name,
                city,
                status
            FROM college_requests
            WHERE id = %s
        """, (
            request_id,
        ))

        college_request = cursor.fetchone()

        if college_request is None:

            return error_response(
                "College request not found.",
                404
            )

        college_name = college_request[0]

        status = college_request[2]

        if status != "Pending":

            return error_response(
                "This request has already been processed."
            )

        cursor.execute("""
            SELECT id
            FROM colleges
            WHERE LOWER(name) = LOWER(%s)
        """, (
            college_name,
        ))

        existing_college = cursor.fetchone()

        if existing_college:

            return error_response(
                "This college is already registered.",
                409
            )

        words = re.findall(
            r"[A-Za-z0-9]+",
            college_name.upper()
        )

        if words:

            prefix = "".join(
                word[0]
                for word in words
            )[:4]

        else:

            prefix = "CLG"

        if len(prefix) < 3:

            prefix = (
                prefix + "CLG"
            )[:4]

        base_code = prefix

        counter = 1

        college_code = (
            base_code
            + f"{counter:03d}"
        )

        while True:

            cursor.execute("""
                SELECT id
                FROM colleges
                WHERE code = %s
            """, (
                college_code,
            ))

            code_exists = cursor.fetchone()

            if code_exists is None:

                break

            counter += 1

            college_code = (
                base_code
                + f"{counter:03d}"
            )

        cursor.execute("""
            INSERT INTO colleges
            (name, code)
            VALUES (%s, %s)
        """, (
            college_name,
            college_code
        ))

        cursor.execute("""
            UPDATE college_requests
            SET
                status = 'Approved',
                college_code = %s,
                approved_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            college_code,
            request_id
        ))

        db.commit()

        return success_response(
            "College approved successfully.",
            collegeCode=college_code
        )

    except Exception as error:

        if db:
            db.rollback()

        print(
            "Approve College Error:",
            error
        )

        return error_response(
            "Unable to approve college.",
            500
        )

    finally:

        if cursor:
            cursor.close()

        if db:
            db.close()


# ============================================================
# REJECT COLLEGE REQUEST
# ============================================================

@app.route(
    "/api/college-requests/<int:request_id>/reject",
    methods=["POST"]
)
def reject_college_request(request_id):

    if "user_id" not in session:

        return error_response(
            "Login required.",
            401
        )

    if session.get("role") != "admin":

        return error_response(
            "Access denied.",
            403
        )

    db = None
    cursor = None

    try:

        db = get_db()

        cursor = db.cursor(
            buffered=True
        )

        cursor.execute("""
            SELECT status
            FROM college_requests
            WHERE id = %s
        """, (
            request_id,
        ))

        college_request = cursor.fetchone()

        if college_request is None:

            return error_response(
                "College request not found.",
                404
            )

        if college_request[0] != "Pending":

            return error_response(
                "This request has already been processed."
            )

        cursor.execute("""
            UPDATE college_requests
            SET status = 'Rejected'
            WHERE id = %s
        """, (
            request_id,
        ))

        db.commit()

        return success_response(
            "College request rejected."
        )

    except Exception as error:

        if db:
            db.rollback()

        print(
            "Reject College Error:",
            error
        )

        return error_response(
            "Unable to reject college request.",
            500
        )

    finally:

        if cursor:
            cursor.close()

        if db:
            db.close()


# ============================================================
# STUDENT API
# ============================================================

@app.route("/api/users/students")
def get_students():

    denied = api_require_admin()

    if denied:
        return denied

    db = None
    cursor = None

    try:

        db = get_db()

        cursor = db.cursor(
            buffered=True
        )

        cursor.execute("""
            SELECT
                u.id,
                COALESCE(NULLIF(u.full_name, ''), NULLIF(u.name, '')) AS full_name,
                u.email,
                c.name AS college
            FROM users u
            LEFT JOIN colleges c ON u.college_id = c.id
            WHERE u.role = 'student'
            ORDER BY u.id DESC
        """)

        students = cursor.fetchall()

        return jsonify([

            {
                "id": user[0],
                "name": user[1],
                "email": user[2],
                "college": user[3]
            }

            for user in students

        ])

    except Exception as error:

        print(
            "Student API Error:",
            error
        )

        return error_response(
            "Unable to load students.",
            500
        )

    finally:

        if cursor:
            cursor.close()

        if db:
            db.close()


# ============================================================
# FACULTY API
# ============================================================

@app.route("/api/users/faculty")
def get_faculty():

    denied = api_require_admin()

    if denied:
        return denied

    db = None
    cursor = None

    try:

        db = get_db()

        cursor = db.cursor(
            buffered=True
        )

        cursor.execute("""
            SELECT
                u.id,
                COALESCE(NULLIF(u.full_name, ''), NULLIF(u.name, '')) AS full_name,
                u.email,
                c.name AS college
            FROM users u
            LEFT JOIN colleges c ON c.id = u.college_id
            WHERE u.role = 'faculty'
            ORDER BY u.id DESC
        """)

        faculty = cursor.fetchall()

        return jsonify([

            {
                "id": user[0],
                "name": user[1],
                "email": user[2],
                "college": user[3]
            }

            for user in faculty

        ])

    except Exception as error:

        print(
            "Faculty API Error:",
            error
        )

        return error_response(
            "Unable to load faculty.",
            500
        )

    finally:

        if cursor:
            cursor.close()

        if db:
            db.close()


# ============================================================
# ADD USER API
# ============================================================

@app.route(
    "/api/users/add",
    methods=["POST"]
)
def add_user():

    denied = api_require_admin()

    if denied:
        return denied

    data = request.get_json()

    if not data:

        return error_response(
            "Invalid request."
        )

    name = (
        data.get("name")
        or ""
    ).strip()

    email = normalize_email(
        data.get("email")
    )

    mobile = normalize_mobile(
        data.get("mobile")
    )

    college = (
        data.get("college")
        or ""
    ).strip()

    role = (
        data.get("role")
        or ""
    ).strip()

    department_id = None
    student_class_id = None
    roll_number = None
    if role == "faculty":
        if isinstance(data.get("department_id"), bool):
            return error_response("Please select a valid faculty department.")
        try:
            department_id = int(data.get("department_id"))
        except (TypeError, ValueError):
            return error_response("Please select a valid faculty department.")
        if department_id <= 0:
            return error_response("Please select a valid faculty department.")
    elif role == "student":
        if isinstance(data.get("class_id"), bool):
            return error_response("Please select a valid student class.")
        try:
            student_class_id = int(data.get("class_id"))
        except (TypeError, ValueError):
            return error_response("Please select a valid student class.")
        roll_number = (data.get("roll_number") or "").strip()
        if student_class_id <= 0 or not roll_number or len(roll_number) > 50:
            return error_response("Please select a class and enter a valid roll number.")

    password = (
        data.get("password")
        or ""
    )

    if not name or not email or not college or not role or not password:

        return error_response(
            "Please fill all required fields."
        )

    if not valid_email(email):

        return error_response(
            "Please enter a valid email address."
        )

    if mobile and not valid_mobile(mobile):

        return error_response(
            "Please enter a valid mobile number."
        )

    if not valid_password(password):

        return error_response(
            f"Password must contain at least {PASSWORD_MIN_LENGTH} characters."
        )

    if role not in [
        "student",
        "faculty"
    ]:

        return error_response(
            "Invalid role."
        )

    if college == "OTHER":

        return error_response(
            "Other College must be approved by admin before creating a user."
        )

    db = None
    cursor = None

    try:

        db = get_db()

        cursor = db.cursor(
            buffered=True
        )

        cursor.execute("""
            SELECT id
            FROM users
            WHERE email = %s
        """, (
            email,
        ))

        if cursor.fetchone():

            return error_response(
                "Email already exists.",
                409
            )

        if mobile:

            cursor.execute("""
                SELECT id
                FROM users
                WHERE mobile = %s
            """, (
                mobile,
            ))

            if cursor.fetchone():

                return error_response(
                    "Mobile number already exists.",
                    409
                )

        cursor.execute("""
            SELECT
                id,
                name,
                code
            FROM colleges
            WHERE code = %s
        """, (
            college,
        ))

        college_data = cursor.fetchone()

        if college_data is None:

            return error_response(
                "Selected college is not registered."
            )

        if role == "faculty":
            cursor.execute("""
                SELECT id
                FROM departments
                WHERE id = %s
                  AND college_id = %s
                  AND is_active = 1
                LIMIT 1
            """, (
                department_id,
                college_data[0]
            ))
            if cursor.fetchone() is None:
                return error_response(
                    "Selected department is not active for this college."
                )

        hashed_password = (
            generate_password_hash(password)
        )

        user_id = insert_user_account(
            cursor,
            college_data[0],
            name,
            email,
            mobile or None,
            hashed_password,
            role
        )

        profile_error = create_user_profile(
            cursor,
            user_id,
            college_data[0],
            role,
            department_id,
            student_class_id,
            roll_number
        )
        if profile_error:
            db.rollback()
            return error_response(*profile_error)

        db.commit()

        return success_response(
            "User created successfully."
        )

    except Exception as error:

        if db:
            db.rollback()

        if getattr(error, "errno", None) == 1062:
            return error_response(
                "Email, mobile number, or roll number is already in use.",
                409
            )

        print(
            "Add User Error:",
            error
        )

        return error_response(
            "Unable to create user.",
            500
        )

    finally:

        if cursor:
            cursor.close()

        if db:
            db.close()


# ============================================================
# EDIT USER API
# ============================================================

@app.route(
    "/api/users/edit/<int:user_id>",
    methods=["PUT"]
)
def edit_user(user_id):

    denied = api_require_admin()

    if denied:
        return denied

    data = request.get_json()

    if not data:

        return error_response(
            "Invalid request."
        )

    name = (
        data.get("name")
        or ""
    ).strip()

    email = normalize_email(
        data.get("email")
    )

    mobile = normalize_mobile(
        data.get("mobile")
    )

    college = (
        data.get("college")
        or ""
    ).strip()

    if not name or not email or not college:

        return error_response(
            "Please fill all required fields."
        )

    if not valid_email(email):

        return error_response(
            "Please enter a valid email address."
        )

    if mobile and not valid_mobile(mobile):

        return error_response(
            "Please enter a valid mobile number."
        )

    db = None
    cursor = None

    try:

        db = get_db()

        cursor = db.cursor(
            buffered=True
        )

        cursor.execute("""
            SELECT id
            FROM users
            WHERE id = %s
            AND role != 'admin'
        """, (
            user_id,
        ))

        if cursor.fetchone() is None:

            return error_response(
                "User not found.",
                404
            )

        cursor.execute("""
            SELECT id
            FROM users
            WHERE email = %s
            AND id != %s
        """, (
            email,
            user_id
        ))

        if cursor.fetchone():

            return error_response(
                "Email already exists.",
                409
            )

        if mobile:

            cursor.execute("""
                SELECT id
                FROM users
                WHERE mobile = %s
                AND id != %s
            """, (
                mobile,
                user_id
            ))

            if cursor.fetchone():

                return error_response(
                    "Mobile number already exists.",
                    409
                )

        cursor.execute("""
            SELECT id
            FROM colleges
            WHERE code = %s
            LIMIT 1
        """, (college,))

        college_data = cursor.fetchone()

        # The current admin UI seeds this prompt with the college name,
        # while the prompt asks for the college code. Accept either value.
        if college_data is None:
            cursor.execute("""
                SELECT id
                FROM colleges
                WHERE name = %s
                LIMIT 1
            """, (college,))
            college_data = cursor.fetchone()

        if college_data is None:

            return error_response(
                "Selected college is not registered."
            )

        cursor.execute("""
            UPDATE users
            SET
                college_id = %s,
                full_name = %s,
                email = %s,
                mobile = %s
            WHERE id = %s
            AND role != 'admin'
        """, (
            college_data[0],
            name,
            email,
            mobile or None,
            user_id
        ))

        db.commit()

        return success_response(
            "User updated successfully."
        )

    except Exception as error:

        if db:
            db.rollback()

        print(
            "Edit User Error:",
            error
        )

        return error_response(
            "Unable to update user.",
            500
        )

    finally:

        if cursor:
            cursor.close()

        if db:
            db.close()


# ============================================================
# DELETE USER API
# ============================================================

@app.route(
    "/api/users/delete/<int:user_id>",
    methods=["DELETE"]
)
def delete_user(user_id):

    denied = api_require_admin()

    if denied:
        return denied

    db = None
    cursor = None

    try:

        db = get_db()

        cursor = db.cursor(
            buffered=True
        )

        cursor.execute("""
            DELETE FROM users
            WHERE id = %s
            AND role != 'admin'
        """, (
            user_id,
        ))

        db.commit()

        if cursor.rowcount == 0:

            return error_response(
                "User not found.",
                404
            )

        return success_response(
            "User deleted successfully."
        )

    except Exception as error:

        if db:
            db.rollback()

        print(
            "Delete User Error:",
            error
        )

        return error_response(
            "Unable to delete user.",
            500
        )

    finally:

        if cursor:
            cursor.close()

        if db:
            db.close()


# ============================================================
# LOGIN API
#
# IMPORTANT:
# College is NOT required.
# Role IS chosen on login and checked against MySQL.
#
# User chooses:
#
# Email
# OR
# Mobile Number
#
# Then enters password and role.
# ============================================================

@app.route(
    "/api/login",
    methods=["POST"]
)
def login():

    data = request.get_json()

    if not data:

        return error_response(
            "Invalid request."
        )

    login_type = (
        data.get("loginType")
        or ""
    ).strip().lower()

    identifier = (
        data.get("identifier")
        or ""
    ).strip()

    password = (
        data.get("password")
        or ""
    )

    selected_role = (
        data.get("role")
        or ""
    ).strip().lower()

    # --------------------------------------------------------
    # Validate login type
    # --------------------------------------------------------

    if login_type not in [
        "email",
        "mobile"
    ]:

        return error_response(
            "Please select Email or Mobile Number."
        )

    # --------------------------------------------------------
    # Normalize identifier
    # --------------------------------------------------------

    if login_type == "email":

        identifier = normalize_email(
            identifier
        )

        if not valid_email(identifier):

            return error_response(
                "Please enter a valid email address."
            )

    else:

        identifier = normalize_mobile(
            identifier
        )

        if not valid_mobile(identifier):

            return error_response(
                "Please enter a valid mobile number."
            )

    if not password:

        return error_response(
            "Please enter your password."
        )

    if selected_role not in [
        "student",
        "faculty",
        "admin"
    ]:

        return error_response(
            "Please select Student, Faculty, or Admin."
        )

    db = None
    cursor = None

    try:

        db = get_db()

        cursor = db.cursor(
            buffered=True
        )

        cursor.execute("SHOW COLUMNS FROM users LIKE 'updated_at'")
        has_updated_at = cursor.fetchone() is not None
        cursor.execute("SHOW COLUMNS FROM users LIKE 'password'")
        has_legacy_password = cursor.fetchone() is not None
        updated_at_select = "u.updated_at" if has_updated_at else "NULL"
        password_hash_select = (
            "COALESCE(NULLIF(u.password_hash, ''), NULLIF(u.password, ''))"
            if has_legacy_password else "u.password_hash"
        )

        # ----------------------------------------------------
        # Find user
        # ----------------------------------------------------

        if login_type == "email":

            cursor.execute(f"""
                SELECT
                    u.id,
                    COALESCE(NULLIF(u.full_name, ''), NULLIF(u.name, '')) AS full_name,
                    u.email,
                    u.mobile,
                    {password_hash_select} AS password_hash,
                    u.role,
                    u.college_id,
                    c.name AS college,
                    u.is_active,
                    u.status,
                    {updated_at_select} AS updated_at
                FROM users u
                LEFT JOIN colleges c ON c.id = u.college_id
                WHERE LOWER(u.email) = %s
                LIMIT 1
            """, (
                identifier,
            ))

        else:

            cursor.execute(f"""
                SELECT
                    u.id,
                    COALESCE(NULLIF(u.full_name, ''), NULLIF(u.name, '')) AS full_name,
                    u.email,
                    u.mobile,
                    {password_hash_select} AS password_hash,
                    u.role,
                    u.college_id,
                    c.name AS college,
                    u.is_active,
                    u.status,
                    {updated_at_select} AS updated_at
                FROM users u
                LEFT JOIN colleges c ON c.id = u.college_id
                WHERE u.mobile = %s
                LIMIT 1
            """, (
                identifier,
            ))

        user = cursor.fetchone()

        # ----------------------------------------------------
        # Generic login error
        # ----------------------------------------------------

        if user is None:

            return error_response(
                "No account was found with these details.",
                401
            )

        user_id = user[0]

        user_name = user[1]

        user_email = user[2]

        user_mobile = user[3]

        stored_password = user[4]

        role = user[5]

        college_id = user[6]

        college = user[7]

        is_active = user[8]

        account_status = user[9]

        account_updated_at = user[10]

        # ----------------------------------------------------
        # Account status
        # ----------------------------------------------------

        if not is_active or account_status != "active":

            return error_response(
                "Your account is inactive. Please contact college administration.",
                403
            )

        # ----------------------------------------------------
        # Verify password
        # ----------------------------------------------------

        password_valid, was_plaintext = (
            verify_user_password(
                stored_password,
                password
            )
        )

        if not password_valid:

            return error_response(
                "Wrong password. Please try again.",
                401
            )

        stored_role = (
            role or ""
        ).strip().lower()

        if stored_role != selected_role:

            return error_response(
                "This account does not match the selected role.",
                403
            )

        role = stored_role

        # ----------------------------------------------------
        # Automatically migrate old plaintext password
        # ----------------------------------------------------

        if was_plaintext:

            new_hash = (
                generate_password_hash(
                    password
                )
            )

            cursor.execute("""
                UPDATE users
                SET password_hash = %s
                WHERE id = %s
            """, (
                new_hash,
                user_id
            ))

            db.commit()
            stored_password = new_hash

            if has_updated_at:
                cursor.execute(
                    "SELECT updated_at FROM users WHERE id = %s LIMIT 1",
                    (user_id,)
                )
                updated_row = cursor.fetchone()
                if updated_row:
                    account_updated_at = updated_row[0]

        # ----------------------------------------------------
        # Clear old session
        # ----------------------------------------------------

        session.clear()

        # ----------------------------------------------------
        # Create authenticated session
        # ----------------------------------------------------

        session.permanent = True

        session["user_id"] = user_id

        session["user_name"] = user_name

        session["email"] = user_email

        session["mobile"] = user_mobile

        session["role"] = role

        session["college"] = college

        session["account_updated_at"] = account_session_version({
            "id": user_id,
            "college_id": college_id,
            "full_name": user_name,
            "email": user_email,
            "mobile": user_mobile,
            "password_hash": stored_password,
            "role": role,
            "is_active": is_active,
            "status": account_status,
            "updated_at": account_updated_at,
        })

        # ----------------------------------------------------
        # Dashboard
        # ----------------------------------------------------

        redirect_page = (
            f"{role}-dashboard.html"
        )

        return success_response(
            "Login successful!",
            name=user_name,
            role=role,
            college=college,
            redirect=redirect_page
        )

    except Exception as error:

        print(
            "Login Error:",
            error
        )

        return error_response(
            "Database connection failed.",
            500
        )

    finally:

        if cursor:
            cursor.close()

        if db:
            db.close()


# ============================================================
# REGISTER - SEND OTP
# ============================================================

@app.route(
    "/api/register/send-otp",
    methods=["POST"]
)
def register_send_otp():

    data = request.get_json()

    if not data:

        return error_response(
            "Invalid request."
        )

    full_name = (
        data.get("name")
        or data.get("fullName")
        or ""
    ).strip()

    register_method = (
        data.get("registerMethod")
        or ""
    ).strip().lower()

    identifier = (
        data.get("identifier")
        or ""
    ).strip()

    if not full_name:

        return error_response(
            "Please enter your full name."
        )

    if register_method not in [
        "email",
        "mobile"
    ]:

        return error_response(
            "Please choose Email or Mobile Number."
        )

    if register_method == "email":

        identifier = normalize_email(
            identifier
        )

        if not valid_email(identifier):

            return error_response(
                "Please enter a valid email address."
            )

        delivery_method = "email"

    else:

        identifier = normalize_mobile(
            identifier
        )

        if not valid_mobile(identifier):

            return error_response(
                "Please enter a valid mobile number."
            )

        delivery_method = "sms"

    db = None
    cursor = None

    try:

        db = get_db()

        cursor = db.cursor(
            buffered=True
        )

        if register_method == "email":

            cursor.execute("""
                SELECT id
                FROM users
                WHERE LOWER(email) = %s
                LIMIT 1
            """, (
                identifier,
            ))

        else:

            cursor.execute("""
                SELECT id
                FROM users
                WHERE mobile = %s
                LIMIT 1
            """, (
                identifier,
            ))

        if cursor.fetchone():

            return error_response(
                "An account already exists with these details. Please sign in.",
                409
            )

        cursor.execute("""
            SELECT created_at
            FROM auth_otps
            WHERE identifier = %s
            AND purpose = 'registration'
            ORDER BY created_at DESC
            LIMIT 1
        """, (
            identifier,
        ))

        last_otp = cursor.fetchone()

        cooldown = resend_cooldown_remaining(
            last_otp[0] if last_otp else None
        )

        if cooldown:

            return error_response(
                "Please wait "
                + str(cooldown)
                + " seconds before requesting another OTP.",
                429
            )

        otp = generate_otp()

        otp_hash = hash_otp(
            otp
        )

        expires_at = (
            datetime.now()
            + timedelta(
                minutes=OTP_EXPIRY_MINUTES
            )
        )

        cursor.execute("""
            UPDATE auth_otps
            SET used = 1
            WHERE identifier = %s
            AND purpose = 'registration'
            AND used = 0
        """, (
            identifier,
        ))

        cursor.execute("""
            INSERT INTO auth_otps
            (
                identifier,
                full_name,
                purpose,
                delivery_method,
                otp_hash,
                expires_at,
                attempts,
                used
            )
            VALUES
            (
                %s,
                %s,
                'registration',
                %s,
                %s,
                %s,
                0,
                0
            )
        """, (
            identifier,
            full_name,
            delivery_method,
            otp_hash,
            expires_at
        ))

        db.commit()

        delivered = False

        if register_method == "email":

            delivered = send_email_otp(
                identifier,
                otp,
                "registration"
            )

        else:

            delivered = send_mobile_otp(
                identifier,
                otp
            )

        if not delivered:

            cursor.execute("""
                UPDATE auth_otps
                SET used = 1
                WHERE identifier = %s
                AND purpose = 'registration'
                AND otp_hash = %s
            """, (
                identifier,
                otp_hash
            ))

            db.commit()

            return error_response(
                "Unable to send OTP. Please try again later.",
                500
            )

        extra = otp_delivery_payload(
            otp,
            delivery_method
        )

        extra["expiresIn"] = OTP_EXPIRY_MINUTES * 60

        return success_response(
            "Verification OTP has been sent.",
            **extra
        )

    except Exception as error:

        if db:
            db.rollback()

        print(
            "Register Send OTP Error:",
            error
        )

        return error_response(
            "Unable to send registration OTP.",
            500
        )

    finally:

        if cursor:
            cursor.close()

        if db:
            db.close()


# ============================================================
# REGISTER - VERIFY OTP
# ============================================================

@app.route(
    "/api/register/verify-otp",
    methods=["POST"]
)
def register_verify_otp():

    data = request.get_json()

    if not data:

        return error_response(
            "Invalid request."
        )

    register_method = (
        data.get("registerMethod")
        or ""
    ).strip().lower()

    identifier = (
        data.get("identifier")
        or ""
    ).strip()

    otp = (
        data.get("otp")
        or ""
    ).strip()

    if register_method == "email":

        identifier = normalize_email(
            identifier
        )

    else:

        identifier = normalize_mobile(
            identifier
        )

    if not re.fullmatch(
        r"[0-9]{6}",
        otp
    ):

        return error_response(
            "Please enter a valid 6-digit OTP."
        )

    db = None
    cursor = None

    try:

        db = get_db()

        cursor = db.cursor(
            buffered=True
        )

        cursor.execute("""
            SELECT
                id,
                otp_hash,
                expires_at,
                attempts,
                used,
                verified_at
            FROM auth_otps
            WHERE identifier = %s
            AND purpose = 'registration'
            AND used = 0
            ORDER BY id DESC
            LIMIT 1
            FOR UPDATE
        """, (
            identifier,
        ))

        otp_row = cursor.fetchone()

        if otp_row is None:

            return error_response(
                "OTP is invalid or expired."
            )

        otp_id = otp_row[0]

        stored_otp_hash = otp_row[1]

        expires_at = otp_row[2]

        attempts = otp_row[3]
        verified_at = otp_row[5]

        if verified_at is not None:
            return error_response("OTP is invalid or expired.")

        if datetime.now() > expires_at:

            cursor.execute("""
                UPDATE auth_otps
                SET used = 1
                WHERE id = %s
            """, (
                otp_id,
            ))

            db.commit()

            return error_response(
                "OTP has expired. Please request a new OTP."
            )

        if attempts >= MAX_OTP_ATTEMPTS:

            cursor.execute("""
                UPDATE auth_otps
                SET used = 1
                WHERE id = %s
            """, (
                otp_id,
            ))

            db.commit()

            return error_response(
                "Too many incorrect attempts. Please request a new OTP."
            )

        entered_hash = hash_otp(
            otp
        )

        if not secrets.compare_digest(
            entered_hash,
            stored_otp_hash
        ):

            cursor.execute("""
                UPDATE auth_otps
                SET attempts = attempts + 1
                WHERE id = %s
            """, (
                otp_id,
            ))

            db.commit()

            remaining = (
                MAX_OTP_ATTEMPTS
                - attempts
                - 1
            )

            return error_response(
                "Incorrect OTP. "
                + str(remaining)
                + " attempts remaining."
            )

        verification_token = secrets.token_urlsafe(32)
        cursor.execute("""
            UPDATE auth_otps
            SET otp_hash = %s, verified_at = %s
            WHERE id = %s AND used = 0 AND verified_at IS NULL
        """, (
            hash_otp(verification_token),
            datetime.now(),
            otp_id
        ))
        if cursor.rowcount != 1:
            db.rollback()
            return error_response("OTP is invalid or expired.")

        db.commit()

        return success_response(
            "OTP verified successfully.",
            verificationToken=verification_token
        )

    except Exception as error:

        print(
            "Register Verify OTP Error:",
            error
        )

        return error_response(
            "Unable to verify OTP.",
            500
        )

    finally:

        if cursor:
            cursor.close()

        if db:
            db.close()


# ============================================================
# REGISTER - CREATE ACCOUNT
# ============================================================

@app.route(
    "/api/register",
    methods=["POST"]
)
def register_user():

    data = request.get_json()

    if not data:

        return error_response(
            "Invalid request."
        )

    full_name = (
        data.get("name")
        or data.get("fullName")
        or ""
    ).strip()

    register_method = (
        data.get("registerMethod")
        or ""
    ).strip().lower()

    identifier = (
        data.get("identifier")
        or ""
    ).strip()

    verification_token = data.get("verificationToken") or ""
    if not isinstance(verification_token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", verification_token):
        return error_response("Please verify the OTP before creating your account.")

    password = (
        data.get("password")
        or ""
    )

    confirm_password = (
        data.get("confirmPassword")
        or ""
    )

    if not full_name:

        return error_response(
            "Please enter your full name."
        )

    if register_method not in [
        "email",
        "mobile"
    ]:

        return error_response(
            "Please choose Email or Mobile Number."
        )

    if register_method == "email":

        identifier = normalize_email(
            identifier
        )

        if not valid_email(identifier):

            return error_response(
                "Please enter a valid email address."
            )

        email = identifier

        mobile = None

    else:

        identifier = normalize_mobile(
            identifier
        )

        if not valid_mobile(identifier):

            return error_response(
                "Please enter a valid mobile number."
            )

        email = None

        mobile = identifier

    if not valid_password(password):

        return error_response(
            "Password must contain at least "
            + str(PASSWORD_MIN_LENGTH)
            + " characters."
        )

    if password != confirm_password:

        return error_response(
            "Passwords do not match."
        )

    try:

        college_id = int(
            data.get("college_id")
        )

    except (TypeError, ValueError):

        return error_response(
            "Please select your college."
        )

    if college_id <= 0:

        return error_response(
            "Please select your college."
        )

    if isinstance(data.get("class_id"), bool):
        return error_response("Please select a valid class.")
    try:
        student_class_id = int(data.get("class_id"))
    except (TypeError, ValueError):
        return error_response("Please select a valid class.")

    roll_number = (data.get("roll_number") or "").strip()
    if student_class_id <= 0 or not roll_number or len(roll_number) > 50:
        return error_response("Please select a class and enter a valid roll number.")

    db = None
    cursor = None

    try:

        db = get_db()

        cursor = db.cursor(
            buffered=True
        )

        cursor.execute("""
            SELECT
                id,
                name
            FROM colleges
            WHERE id = %s
            AND is_active = 1
            LIMIT 1
        """, (
            college_id,
        ))

        college_row = cursor.fetchone()

        if college_row is None:

            return error_response(
                "Please select a valid college."
            )

        college_id = college_row[0]

        college_name = college_row[1]

        cursor.execute("""
            SELECT
                id,
                full_name,
                verified_at,
                expires_at,
                used
            FROM auth_otps
            WHERE identifier = %s
            AND purpose = 'registration'
            AND otp_hash = %s
            AND used = 0
            ORDER BY id DESC
            LIMIT 1
            FOR UPDATE
        """, (
            identifier,
            hash_otp(verification_token)
        ))

        otp_row = cursor.fetchone()

        if (
            otp_row is None
            or otp_row[2] is None
        ):

            return error_response(
                "Please verify the OTP before creating your account."
            )

        otp_id = otp_row[0]

        stored_name = otp_row[1] or full_name

        expires_at = otp_row[3]

        if datetime.now() > expires_at:

            cursor.execute("""
                UPDATE auth_otps
                SET used = 1
                WHERE id = %s
            """, (
                otp_id,
            ))

            db.commit()

            return error_response(
                "OTP has expired. Please request a new OTP."
            )

        if register_method == "email":

            cursor.execute("""
                SELECT id
                FROM users
                WHERE LOWER(email) = %s
                LIMIT 1
            """, (
                identifier,
            ))

        else:

            cursor.execute("""
                SELECT id
                FROM users
                WHERE mobile = %s
                LIMIT 1
            """, (
                identifier,
            ))

        if cursor.fetchone():

            return error_response(
                "An account already exists with these details. Please sign in.",
                409
            )

        hashed_password = generate_password_hash(
            password
        )

        user_id = insert_user_account(
            cursor,
            college_id,
            stored_name,
            email,
            mobile,
            hashed_password,
            "student"
        )

        profile_error = create_user_profile(
            cursor,
            user_id,
            college_id,
            "student",
            class_id=student_class_id,
            roll_number=roll_number
        )
        if profile_error:
            db.rollback()
            return error_response(*profile_error)

        cursor.execute("""
            UPDATE auth_otps
            SET used = 1
            WHERE id = %s
        """, (
            otp_id,
        ))

        db.commit()

        return success_response(
            "Account created successfully. You can now sign in."
        )

    except Exception as error:

        if db:
            db.rollback()

        if getattr(error, "errno", None) == 1062:
            return error_response(
                "Email, mobile number, or roll number is already in use.",
                409
            )

        print(
            "Register Error:",
            error
        )

        return error_response(
            "Unable to create account.",
            500
        )

    finally:

        if cursor:
            cursor.close()

        if db:
            db.close()


# ============================================================
# FORGOT PASSWORD - SEND OTP
# ============================================================

@app.route(
    "/api/auth/forgot-password",
    methods=["POST"]
)
def forgot_password():

    data = request.get_json()

    if not data:

        return error_response(
            "Invalid request."
        )

    login_type = (
        data.get("loginType")
        or ""
    ).strip().lower()

    identifier = (
        data.get("identifier")
        or ""
    ).strip()

    if login_type not in [
        "email",
        "mobile"
    ]:

        return error_response(
            "Please select Email or Mobile Number."
        )

    if login_type == "email":

        identifier = normalize_email(
            identifier
        )

        if not valid_email(identifier):

            return error_response(
                "Please enter a valid email address."
            )

    else:

        identifier = normalize_mobile(
            identifier
        )

        if not valid_mobile(identifier):

            return error_response(
                "Please enter a valid mobile number."
            )

    db = None
    cursor = None

    try:

        db = get_db()

        cursor = db.cursor(
            buffered=True
        )

        # ----------------------------------------------------
        # Find account
        # ----------------------------------------------------

        if login_type == "email":

            cursor.execute("""
                SELECT
                    id,
                    email,
                    mobile,
                    is_active
                FROM users
                WHERE LOWER(email) = %s
                LIMIT 1
            """, (
                identifier,
            ))

        else:

            cursor.execute("""
                SELECT
                    id,
                    email,
                    mobile,
                    is_active
                FROM users
                WHERE mobile = %s
                LIMIT 1
            """, (
                identifier,
            ))

        user = cursor.fetchone()

        # ----------------------------------------------------
        # Security:
        # Do not reveal whether account exists in production.
        # ----------------------------------------------------

        if user is None:

            return success_response(
                "If an account exists, a verification OTP has been sent.",
                expiresIn=OTP_EXPIRY_MINUTES * 60
            )

        user_id = user[0]

        email = user[1]

        mobile = user[2]

        is_active = user[3]

        if not is_active:

            return success_response(
                "If an account exists, a verification OTP has been sent.",
                expiresIn=OTP_EXPIRY_MINUTES * 60
            )

        cursor.execute("""
            SELECT created_at
            FROM password_resets
            WHERE identifier = %s
            ORDER BY created_at DESC
            LIMIT 1
        """, (
            identifier,
        ))

        last_reset = cursor.fetchone()

        cooldown = resend_cooldown_remaining(
            last_reset[0] if last_reset else None
        )

        if cooldown:

            return success_response(
                "If an account exists, a verification OTP has been sent.",
                expiresIn=OTP_EXPIRY_MINUTES * 60
            )

        # ----------------------------------------------------
        # Generate OTP
        # ----------------------------------------------------

        otp = generate_otp()

        otp_hash = hash_otp(
            otp
        )

        expires_at = (
            datetime.now()
            + timedelta(
                minutes=OTP_EXPIRY_MINUTES
            )
        )

        # ----------------------------------------------------
        # Invalidate previous reset requests
        # ----------------------------------------------------

        cursor.execute("""
            UPDATE password_resets
            SET used = 1
            WHERE user_id = %s
            AND used = 0
        """, (
            user_id,
        ))

        # ----------------------------------------------------
        # Store OTP hash
        # ----------------------------------------------------

        cursor.execute("""
            INSERT INTO password_resets
            (
                user_id,
                identifier,
                otp_hash,
                expires_at,
                attempts,
                used
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                0,
                0
            )
        """, (
            user_id,
            identifier,
            otp_hash,
            expires_at
        ))

        db.commit()

        # ----------------------------------------------------
        # Deliver OTP
        # ----------------------------------------------------

        delivered = False

        if login_type == "email":

            delivered = send_email_otp(
                email,
                otp,
                "password_reset"
            )

        else:

            delivered = send_mobile_otp(
                mobile,
                otp
            )

        if not delivered:

            cursor.execute("""
                DELETE FROM password_resets
                WHERE user_id = %s
                AND otp_hash = %s
            """, (
                user_id,
                otp_hash
            ))

            db.commit()

            return success_response(
                "If an account exists, a verification OTP has been sent.",
                expiresIn=OTP_EXPIRY_MINUTES * 60
            )

        return success_response(
            "If an account exists, a verification OTP has been sent.",
            expiresIn=OTP_EXPIRY_MINUTES * 60
        )

    except Exception as error:

        if db:
            db.rollback()

        print(
            "Forgot Password Error:",
            error
        )

        return error_response(
            "Unable to process password recovery.",
            500
        )

    finally:

        if cursor:
            cursor.close()

        if db:
            db.close()


# ============================================================
# VERIFY OTP
# ============================================================

@app.route(
    "/api/auth/verify-otp",
    methods=["POST"]
)
def verify_otp():

    data = request.get_json()

    if not data:

        return error_response(
            "Invalid request."
        )

    login_type = (
        data.get("loginType")
        or ""
    ).strip().lower()

    identifier = (
        data.get("identifier")
        or ""
    ).strip()

    otp = (
        data.get("otp")
        or ""
    ).strip()

    if login_type not in [
        "email",
        "mobile"
    ]:

        return error_response(
            "Invalid verification method."
        )

    if login_type == "email":

        identifier = normalize_email(
            identifier
        )

    else:

        identifier = normalize_mobile(
            identifier
        )

    if not re.fullmatch(
        r"[0-9]{6}",
        otp
    ):

        return error_response(
            "Please enter a valid 6-digit OTP."
        )

    db = None
    cursor = None

    try:

        db = get_db()

        cursor = db.cursor(
            buffered=True
        )

        cursor.execute("""
            SELECT
                id,
                user_id,
                otp_hash,
                expires_at,
                attempts,
                used
            FROM password_resets
            WHERE identifier = %s
            AND used = 0
            ORDER BY id DESC
            LIMIT 1
            FOR UPDATE
        """, (
            identifier,
        ))

        reset_request = cursor.fetchone()

        if reset_request is None:

            return error_response(
                "OTP is invalid or expired.",
                400
            )

        reset_id = reset_request[0]

        user_id = reset_request[1]

        stored_otp_hash = reset_request[2]

        expires_at = reset_request[3]

        attempts = reset_request[4]

        used = reset_request[5]

        if stored_otp_hash.startswith("reset:"):
            return error_response("OTP is invalid or expired.", 400)

        # ----------------------------------------------------
        # Expiry
        # ----------------------------------------------------

        if datetime.now() > expires_at:

            cursor.execute("""
                UPDATE password_resets
                SET used = 1
                WHERE id = %s
            """, (
                reset_id,
            ))

            db.commit()

            return error_response(
                "OTP has expired. Please request a new OTP."
            )

        # ----------------------------------------------------
        # Attempts
        # ----------------------------------------------------

        if attempts >= MAX_OTP_ATTEMPTS:

            cursor.execute("""
                UPDATE password_resets
                SET used = 1
                WHERE id = %s
            """, (
                reset_id,
            ))

            db.commit()

            return error_response(
                "Too many incorrect attempts. Please request a new OTP."
            )

        # ----------------------------------------------------
        # Verify hash
        # ----------------------------------------------------

        entered_hash = hash_otp(
            otp
        )

        if not secrets.compare_digest(
            entered_hash,
            stored_otp_hash
        ):

            cursor.execute("""
                UPDATE password_resets
                SET attempts = attempts + 1
                WHERE id = %s
            """, (
                reset_id,
            ))

            db.commit()

            remaining = (
                MAX_OTP_ATTEMPTS
                - attempts
                - 1
            )

            return error_response(
                f"Incorrect OTP. {remaining} attempts remaining."
            )

        # ----------------------------------------------------
        # OTP correct
        # ----------------------------------------------------

        reset_token = secrets.token_urlsafe(32)
        cursor.execute("""
            UPDATE password_resets
            SET otp_hash = %s
            WHERE id = %s AND used = 0
        """, (
            "reset:" + hash_otp(reset_token),
            reset_id
        ))
        if cursor.rowcount != 1:
            db.rollback()
            return error_response("OTP is invalid or expired.", 400)
        db.commit()

        return success_response(
            "OTP verified successfully.",
            resetToken=reset_token
        )

    except Exception as error:

        print(
            "OTP Verification Error:",
            error
        )

        return error_response(
            "Unable to verify OTP.",
            500
        )

    finally:

        if cursor:
            cursor.close()

        if db:
            db.close()


# ============================================================
# RESET PASSWORD
# ============================================================

@app.route(
    "/api/auth/reset-password",
    methods=["POST"]
)
def reset_password():

    data = request.get_json()

    if not data:

        return error_response(
            "Invalid request."
        )

    reset_token = (
        data.get("resetToken")
        or ""
    ).strip()

    new_password = (
        data.get("newPassword")
        or ""
    )

    confirm_password = (
        data.get("confirmPassword")
        or ""
    )

    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", reset_token):

        return error_response(
            "Invalid password reset session."
        )

    if not valid_password(
        new_password
    ):

        return error_response(
            f"Password must contain at least {PASSWORD_MIN_LENGTH} characters."
        )

    if new_password != confirm_password:

        return error_response(
            "Passwords do not match."
        )

    db = None
    cursor = None

    try:

        db = get_db()

        cursor = db.cursor(
            buffered=True
        )

        cursor.execute("""
            SELECT
                id,
                user_id,
                expires_at,
                attempts,
                used
            FROM password_resets
            WHERE otp_hash = %s
              AND used = 0
            LIMIT 1
            FOR UPDATE
        """, (
            "reset:" + hash_otp(reset_token),
        ))

        reset_request = cursor.fetchone()

        if reset_request is None:

            return error_response(
                "Invalid password reset session."
            )

        reset_id = reset_request[0]

        user_id = reset_request[1]

        expires_at = reset_request[2]

        used = reset_request[4]

        if used:

            return error_response(
                "This password reset session has already been used."
            )

        if datetime.now() > expires_at:

            cursor.execute("""
                UPDATE password_resets
                SET used = 1
                WHERE id = %s
            """, (
                reset_id,
            ))

            db.commit()

            return error_response(
                "Password reset session expired. Please request a new OTP."
            )

        # ----------------------------------------------------
        # Hash new password
        # ----------------------------------------------------

        new_password_hash = (
            generate_password_hash(
                new_password
            )
        )

        # ----------------------------------------------------
        # Update password
        # ----------------------------------------------------

        cursor.execute("""
            UPDATE users
            SET password_hash = %s
            WHERE id = %s
        """, (
            new_password_hash,
            user_id
        ))

        # ----------------------------------------------------
        # Mark reset request used
        # ----------------------------------------------------

        cursor.execute("""
            UPDATE password_resets
            SET used = 1
            WHERE id = %s
        """, (
            reset_id,
        ))

        db.commit()

        return success_response(
            "Password reset successfully. You can now login."
        )

    except Exception as error:

        if db:
            db.rollback()

        print(
            "Reset Password Error:",
            error
        )

        return error_response(
            "Unable to reset password.",
            500
        )

    finally:

        if cursor:
            cursor.close()

        if db:
            db.close()

# ============================================================
# STUDENT ATTENDANCE API
# ============================================================

@app.route(
    "/api/student/attendance",
    methods=["GET"]
)
def student_attendance():

    if "user_id" not in session:
        return error_response(
            "Please login first.",
            401
        )

    if session.get("role") != "student":
        return error_response(
            "Student access required.",
            403
        )

    db = None
    cursor = None

    try:

        db = get_db()

        cursor = db.cursor(dictionary=True)

        user_id = session.get("user_id")

        # ----------------------------------------------------
        # Find logged-in student's record
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT
                s.id,
                s.class_id,
                s.roll_number AS roll_no,
                c.college_id,
                c.year_level,
                c.academic_year,
                c.semester,
                c.division,
                co.name AS course
            FROM students s
            INNER JOIN users u ON u.id = s.user_id
            INNER JOIN classes c ON c.id = s.class_id
                AND c.college_id = u.college_id
            INNER JOIN courses co ON co.id = c.course_id
                AND co.college_id = c.college_id
            WHERE u.id = %s
              AND u.role = 'student'
            LIMIT 1
            """,
            (user_id,)
        )

        student = cursor.fetchone()

        if not student:
            return error_response(
                "Student profile not found.",
                404
            )

        student_id = student["id"]

        # ----------------------------------------------------
        # Subject-wise attendance
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT
                s.id AS subject_id,
                s.name AS subject_name,
                s.code AS subject_code,

                COUNT(a.id) AS total_classes,

                SUM(
                    CASE
                        WHEN a.status IN ('present', 'late')
                        THEN 1
                        ELSE 0
                    END
                ) AS attended_classes

            FROM class_subjects cs

            INNER JOIN classes c
                ON c.id = cs.class_id

            INNER JOIN subjects s
                ON s.id = cs.subject_id

            LEFT JOIN attendance a
                ON a.class_subject_id = cs.id
                AND a.student_id = %s

            WHERE cs.class_id = %s

            GROUP BY
                s.id,
                s.name,
                s.code

            ORDER BY s.id
            """,
            (
                student_id,
                student["class_id"]
            )
        )

        subjects = cursor.fetchall()

        # ----------------------------------------------------
        # Calculate percentages
        # ----------------------------------------------------

        total_classes = 0
        total_attended = 0

        attendance_list = []

        for item in subjects:

            total = int(
                item["total_classes"] or 0
            )

            attended = int(
                item["attended_classes"] or 0
            )

            percentage = (
                round(
                    (attended / total) * 100,
                    1
                )
                if total > 0
                else 0
            )

            total_classes += total
            total_attended += attended

            attendance_list.append({
                "subject_id": item["subject_id"],
                "subject": item["subject_name"],
                "code": item["subject_code"],
                "total_classes": total,
                "present": attended,
                "attendance": percentage
            })

        overall = (
            round(
                (total_attended / total_classes) * 100,
                1
            )
            if total_classes > 0
            else 0
        )

        return success_response(
            "Attendance loaded successfully.",
            student={
                "name": session.get("user_name"),
                "roll_no": student["roll_no"],
                "course": student["course"],
                "year": student["year_level"],
                "division": student["division"],
                "academic_year": student["academic_year"],
                "semester": student["semester"]
            },
            overall_attendance=overall,
            total_classes=total_classes,
            total_attended=total_attended,
            attendance=attendance_list
        )

    except Exception as error:

        print(
            "Student Attendance Error:",
            error
        )

        return error_response(
            "Unable to load attendance.",
            500
        )

    finally:

        if cursor:
            cursor.close()

        if db:
            db.close()
# ============================================================
# LOGOUT
# ============================================================

@app.route(
    "/api/logout",
    methods=["POST"]
)
def logout():

    session.clear()

    return success_response(
        "Logged out successfully."
    )


@app.route(
    "/logout",
    methods=["POST"]
)
def logout_and_redirect():

    session.clear()

    return redirect(
        "/login.html"
    )


# ============================================================
# CURRENT USER
# ============================================================

@app.route(
    "/api/auth/me",
    methods=["GET"]
)
def current_user():

    if "user_id" not in session:

        return error_response(
            "Not authenticated.",
            401
        )

    return success_response(
        "Authenticated.",
        user={
            "id": session.get("user_id"),
            "name": session.get("user_name"),
            "email": session.get("email"),
            "mobile": session.get("mobile"),
            "role": session.get("role"),
            "college": session.get("college"),
            "admin_managed": bool(session.get("admin_management"))
        }
    )



# ============================================================
# STUDENT MARKS / PERFORMANCE
# ============================================================

@app.route(
    "/api/student/marks",
    methods=["GET"]
)
def student_marks():

    if "user_id" not in session:
        return error_response("Not authenticated.", 401)

    if session.get("role") != "student":
        return error_response("Student access required.", 403)

    db = None
    cursor = None

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                s.id AS student_id,
                s.class_id,
                s.roll_number,
                c.college_id,
                c.course_id,
                c.academic_year,
                c.semester,
                c.year_level,
                c.division,
                co.name AS course
            FROM students s
            INNER JOIN users u ON u.id = s.user_id
            INNER JOIN classes c ON c.id = s.class_id
                AND c.college_id = u.college_id
            INNER JOIN courses co ON co.id = c.course_id
                AND co.college_id = c.college_id
            WHERE u.id = %s
              AND u.role = 'student'
              AND u.is_active = TRUE
            LIMIT 1
        """, (session.get("user_id"),))

        student = cursor.fetchone()

        if not student:
            return error_response("Student profile was not found.", 404)

        cursor.execute("""
            SELECT
                m.id,
                m.exam_type,
                m.marks_obtained,
                m.max_marks,
                m.created_at,
                sub.id AS subject_id,
                sub.name AS subject_name,
                sub.code AS subject_code
            FROM marks m
            INNER JOIN subjects sub ON sub.id = m.subject_id
            INNER JOIN class_subjects cs
                ON cs.subject_id = sub.id
               AND cs.class_id = %s
            WHERE m.student_id = %s
              AND sub.college_id = %s
            ORDER BY sub.name ASC, m.exam_type ASC, m.id ASC
        """, (
            student["class_id"],
            student["student_id"],
            student["college_id"]
        ))

        rows = cursor.fetchall()
        records = []
        subject_map = {}
        total_obtained = 0.0
        total_max = 0.0

        for row in rows:
            obtained = float(row["marks_obtained"] or 0)
            maximum = float(row["max_marks"] or 0)
            percentage = round((obtained / maximum) * 100, 1) if maximum > 0 else 0

            records.append({
                "id": row["id"],
                "subject_id": row["subject_id"],
                "subject_name": row["subject_name"],
                "subject_code": row["subject_code"],
                "exam_type": row["exam_type"],
                "marks_obtained": obtained,
                "max_marks": maximum,
                "percentage": percentage
            })

            key = row["subject_id"]
            if key not in subject_map:
                subject_map[key] = {
                    "subject_id": row["subject_id"],
                    "subject_name": row["subject_name"],
                    "subject_code": row["subject_code"],
                    "marks_obtained": 0.0,
                    "max_marks": 0.0
                }

            subject_map[key]["marks_obtained"] += obtained
            subject_map[key]["max_marks"] += maximum
            total_obtained += obtained
            total_max += maximum

        subjects = []
        for item in subject_map.values():
            subject_percentage = (
                round((item["marks_obtained"] / item["max_marks"]) * 100, 1)
                if item["max_marks"] > 0 else 0
            )
            subjects.append({
                "subject_id": item["subject_id"],
                "subject_name": item["subject_name"],
                "subject_code": item["subject_code"],
                "marks_obtained": round(item["marks_obtained"], 2),
                "max_marks": round(item["max_marks"], 2),
                "percentage": subject_percentage
            })

        overall_percentage = (
            round((total_obtained / total_max) * 100, 1)
            if total_max > 0 else 0
        )

        return success_response(
            "Marks loaded successfully.",
            summary={
                "total_obtained": round(total_obtained, 2),
                "total_max": round(total_max, 2),
                "percentage": overall_percentage,
                "subject_count": len(subjects)
            },
            subjects=subjects,
            records=records
        )

    except mysql.connector.Error as error:
        print("Student Marks Database Error:", error)
        return error_response("Unable to load marks right now.", 500)

    except Exception as error:
        print("Student Marks Error:", error)
        return error_response("Unable to load marks right now.", 500)

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


# ============================================================
# FACULTY MARKS - SAVE
# ============================================================

@app.route(
    "/api/faculty/marks",
    methods=["GET", "POST"]
)
def save_faculty_marks():

    if "user_id" not in session:
        return error_response("Not authenticated.", 401)

    if session.get("role") != "faculty":
        return error_response("Faculty access required.", 403)

    if request.method == "GET":
        try:
            class_subject_id = int(request.args.get("class_subject_id", ""))
        except (TypeError, ValueError):
            return error_response("Please select an assigned class and subject.")
        if class_subject_id <= 0:
            return error_response("Please select an assigned class and subject.")

        db = cursor = None
        try:
            db = get_db()
            cursor = db.cursor(dictionary=True)
            cursor.execute("""
                SELECT f.id AS faculty_id, u.college_id
                FROM faculty f
                INNER JOIN users u ON u.id = f.user_id
                WHERE u.id = %s
                  AND u.role = 'faculty'
                  AND u.is_active = TRUE
                  AND u.status = 'active'
                LIMIT 1
            """, (session.get("user_id"),))
            faculty = cursor.fetchone()
            if not faculty:
                return error_response("Faculty account was not found.", 403)

            cursor.execute("""
                SELECT cs.id, cs.class_id, cs.subject_id
                FROM class_subjects cs
                INNER JOIN classes c ON c.id = cs.class_id
                INNER JOIN subjects sub ON sub.id = cs.subject_id
                INNER JOIN courses co ON co.id = c.course_id
                WHERE cs.id = %s
                  AND cs.faculty_id = %s
                  AND c.college_id = %s
                  AND co.college_id = c.college_id
                  AND sub.college_id = c.college_id
                  AND sub.course_id = c.course_id
                  AND sub.semester = c.semester
                LIMIT 1
            """, (
                class_subject_id,
                faculty["faculty_id"],
                faculty["college_id"]
            ))
            class_subject = cursor.fetchone()
            if not class_subject:
                return error_response(
                    "Class subject not found or not assigned to you.",
                    403
                )

            cursor.execute("""
                SELECT
                    m.id,
                    m.student_id,
                    s.roll_number,
                    COALESCE(NULLIF(su.full_name, ''), NULLIF(su.name, '')) AS student_name,
                    m.subject_id,
                    sub.name AS subject_name,
                    sub.code AS subject_code,
                    m.exam_type,
                    m.marks_obtained,
                    m.max_marks,
                    m.created_at
                FROM marks m
                INNER JOIN students s ON s.id = m.student_id
                    AND s.class_id = %s
                INNER JOIN users su ON su.id = s.user_id
                    AND su.college_id = %s
                    AND su.role = 'student'
                INNER JOIN subjects sub ON sub.id = m.subject_id
                    AND sub.id = %s
                    AND sub.college_id = %s
                INNER JOIN classes c ON c.id = s.class_id
                WHERE c.college_id = %s
                ORDER BY su.full_name, su.name, s.roll_number, m.created_at DESC, m.id DESC
            """, (
                class_subject["class_id"],
                faculty["college_id"],
                class_subject["subject_id"],
                faculty["college_id"],
                faculty["college_id"]
            ))
            records = cursor.fetchall()
            for row in records:
                row["marks_obtained"] = float(row["marks_obtained"])
                row["max_marks"] = float(row["max_marks"])
                if row.get("created_at"):
                    row["created_at"] = row["created_at"].isoformat()
            return success_response("Marks loaded successfully.", records=records)
        except mysql.connector.Error as error:
            print("Faculty Marks List Database Error:", error)
            return error_response("Unable to load marks right now.", 500)
        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    data = request.get_json() or {}

    student_id = data.get("student_id")
    subject_id = data.get("subject_id")
    exam_type = (data.get("exam_type") or "").strip()
    marks_obtained = data.get("marks_obtained")
    max_marks = data.get("max_marks")

    if not student_id or not subject_id or not exam_type:
        return error_response("Student, subject and exam type are required.")

    try:
        student_id = int(student_id)
        subject_id = int(subject_id)
        marks_obtained = float(marks_obtained)
        max_marks = float(max_marks)
    except (TypeError, ValueError):
        return error_response("Marks values must be valid numbers.")

    if student_id <= 0 or subject_id <= 0:
        return error_response("Invalid student or subject.")

    if max_marks <= 0:
        return error_response("Maximum marks must be greater than zero.")

    if marks_obtained < 0 or marks_obtained > max_marks:
        return error_response("Obtained marks must be between 0 and maximum marks.")

    if len(exam_type) > 50:
        return error_response("Exam type is too long.")

    valid_exam_types = {
        "internal",
        "practical",
        "assignment",
        "midterm",
        "final"
    }
    if exam_type.lower() not in valid_exam_types:
        return error_response("Invalid exam type.")
    exam_type = exam_type.lower()

    db = None
    cursor = None

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                f.id AS faculty_id,
                u.id AS user_id,
                u.college_id
            FROM faculty f
            INNER JOIN users u ON u.id = f.user_id
            WHERE u.id = %s
              AND u.role = 'faculty'
              AND u.is_active = TRUE
            LIMIT 1
        """, (session.get("user_id"),))

        faculty = cursor.fetchone()
        if not faculty:
            return error_response("Faculty account was not found.", 403)

        cursor.execute("""
            SELECT
                s.id,
                s.class_id,
                c.college_id,
                c.course_id
            FROM students s
            INNER JOIN users su ON su.id = s.user_id
            INNER JOIN classes c ON c.id = s.class_id
                AND c.college_id = su.college_id
            WHERE s.id = %s
              AND su.role = 'student'
            LIMIT 1
        """, (student_id,))

        student = cursor.fetchone()
        if not student:
            return error_response("Student not found.", 404)

        if student["college_id"] != faculty["college_id"]:
            return error_response("You cannot enter marks for another college.", 403)

        cursor.execute("""
            SELECT cs.id AS class_subject_id
            FROM class_subjects cs
            INNER JOIN classes c ON c.id = cs.class_id
            INNER JOIN subjects sub ON sub.id = cs.subject_id
            INNER JOIN courses co ON co.id = c.course_id
                AND co.college_id = c.college_id
            WHERE cs.faculty_id = %s
              AND cs.class_id = %s
              AND cs.subject_id = %s
              AND c.college_id = %s
              AND sub.college_id = c.college_id
              AND sub.course_id = c.course_id
            LIMIT 1
        """, (
            faculty["faculty_id"],
            student["class_id"],
            subject_id,
            faculty["college_id"]
        ))

        if cursor.fetchone() is None:
            return error_response(
                "You are not assigned to this student's class and subject.",
                403
            )

        cursor.execute("""
            INSERT INTO marks
            (
                student_id,
                subject_id,
                exam_type,
                marks_obtained,
                max_marks,
                entered_by
            )
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            student_id,
            subject_id,
            exam_type,
            marks_obtained,
            max_marks,
            faculty["user_id"]
        ))

        db.commit()

        return success_response(
            "Marks saved successfully.",
            mark_id=cursor.lastrowid
        )

    except mysql.connector.Error as error:
        if db:
            db.rollback()
        print("Faculty Marks Database Error:", error)
        return error_response("Unable to save marks right now.", 500)

    except Exception as error:
        if db:
            db.rollback()
        print("Faculty Marks Error:", error)
        return error_response("Unable to save marks right now.", 500)

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


# ============================================================
# FACULTY ATTENDANCE - SAVE
# ============================================================

@app.route(
    "/api/faculty/attendance",
    methods=["GET", "POST"]
)
def save_faculty_attendance():

    if "user_id" not in session:
        return error_response("Not authenticated.", 401)

    if session.get("role") != "faculty":
        return error_response("Faculty access required.", 403)

    if request.method == "GET":
        try:
            class_subject_id = int(request.args.get("class_subject_id", ""))
        except (TypeError, ValueError):
            return error_response("Please select an assigned class and subject.")
        if class_subject_id <= 0:
            return error_response("Please select an assigned class and subject.")

        db = cursor = None
        try:
            db = get_db()
            cursor = db.cursor(dictionary=True)
            cursor.execute("""
                SELECT f.id AS faculty_id, u.college_id
                FROM faculty f
                INNER JOIN users u ON u.id = f.user_id
                WHERE u.id = %s
                  AND u.role = 'faculty'
                  AND u.is_active = TRUE
                  AND u.status = 'active'
                LIMIT 1
            """, (session.get("user_id"),))
            faculty = cursor.fetchone()
            if not faculty:
                return error_response("Faculty account was not found.", 403)

            cursor.execute("""
                SELECT cs.id, cs.class_id
                FROM class_subjects cs
                INNER JOIN classes c ON c.id = cs.class_id
                INNER JOIN subjects sub ON sub.id = cs.subject_id
                INNER JOIN courses co ON co.id = c.course_id
                WHERE cs.id = %s
                  AND cs.faculty_id = %s
                  AND c.college_id = %s
                  AND co.college_id = c.college_id
                  AND sub.college_id = c.college_id
                  AND sub.course_id = c.course_id
                  AND sub.semester = c.semester
                LIMIT 1
            """, (
                class_subject_id,
                faculty["faculty_id"],
                faculty["college_id"]
            ))
            class_subject = cursor.fetchone()
            if not class_subject:
                return error_response(
                    "Class subject not found or not assigned to you.",
                    403
                )

            cursor.execute("""
                SELECT
                    a.id,
                    a.student_id,
                    s.roll_number,
                    COALESCE(NULLIF(su.full_name, ''), NULLIF(su.name, '')) AS student_name,
                    a.class_subject_id,
                    a.attendance_date,
                    a.status
                FROM attendance a
                INNER JOIN students s ON s.id = a.student_id
                    AND s.class_id = %s
                INNER JOIN users su ON su.id = s.user_id
                    AND su.college_id = %s
                    AND su.role = 'student'
                WHERE a.class_subject_id = %s
                ORDER BY a.attendance_date DESC, su.full_name, su.name, s.roll_number, a.id DESC
            """, (
                class_subject["class_id"],
                faculty["college_id"],
                class_subject["id"]
            ))
            records = cursor.fetchall()
            for row in records:
                if row.get("attendance_date"):
                    row["attendance_date"] = row["attendance_date"].isoformat()
            return success_response(
                "Attendance records loaded successfully.",
                records=records
            )
        except mysql.connector.Error as error:
            print("Faculty Attendance List Database Error:", error)
            return error_response("Unable to load attendance right now.", 500)
        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    data = request.get_json() or {}

    student_id = data.get("student_id")
    class_subject_id = data.get("class_subject_id")
    attendance_date = data.get("attendance_date")
    status = (data.get("status") or "").strip().lower()

    if not student_id or not class_subject_id or not attendance_date or not status:
        return error_response("Student, class subject, date and status are required.")

    valid_statuses = ["present", "absent", "late", "excused"]
    if status not in valid_statuses:
        return error_response(f"Status must be one of: {', '.join(valid_statuses)}")

    try:
        student_id = int(student_id)
        class_subject_id = int(class_subject_id)
    except (TypeError, ValueError):
        return error_response("Student ID and class subject ID must be valid numbers.")

    if student_id <= 0 or class_subject_id <= 0:
        return error_response("Invalid student or class subject.")

    db = None
    cursor = None

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                f.id AS faculty_id,
                u.id AS user_id,
                u.college_id
            FROM faculty f
            INNER JOIN users u ON u.id = f.user_id
            WHERE u.id = %s
              AND u.role = 'faculty'
              AND u.is_active = TRUE
            LIMIT 1
        """, (session.get("user_id"),))

        faculty = cursor.fetchone()
        if not faculty:
            return error_response("Faculty account was not found.", 403)

        cursor.execute("""
            SELECT
                cs.id,
                cs.class_id,
                cs.subject_id,
                c.college_id
            FROM class_subjects cs
            INNER JOIN classes c ON c.id = cs.class_id
            INNER JOIN subjects sub ON sub.id = cs.subject_id
            INNER JOIN courses co ON co.id = c.course_id
                AND co.college_id = c.college_id
            WHERE cs.id = %s
              AND cs.faculty_id = %s
              AND c.college_id = %s
              AND sub.college_id = c.college_id
              AND sub.course_id = c.course_id
            LIMIT 1
        """, (
            class_subject_id,
            faculty["faculty_id"],
            faculty["college_id"]
        ))

        class_subject = cursor.fetchone()
        if not class_subject:
            return error_response(
                "Class subject not found or not assigned to you.",
                403
            )

        cursor.execute("""
            SELECT s.id
            FROM students s
            INNER JOIN users su ON su.id = s.user_id
            INNER JOIN classes c ON c.id = s.class_id
                AND c.college_id = su.college_id
            WHERE s.id = %s
              AND s.class_id = %s
              AND su.role = 'student'
            LIMIT 1
        """, (student_id, class_subject["class_id"]))

        if cursor.fetchone() is None:
            return error_response(
                "Student does not belong to the selected class.",
                403
            )

        try:
            from datetime import datetime
            parsed_date = datetime.strptime(attendance_date, "%Y-%m-%d").date()
        except ValueError:
            return error_response("Invalid date format. Use YYYY-MM-DD.")

        cursor.execute("""
            SELECT id
            FROM attendance
            WHERE student_id = %s
              AND class_subject_id = %s
              AND attendance_date = %s
            LIMIT 1
        """, (student_id, class_subject_id, parsed_date))

        existing = cursor.fetchone()

        if existing:
            cursor.execute("""
                UPDATE attendance
                SET status = %s,
                    marked_by = %s
                WHERE id = %s
            """, (status, faculty["user_id"], existing["id"]))
        else:
            cursor.execute("""
                INSERT INTO attendance
                (
                    student_id,
                    class_subject_id,
                    attendance_date,
                    status,
                    marked_by
                )
                VALUES (%s, %s, %s, %s, %s)
            """, (
                student_id,
                class_subject_id,
                parsed_date,
                status,
                faculty["user_id"]
            ))

        db.commit()

        return success_response(
            "Attendance saved successfully."
        )

    except mysql.connector.Error as error:
        if db:
            db.rollback()
        print("Faculty Attendance Database Error:", error)
        return error_response("Unable to save attendance right now.", 500)

    except Exception as error:
        if db:
            db.rollback()
        print("Faculty Attendance Error:", error)
        return error_response("Unable to save attendance right now.", 500)

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

# ============================================================
# FACULTY ASSIGNMENT - CREATE
# ============================================================

@app.route(
    "/api/faculty/assignments",
    methods=["POST"]
)
def create_faculty_assignment():

    if "user_id" not in session:
        return error_response(
            "Not authenticated.",
            401
        )

    if session.get("role") != "faculty":
        return error_response(
            "Faculty access required.",
            403
        )

    data = request.get_json() or {}

    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()
    subject_id = data.get("subject_id")
    class_id = data.get("class_id")
    due_date = (data.get("due_date") or "").strip()

    if not title or not description or not subject_id or not class_id or not due_date:
        return error_response(
            "Title, description, subject, class and due date are required."
        )

    if len(title) > 200:
        return error_response(
            "Assignment title is too long."
        )

    try:
        subject_id = int(subject_id)
        class_id = int(class_id)

    except (TypeError, ValueError):
        return error_response(
            "Subject and class must be valid numbers."
        )

    if subject_id <= 0 or class_id <= 0:
        return error_response(
            "Invalid subject or class."
        )

    try:
        from datetime import datetime

        parsed_due_date = datetime.strptime(
            due_date,
            "%Y-%m-%d"
        ).replace(hour=23, minute=59, second=59)

    except ValueError:
        return error_response(
            "Invalid due date. Use YYYY-MM-DD."
        )

    db = None
    cursor = None

    try:

        db = get_db()
        cursor = db.cursor(dictionary=True)

        # ----------------------------------------------------
        # VERIFY FACULTY
        # ----------------------------------------------------

        cursor.execute("""
            SELECT
                f.id AS faculty_id,
                u.id AS user_id,
                u.college_id
            FROM faculty f
            INNER JOIN users u ON u.id = f.user_id
            WHERE u.id = %s
              AND u.role = 'faculty'
              AND u.is_active = TRUE
            LIMIT 1
        """, (session.get("user_id"),))

        faculty = cursor.fetchone()

        if not faculty:
            return error_response(
                "Faculty account was not found.",
                403
            )

        cursor.execute("""
            SELECT cs.id AS class_subject_id
            FROM class_subjects cs
            INNER JOIN classes c ON c.id = cs.class_id
            INNER JOIN subjects sub ON sub.id = cs.subject_id
            INNER JOIN courses co ON co.id = c.course_id
                AND co.college_id = c.college_id
            WHERE cs.class_id = %s
              AND cs.subject_id = %s
              AND cs.faculty_id = %s
              AND c.college_id = %s
              AND sub.college_id = c.college_id
              AND sub.course_id = c.course_id
              AND sub.semester = c.semester
            LIMIT 1
        """, (
            class_id,
            subject_id,
            faculty["faculty_id"],
            faculty["college_id"]
        ))

        class_subject = cursor.fetchone()
        if class_subject is None:
            return error_response(
                "You are not assigned to this class and subject.",
                403
            )

        # ----------------------------------------------------
        # CREATE ASSIGNMENT
        # ----------------------------------------------------

        cursor.execute("""
            INSERT INTO assignments
            (
                class_subject_id,
                title,
                description,
                due_date,
                created_by
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s
            )
        """, (
            class_subject["class_subject_id"],
            title,
            description,
            parsed_due_date,
            faculty["user_id"]
        ))

        db.commit()

        return success_response(
            "Assignment published successfully.",
            assignment_id=cursor.lastrowid
        )

    except mysql.connector.Error as error:

        if db:
            db.rollback()

        print(
            "Faculty Assignment Database Error:",
            error
        )

        return error_response(
            "Unable to publish assignment right now.",
            500
        )

    except Exception as error:

        if db:
            db.rollback()

        print(
            "Faculty Assignment Error:",
            error
        )

        return error_response(
            "Unable to publish assignment right now.",
            500
        )

    finally:

        if cursor:
            cursor.close()

        if db:
            db.close()


# ============================================================
# FACULTY ASSIGNMENT - LIST
# ============================================================

@app.route(
    "/api/faculty/assignments",
    methods=["GET"]
)
def get_faculty_assignments():

    if "user_id" not in session:
        return error_response(
            "Not authenticated.",
            401
        )

    if session.get("role") != "faculty":
        return error_response(
            "Faculty access required.",
            403
        )

    db = None
    cursor = None

    try:

        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT f.id AS faculty_id, u.id AS user_id, u.college_id
            FROM faculty f
            INNER JOIN users u ON u.id = f.user_id
            WHERE u.id = %s
              AND u.role = 'faculty'
              AND u.is_active = TRUE
            LIMIT 1
        """, (session.get("user_id"),))

        faculty = cursor.fetchone()
        if not faculty:
            return error_response("Faculty account was not found.", 403)

        cursor.execute("""
            SELECT
                a.id,
                a.title,
                a.description,
                a.due_date,
                a.attachment_url,
                a.created_at,
                cs.id AS class_subject_id,
                cs.class_id,
                cs.subject_id,
                sub.name AS subject_name,
                sub.code AS subject_code,
                co.name AS course,
                c.academic_year,
                c.year_level AS year,
                c.semester,
                c.division
            FROM assignments a
            INNER JOIN class_subjects cs
                ON cs.id = a.class_subject_id
            INNER JOIN classes c ON c.id = cs.class_id
            INNER JOIN subjects sub ON sub.id = cs.subject_id
            INNER JOIN courses co ON co.id = c.course_id
            WHERE a.created_by = %s
              AND cs.faculty_id = %s
              AND c.college_id = %s
              AND co.college_id = c.college_id
              AND sub.college_id = c.college_id
              AND sub.course_id = c.course_id
              AND sub.semester = c.semester
            ORDER BY a.created_at DESC
        """, (
            faculty["user_id"],
            faculty["faculty_id"],
            faculty["college_id"]
        ))

        assignments = cursor.fetchall()

        for assignment in assignments:

            if assignment.get("due_date"):
                assignment["due_date"] = (
                    assignment["due_date"].isoformat()
                )

            if assignment.get("created_at"):
                assignment["created_at"] = (
                    assignment["created_at"].isoformat()
                )

        return success_response(
            "Assignments loaded successfully.",
            assignments=assignments
        )

    except mysql.connector.Error as error:

        print(
            "Faculty Assignment List Database Error:",
            error
        )

        return error_response(
            "Unable to load assignments right now.",
            500
        )

    except Exception as error:

        print(
            "Faculty Assignment List Error:",
            error
        )

        return error_response(
            "Unable to load assignments right now.",
            500
        )

    finally:

        if cursor:
            cursor.close()

        if db:
            db.close()

# ============================================================
# FACULTY CLASS/SUBJECT OPTIONS FOR ASSIGNMENTS
# ============================================================

@app.route("/api/faculty/class-subjects", methods=["GET"])
def get_faculty_class_subjects():

    if "user_id" not in session:
        return error_response("Not authenticated.", 401)

    if session.get("role") != "faculty":
        return error_response("Faculty access required.", 403)

    db = None
    cursor = None

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT f.id AS faculty_id, u.id AS user_id, u.college_id
            FROM faculty f
            INNER JOIN users u ON u.id = f.user_id
            WHERE u.id = %s
              AND u.role = 'faculty'
              AND u.is_active = TRUE
            LIMIT 1
        """, (session.get("user_id"),))
        faculty = cursor.fetchone()
        if not faculty:
            return error_response("Faculty account was not found.", 403)

        cursor.execute("""
            SELECT
                cs.id AS class_subject_id,
                cs.class_id,
                cs.subject_id,
                sub.name AS subject_name,
                sub.code AS subject_code,
                co.name AS course_name,
                c.academic_year,
                c.year_level,
                c.semester,
                c.division
            FROM class_subjects cs
            INNER JOIN classes c ON c.id = cs.class_id
            INNER JOIN subjects sub ON sub.id = cs.subject_id
            INNER JOIN courses co ON co.id = c.course_id
            WHERE cs.faculty_id = %s
              AND c.college_id = %s
              AND co.college_id = c.college_id
              AND sub.college_id = c.college_id
              AND sub.course_id = c.course_id
              AND sub.semester = c.semester
            ORDER BY co.name, c.year_level, c.division, sub.name
        """, (faculty["faculty_id"], faculty["college_id"]))

        return success_response(
            "Class subjects loaded successfully.",
            class_subjects=cursor.fetchall()
        )

    except mysql.connector.Error as error:
        print("Faculty Class Subject Options Database Error:", error)
        return error_response("Unable to load class subjects right now.", 500)

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@app.route("/api/faculty/students", methods=["GET"])
def get_faculty_students():

    if "user_id" not in session:
        return error_response("Not authenticated.", 401)

    if session.get("role") != "faculty":
        return error_response("Faculty access required.", 403)

    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT f.id AS faculty_id, u.college_id
            FROM faculty f
            INNER JOIN users u ON u.id = f.user_id
            WHERE u.id = %s
              AND u.role = 'faculty'
              AND u.is_active = TRUE
              AND u.status = 'active'
            LIMIT 1
        """, (session.get("user_id"),))
        faculty = cursor.fetchone()
        if not faculty:
            return error_response("Faculty account was not found.", 403)

        cursor.execute("""
            SELECT DISTINCT
                s.id AS student_id,
                s.roll_number,
                COALESCE(NULLIF(su.full_name, ''), NULLIF(su.name, '')) AS full_name,
                su.email,
                co.name AS course,
                c.year_level,
                c.semester,
                c.academic_year,
                c.division
            FROM class_subjects cs
            INNER JOIN classes c ON c.id = cs.class_id
            INNER JOIN courses co ON co.id = c.course_id
            INNER JOIN subjects sub ON sub.id = cs.subject_id
            INNER JOIN students s ON s.class_id = c.id
            INNER JOIN users su ON su.id = s.user_id
            WHERE cs.faculty_id = %s
              AND c.college_id = %s
              AND co.college_id = c.college_id
              AND sub.college_id = c.college_id
              AND sub.course_id = c.course_id
              AND sub.semester = c.semester
              AND su.college_id = c.college_id
              AND su.role = 'student'
              AND su.is_active = TRUE
              AND su.status = 'active'
            ORDER BY c.year_level, c.semester, c.division, s.roll_number, s.id
        """, (faculty["faculty_id"], faculty["college_id"]))
        return success_response(
            "Assigned students loaded successfully.",
            students=cursor.fetchall()
        )

    except mysql.connector.Error as error:
        print("Faculty Students Database Error:", error)
        return error_response("Unable to load assigned students right now.", 500)
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@app.route(
    "/api/faculty/class-subjects/<int:class_subject_id>/students",
    methods=["GET"]
)
def get_faculty_class_subject_students(class_subject_id):

    if "user_id" not in session:
        return error_response("Not authenticated.", 401)

    if session.get("role") != "faculty":
        return error_response("Faculty access required.", 403)

    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT f.id AS faculty_id, u.college_id
            FROM faculty f
            INNER JOIN users u ON u.id = f.user_id
            WHERE u.id = %s
              AND u.role = 'faculty'
              AND u.is_active = TRUE
              AND u.status = 'active'
            LIMIT 1
        """, (session.get("user_id"),))
        faculty = cursor.fetchone()
        if not faculty:
            return error_response("Faculty account was not found.", 403)

        cursor.execute("""
            SELECT cs.class_id
            FROM class_subjects cs
            INNER JOIN classes c ON c.id = cs.class_id
            INNER JOIN subjects sub ON sub.id = cs.subject_id
            INNER JOIN courses co ON co.id = c.course_id
            WHERE cs.id = %s
              AND cs.faculty_id = %s
              AND c.college_id = %s
              AND co.college_id = c.college_id
              AND sub.college_id = c.college_id
              AND sub.course_id = c.course_id
              AND sub.semester = c.semester
            LIMIT 1
        """, (
            class_subject_id,
            faculty["faculty_id"],
            faculty["college_id"]
        ))
        class_subject = cursor.fetchone()
        if not class_subject:
            return error_response(
                "Class subject not found or not assigned to you.",
                403
            )

        cursor.execute("""
            SELECT
                s.id AS student_id,
                s.roll_number,
                COALESCE(NULLIF(u.full_name, ''), NULLIF(u.name, '')) AS full_name
            FROM students s
            INNER JOIN users u ON u.id = s.user_id
            WHERE s.class_id = %s
              AND u.college_id = %s
              AND u.role = 'student'
              AND u.is_active = TRUE
              AND u.status = 'active'
            ORDER BY s.roll_number, s.id
        """, (class_subject["class_id"], faculty["college_id"]))
        return success_response(
            "Class students loaded successfully.",
            students=cursor.fetchall()
        )

    except mysql.connector.Error as error:
        print("Faculty Class Students Database Error:", error)
        return error_response("Unable to load class students right now.", 500)
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@app.route("/api/faculty/submissions", methods=["GET"])
def get_faculty_submissions():

    if "user_id" not in session:
        return error_response("Not authenticated.", 401)

    if session.get("role") != "faculty":
        return error_response("Faculty access required.", 403)

    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT f.id AS faculty_id, u.id AS user_id, u.college_id
            FROM faculty f
            INNER JOIN users u ON u.id = f.user_id
            WHERE u.id = %s
              AND u.role = 'faculty'
              AND u.is_active = TRUE
              AND u.status = 'active'
            LIMIT 1
        """, (session.get("user_id"),))
        faculty = cursor.fetchone()
        if not faculty:
            return error_response("Faculty account was not found.", 403)

        cursor.execute("""
            SELECT
                submission.id,
                submission.assignment_id,
                submission.student_id,
                submission.submission_url,
                submission.submitted_at,
                submission.status,
                submission.marks,
                submission.feedback,
                a.title AS assignment_title,
                a.due_date,
                s.roll_number,
                COALESCE(NULLIF(u.full_name, ''), NULLIF(u.name, '')) AS student_name,
                sub.name AS subject_name,
                sub.code AS subject_code,
                co.name AS course_name,
                c.year_level,
                c.semester,
                c.academic_year,
                c.division
            FROM assignment_submissions submission
            INNER JOIN assignments a ON a.id = submission.assignment_id
            INNER JOIN class_subjects cs ON cs.id = a.class_subject_id
            INNER JOIN classes c ON c.id = cs.class_id
            INNER JOIN subjects sub ON sub.id = cs.subject_id
            INNER JOIN courses co ON co.id = c.course_id
            INNER JOIN students s ON s.id = submission.student_id
                AND s.class_id = cs.class_id
            INNER JOIN users u ON u.id = s.user_id
                AND u.college_id = c.college_id
                AND u.role = 'student'
            WHERE cs.faculty_id = %s
              AND c.college_id = %s
              AND co.college_id = c.college_id
              AND sub.college_id = c.college_id
              AND sub.course_id = c.course_id
              AND sub.semester = c.semester
            ORDER BY submission.submitted_at DESC, submission.id DESC
        """, (faculty["faculty_id"], faculty["college_id"]))
        submissions = cursor.fetchall()
        for row in submissions:
            for key in ("submitted_at", "due_date"):
                if row.get(key):
                    row[key] = row[key].isoformat()
            if row.get("marks") is not None:
                row["marks"] = float(row["marks"])
        return success_response(
            "Assignment submissions loaded successfully.",
            submissions=submissions
        )

    except mysql.connector.Error as error:
        print("Faculty Submissions Database Error:", error)
        return error_response("Unable to load submissions right now.", 500)
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@app.route(
    "/api/faculty/submissions/<int:submission_id>/review",
    methods=["POST"]
)
def review_faculty_submission(submission_id):

    if "user_id" not in session:
        return error_response("Not authenticated.", 401)

    if session.get("role") != "faculty":
        return error_response("Faculty access required.", 403)

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response("Invalid review data.")

    raw_marks = data.get("marks")
    feedback = data.get("feedback")
    if raw_marks in (None, ""):
        marks = None
    else:
        if isinstance(raw_marks, bool):
            return error_response("Review marks must be a valid number.")
        try:
            marks = float(raw_marks)
        except (TypeError, ValueError):
            return error_response("Review marks must be a valid number.")
        if not math.isfinite(marks) or marks < 0 or marks > 9999.99:
            return error_response("Review marks must be between 0 and 9999.99.")
    if feedback is not None and not isinstance(feedback, str):
        return error_response("Feedback must be text.")
    feedback = feedback.strip() if feedback else None
    if feedback and len(feedback) > 10000:
        return error_response("Feedback is too long.")

    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT f.id AS faculty_id, u.college_id
            FROM faculty f
            INNER JOIN users u ON u.id = f.user_id
            WHERE u.id = %s
              AND u.role = 'faculty'
              AND u.is_active = TRUE
              AND u.status = 'active'
            LIMIT 1
        """, (session.get("user_id"),))
        faculty = cursor.fetchone()
        if not faculty:
            return error_response("Faculty account was not found.", 403)

        cursor.execute("""
            SELECT submission.id
            FROM assignment_submissions submission
            INNER JOIN assignments a ON a.id = submission.assignment_id
            INNER JOIN class_subjects cs ON cs.id = a.class_subject_id
            INNER JOIN classes c ON c.id = cs.class_id
            INNER JOIN subjects sub ON sub.id = cs.subject_id
            INNER JOIN courses co ON co.id = c.course_id
            INNER JOIN students s ON s.id = submission.student_id
                AND s.class_id = cs.class_id
            INNER JOIN users su ON su.id = s.user_id
                AND su.college_id = c.college_id
                AND su.role = 'student'
            WHERE submission.id = %s
              AND cs.faculty_id = %s
              AND c.college_id = %s
              AND co.college_id = c.college_id
              AND sub.college_id = c.college_id
              AND sub.course_id = c.course_id
              AND sub.semester = c.semester
            LIMIT 1
        """, (
            submission_id,
            faculty["faculty_id"],
            faculty["college_id"]
        ))
        if not cursor.fetchone():
            return error_response(
                "Submission not found for your assigned class and subject.",
                404
            )

        cursor.execute("""
            UPDATE assignment_submissions
            SET marks = %s,
                feedback = %s,
                status = 'checked'
            WHERE id = %s
        """, (marks, feedback, submission_id))
        db.commit()
        return success_response("Submission reviewed successfully.")

    except mysql.connector.Error as error:
        if db:
            db.rollback()
        print("Faculty Submission Review Database Error:", error)
        return error_response("Unable to save the review right now.", 500)
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


def _get_student_assignment_context(cursor, user_id):
    cursor.execute("""
        SELECT
            s.id AS student_id,
            s.class_id,
            u.college_id
        FROM students s
        INNER JOIN users u ON u.id = s.user_id
        INNER JOIN classes c ON c.id = s.class_id
            AND c.college_id = u.college_id
        WHERE u.id = %s
          AND u.role = 'student'
          AND u.is_active = TRUE
        LIMIT 1
    """, (user_id,))
    return cursor.fetchone()


# ============================================================
# STUDENT ASSIGNMENTS
# ============================================================

@app.route("/api/student/assignments", methods=["GET"])
def get_student_assignments():

    if "user_id" not in session:
        return error_response("Not authenticated.", 401)

    if session.get("role") != "student":
        return error_response("Student access required.", 403)

    db = None
    cursor = None

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        student = _get_student_assignment_context(
            cursor,
            session.get("user_id")
        )
        if not student:
            return error_response("Student profile not found.", 404)

        cursor.execute("""
            SELECT
                a.id,
                a.title,
                a.description,
                a.due_date,
                a.attachment_url,
                a.created_at,
                cs.id AS class_subject_id,
                cs.class_id,
                cs.subject_id,
                sub.name AS subject_name,
                sub.code AS subject_code,
                co.name AS course,
                c.academic_year,
                c.year_level,
                c.semester,
                c.division,
                submission.id AS submission_id,
                submission.status AS submission_status,
                submission.submission_url,
                submission.submitted_at,
                submission.marks AS submission_marks,
                submission.feedback AS submission_feedback
            FROM assignments a
            INNER JOIN class_subjects cs ON cs.id = a.class_subject_id
            INNER JOIN classes c ON c.id = cs.class_id
            INNER JOIN subjects sub ON sub.id = cs.subject_id
            INNER JOIN courses co ON co.id = c.course_id
            LEFT JOIN assignment_submissions submission
                ON submission.assignment_id = a.id
               AND submission.student_id = %s
            WHERE cs.class_id = %s
              AND c.college_id = %s
              AND co.college_id = c.college_id
              AND sub.college_id = c.college_id
              AND sub.course_id = c.course_id
              AND sub.semester = c.semester
            ORDER BY a.due_date IS NULL, a.due_date, a.created_at DESC
        """, (
            student["student_id"],
            student["class_id"],
            student["college_id"]
        ))

        assignments = cursor.fetchall()
        for assignment in assignments:
            for key in ("due_date", "created_at", "submitted_at"):
                if assignment.get(key):
                    assignment[key] = assignment[key].isoformat()
            if assignment.get("submission_marks") is not None:
                assignment["submission_marks"] = float(
                    assignment["submission_marks"]
                )

        return success_response(
            "Assignments loaded successfully.",
            assignments=assignments
        )

    except mysql.connector.Error as error:
        print("Student Assignment List Database Error:", error)
        return error_response("Unable to load assignments right now.", 500)

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@app.route("/api/student/assignments/<int:assignment_id>/submit", methods=["POST"])
def submit_student_assignment(assignment_id):

    if "user_id" not in session:
        return error_response("Not authenticated.", 401)

    if session.get("role") != "student":
        return error_response("Student access required.", 403)

    data = request.get_json() or {}
    submission_url = (data.get("submission_url") or "").strip()
    if not submission_url or len(submission_url) > 500:
        return error_response("A valid submission link is required.")

    parsed_url = urllib.parse.urlparse(submission_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        return error_response("Submission link must be an HTTP or HTTPS URL.")

    db = None
    cursor = None

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        student = _get_student_assignment_context(
            cursor,
            session.get("user_id")
        )
        if not student:
            return error_response("Student profile not found.", 404)

        cursor.execute("""
            SELECT a.id, a.due_date
            FROM assignments a
            INNER JOIN class_subjects cs ON cs.id = a.class_subject_id
            INNER JOIN classes c ON c.id = cs.class_id
            INNER JOIN subjects sub ON sub.id = cs.subject_id
            INNER JOIN courses co ON co.id = c.course_id
            WHERE a.id = %s
              AND cs.class_id = %s
              AND c.college_id = %s
              AND co.college_id = c.college_id
              AND sub.college_id = c.college_id
              AND sub.course_id = c.course_id
              AND sub.semester = c.semester
            LIMIT 1
        """, (
            assignment_id,
            student["class_id"],
            student["college_id"]
        ))
        assignment = cursor.fetchone()
        if not assignment:
            return error_response("Assignment not found for your class.", 404)

        cursor.execute("""
            SELECT id
            FROM assignment_submissions
            WHERE assignment_id = %s
              AND student_id = %s
            LIMIT 1
        """, (assignment_id, student["student_id"]))
        if cursor.fetchone():
            return error_response("You have already submitted this assignment.", 409)

        submitted_at = datetime.now()
        due_date = assignment["due_date"]
        submission_status = (
            "late"
            if due_date and submitted_at > due_date
            else "submitted"
        )

        cursor.execute("""
            INSERT INTO assignment_submissions
            (
                assignment_id,
                student_id,
                submission_url,
                submitted_at,
                status
            )
            VALUES (%s, %s, %s, %s, %s)
        """, (
            assignment_id,
            student["student_id"],
            submission_url,
            submitted_at,
            submission_status
        ))
        db.commit()

        return success_response(
            "Assignment submitted successfully.",
            submission_id=cursor.lastrowid,
            status=submission_status
        )

    except mysql.connector.Error as error:
        if db:
            db.rollback()
        if getattr(error, "errno", None) == 1062:
            return error_response("You have already submitted this assignment.", 409)
        print("Student Assignment Submission Database Error:", error)
        return error_response("Unable to submit assignment right now.", 500)

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@app.route("/api/student/submissions", methods=["GET"])
def get_student_submissions():

    if "user_id" not in session:
        return error_response("Not authenticated.", 401)

    if session.get("role") != "student":
        return error_response("Student access required.", 403)

    db = None
    cursor = None

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        student = _get_student_assignment_context(
            cursor,
            session.get("user_id")
        )
        if not student:
            return error_response("Student profile not found.", 404)

        cursor.execute("""
            SELECT
                submission.id,
                submission.assignment_id,
                submission.submission_url,
                submission.submitted_at,
                submission.marks,
                submission.feedback,
                submission.status,
                a.title,
                a.due_date,
                sub.name AS subject_name,
                sub.code AS subject_code,
                co.name AS course,
                c.academic_year,
                c.year_level,
                c.semester,
                c.division
            FROM assignment_submissions submission
            INNER JOIN assignments a ON a.id = submission.assignment_id
            INNER JOIN class_subjects cs ON cs.id = a.class_subject_id
            INNER JOIN classes c ON c.id = cs.class_id
            INNER JOIN subjects sub ON sub.id = cs.subject_id
            INNER JOIN courses co ON co.id = c.course_id
            WHERE submission.student_id = %s
              AND cs.class_id = %s
              AND c.college_id = %s
              AND co.college_id = c.college_id
              AND sub.college_id = c.college_id
              AND sub.course_id = c.course_id
              AND sub.semester = c.semester
            ORDER BY submission.submitted_at DESC
        """, (
            student["student_id"],
            student["class_id"],
            student["college_id"]
        ))

        submissions = cursor.fetchall()
        for submission in submissions:
            for key in ("submitted_at", "due_date"):
                if submission.get(key):
                    submission[key] = submission[key].isoformat()
            if submission.get("marks") is not None:
                submission["marks"] = float(submission["marks"])

        return success_response(
            "Submissions loaded successfully.",
            submissions=submissions
        )

    except mysql.connector.Error as error:
        print("Student Submission List Database Error:", error)
        return error_response("Unable to load submissions right now.", 500)

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


# ============================================================
# NOTICES AND EVENTS
# ============================================================

def _get_session_faculty(cursor):
    cursor.execute("""
        SELECT f.id AS faculty_id, u.id AS user_id, u.college_id
        FROM faculty f
        INNER JOIN users u ON u.id = f.user_id
        WHERE u.id = %s
          AND u.role = 'faculty'
          AND u.is_active = TRUE
        LIMIT 1
    """, (session.get("user_id"),))
    return cursor.fetchone()


@app.route("/api/faculty/profile", methods=["GET"])
def faculty_profile():
    if "user_id" not in session:
        return error_response("Not authenticated.", 401)
    if session_role() != "faculty":
        return error_response("Faculty access required.", 403)

    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                u.id AS user_id,
                u.full_name,
                u.email,
                u.mobile,
                u.college_id,
                c.name AS college,
                f.id AS faculty_id,
                f.employee_number,
                f.designation,
                f.joining_date,
                d.id AS department_id,
                d.name AS department
            FROM faculty f
            INNER JOIN users u
                ON u.id = f.user_id
               AND u.role = 'faculty'
               AND u.is_active = 1
               AND u.status = 'active'
            INNER JOIN departments d
                ON d.id = f.department_id
               AND d.college_id = u.college_id
            INNER JOIN colleges c
                ON c.id = u.college_id
            WHERE u.id = %s
            LIMIT 1
        """, (session.get("user_id"),))
        profile = cursor.fetchone()
        if not profile:
            return error_response("Faculty profile not found.", 404)
        if profile.get("joining_date"):
            profile["joining_date"] = profile["joining_date"].isoformat()
        return success_response("Faculty profile loaded successfully.", profile=profile)
    except mysql.connector.Error as error:
        print("Faculty Profile Database Error:", error)
        return error_response("Unable to load faculty profile right now.", 500)
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


def _serialize_event(row):
    for key in ("start_datetime", "end_datetime", "created_at"):
        value = row.get(key)
        if value is not None and hasattr(value, "isoformat"):
            row[key] = value.isoformat(sep="T") if isinstance(value, datetime) else value.isoformat()
    return row


@app.route("/api/student/notices", methods=["GET"])
def get_student_notices():
    if "user_id" not in session:
        return error_response("Not authenticated.", 401)
    if session_role() != "student":
        return error_response("Student access required.", 403)

    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT n.id, n.title, n.description, n.priority, n.audience,
                   n.publish_at, n.expires_at, n.attachment_url, n.created_at
            FROM users u
            INNER JOIN students s ON s.user_id = u.id
            INNER JOIN notices n ON n.college_id = u.college_id
            INNER JOIN users notice_author ON notice_author.id = n.created_by
            WHERE u.id = %s AND u.role = 'student'
              AND (n.audience IN ('all', 'students'))
              AND (
                    (notice_author.role = 'faculty' AND n.created_at <= NOW())
                    OR (
                        notice_author.role <> 'faculty'
                        AND (n.publish_at IS NULL OR n.publish_at <= NOW())
                    )
              )
              AND (n.expires_at IS NULL OR n.expires_at >= NOW())
            ORDER BY COALESCE(n.publish_at, n.created_at) DESC, n.id DESC
        """, (session.get("user_id"),))
        return success_response("Notices loaded successfully.", notices=cursor.fetchall())
    except mysql.connector.Error as error:
        print("Student Notices Database Error:", error)
        return error_response("Unable to load notices right now.", 500)
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@app.route("/api/student/events", methods=["GET"])
def get_student_events():
    if "user_id" not in session:
        return error_response("Not authenticated.", 401)
    if session_role() != "student":
        return error_response("Student access required.", 403)

    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT e.id, e.title, e.description, e.location AS venue,
                   e.start_datetime, e.end_datetime, e.created_at
            FROM users u
            INNER JOIN students s ON s.user_id = u.id
            INNER JOIN events e ON e.college_id = u.college_id
            WHERE u.id = %s AND u.role = 'student'
            ORDER BY e.start_datetime, e.id
        """, (session.get("user_id"),))
        events = [_serialize_event(row) for row in cursor.fetchall()]
        return success_response("Events loaded successfully.", events=events)
    except mysql.connector.Error as error:
        print("Student Events Database Error:", error)
        return error_response("Unable to load events right now.", 500)
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@app.route("/api/faculty/notices", methods=["GET", "POST"])
def faculty_notices():
    if "user_id" not in session:
        return error_response("Not authenticated.", 401)
    if session_role() != "faculty":
        return error_response("Faculty access required.", 403)

    data = request.get_json(silent=True) or {} if request.method == "POST" else {}
    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()
    publish_date = (data.get("publish_date") or "").strip()
    if request.method == "POST":
        if not title or not description or not publish_date:
            return error_response("Title, date and details are required.")
        if len(title) > 200:
            return error_response("Notice title is too long.")
        try:
            publish_at = datetime.strptime(publish_date, "%Y-%m-%d")
        except ValueError:
            return error_response("Invalid notice date. Use YYYY-MM-DD.")

    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        faculty = _get_session_faculty(cursor)
        if not faculty:
            return error_response("Faculty account was not found.", 403)

        if request.method == "POST":
            cursor.execute("""
                INSERT INTO notices
                    (college_id, title, description, audience, publish_at, created_by)
                VALUES (%s, %s, %s, 'students', %s, %s)
            """, (faculty["college_id"], title, description, publish_at, faculty["user_id"]))
            db.commit()
            return success_response("Notice published successfully.", notice_id=cursor.lastrowid), 201

        cursor.execute("""
            SELECT n.id, n.title, n.description, n.priority, n.audience,
                   n.publish_at, n.expires_at, n.attachment_url, n.created_at
            FROM notices n
            WHERE n.college_id = %s
            ORDER BY COALESCE(n.publish_at, n.created_at) DESC, n.id DESC
        """, (faculty["college_id"],))
        return success_response("Notices loaded successfully.", notices=cursor.fetchall())
    except mysql.connector.Error as error:
        if db and request.method == "POST":
            db.rollback()
        print("Faculty Notices Database Error:", error)
        return error_response("Unable to process notices right now.", 500)
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@app.route("/api/faculty/events", methods=["GET", "POST"])
def faculty_events():
    if "user_id" not in session:
        return error_response("Not authenticated.", 401)
    if session_role() != "faculty":
        return error_response("Faculty access required.", 403)

    data = request.get_json(silent=True) or {} if request.method == "POST" else {}
    title = (data.get("title") or data.get("name") or "").strip()
    description = (data.get("description") or "").strip()
    event_date = (data.get("event_date") or "").strip()
    event_time = (data.get("event_time") or "").strip()
    venue = (data.get("venue") or "").strip()
    if request.method == "POST":
        if not title or not event_date or not event_time or not venue:
            return error_response("Event name, date, time and venue are required.")
        if len(title) > 200 or len(venue) > 250:
            return error_response("Event name or venue is too long.")
        try:
            start_datetime = datetime.strptime(
                f"{event_date} {event_time}", "%Y-%m-%d %H:%M"
            )
        except ValueError:
            return error_response("Invalid event date or time.")

    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        faculty = _get_session_faculty(cursor)
        if not faculty:
            return error_response("Faculty account was not found.", 403)

        if request.method == "POST":
            cursor.execute("""
                INSERT INTO events
                    (college_id, title, description, location, start_datetime, created_by)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (faculty["college_id"], title, description or None, venue,
                  start_datetime, faculty["user_id"]))
            db.commit()
            return success_response("Event published successfully.", event_id=cursor.lastrowid), 201

        cursor.execute("""
            SELECT e.id, e.title, e.description, e.location AS venue,
                   e.start_datetime, e.end_datetime, e.created_at
            FROM events e
            WHERE e.college_id = %s
            ORDER BY e.start_datetime, e.id
        """, (faculty["college_id"],))
        events = [_serialize_event(row) for row in cursor.fetchall()]
        return success_response("Events loaded successfully.", events=events)
    except mysql.connector.Error as error:
        if db and request.method == "POST":
            db.rollback()
        print("Faculty Events Database Error:", error)
        return error_response("Unable to process events right now.", 500)
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@app.route("/api/admin/notices", methods=["GET"])
def get_admin_notices():
    denied = api_require_admin()
    if denied:
        return denied
    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT n.id, n.title, n.description, n.priority, n.audience,
                   n.publish_at, n.expires_at, n.attachment_url, n.created_at,
                   c.name AS college_name,
                   COALESCE(NULLIF(u.full_name, ''), NULLIF(u.name, '')) AS created_by_name
            FROM notices n
            INNER JOIN colleges c ON c.id = n.college_id
            INNER JOIN users u ON u.id = n.created_by
            ORDER BY n.created_at DESC, n.id DESC
        """)
        return success_response("Notices loaded successfully.", notices=cursor.fetchall())
    except mysql.connector.Error as error:
        print("Admin Notices Database Error:", error)
        return error_response("Unable to load notices right now.", 500)
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@app.route("/api/admin/events", methods=["GET"])
def get_admin_events():
    denied = api_require_admin()
    if denied:
        return denied
    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT e.id, e.title, e.description, e.location AS venue,
                   e.start_datetime, e.end_datetime, e.created_at,
                   c.name AS college_name,
                   COALESCE(NULLIF(u.full_name, ''), NULLIF(u.name, '')) AS created_by_name
            FROM events e
            INNER JOIN colleges c ON c.id = e.college_id
            INNER JOIN users u ON u.id = e.created_by
            ORDER BY e.start_datetime, e.id
        """)
        events = [_serialize_event(row) for row in cursor.fetchall()]
        return success_response("Events loaded successfully.", events=events)
    except mysql.connector.Error as error:
        print("Admin Events Database Error:", error)
        return error_response("Unable to load events right now.", 500)
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


# ============================================================
# NOTES / RESOURCES
# ============================================================

@app.route("/api/student/notes", methods=["GET"])
def get_student_notes():
    if "user_id" not in session:
        return error_response("Not authenticated.", 401)
    if session_role() != "student":
        return error_response("Student access required.", 403)

    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                r.id,
                r.title,
                r.description,
                r.file_url,
                r.file_type,
                r.created_at,
                sub.name AS subject_name,
                sub.code AS subject_code,
                co.name AS course_name,
                c.semester
            FROM users u
            INNER JOIN students s ON s.user_id = u.id
            INNER JOIN classes c ON c.id = s.class_id
                AND c.college_id = u.college_id
            INNER JOIN courses co ON co.id = c.course_id
                AND co.college_id = c.college_id
            INNER JOIN resources r ON r.college_id = u.college_id
                AND (
                    r.subject_id IS NULL
                    OR EXISTS (
                        SELECT 1
                        FROM subjects allowed_subject
                        WHERE allowed_subject.id = r.subject_id
                          AND allowed_subject.college_id = u.college_id
                          AND allowed_subject.course_id = c.course_id
                          AND allowed_subject.semester = c.semester
                    )
                )
            LEFT JOIN subjects sub ON sub.id = r.subject_id
                AND sub.college_id = r.college_id
            WHERE u.id = %s
              AND u.role = 'student'
            ORDER BY r.created_at DESC, r.id DESC
        """, (session.get("user_id"),))
        return success_response("Study resources loaded successfully.", resources=cursor.fetchall())
    except mysql.connector.Error as error:
        print("Student Resources Database Error:", error)
        return error_response("Unable to load study resources right now.", 500)
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@app.route("/api/student/timetable", methods=["GET"])
def get_student_timetable():
    if "user_id" not in session:
        return error_response("Not authenticated.", 401)
    if session_role() != "student":
        return error_response("Student access required.", 403)

    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        ensure_timetable_table(cursor)

        cursor.execute("""
            SELECT s.class_id
            FROM students s
            INNER JOIN users u ON u.id = s.user_id
            WHERE s.user_id = %s
              AND u.role = 'student'
            LIMIT 1
        """, (session.get("user_id"),))
        student = cursor.fetchone()
        if not student:
            return error_response("Student profile not found.", 404)

        cursor.execute("""
            SELECT
                ct.id,
                ct.day_of_week,
                TIME_FORMAT(ct.start_time, '%H:%i') AS start_time,
                TIME_FORMAT(ct.end_time, '%H:%i') AS end_time,
                ct.room,
                sub.id AS subject_id,
                sub.name AS subject_name,
                sub.code AS subject_code,
                COALESCE(NULLIF(fu.full_name, ''), NULLIF(fu.name, '')) AS faculty_name
            FROM class_timetable ct
            INNER JOIN subjects sub ON sub.id = ct.subject_id
            LEFT JOIN faculty f ON f.id = ct.faculty_id
            LEFT JOIN users fu ON fu.id = f.user_id
            WHERE ct.class_id = %s
            ORDER BY
                FIELD(ct.day_of_week, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'),
                ct.start_time,
                ct.end_time
        """, (student["class_id"],))

        timetable = cursor.fetchall()
        return success_response("Timetable loaded successfully.", timetable=timetable)
    except mysql.connector.Error as error:
        print("Student Timetable Database Error:", error)
        return error_response("Unable to load timetable right now.", 500)
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@app.route("/api/faculty/timetable", methods=["GET"])
def get_faculty_timetable():
    if "user_id" not in session:
        return error_response("Not authenticated.", 401)
    if session_role() != "faculty":
        return error_response("Faculty access required.", 403)

    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        ensure_timetable_table(cursor)
        cursor.execute("""
            SELECT f.id AS faculty_id
            FROM faculty f
            INNER JOIN users u ON u.id = f.user_id
            WHERE f.user_id = %s AND u.role = 'faculty'
            LIMIT 1
        """, (session.get("user_id"),))
        faculty = cursor.fetchone()
        if not faculty:
            return error_response("Faculty profile not found.", 404)

        cursor.execute("""
            SELECT ct.id, ct.day_of_week,
                   TIME_FORMAT(ct.start_time, '%H:%i') AS start_time,
                   TIME_FORMAT(ct.end_time, '%H:%i') AS end_time,
                   ct.room,
                   c.year_level AS class_year, c.division AS class_division,
                   sub.name AS subject_name, sub.code AS subject_code
            FROM class_timetable ct
            INNER JOIN classes c ON c.id = ct.class_id
            INNER JOIN subjects sub ON sub.id = ct.subject_id
            WHERE ct.faculty_id = %s
            ORDER BY FIELD(ct.day_of_week, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'),
                     ct.start_time, ct.end_time
        """, (faculty["faculty_id"],))
        return success_response("Timetable loaded successfully.", timetable=cursor.fetchall())
    except mysql.connector.Error as error:
        print("Faculty Timetable Database Error:", error)
        return error_response("Unable to load timetable. Please try again.", 503)
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@app.route("/api/faculty/notes", methods=["GET", "POST"])
def faculty_notes():
    if "user_id" not in session:
        return error_response("Not authenticated.", 401)
    if session_role() != "faculty":
        return error_response("Faculty access required.", 403)

    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT f.id AS faculty_id, u.college_id
            FROM faculty f
            INNER JOIN users u ON u.id = f.user_id
            WHERE u.id = %s
              AND u.role = 'faculty'
              AND u.is_active = TRUE
              AND u.status = 'active'
            LIMIT 1
        """, (session.get("user_id"),))
        faculty = cursor.fetchone()
        if not faculty:
            return error_response("Faculty profile was not found.", 403)

        if request.method == "POST":
            data = request.get_json(silent=True) or {}
            title = (data.get("title") or "").strip()
            description = (data.get("description") or "").strip()
            file_url = (data.get("file_url") or "").strip()
            file_type = (data.get("file_type") or "Link").strip() or "Link"
            subject_id = data.get("subject_id")

            if not title or not file_url:
                return error_response("Title and resource link are required.")
            if len(title) > 200:
                return error_response("Resource title is too long.")
            if len(description) > 2000:
                return error_response("Resource description is too long.")

            try:
                if subject_id is not None:
                    subject_id = int(subject_id)
            except (TypeError, ValueError):
                return error_response("Subject selection is invalid.")

            if subject_id is not None and subject_id > 0:
                cursor.execute("""
                    SELECT s.id
                    FROM subjects s
                    INNER JOIN class_subjects cs ON cs.subject_id = s.id
                    WHERE s.id = %s
                      AND s.college_id = %s
                      AND cs.faculty_id = %s
                    LIMIT 1
                """, (subject_id, faculty["college_id"], faculty["faculty_id"]))
                if cursor.fetchone() is None:
                    return error_response("Selected subject is not assigned to you.", 403)
            elif subject_id is not None and subject_id <= 0:
                return error_response("Selected subject is invalid.")

            parsed = urllib.parse.urlsplit(file_url)
            if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
                return error_response("Resource link must be a valid HTTP or HTTPS URL.")

            cursor.execute("""
                INSERT INTO resources (college_id, subject_id, title, description, file_url, file_type, uploaded_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                faculty["college_id"],
                subject_id if subject_id not in (None, "") else None,
                title,
                description or None,
                file_url,
                file_type,
                session.get("user_id")
            ))
            db.commit()
            return success_response("Resource saved successfully.", resource_id=cursor.lastrowid), 201

        cursor.execute("""
            SELECT
                r.id,
                r.title,
                r.description,
                r.file_url,
                r.file_type,
                r.created_at,
                sub.name AS subject_name,
                sub.code AS subject_code,
                co.name AS course_name,
                COALESCE(NULLIF(u.full_name, ''), NULLIF(u.name, '')) AS uploaded_by_name
            FROM resources r
            INNER JOIN colleges c ON c.id = r.college_id
            LEFT JOIN subjects sub ON sub.id = r.subject_id
                AND sub.college_id = r.college_id
            LEFT JOIN courses co ON co.id = sub.course_id
                AND co.college_id = sub.college_id
            LEFT JOIN users u ON u.id = r.uploaded_by
            WHERE r.college_id = %s
            ORDER BY r.created_at DESC, r.id DESC
        """, (faculty["college_id"],))
        return success_response("Study resources loaded successfully.", resources=cursor.fetchall())
    except mysql.connector.Error as error:
        if db and request.method == "POST":
            db.rollback()
        print("Faculty Resources Database Error:", error)
        return error_response("Unable to process study resources right now.", 500)
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@app.route("/api/admin/assignments", methods=["GET"])
def get_admin_assignments():
    denied = api_require_admin()
    if denied:
        return denied

    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                a.id,
                a.title,
                a.description,
                a.due_date,
                a.attachment_url,
                a.created_at,
                a.created_by,
                COALESCE(NULLIF(u.full_name, ''), NULLIF(u.name, '')) AS created_by_name,
                cs.class_id,
                c.academic_year,
                c.year_level,
                c.semester,
                c.division,
                sub.name AS subject_name,
                sub.code AS subject_code,
                co.name AS course_name
            FROM assignments a
            INNER JOIN class_subjects cs ON cs.id = a.class_subject_id
            INNER JOIN classes c ON c.id = cs.class_id
            INNER JOIN subjects sub ON sub.id = cs.subject_id
            INNER JOIN courses co ON co.id = c.course_id
            LEFT JOIN users u ON u.id = a.created_by
            ORDER BY a.created_at DESC, a.id DESC
        """)
        assignments = cursor.fetchall()
        for assignment in assignments:
            if assignment.get("due_date"):
                assignment["due_date"] = assignment["due_date"].isoformat() if hasattr(assignment["due_date"], "isoformat") else assignment["due_date"]
            if assignment.get("created_at"):
                assignment["created_at"] = assignment["created_at"].isoformat() if hasattr(assignment["created_at"], "isoformat") else assignment["created_at"]
        return success_response("Assignments loaded successfully.", assignments=assignments)
    except mysql.connector.Error as error:
        print("Admin Assignments Database Error:", error)
        return error_response("Unable to load assignments right now.", 500)
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@app.route("/api/admin/profile", methods=["GET"])
def admin_profile():
    denied = api_require_admin()
    if denied:
        return denied

    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                u.id AS user_id,
                u.full_name,
                u.name,
                u.email,
                u.mobile,
                u.college_id,
                u.role,
                u.status,
                u.is_active,
                u.created_at,
                u.last_login_at,
                c.name AS college_name
            FROM users u
            LEFT JOIN colleges c ON c.id = u.college_id
            WHERE u.id = %s
              AND u.role = 'admin'
            LIMIT 1
        """, (session.get("user_id"),))
        profile = cursor.fetchone()
        if not profile:
            return error_response("Admin profile not found.", 404)
        if profile.get("created_at"):
            profile["created_at"] = profile["created_at"].isoformat() if hasattr(profile["created_at"], "isoformat") else profile["created_at"]
        if profile.get("last_login_at"):
            profile["last_login_at"] = profile["last_login_at"].isoformat() if hasattr(profile["last_login_at"], "isoformat") else profile["last_login_at"]
        return success_response("Admin profile loaded successfully.", profile=profile)
    except mysql.connector.Error as error:
        print("Admin Profile Database Error:", error)
        return error_response("Unable to load admin profile right now.", 500)
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@app.route("/api/admin/notes", methods=["GET"])
def get_admin_notes():
    denied = api_require_admin()
    if denied:
        return denied

    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                r.id,
                r.title,
                r.description,
                r.file_url,
                r.file_type,
                r.created_at,
                r.college_id,
                c.name AS college_name,
                s.name AS subject_name,
                s.code AS subject_code,
                co.name AS course_name,
                COALESCE(NULLIF(u.full_name, ''), NULLIF(u.name, '')) AS uploaded_by_name
            FROM resources r
            INNER JOIN colleges c ON c.id = r.college_id
            INNER JOIN users u ON u.id = r.uploaded_by
            LEFT JOIN subjects s ON s.id = r.subject_id
                AND s.college_id = r.college_id
            LEFT JOIN courses co ON co.id = s.course_id
                AND co.college_id = s.college_id
            ORDER BY r.created_at DESC, r.id DESC
        """)
        return success_response("Study resources loaded successfully.", resources=cursor.fetchall())
    except mysql.connector.Error as error:
        print("Admin Resources Database Error:", error)
        return error_response("Unable to load study resources right now.", 500)
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


# ============================================================
# CYBER INCIDENT REPORTS
# ============================================================

@app.route("/api/student/cyber-incidents", methods=["GET", "POST"])
def student_cyber_incidents():
    if "user_id" not in session:
        return error_response("Not authenticated.", 401)
    if session_role() != "student":
        return error_response("Student access required.", 403)

    user_id = session.get("user_id")
    data = request.get_json(silent=True) or {} if request.method == "POST" else {}
    if request.method == "POST":
        if not isinstance(data, dict):
            return error_response("Invalid incident report data.")
        for field in ("incident_type", "title", "description", "evidence_url"):
            if data.get(field) is not None and not isinstance(data.get(field), str):
                return error_response("Incident report fields must be text.")
    incident_type = (data.get("incident_type") or "").strip().lower()
    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()
    evidence_url = (data.get("evidence_url") or "").strip() or None
    allowed_types = {
        "phishing", "account_hacked", "cyberbullying", "fake_account",
        "online_fraud", "password_compromise", "malware",
        "suspicious_message", "suspicious_link", "other"
    }

    if request.method == "POST":
        if incident_type not in allowed_types:
            return error_response("Choose a valid incident type.")
        if not title or not description:
            return error_response("Title and description are required.")
        if len(title) > 200 or len(description) > 10000:
            return error_response("Title or description is too long.")
        if evidence_url:
            if len(evidence_url) > 500:
                return error_response("Evidence link is too long.")
            parsed_url = urllib.parse.urlsplit(evidence_url)
            if parsed_url.scheme.lower() not in ("http", "https") or not parsed_url.netloc:
                return error_response("Evidence link must be a valid HTTP or HTTPS URL.")

    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT s.id AS student_id, u.id AS user_id, u.college_id
            FROM students s
            INNER JOIN users u ON u.id = s.user_id
            WHERE u.id = %s
              AND u.role = 'student'
            LIMIT 1
        """, (user_id,))
        student = cursor.fetchone()
        if not student:
            return error_response("Student profile not found.", 404)

        if request.method == "POST":
            cursor.execute("""
                INSERT INTO cyber_incidents
                    (college_id, reported_by, incident_type, title, description, evidence_url)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (student["college_id"], student["user_id"], incident_type,
                  title, description, evidence_url))
            db.commit()
            return success_response(
                "Incident report submitted successfully.",
                incident_id=cursor.lastrowid
            ), 201

        cursor.execute("""
            SELECT ci.id, ci.incident_type, ci.title, ci.description,
                   ci.evidence_url, ci.status, ci.priority, ci.created_at, ci.updated_at
            FROM cyber_incidents ci
            WHERE ci.reported_by = %s
              AND ci.college_id = %s
            ORDER BY ci.created_at DESC, ci.id DESC
        """, (student["user_id"], student["college_id"]))
        return success_response("Your incident reports loaded successfully.", incidents=cursor.fetchall())
    except mysql.connector.Error as error:
        if db and request.method == "POST":
            db.rollback()
        print("Student Cyber Incident Database Error:", error)
        return error_response("Unable to process your incident report right now.", 500)
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@app.route("/api/admin/cyber-incidents", methods=["GET"])
def get_admin_cyber_incidents():
    denied = api_require_admin()
    if denied:
        return denied

    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                ci.id,
                ci.college_id,
                ci.reported_by,
                ci.incident_type,
                ci.title,
                ci.description,
                ci.evidence_url,
                ci.status,
                ci.priority,
                ci.assigned_to,
                ci.resolution_notes,
                ci.created_at,
                ci.updated_at,
                college.name AS college_name,
                COALESCE(NULLIF(reporter.full_name, ''), NULLIF(reporter.name, '')) AS reporter_name,
                reporter.role AS reporter_role,
                s.roll_number,
                co.name AS course_name,
                cl.year_level,
                cl.division,
                COALESCE(NULLIF(assignee.full_name, ''), NULLIF(assignee.name, '')) AS assigned_to_name
            FROM cyber_incidents ci
            INNER JOIN colleges college ON college.id = ci.college_id
            INNER JOIN users reporter ON reporter.id = ci.reported_by
            LEFT JOIN students s ON s.user_id = reporter.id
            LEFT JOIN classes cl ON cl.id = s.class_id
                AND cl.college_id = ci.college_id
            LEFT JOIN courses co ON co.id = cl.course_id
                AND co.college_id = cl.college_id
            LEFT JOIN users assignee ON assignee.id = ci.assigned_to
            ORDER BY ci.created_at DESC, ci.id DESC
        """)
        return success_response("Incident reports loaded successfully.", incidents=cursor.fetchall())
    except mysql.connector.Error as error:
        print("Admin Cyber Incident Database Error:", error)
        return error_response("Unable to load incident reports right now.", 500)
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


# ============================================================
# ADMIN REPORT AGGREGATES
# ============================================================

@app.route("/api/admin/reports", methods=["GET"])
def get_admin_reports():
    denied = api_require_admin()
    if denied:
        return denied

    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) AS total_students FROM students")
        students = cursor.fetchone()["total_students"]
        cursor.execute("""
            SELECT COUNT(*) AS total_faculty
            FROM faculty f
            INNER JOIN users u ON u.id = f.user_id
            WHERE u.role = 'faculty' AND u.is_active = TRUE
        """)
        faculty = cursor.fetchone()["total_faculty"]
        cursor.execute("SELECT COUNT(*) AS total_colleges FROM colleges")
        colleges = cursor.fetchone()["total_colleges"]
        cursor.execute("""
            SELECT
                COUNT(*) AS total_records,
                COALESCE(SUM(status IN ('present', 'late')), 0) AS attended_records,
                COALESCE(ROUND(
                    100.0 * SUM(status IN ('present', 'late')) / NULLIF(COUNT(*), 0),
                    1
                ), 0) AS rate_percent
            FROM attendance
        """)
        attendance = cursor.fetchone()
        cursor.execute("SELECT COUNT(*) AS total_assignments FROM assignments")
        assignments = cursor.fetchone()["total_assignments"]
        cursor.execute("SELECT COUNT(*) AS total_submissions FROM assignment_submissions")
        submissions = cursor.fetchone()["total_submissions"]
        cursor.execute("SELECT COUNT(*) AS total_events FROM events")
        events = cursor.fetchone()["total_events"]
        cursor.execute("SELECT COUNT(*) AS total_notices FROM notices")
        notices = cursor.fetchone()["total_notices"]
        cursor.execute("""
            SELECT
                COUNT(*) AS total_incidents,
                COALESCE(SUM(status IN ('submitted', 'under_review', 'investigating')), 0) AS open_incidents
            FROM cyber_incidents
        """)
        incidents = cursor.fetchone()
        cursor.execute("""
            SELECT
                COUNT(*) AS total_entries,
                COALESCE(ROUND(
                    100.0 * SUM(marks_obtained) / NULLIF(SUM(max_marks), 0),
                    1
                ), 0) AS average_percent
            FROM marks
        """)
        marks = cursor.fetchone()

        reports = {
            "students": students,
            "faculty": faculty,
            "colleges": colleges,
            "attendance": attendance,
            "assignments": {"total": assignments, "submissions": submissions},
            "events": events,
            "notices": notices,
            "cyber_incidents": incidents,
            "marks": marks
        }
        return success_response("Reports loaded successfully.", reports=reports)
    except mysql.connector.Error as error:
        print("Admin Reports Database Error:", error)
        return error_response("Unable to load reports right now.", 500)
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():
    return app.send_static_file("index.html")

    # ============================================================
# STUDENT PROFILE
# ============================================================

@app.route("/api/student/profile", methods=["GET"])
def student_profile():

    if "user_id" not in session:
        return error_response("Not authenticated.", 401)

    if session.get("role") != "student":
        return error_response("Student access required.", 403)

    db = None
    cursor = None

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                u.id,
                COALESCE(NULLIF(u.full_name, ''), NULLIF(u.name, '')) AS full_name,
                u.email,
                u.mobile,
                u.college_id,
                c.name AS college,
                u.role,
                u.profile_photo,
                u.is_active
            FROM users u
            LEFT JOIN colleges c ON c.id = u.college_id
            WHERE u.id = %s
            AND u.role = 'student'
            LIMIT 1
        """, (session.get("user_id"),))

        student = cursor.fetchone()

        if not student:
            return error_response(
                "Student profile not found.",
                404
            )

        return success_response(
            "Student profile loaded successfully.",
            profile=student
        )

    except Exception as error:

        print("Student Profile Error:", error)

        return error_response(
            "Unable to load student profile.",
            500
        )

    finally:

        if cursor:
            cursor.close()

        if db:
            db.close()


# ============================================================
# START FLASK
# ============================================================

if __name__ == "__main__":
    create_college_requests_table()
    ensure_auth_tables()

    app.run(
        debug=DEBUG_MODE,
        use_reloader=False
    )
