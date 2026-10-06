-- One-time migration for the verified legacy campusshield schema.
-- Take and verify a full database backup before running this file.
-- This migration uses existing BCA class/subject records and the user-confirmed
-- BCA department, semester 5, and 2026-2027 academic year.

ALTER TABLE users
    ADD COLUMN profile_photo VARCHAR(500) NULL,
    ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    MODIFY COLUMN password VARCHAR(255) NULL;

UPDATE users
SET full_name = COALESCE(NULLIF(TRIM(full_name), ''), NULLIF(TRIM(name), ''))
WHERE NULLIF(TRIM(full_name), '') IS NULL;

ALTER TABLE users
    MODIFY COLUMN full_name VARCHAR(150) NOT NULL;

INSERT INTO departments (college_id, name, code)
SELECT u.college_id, 'BCA', 'BCA'
FROM users u
WHERE LOWER(u.email) = 'faculty@campusshield.com'
  AND u.role = 'faculty'
  AND u.college_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
      FROM departments d
      WHERE d.college_id = u.college_id
        AND d.code = 'BCA'
  )
LIMIT 1;

INSERT INTO courses (college_id, department_id, name, code, is_active)
SELECT d.college_id, d.id, 'BCA', 'BCA', 1
FROM departments d
WHERE d.code = 'BCA'
  AND d.name = 'BCA'
  AND NOT EXISTS (
      SELECT 1
      FROM courses c
      WHERE c.college_id = d.college_id
        AND c.code = 'BCA'
  );

ALTER TABLE classes
    ADD COLUMN course_id INT NULL,
    ADD COLUMN academic_year VARCHAR(20) NULL,
    ADD COLUMN semester TINYINT UNSIGNED NULL,
    ADD COLUMN year_level TINYINT UNSIGNED NULL;

UPDATE classes cl
JOIN courses co
  ON co.college_id = cl.college_id
 AND co.name = cl.course
SET cl.course_id = co.id;

UPDATE classes
SET academic_year = '2026-2027',
    semester = 5,
    year_level = 3
WHERE course = 'BCA'
  AND year = 'Third Year'
  AND division = 'A';

ALTER TABLE subjects
    ADD COLUMN course_id INT NULL,
    ADD COLUMN semester TINYINT UNSIGNED NULL;

UPDATE subjects sub
JOIN class_subjects cs
  ON cs.subject_id = sub.id
JOIN classes cl
  ON cl.id = cs.class_id
 AND cl.college_id = sub.college_id
SET sub.course_id = cl.course_id,
    sub.semester = cl.semester;

ALTER TABLE students
    ADD COLUMN class_id INT NULL,
    CHANGE COLUMN roll_no roll_number VARCHAR(50) NULL;

UPDATE students s
JOIN classes cl
  ON cl.college_id = s.college_id
 AND cl.course = COALESCE(NULLIF(s.course, ''), NULLIF(s.class_name, ''))
 AND cl.year = s.year
 AND cl.division <=> s.division
SET s.class_id = cl.id;

INSERT INTO faculty (user_id, department_id)
SELECT u.id, d.id
FROM users u
JOIN departments d
  ON d.college_id = u.college_id
 AND d.code = 'BCA'
WHERE LOWER(u.email) = 'faculty@campusshield.com'
  AND u.role = 'faculty'
  AND u.is_active = 1
  AND NOT EXISTS (
      SELECT 1
      FROM faculty existing_faculty
      WHERE existing_faculty.user_id = u.id
  );

ALTER TABLE class_subjects
    ADD COLUMN faculty_id INT NULL;

UPDATE class_subjects cs
JOIN assignments a
  ON a.class_id = cs.class_id
 AND a.subject_id = cs.subject_id
JOIN faculty f
  ON f.user_id = a.faculty_id
SET cs.faculty_id = f.id;

ALTER TABLE attendance
    ADD COLUMN marked_by INT NULL;

ALTER TABLE marks
    ADD COLUMN entered_by INT NULL;

ALTER TABLE assignments
    ADD COLUMN class_subject_id INT NULL,
    ADD COLUMN attachment_url VARCHAR(500) NULL,
    ADD COLUMN created_by INT NULL;

UPDATE assignments a
JOIN class_subjects cs
  ON cs.class_id = a.class_id
 AND cs.subject_id = a.subject_id
JOIN users u
  ON u.id = a.faculty_id
 AND u.role = 'faculty'
SET a.class_subject_id = cs.id,
    a.created_by = u.id;

ALTER TABLE assignments
    DROP INDEX idx_faculty,
    DROP INDEX idx_college,
    DROP INDEX idx_class,
    DROP INDEX idx_subject,
    MODIFY COLUMN due_date DATETIME NOT NULL,
    MODIFY COLUMN class_subject_id INT NOT NULL,
    MODIFY COLUMN created_by INT NOT NULL,
    DROP COLUMN faculty_id,
    DROP COLUMN college_id,
    DROP COLUMN class_id,
    DROP COLUMN subject_id;

UPDATE assignments
SET due_date = TIMESTAMP(DATE(due_date), '23:59:59');

ALTER TABLE assignment_submissions
    MODIFY COLUMN status ENUM('submitted', 'late', 'reviewed', 'pending', 'checked')
        NOT NULL DEFAULT 'pending';

