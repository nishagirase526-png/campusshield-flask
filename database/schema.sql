-- =========================================================
-- CAMPUSSHIELD DATABASE
-- College Assistant + Integrated Cyber Safety Portal
-- =========================================================

CREATE DATABASE IF NOT EXISTS campusshield
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE campusshield;


-- =========================================================
-- 1. COLLEGES
-- =========================================================

CREATE TABLE colleges (
    id INT AUTO_INCREMENT PRIMARY KEY,

    name VARCHAR(150) NOT NULL,
    code VARCHAR(50) UNIQUE,

    email VARCHAR(150),
    phone VARCHAR(20),

    address TEXT,

    logo_url VARCHAR(500),

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP
);


-- =========================================================
-- COLLEGE REGISTRATION REQUESTS
-- =========================================================

CREATE TABLE college_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,

    college_name VARCHAR(255) NOT NULL,
    city VARCHAR(100) NOT NULL,
    requested_by VARCHAR(255) NOT NULL,
    requested_email VARCHAR(255),

    status ENUM('Pending', 'Approved', 'Rejected')
        DEFAULT 'Pending',
    college_code VARCHAR(50),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP NULL
);


-- =========================================================
-- 2. DEPARTMENTS
-- =========================================================

CREATE TABLE departments (
    id INT AUTO_INCREMENT PRIMARY KEY,

    college_id INT NOT NULL,

    name VARCHAR(120) NOT NULL,
    code VARCHAR(30) NOT NULL,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_departments_college
        FOREIGN KEY (college_id)
        REFERENCES colleges(id)
        ON DELETE CASCADE,

    UNIQUE (college_id, code)
);


-- =========================================================
-- 3. COURSES
-- =========================================================

CREATE TABLE courses (
    id INT AUTO_INCREMENT PRIMARY KEY,

    college_id INT NOT NULL,
    department_id INT NOT NULL,

    name VARCHAR(150) NOT NULL,
    code VARCHAR(30) NOT NULL,

    duration_years TINYINT UNSIGNED,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (college_id)
        REFERENCES colleges(id)
        ON DELETE CASCADE,

    FOREIGN KEY (department_id)
        REFERENCES departments(id)
        ON DELETE CASCADE,

    UNIQUE (college_id, code)
);


-- =========================================================
-- 4. CLASSES / DIVISIONS
-- =========================================================

CREATE TABLE classes (
    id INT AUTO_INCREMENT PRIMARY KEY,

    college_id INT NOT NULL,
    course_id INT NOT NULL,

    academic_year VARCHAR(20) NOT NULL,
    semester TINYINT UNSIGNED NOT NULL,

    year_level TINYINT UNSIGNED NOT NULL,
    division VARCHAR(20) NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uq_classes_offering
        (college_id, course_id, academic_year, semester, year_level, division),

    FOREIGN KEY (college_id)
        REFERENCES colleges(id)
        ON DELETE CASCADE,

    FOREIGN KEY (course_id)
        REFERENCES courses(id)
        ON DELETE CASCADE
);


-- =========================================================
-- 5. USERS
-- =========================================================

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,

    college_id INT NULL,

    full_name VARCHAR(150) NOT NULL,

    name VARCHAR(100),
    college VARCHAR(100),

    email VARCHAR(150),
    mobile VARCHAR(20),

    password_hash VARCHAR(255),

    role ENUM(
        'student',
        'faculty',
        'admin'
    ) NOT NULL,

    profile_photo VARCHAR(500),

    status ENUM('active', 'inactive', 'blocked') NOT NULL DEFAULT 'active',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    must_set_password BOOLEAN NOT NULL DEFAULT FALSE,

    last_login_at TIMESTAMP NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (college_id)
        REFERENCES colleges(id)
        ON DELETE CASCADE,

    UNIQUE (email),
    UNIQUE (mobile)
);


-- =========================================================
-- 6. STUDENTS
-- =========================================================

