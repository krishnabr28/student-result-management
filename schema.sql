-- Student Result Management System: MySQL 8.0 schema.
-- Applied by `python setup_db.py`; can also be run manually in MySQL Workbench
-- after `CREATE DATABASE internship_result_db; USE internship_result_db;`.

CREATE TABLE IF NOT EXISTS users (
    id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name     VARCHAR(100) NOT NULL,
    role          ENUM('admin', 'faculty', 'student') NOT NULL,
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS students (
    id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id      INT UNSIGNED NULL UNIQUE,
    roll_no      VARCHAR(20)  NOT NULL UNIQUE,
    student_name VARCHAR(100) NOT NULL,
    course       VARCHAR(50)  NOT NULL,
    company      VARCHAR(100) NOT NULL,
    topic        VARCHAR(150) NOT NULL,
    created_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_students_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS results (
    id             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_id     INT UNSIGNED  NOT NULL UNIQUE,
    marks_obtained DECIMAL(6, 2) NOT NULL,
    total_marks    DECIMAL(6, 2) NOT NULL,
    percentage     DECIMAL(5, 2) NOT NULL,
    grade          VARCHAR(2)    NOT NULL,
    remarks        VARCHAR(255)  NULL,
    entered_by     INT UNSIGNED  NULL,
    updated_at     TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_results_student FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE,
    CONSTRAINT fk_results_user FOREIGN KEY (entered_by) REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT chk_results_marks CHECK (total_marks > 0 AND marks_obtained >= 0 AND marks_obtained <= total_marks)
) ENGINE = InnoDB;

-- audience decides who sees a notification; 'user' targets one account (e.g. a published result).
CREATE TABLE IF NOT EXISTS notifications (
    id             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    title          VARCHAR(150) NOT NULL,
    message        TEXT         NOT NULL,
    category       ENUM('result', 'announcement', 'notice', 'exam') NOT NULL,
    priority       ENUM('normal', 'important') NOT NULL DEFAULT 'normal',
    audience       ENUM('all', 'students', 'faculty', 'user') NOT NULL,
    target_user_id INT UNSIGNED NULL,
    created_by     INT UNSIGNED NULL,
    created_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_notifications_created (created_at),
    CONSTRAINT fk_notifications_target FOREIGN KEY (target_user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_notifications_author FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE SET NULL
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS notification_reads (
    notification_id INT UNSIGNED NOT NULL,
    user_id         INT UNSIGNED NOT NULL,
    read_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (notification_id, user_id),
    CONSTRAINT fk_reads_notification FOREIGN KEY (notification_id) REFERENCES notifications (id) ON DELETE CASCADE,
    CONSTRAINT fk_reads_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE = InnoDB;
