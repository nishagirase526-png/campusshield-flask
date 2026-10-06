# CampusShield database setup

CampusShield uses MySQL/MariaDB through `mysql-connector-python`.

## Local development

1. Start the MySQL service from the local XAMPP installation and confirm it
   listens on `localhost:3306`.
2. Configure the `CAMPUSSHIELD_DB_HOST`, `CAMPUSSHIELD_DB_PORT`,
   `CAMPUSSHIELD_DB_NAME`, `CAMPUSSHIELD_DB_USER`, and
   `CAMPUSSHIELD_DB_PASSWORD` settings in a local, uncommitted `.env` file.
   The variable names and XAMPP defaults are listed in `.env.example`.
3. For a fresh development database only, import `schema.sql`. It creates the
   `campusshield` database and its tables, including `class_timetable` and its
   foreign keys. Back up an existing database before applying schema changes;
   do not import the fresh-install schema over an existing database.
4. Install Python requirements with `python -m pip install -r requirements.txt`
   and start the existing Flask app with `python backend/app.py`.

## Database-backed timetable check

The opt-in integration test creates uniquely labeled development-only college,
faculty, student, class, subject, and timetable rows in the configured database.
It verifies login, dashboard navigation, the timetable API, student/admin
authorization, the empty response, and the Cyber Safety resource count. It
deletes the test rows after the check.

In PowerShell, run:

```powershell
$env:CAMPUSSHIELD_RUN_DB_TESTS = "1"
python -m unittest discover -s tests -v
Remove-Item Env:CAMPUSSHIELD_RUN_DB_TESTS
```

Use a disposable development database for this integration test. Do not run it
against production data.