CREATE TABLE students (
    id INT AUTO_INCREMENT PRIMARY KEY,

    user_id INT NOT NULL UNIQUE,

    class_id INT NOT NULL,

    roll_number VARCHAR(50) NOT NULL,
    enrollment_number VARCHAR(50),

    admission_year YEAR,

    date_of_birth DATE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,

    FOREIGN KEY (class_id)
        REFERENCES classes(id)
        ON DELETE RESTRICT,

    UNIQUE (class_id, roll_number)
);


-- =========================================================
-- 7. FACULTY
-- =========================================================

CREATE TABLE faculty (
    id INT AUTO_INCREMENT PRIMARY KEY,

    user_id INT NOT NULL UNIQUE,

    department_id INT NOT NULL,

    employee_number VARCHAR(50),

    designation VARCHAR(100),

    joining_date DATE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,

    FOREIGN KEY (department_id)
        REFERENCES departments(id)
        ON DELETE RESTRICT,

    UNIQUE (employee_number)
);


-- =========================================================
-- 8. SUBJECTS
-- =========================================================

CREATE TABLE subjects (
    id INT AUTO_INCREMENT PRIMARY KEY,

    college_id INT NOT NULL,
    course_id INT NOT NULL,

    name VARCHAR(150) NOT NULL,
    code VARCHAR(50) NOT NULL,

    semester TINYINT UNSIGNED NOT NULL,

    subject_type ENUM(
        'theory',
        'practical',
        'project'
    ) DEFAULT 'theory',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (college_id)
        REFERENCES colleges(id)
        ON DELETE CASCADE,

    FOREIGN KEY (course_id)
        REFERENCES courses(id)
        ON DELETE CASCADE,

    UNIQUE (course_id, code, semester)
);


-- =========================================================
-- 9. CLASS SUBJECT ASSIGNMENT
-- =========================================================

CREATE TABLE class_subjects (
    id INT AUTO_INCREMENT PRIMARY KEY,

    class_id INT NOT NULL,
    subject_id INT NOT NULL,
    faculty_id INT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (class_id)
        REFERENCES classes(id)
        ON DELETE CASCADE,

    FOREIGN KEY (subject_id)
        REFERENCES subjects(id)
        ON DELETE CASCADE,

    FOREIGN KEY (faculty_id)
        REFERENCES faculty(id)
        ON DELETE RESTRICT,

    UNIQUE (class_id, subject_id)
);


-- =========================================================
-- 9A. CLASS TIMETABLE
-- =========================================================

CREATE TABLE class_timetable (
    id INT AUTO_INCREMENT PRIMARY KEY,

    class_id INT NOT NULL,
    subject_id INT NOT NULL,
    faculty_id INT NULL,

    day_of_week ENUM(
        'Monday',
        'Tuesday',
        'Wednesday',
        'Thursday',
        'Friday',
        'Saturday',
        'Sunday'
    ) NOT NULL,

    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    room VARCHAR(100) NULL,

    created_by INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (class_id)
        REFERENCES classes(id)
        ON DELETE CASCADE,

    FOREIGN KEY (subject_id)
        REFERENCES subjects(id)
        ON DELETE CASCADE,

    FOREIGN KEY (faculty_id)
        REFERENCES faculty(id)
        ON DELETE SET NULL,

    FOREIGN KEY (created_by)
        REFERENCES users(id)
        ON DELETE RESTRICT,

    UNIQUE (class_id, subject_id, day_of_week, start_time)
);


-- =========================================================
-- 10. ATTENDANCE
-- =========================================================

CREATE TABLE attendance (
    id INT AUTO_INCREMENT PRIMARY KEY,

    student_id INT NOT NULL,
    class_subject_id INT NOT NULL,

    attendance_date DATE NOT NULL,

    status ENUM(
        'present',
        'absent',
        'late',
        'excused'
    ) NOT NULL,

    marked_by INT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (student_id)
        REFERENCES students(id)
        ON DELETE CASCADE,

    FOREIGN KEY (class_subject_id)
        REFERENCES class_subjects(id)
        ON DELETE CASCADE,

    FOREIGN KEY (marked_by)
        REFERENCES users(id)
        ON DELETE RESTRICT,

    UNIQUE (
        student_id,
        class_subject_id,
        attendance_date
    )
);


