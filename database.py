import os
import sqlite3
from datetime import datetime

try:
    import mysql.connector
    MYSQL_AVAILABLE = True
except Exception:
    MYSQL_AVAILABLE = False

DB_NAME = os.getenv('DB_NAME', 'leave_reconciliation')
DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_PORT = int(os.getenv('DB_PORT', '3306'))
USE_SQLITE = os.getenv('USE_SQLITE', '1').lower() in {'1', 'true', 'yes'}


def row_to_dict(row, columns=None):
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    if columns is None:
        return dict(row)
    return dict(zip(columns, row))


def rows_to_list(rows, columns=None):
    if not rows:
        return []
    if isinstance(rows[0], dict):
        return rows
    if columns is None:
        return [dict(row) for row in rows]
    return [dict(zip(columns, row)) for row in rows]


def get_db_connection():
    global USE_SQLITE
    if USE_SQLITE:
        conn = sqlite3.connect('leave_reconciliation.db')
        conn.row_factory = sqlite3.Row
        return conn

    if not MYSQL_AVAILABLE:
        USE_SQLITE = True
        conn = sqlite3.connect('leave_reconciliation.db')
        conn.row_factory = sqlite3.Row
        return conn

    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            autocommit=True,
        )
        return conn
    except Exception:
        USE_SQLITE = True
        conn = sqlite3.connect('leave_reconciliation.db')
        conn.row_factory = sqlite3.Row
        return conn


def initialize_database():
    if USE_SQLITE:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                student_id TEXT DEFAULT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                subject TEXT NOT NULL,
                attendance_date TEXT NOT NULL,
                status TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS timetable (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timetable_date TEXT NOT NULL,
                day_name TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                subject TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                request_type TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                reason TEXT NOT NULL,
                organization_name TEXT DEFAULT NULL,
                status TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                document_id INTEGER DEFAULT NULL,
                hod_note TEXT DEFAULT NULL,
                coordinator_note TEXT DEFAULT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                original_name TEXT NOT NULL,
                uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                ocr_text TEXT,
                extracted_name TEXT DEFAULT NULL,
                extracted_date TEXT DEFAULT NULL,
                extracted_time TEXT DEFAULT NULL,
                extracted_organization TEXT DEFAULT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS department_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                event_name TEXT NOT NULL,
                organization TEXT DEFAULT NULL,
                date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                venue TEXT DEFAULT NULL,
                purpose TEXT NOT NULL,
                reason TEXT DEFAULT NULL,
                document_path TEXT DEFAULT NULL,
                status TEXT NOT NULL,
                coordinator_remark TEXT DEFAULT NULL,
                hod_remark TEXT DEFAULT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        columns = [row[1] for row in cursor.execute('PRAGMA table_info(documents)').fetchall()]
        if 'extracted_time' not in columns:
            cursor.execute('ALTER TABLE documents ADD COLUMN extracted_time TEXT DEFAULT NULL')
        conn.commit()
        conn.close()
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f'CREATE DATABASE IF NOT EXISTS {DB_NAME}')
    cursor.execute(f'USE {DB_NAME}')
    with open('schema.sql', 'r', encoding='utf-8') as file:
        script = file.read()
        script = script.replace('CREATE DATABASE IF NOT EXISTS leave_reconciliation;\nUSE leave_reconciliation;\n', '')
        for statement in script.split(';'):
            stmt = statement.strip()
            if stmt:
                cursor.execute(stmt)
    try:
        cursor.execute('SHOW COLUMNS FROM documents LIKE \'extracted_time\'')
        if cursor.fetchone() is None:
            cursor.execute('ALTER TABLE documents ADD COLUMN extracted_time VARCHAR(100) DEFAULT NULL')
    except Exception:
        pass
    conn.commit()
    cursor.close()
    conn.close()