UPDATE assignment_submissions
SET status = 'checked'
WHERE status = 'reviewed';

ALTER TABLE assignment_submissions
    CHANGE COLUMN submission_text submission_url VARCHAR(500) NULL,
    MODIFY COLUMN submitted_at DATETIME NULL DEFAULT NULL,
    MODIFY COLUMN status ENUM('pending', 'submitted', 'late', 'checked')
        NOT NULL DEFAULT 'pending',
    ADD COLUMN marks DECIMAL(6,2) NULL,
    ADD COLUMN feedback TEXT NULL;

ALTER TABLE classes
    MODIFY COLUMN course_id INT NOT NULL,
    MODIFY COLUMN academic_year VARCHAR(20) NOT NULL,
    MODIFY COLUMN semester TINYINT UNSIGNED NOT NULL,
    MODIFY COLUMN year_level TINYINT UNSIGNED NOT NULL,
    MODIFY COLUMN division VARCHAR(20) NOT NULL,
    DROP COLUMN course,
    DROP COLUMN year,
    ADD UNIQUE KEY uq_classes_offering
        (college_id, course_id, academic_year, semester, year_level, division),
    ADD KEY idx_classes_course (course_id),
    ADD CONSTRAINT fk_classes_course
        FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE;

ALTER TABLE subjects
    MODIFY COLUMN course_id INT NOT NULL,
    MODIFY COLUMN semester TINYINT UNSIGNED NOT NULL,
    ADD UNIQUE KEY uq_subject_course_code_semester (course_id, code, semester),
    ADD KEY idx_subjects_course (course_id),
    ADD CONSTRAINT fk_subjects_course
        FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE;

ALTER TABLE students
    MODIFY COLUMN class_id INT NOT NULL,
    MODIFY COLUMN roll_number VARCHAR(50) NOT NULL,
    DROP COLUMN college_id,
    DROP COLUMN class_name,
    DROP COLUMN course,
    DROP COLUMN year,
    DROP COLUMN division,
    ADD UNIQUE KEY uq_students_user (user_id),
    ADD UNIQUE KEY uq_students_class_roll (class_id, roll_number),
    ADD KEY idx_students_class (class_id),
    ADD CONSTRAINT fk_students_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    ADD CONSTRAINT fk_students_class
        FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE RESTRICT;

ALTER TABLE class_subjects
    ADD UNIQUE KEY uq_class_subject (class_id, subject_id),
    ADD KEY idx_class_subject_faculty (faculty_id),
    ADD CONSTRAINT fk_class_subjects_class
        FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE,
    ADD CONSTRAINT fk_class_subjects_subject
        FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
    ADD CONSTRAINT fk_class_subjects_faculty
        FOREIGN KEY (faculty_id) REFERENCES faculty(id) ON DELETE RESTRICT;

ALTER TABLE attendance
    ADD UNIQUE KEY uq_attendance_student_class_date
        (student_id, class_subject_id, attendance_date),
    ADD KEY idx_attendance_student (student_id),
    ADD KEY idx_attendance_class_subject (class_subject_id),
    ADD KEY idx_attendance_marked_by (marked_by),
    ADD CONSTRAINT fk_attendance_student
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    ADD CONSTRAINT fk_attendance_class_subject
        FOREIGN KEY (class_subject_id) REFERENCES class_subjects(id) ON DELETE CASCADE,
    ADD CONSTRAINT fk_attendance_marked_by
        FOREIGN KEY (marked_by) REFERENCES users(id) ON DELETE RESTRICT;

ALTER TABLE marks
    ADD KEY idx_marks_student (student_id),
    ADD KEY idx_marks_subject (subject_id),
    ADD KEY idx_marks_entered_by (entered_by),
    ADD CONSTRAINT fk_marks_student
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    ADD CONSTRAINT fk_marks_subject
        FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
    ADD CONSTRAINT fk_marks_entered_by
        FOREIGN KEY (entered_by) REFERENCES users(id) ON DELETE RESTRICT;

ALTER TABLE assignments
    ADD KEY idx_assignments_class_subject (class_subject_id),
    ADD KEY idx_assignments_created_by (created_by),
    ADD CONSTRAINT fk_assignments_class_subject
        FOREIGN KEY (class_subject_id) REFERENCES class_subjects(id) ON DELETE CASCADE,
    ADD CONSTRAINT fk_assignments_created_by
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT;

ALTER TABLE assignment_submissions
    ADD UNIQUE KEY uq_assignment_submission_student (assignment_id, student_id),
    ADD CONSTRAINT fk_submissions_assignment
        FOREIGN KEY (assignment_id) REFERENCES assignments(id) ON DELETE CASCADE,
    ADD CONSTRAINT fk_submissions_student
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE;

ALTER TABLE classes
    ADD CONSTRAINT fk_classes_college
        FOREIGN KEY (college_id) REFERENCES colleges(id) ON DELETE CASCADE;

ALTER TABLE subjects
    ADD CONSTRAINT fk_subjects_college
        FOREIGN KEY (college_id) REFERENCES colleges(id) ON DELETE CASCADE;

ALTER TABLE activity_logs
    ADD CONSTRAINT fk_activity_logs_college
        FOREIGN KEY (college_id) REFERENCES colleges(id) ON DELETE SET NULL,
    ADD CONSTRAINT fk_activity_logs_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL;