-- =========================================================
-- 11. MARKS
-- =========================================================

CREATE TABLE marks (
    id INT AUTO_INCREMENT PRIMARY KEY,

    student_id INT NOT NULL,
    subject_id INT NOT NULL,

    exam_type VARCHAR(50) NOT NULL,

    marks_obtained DECIMAL(6,2) NOT NULL,
    max_marks DECIMAL(6,2) NOT NULL,

    entered_by INT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (student_id)
        REFERENCES students(id)
        ON DELETE CASCADE,

    FOREIGN KEY (subject_id)
        REFERENCES subjects(id)
        ON DELETE CASCADE,

    FOREIGN KEY (entered_by)
        REFERENCES users(id)
        ON DELETE RESTRICT
);


-- =========================================================
-- 12. ASSIGNMENTS
-- =========================================================

CREATE TABLE assignments (
    id INT AUTO_INCREMENT PRIMARY KEY,

    class_subject_id INT NOT NULL,

    title VARCHAR(200) NOT NULL,
    description TEXT,

    due_date DATETIME NOT NULL,

    attachment_url VARCHAR(500),

    created_by INT NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (class_subject_id)
        REFERENCES class_subjects(id)
        ON DELETE CASCADE,

    FOREIGN KEY (created_by)
        REFERENCES users(id)
        ON DELETE RESTRICT
);


-- =========================================================
-- 13. ASSIGNMENT SUBMISSIONS
-- =========================================================

CREATE TABLE assignment_submissions (
    id INT AUTO_INCREMENT PRIMARY KEY,

    assignment_id INT NOT NULL,
    student_id INT NOT NULL,

    submission_url VARCHAR(500),

    submitted_at DATETIME NULL DEFAULT NULL,

    marks DECIMAL(6,2),

    feedback TEXT,

    status ENUM(
        'pending',
        'submitted',
        'late',
        'checked'
    ) NOT NULL DEFAULT 'pending',

    FOREIGN KEY (assignment_id)
        REFERENCES assignments(id)
        ON DELETE CASCADE,

    FOREIGN KEY (student_id)
        REFERENCES students(id)
        ON DELETE CASCADE,

    UNIQUE (assignment_id, student_id)
);


-- =========================================================
-- 14. NOTICES
-- =========================================================

CREATE TABLE notices (
    id INT AUTO_INCREMENT PRIMARY KEY,

    college_id INT NOT NULL,

    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,

    priority ENUM(
        'low',
        'normal',
        'high',
        'urgent'
    ) DEFAULT 'normal',

    audience ENUM(
        'all',
        'students',
        'faculty',
        'admins'
    ) DEFAULT 'all',

    publish_at DATETIME,
    expires_at DATETIME,

    attachment_url VARCHAR(500),

    created_by INT NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (college_id)
        REFERENCES colleges(id)
        ON DELETE CASCADE,

    FOREIGN KEY (created_by)
        REFERENCES users(id)
        ON DELETE RESTRICT
);


-- =========================================================
-- 15. EVENTS
-- =========================================================

CREATE TABLE events (
    id INT AUTO_INCREMENT PRIMARY KEY,

    college_id INT NOT NULL,

    title VARCHAR(200) NOT NULL,
    description TEXT,

    location VARCHAR(250),

    start_datetime DATETIME NOT NULL,
    end_datetime DATETIME,

    created_by INT NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (college_id)
        REFERENCES colleges(id)
        ON DELETE CASCADE,

    FOREIGN KEY (created_by)
        REFERENCES users(id)
        ON DELETE RESTRICT
);


-- =========================================================
-- 16. RESOURCES / STUDY MATERIAL
-- =========================================================

CREATE TABLE resources (
    id INT AUTO_INCREMENT PRIMARY KEY,

    college_id INT NOT NULL,
    subject_id INT,

    title VARCHAR(200) NOT NULL,

    description TEXT,

    file_url VARCHAR(500) NOT NULL,

    file_type VARCHAR(50),

    uploaded_by INT NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (college_id)
        REFERENCES colleges(id)
        ON DELETE CASCADE,

    FOREIGN KEY (subject_id)
        REFERENCES subjects(id)
        ON DELETE SET NULL,

    FOREIGN KEY (uploaded_by)
        REFERENCES users(id)
        ON DELETE RESTRICT
);