def seed_demo_data():
    conn = get_db_connection()
    cursor = conn.cursor()
    from werkzeug.security import generate_password_hash

    if USE_SQLITE:
        cursor.execute('SELECT COUNT(*) FROM users')
    else:
        cursor.execute('SELECT COUNT(*) FROM users')

    existing_users = cursor.fetchone()[0]

    sample_users = [
        ('Haripriya', 'haripriya@student.com', generate_password_hash('haripriya123'), 'student', 'STU-101'),
        ('Rohit Verma', 'rohit@student.com', generate_password_hash('student123'), 'student', 'STU-102'),
        ('Dr. Meera Nair', 'coordinator@college.edu', generate_password_hash('coord123'), 'coordinator', None),
        ('Prof. Suresh Kumar', 'hod@college.edu', generate_password_hash('hod123'), 'hod', None),
    ]

    if existing_users > 0:
        for name, email, password_hash, role, student_id in sample_users:
            if USE_SQLITE:
                cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
            else:
                cursor.execute('SELECT id FROM users WHERE email = %s', (email,))
            user_row = cursor.fetchone()
            if user_row:
                if USE_SQLITE:
                    cursor.execute(
                        'UPDATE users SET name = ?, password_hash = ?, role = ?, student_id = ? WHERE email = ?',
                        (name, password_hash, role, student_id, email),
                    )
                else:
                    cursor.execute(
                        'UPDATE users SET name = %s, password_hash = %s, role = %s, student_id = %s WHERE email = %s',
                        (name, password_hash, role, student_id, email),
                    )
            else:
                if USE_SQLITE:
                    cursor.execute(
                        'INSERT INTO users (name, email, password_hash, role, student_id) VALUES (?, ?, ?, ?, ?)',
                        (name, email, password_hash, role, student_id),
                    )
                else:
                    cursor.execute(
                        'INSERT INTO users (name, email, password_hash, role, student_id) VALUES (%s, %s, %s, %s, %s)',
                        (name, email, password_hash, role, student_id),
                    )
    else:
        if USE_SQLITE:
            cursor.executemany('INSERT INTO users (name, email, password_hash, role, student_id) VALUES (?, ?, ?, ?, ?)', sample_users)
        else:
            cursor.executemany('INSERT INTO users (name, email, password_hash, role, student_id) VALUES (%s, %s, %s, %s, %s)', sample_users)

    if USE_SQLITE:
        cursor.execute('DELETE FROM requests')
        cursor.execute('DELETE FROM documents')
        cursor.execute('DELETE FROM attendance')
    else:
        cursor.execute('DELETE FROM requests')
        cursor.execute('DELETE FROM documents')
        cursor.execute('DELETE FROM attendance')

    sample_attendance = [
        ('STU-101', 'DBMS', '2026-09-08', 'Absent'),
        ('STU-101', 'OS', '2026-09-08', 'Present'),
        ('STU-101', 'ML', '2026-09-08', 'Absent'),
        ('STU-101', 'DBMS', '2026-09-09', 'Absent'),
        ('STU-101', 'OS', '2026-09-09', 'Present'),
        ('STU-101', 'ML', '2026-09-09', 'Absent'),
        ('STU-101', 'DBMS', '2026-09-10', 'Present'),
        ('STU-101', 'OS', '2026-09-10', 'Absent'),
        ('STU-101', 'ML', '2026-09-10', 'Present'),
        ('STU-101', 'DBMS', '2026-09-11', 'Absent'),
        ('STU-101', 'OS', '2026-09-11', 'Absent'),
        ('STU-101', 'ML', '2026-09-11', 'Present'),
        ('STU-101', 'DBMS', '2026-09-12', 'Absent'),
        ('STU-101', 'OS', '2026-09-12', 'Absent'),
        ('STU-101', 'ML', '2026-09-12', 'Absent'),
        ('STU-101', 'DBMS', '2026-09-12', 'Absent'),
        ('STU-101', 'OS', '2026-09-12', 'Absent'),
        ('STU-101', 'ML', '2026-09-12', 'Absent'),
        ('STU-101', 'DBMS', '2026-09-12', 'Absent'),
        ('STU-101', 'OS', '2026-09-12', 'Absent'),
        ('STU-101', 'ML', '2026-09-12', 'Absent'),
        ('STU-101', 'DBMS', '2026-09-13', 'Absent'),
        ('STU-101', 'OS', '2026-09-13', 'Absent'),
        ('STU-101', 'ML', '2026-09-13', 'Absent'),
    ]

    if USE_SQLITE:
        cursor.executemany('INSERT INTO attendance (student_id, subject, attendance_date, status) VALUES (?, ?, ?, ?)', sample_attendance)
    else:
        cursor.executemany('INSERT INTO attendance (student_id, subject, attendance_date, status) VALUES (%s, %s, %s, %s)', sample_attendance)

    sample_timetable = [
        ('2026-09-12', 'Saturday', '09:00:00', '10:00:00', 'DBMS'),
        ('2026-09-12', 'Saturday', '10:15:00', '11:15:00', 'OS'),
        ('2026-09-12', 'Saturday', '11:30:00', '12:30:00', 'ML'),
        ('2026-09-13', 'Sunday', '09:00:00', '10:00:00', 'DBMS'),
        ('2026-09-13', 'Sunday', '10:15:00', '11:15:00', 'OS'),
        ('2026-09-13', 'Sunday', '11:30:00', '12:30:00', 'ML'),
    ]

    if USE_SQLITE:
        cursor.executemany('INSERT INTO timetable (timetable_date, day_name, start_time, end_time, subject) VALUES (?, ?, ?, ?, ?)', sample_timetable)
    else:
        cursor.executemany('INSERT INTO timetable (timetable_date, day_name, start_time, end_time, subject) VALUES (%s, %s, %s, %s, %s)', sample_timetable)

    conn.commit()
    conn.close()


