CREATE DATABASE IF NOT EXISTS leave_reconciliation;
USE leave_reconciliation;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('student', 'coordinator', 'hod') NOT NULL,
    student_id VARCHAR(50) DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS attendance (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id VARCHAR(50) NOT NULL,
    subject VARCHAR(100) NOT NULL,
    attendance_date DATE NOT NULL,
    status VARCHAR(30) NOT NULL
);

CREATE TABLE IF NOT EXISTS timetable (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timetable_date DATE NOT NULL,
    day_name VARCHAR(20) NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    subject VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id VARCHAR(50) NOT NULL,
    request_type VARCHAR(30) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    reason TEXT NOT NULL,
    organization_name VARCHAR(200) DEFAULT NULL,
    status VARCHAR(40) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    document_id INT DEFAULT NULL,
    hod_note TEXT DEFAULT NULL,
    coordinator_note TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    request_id INT NOT NULL,
    filename VARCHAR(255) NOT NULL,
    original_name VARCHAR(255) NOT NULL,
    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    ocr_text TEXT,
    extracted_name VARCHAR(200) DEFAULT NULL,
    extracted_date VARCHAR(100) DEFAULT NULL,
    extracted_time VARCHAR(100) DEFAULT NULL,
    extracted_organization VARCHAR(200) DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS department_permissions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id VARCHAR(50) NOT NULL,
    event_name VARCHAR(200) NOT NULL,
    organization VARCHAR(200) DEFAULT NULL,
    date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    venue VARCHAR(200) DEFAULT NULL,
    purpose TEXT NOT NULL,
    reason TEXT DEFAULT NULL,
    document_path VARCHAR(255) DEFAULT NULL,
    status VARCHAR(40) NOT NULL,
    coordinator_remark TEXT DEFAULT NULL,
    hod_remark TEXT DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