-- =========================================================
-- 17. CYBER INCIDENT REPORTS
-- =========================================================

CREATE TABLE cyber_incidents (
    id INT AUTO_INCREMENT PRIMARY KEY,

    college_id INT NOT NULL,
    reported_by INT NOT NULL,

    incident_type ENUM(
        'phishing',
        'account_hacked',
        'cyberbullying',
        'fake_account',
        'online_fraud',
        'password_compromise',
        'malware',
        'suspicious_message',
        'suspicious_link',
        'other'
    ) NOT NULL,

    title VARCHAR(200) NOT NULL,

    description TEXT NOT NULL,

    evidence_url VARCHAR(500),

    status ENUM(
        'submitted',
        'under_review',
        'investigating',
        'resolved',
        'closed'
    ) DEFAULT 'submitted',

    priority ENUM(
        'low',
        'medium',
        'high',
        'critical'
    ) DEFAULT 'medium',

    assigned_to INT NULL,

    resolution_notes TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (college_id)
        REFERENCES colleges(id)
        ON DELETE CASCADE,

    FOREIGN KEY (reported_by)
        REFERENCES users(id)
        ON DELETE RESTRICT,

    FOREIGN KEY (assigned_to)
        REFERENCES users(id)
        ON DELETE SET NULL
);


-- =========================================================
-- 18. NOTIFICATIONS
-- =========================================================

CREATE TABLE notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,

    user_id INT NOT NULL,

    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,

    notification_type VARCHAR(50),

    is_read BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);


-- =========================================================
-- 19. AUTHENTICATION OTPs
-- =========================================================

CREATE TABLE auth_otps (
    id INT AUTO_INCREMENT PRIMARY KEY,

    identifier VARCHAR(150) NOT NULL,

    full_name VARCHAR(150),

    purpose VARCHAR(50) NOT NULL,

    delivery_method VARCHAR(20) NOT NULL,

    otp_hash VARCHAR(255) NOT NULL,

    expires_at DATETIME NOT NULL,

    attempts INT NOT NULL DEFAULT 0,

    verified_at DATETIME NULL,

    used BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_auth_otps_identifier (identifier),
    INDEX idx_auth_otps_purpose (purpose)
);


CREATE TABLE password_resets (
    id INT AUTO_INCREMENT PRIMARY KEY,

    user_id INT NOT NULL,
    identifier VARCHAR(150) NOT NULL,
    otp_hash VARCHAR(255) NOT NULL,
    expires_at DATETIME NOT NULL,
    attempts INT NOT NULL DEFAULT 0,
    used BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_password_resets_user (user_id),
    INDEX idx_password_resets_identifier (identifier),
    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);


-- =========================================================
-- 20. ACTIVITY LOGS
-- =========================================================

CREATE TABLE activity_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,

    college_id INT,

    user_id INT,

    action VARCHAR(100) NOT NULL,

    description TEXT,

    ip_address VARCHAR(45),

    user_agent TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (college_id)
        REFERENCES colleges(id)
        ON DELETE SET NULL,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE SET NULL
);


-- =========================================================
-- INDEXES
-- =========================================================

CREATE INDEX idx_users_college_role
ON users(college_id, role);

CREATE INDEX idx_students_class
ON students(class_id);

CREATE INDEX idx_attendance_student
ON attendance(student_id);

CREATE INDEX idx_attendance_date
ON attendance(attendance_date);

CREATE INDEX idx_marks_student
ON marks(student_id);

CREATE INDEX idx_notices_college
ON notices(college_id);

CREATE INDEX idx_events_college
ON events(college_id);

CREATE INDEX idx_cyber_incidents_status
ON cyber_incidents(status);

CREATE INDEX idx_notifications_user
ON notifications(user_id);

CREATE INDEX idx_activity_logs_user
ON activity_logs(user_id);