def get_user_by_email(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    if USE_SQLITE:
        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        row = cursor.fetchone()
        result = row_to_dict(row)
    else:
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        row = cursor.fetchone()
        result = row_to_dict(row, cursor.column_names)
    conn.close()
    return result


def get_user_by_id(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    if USE_SQLITE:
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        row = cursor.fetchone()
        result = row_to_dict(row)
    else:
        cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
        row = cursor.fetchone()
        result = row_to_dict(row, cursor.column_names)
    conn.close()
    return result


def get_user_by_student_id(student_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    if USE_SQLITE:
        cursor.execute('SELECT * FROM users WHERE student_id = ?', (student_id,))
        row = cursor.fetchone()
        result = row_to_dict(row)
    else:
        cursor.execute('SELECT * FROM users WHERE student_id = %s', (student_id,))
        row = cursor.fetchone()
        result = row_to_dict(row, cursor.column_names)
    conn.close()
    return result


def get_student_attendance(student_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    if USE_SQLITE:
        cursor.execute('SELECT * FROM attendance WHERE student_id = ? ORDER BY attendance_date, subject', (student_id,))
        records = cursor.fetchall()
        result = rows_to_list(records)
    else:
        cursor.execute('SELECT * FROM attendance WHERE student_id = %s ORDER BY attendance_date, subject', (student_id,))
        records = cursor.fetchall()
        result = rows_to_list(records, cursor.column_names)
    conn.close()
    return result


def get_attendance_subjects_for_date(student_id, attendance_date):
    conn = get_db_connection()
    cursor = conn.cursor()
    if USE_SQLITE:
        cursor.execute(
            'SELECT DISTINCT subject FROM attendance WHERE student_id = ? AND attendance_date = ?',
            (student_id, attendance_date),
        )
        subjects = [row['subject'] for row in cursor.fetchall()]
    else:
        cursor.execute(
            'SELECT DISTINCT subject FROM attendance WHERE student_id = %s AND attendance_date = %s',
            (student_id, attendance_date),
        )
        subjects = [row[0] for row in cursor.fetchall()]
    conn.close()
    return subjects


def get_department_permission_by_id(permission_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    if USE_SQLITE:
        cursor.execute('SELECT * FROM department_permissions WHERE id = ?', (permission_id,))
        row = cursor.fetchone()
        result = row_to_dict(row)
    else:
        cursor.execute('SELECT * FROM department_permissions WHERE id = %s', (permission_id,))
        row = cursor.fetchone()
        result = row_to_dict(row, cursor.column_names)
    conn.close()
    return result


def get_department_permissions_for_student(student_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    if USE_SQLITE:
        cursor.execute('SELECT * FROM department_permissions WHERE student_id = ? ORDER BY created_at DESC', (student_id,))
        rows = cursor.fetchall()
        result = rows_to_list(rows)
    else:
        cursor.execute('SELECT * FROM department_permissions WHERE student_id = %s ORDER BY created_at DESC', (student_id,))
        rows = cursor.fetchall()
        result = rows_to_list(rows, cursor.column_names)
    conn.close()
    return result


def get_pending_department_permissions(status):
    conn = get_db_connection()
    cursor = conn.cursor()
    if USE_SQLITE:
        cursor.execute('SELECT * FROM department_permissions WHERE status = ? ORDER BY created_at DESC', (status,))
        rows = cursor.fetchall()
        result = rows_to_list(rows)
    else:
        cursor.execute('SELECT * FROM department_permissions WHERE status = %s ORDER BY created_at DESC', (status,))
        rows = cursor.fetchall()
        result = rows_to_list(rows, cursor.column_names)
    conn.close()
    return result


def save_department_permission(permission_data):
    conn = get_db_connection()
    cursor = conn.cursor()
    values = (
        permission_data['student_id'], permission_data['event_name'], permission_data.get('organization'),
        permission_data['date'], permission_data['start_time'], permission_data['end_time'],
        permission_data.get('venue'), permission_data['purpose'], permission_data.get('reason'),
        permission_data.get('document_path'), permission_data['status'],
        permission_data.get('coordinator_remark'), permission_data.get('hod_remark'),
    )
    if USE_SQLITE:
        cursor.execute(
            'INSERT INTO department_permissions (student_id, event_name, organization, date, start_time, end_time, venue, purpose, reason, document_path, status, coordinator_remark, hod_remark) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            values,
        )
    else:
        cursor.execute(
            'INSERT INTO department_permissions (student_id, event_name, organization, date, start_time, end_time, venue, purpose, reason, document_path, status, coordinator_remark, hod_remark) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
            values,
        )
    conn.commit()
    permission_id = cursor.lastrowid
    conn.close()
    return permission_id


def update_department_permission_status(permission_id, status, coordinator_remark=None, hod_remark=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if USE_SQLITE:
        cursor.execute(
            'UPDATE department_permissions SET status = ?, coordinator_remark = ?, hod_remark = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (status, coordinator_remark, hod_remark, permission_id),
        )
    else:
        cursor.execute(
            'UPDATE department_permissions SET status = %s, coordinator_remark = %s, hod_remark = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s',
            (status, coordinator_remark, hod_remark, permission_id),
        )
    conn.commit()
    conn.close()


def get_request_by_id(request_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    if USE_SQLITE:
        cursor.execute('SELECT * FROM requests WHERE id = ?', (request_id,))
        row = cursor.fetchone()
        result = row_to_dict(row)
    else:
        cursor.execute('SELECT * FROM requests WHERE id = %s', (request_id,))
        row = cursor.fetchone()
        result = row_to_dict(row, cursor.column_names)
    conn.close()
    return result


def get_requests_for_student(student_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    if USE_SQLITE:
        query = 'SELECT * FROM requests WHERE student_id = ? ORDER BY created_at DESC'
        cursor.execute(query, (student_id,))
        rows = cursor.fetchall()
        result = rows_to_list(rows)
    else:
        query = 'SELECT * FROM requests WHERE student_id = %s ORDER BY created_at DESC'
        cursor.execute(query, (student_id,))
        rows = cursor.fetchall()
        result = rows_to_list(rows, cursor.column_names)
    conn.close()
    return result


def get_pending_requests(status):
    conn = get_db_connection()
    cursor = conn.cursor()
    if USE_SQLITE:
        query = 'SELECT * FROM requests WHERE status = ? ORDER BY created_at DESC'
        cursor.execute(query, (status,))
        rows = cursor.fetchall()
        result = rows_to_list(rows)
    else:
        query = 'SELECT * FROM requests WHERE status = %s ORDER BY created_at DESC'
        cursor.execute(query, (status,))
        rows = cursor.fetchall()
        result = rows_to_list(rows, cursor.column_names)
    conn.close()
    return result


def save_request(request_data, document_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    if USE_SQLITE:
        cursor.execute(
            'INSERT INTO requests (student_id, request_type, start_date, end_date, start_time, end_time, reason, organization_name, status, document_id, hod_note, coordinator_note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (
                request_data['student_id'], request_data['request_type'], request_data['start_date'], request_data['end_date'],
                request_data['start_time'], request_data['end_time'], request_data['reason'], request_data['organization_name'],
                request_data['status'], document_id, request_data.get('hod_note'), request_data.get('coordinator_note')
            )
        )
    else:
        cursor.execute(
            'INSERT INTO requests (student_id, request_type, start_date, end_date, start_time, end_time, reason, organization_name, status, document_id, hod_note, coordinator_note) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
            (
                request_data['student_id'], request_data['request_type'], request_data['start_date'], request_data['end_date'],
                request_data['start_time'], request_data['end_time'], request_data['reason'], request_data['organization_name'],
                request_data['status'], document_id, request_data.get('hod_note'), request_data.get('coordinator_note')
            )
        )
    conn.commit()
    request_id = cursor.lastrowid
    conn.close()
    return request_id


def save_document(request_id, filename, original_name, ocr_text, extracted_name, extracted_date, extracted_time, extracted_organization):
    conn = get_db_connection()
    cursor = conn.cursor()
    if USE_SQLITE:
        cursor.execute(
            'INSERT INTO documents (request_id, filename, original_name, ocr_text, extracted_name, extracted_date, extracted_time, extracted_organization) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (request_id, filename, original_name, ocr_text, extracted_name, extracted_date, extracted_time, extracted_organization)
        )
    else:
        cursor.execute(
            'INSERT INTO documents (request_id, filename, original_name, ocr_text, extracted_name, extracted_date, extracted_time, extracted_organization) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
            (request_id, filename, original_name, ocr_text, extracted_name, extracted_date, extracted_time, extracted_organization)
        )
    conn.commit()
    document_id = cursor.lastrowid
    conn.close()
    return document_id


def update_request_status(request_id, status, coordinator_note=None, hod_note=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if USE_SQLITE:
        cursor.execute(
            'UPDATE requests SET status = ?, coordinator_note = ?, hod_note = ? WHERE id = ?',
            (status, coordinator_note, hod_note, request_id)
        )
    else:
        cursor.execute(
            'UPDATE requests SET status = %s, coordinator_note = %s, hod_note = %s WHERE id = %s',
            (status, coordinator_note, hod_note, request_id)
        )
    conn.commit()
    conn.close()


def update_request_document_id(request_id, document_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    if USE_SQLITE:
        cursor.execute('UPDATE requests SET document_id = ? WHERE id = ?', (document_id, request_id))
    else:
        cursor.execute('UPDATE requests SET document_id = %s WHERE id = %s', (document_id, request_id))
    conn.commit()
    conn.close()


def get_document_by_request_id(request_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    if USE_SQLITE:
        cursor.execute('SELECT * FROM documents WHERE request_id = ?', (request_id,))
        row = cursor.fetchone()
        result = row_to_dict(row)
    else:
        cursor.execute('SELECT * FROM documents WHERE request_id = %s', (request_id,))
        row = cursor.fetchone()
        result = row_to_dict(row, cursor.column_names)
    conn.close()
    return result


def get_all_students():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE role = 'student' ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    if USE_SQLITE:
        return [dict(row) for row in rows]
    return [row_to_dict(row, cursor.column_names) for row in rows]


def get_timetable_for_date(date_value):
    conn = get_db_connection()
    cursor = conn.cursor()
    if USE_SQLITE:
        cursor.execute('SELECT * FROM timetable WHERE timetable_date = ? ORDER BY start_time', (date_value,))
        rows = cursor.fetchall()
        result = [dict(row) for row in rows]
    else:
        cursor.execute('SELECT * FROM timetable WHERE timetable_date = %s ORDER BY start_time', (date_value,))
        rows = cursor.fetchall()
        result = [row_to_dict(row, cursor.column_names) for row in rows]
    conn.close()
    return result


def update_attendance_status(student_id, subject, attendance_date, new_status):
    conn = get_db_connection()
    cursor = conn.cursor()
    if USE_SQLITE:
        cursor.execute(
            'UPDATE attendance SET status = ? WHERE student_id = ? AND subject = ? AND attendance_date = ? AND status = ?',
            (new_status, student_id, subject, attendance_date, 'Absent')
        )
    else:
        cursor.execute(
            'UPDATE attendance SET status = %s WHERE student_id = %s AND subject = %s AND attendance_date = %s AND status = %s',
            (new_status, student_id, subject, attendance_date, 'Absent')
        )
    conn.commit()
    conn.close()


def update_attendance_status_for_subjects(student_id, subjects, attendance_date, new_status):
    subjects = list(dict.fromkeys(subjects))
    if not subjects:
        return 0
    conn = get_db_connection()
    cursor = conn.cursor()
    if USE_SQLITE:
        placeholders = ', '.join('?' for _ in subjects)
        cursor.execute(
            f'UPDATE attendance SET status = ? WHERE student_id = ? AND attendance_date = ? AND status = ? AND subject IN ({placeholders})',
            [new_status, student_id, attendance_date, 'Absent', *subjects],
        )
    else:
        placeholders = ', '.join('%s' for _ in subjects)
        cursor.execute(
            f'UPDATE attendance SET status = %s WHERE student_id = %s AND attendance_date = %s AND status = %s AND subject IN ({placeholders})',
            [new_status, student_id, attendance_date, 'Absent', *subjects],
        )
    updated_count = cursor.rowcount
    conn.commit()
    conn.close()
    return updated_count
