"""
database.py
-----------
MySQL version of the schema + queries for the AI Attendance System.

Converted from SQLite. Key differences from the SQLite version:
    - Connection uses mysql.connector instead of sqlite3
    - Placeholders are %s instead of ?
    - AUTO_INCREMENT instead of AUTOINCREMENT
    - ENUM instead of SQLite's CHECK(... IN (...)) (MySQL 5.7 compatible;
      MySQL 8.0.16+ also supports CHECK, but ENUM is more universally
      supported and clearer)
    - INSERT IGNORE instead of INSERT OR IGNORE
    - Every cursor uses dictionary=True so rows come back as dicts,
      matching how the rest of the app (templates, app.py) already
      expects to use them (row['column_name'])

SETUP — LOCAL (XAMPP):
    1. Start MySQL (XAMPP Control Panel -> MySQL -> Start)
    2. Create the database via phpMyAdmin (New -> "attendance_system" -> Create)
    Nothing else needed — the defaults below match XAMPP out of the box.

SETUP — HOSTED (Railway, Render, etc.):
    Hosting platforms provide their own MySQL and give you connection
    details as environment variables. This file reads those automatically
    if they're set (MYSQLHOST, MYSQLUSER, MYSQLPASSWORD, MYSQLDATABASE,
    MYSQLPORT — Railway's standard names), and falls back to the local
    XAMPP defaults if they're not. You do not need to edit this file to
    switch between local and hosted — just set the environment variables
    on the hosting platform's dashboard.
"""

import os
import math
from datetime import datetime, date

import mysql.connector
from mysql.connector import pooling

DAYS_OF_WEEK = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# ---------------------------------------------------------------------
# Reads hosting-provided environment variables first; falls back to
# local XAMPP defaults if they're not set (i.e. when running on your
# own laptop). No manual editing needed for either case.
# ---------------------------------------------------------------------
DB_CONFIG = {
    "host": os.environ.get("MYSQLHOST", "localhost"),
    "user": os.environ.get("MYSQLUSER", "root"),
    "password": os.environ.get("MYSQLPASSWORD", ""),
    "database": os.environ.get("MYSQLDATABASE", "attendance_system"),
    "port": int(os.environ.get("MYSQLPORT", 3306)),
}

# Some hosted MySQL providers (e.g. Aiven's free tier) require an
# encrypted connection with a CA certificate. If SSL_CA_PATH is set
# (pointing to the ca.pem file downloaded from the provider's
# dashboard), it's added automatically. Local XAMPP needs no SSL, so
# this stays inactive unless you set that environment variable.
_ssl_ca_path = os.environ.get("SSL_CA_PATH")
if _ssl_ca_path:
    DB_CONFIG["ssl_ca"] = _ssl_ca_path
    DB_CONFIG["ssl_verify_cert"] = True

_pool = pooling.MySQLConnectionPool(pool_name="attendance_pool", pool_size=5, **DB_CONFIG)


def get_connection():
    return _pool.get_connection()


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            name            VARCHAR(255) NOT NULL,
            email           VARCHAR(255) UNIQUE NOT NULL,
            password_hash   VARCHAR(255) NOT NULL,
            role            ENUM('student','admin') NOT NULL,
            admin_type      ENUM('faculty','hod','principal') DEFAULT NULL,
            id_number       VARCHAR(100) UNIQUE,
            class_name      VARCHAR(100),
            face_registered TINYINT DEFAULT 0,
            face_registered_on DATETIME,
            active          TINYINT DEFAULT 1,
            registered_on   DATETIME NOT NULL
        ) ENGINE=InnoDB
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id          INT PRIMARY KEY,
            office_lat  DOUBLE,
            office_lng  DOUBLE,
            radius_m    INT DEFAULT 100
        ) ENGINE=InnoDB
    """)
    cur.execute("INSERT IGNORE INTO settings (id, radius_m) VALUES (1, 100)")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            name        VARCHAR(255) NOT NULL,
            class_name  VARCHAR(100) NOT NULL,
            UNIQUE KEY uniq_subject (name, class_name)
        ) ENGINE=InnoDB
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS timetable (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            subject_id  INT NOT NULL,
            class_name  VARCHAR(100) NOT NULL,
            day_of_week VARCHAR(10) NOT NULL,
            start_time  VARCHAR(10) NOT NULL,
            end_time    VARCHAR(10) NOT NULL,
            faculty_id  INT,
            FOREIGN KEY (subject_id) REFERENCES subjects (id),
            FOREIGN KEY (faculty_id) REFERENCES users (id)
        ) ENGINE=InnoDB
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            user_id     INT NOT NULL,
            subject_id  INT NOT NULL,
            date        DATE NOT NULL,
            time        VARCHAR(10) NOT NULL,
            status      VARCHAR(20) DEFAULT 'Present',
            confidence  DOUBLE,
            location_lat DOUBLE,
            location_lng DOUBLE,
            distance_from_office_m DOUBLE,
            within_geofence TINYINT,
            UNIQUE KEY uniq_attendance (user_id, subject_id, date),
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (subject_id) REFERENCES subjects (id)
        ) ENGINE=InnoDB
    """)

    conn.commit()
    cur.close()
    conn.close()


# ---------------------------------------------------------------------
# Settings (office location / geofence)
# ---------------------------------------------------------------------

def get_settings():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM settings WHERE id = 1")
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


def update_settings(lat, lng, radius_m):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE settings SET office_lat=%s, office_lng=%s, radius_m=%s WHERE id=1",
        (lat, lng, radius_m),
    )
    conn.commit()
    cur.close()
    conn.close()


def haversine_distance_m(lat1, lng1, lat2, lng2):
    if None in (lat1, lng1, lat2, lng2):
        return None
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------

def add_user(name, email, password_hash, role, id_number, class_name, admin_type=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO users
           (name, email, password_hash, role, admin_type, id_number, class_name, registered_on)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (name, email, password_hash, role, admin_type, id_number, class_name, datetime.now()),
    )
    conn.commit()
    uid = cur.lastrowid
    cur.close()
    conn.close()
    return uid


def get_user_by_email(email):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM users WHERE email = %s", (email,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


def get_user_by_id(user_id):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


def email_exists(email):
    return get_user_by_email(email) is not None


def id_number_exists(id_number):
    if not id_number:
        return False
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE id_number = %s", (id_number,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row is not None


def any_users_exist():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count > 0


def get_all_students(class_name=None):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    if class_name:
        cur.execute("SELECT * FROM users WHERE role='student' AND class_name=%s ORDER BY name", (class_name,))
    else:
        cur.execute("SELECT * FROM users WHERE role='student' ORDER BY class_name, name")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def get_all_faculty():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM users WHERE role='admin' ORDER BY name")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def get_all_class_names():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT class_name FROM users WHERE role='student' AND class_name IS NOT NULL ORDER BY class_name"
    )
    rows = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()
    return rows


def mark_face_registered(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET face_registered=1, face_registered_on=%s WHERE id=%s",
        (datetime.now(), user_id),
    )
    conn.commit()
    cur.close()
    conn.close()


def deactivate_user(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET active=0 WHERE id=%s", (user_id,))
    conn.commit()
    cur.close()
    conn.close()


def reactivate_user(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET active=1 WHERE id=%s", (user_id,))
    conn.commit()
    cur.close()
    conn.close()


# ---------------------------------------------------------------------
# Subjects & Timetable
# ---------------------------------------------------------------------

def add_subject(name, class_name):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT IGNORE INTO subjects (name, class_name) VALUES (%s, %s)", (name, class_name))
    conn.commit()
    cur.execute("SELECT id FROM subjects WHERE name=%s AND class_name=%s", (name, class_name))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None


def get_subjects(class_name=None):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    if class_name:
        cur.execute("SELECT * FROM subjects WHERE class_name=%s ORDER BY name", (class_name,))
    else:
        cur.execute("SELECT * FROM subjects ORDER BY class_name, name")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def get_subject(subject_id):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM subjects WHERE id=%s", (subject_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


def add_timetable_entry(subject_id, class_name, day_of_week, start_time, end_time, faculty_id=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO timetable (subject_id, class_name, day_of_week, start_time, end_time, faculty_id)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (subject_id, class_name, day_of_week, start_time, end_time, faculty_id),
    )
    conn.commit()
    tid = cur.lastrowid
    cur.close()
    conn.close()
    return tid


def get_timetable(class_name=None, day_of_week=None):
    query = """
        SELECT t.*, s.name AS subject_name, u.name AS faculty_name
        FROM timetable t
        JOIN subjects s ON t.subject_id = s.id
        LEFT JOIN users u ON t.faculty_id = u.id
        WHERE 1=1
    """
    params = []
    if class_name:
        query += " AND t.class_name = %s"
        params.append(class_name)
    if day_of_week:
        query += " AND t.day_of_week = %s"
        params.append(day_of_week)
    query += " ORDER BY t.day_of_week, t.start_time"

    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def get_timetable_entry(entry_id):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT t.*, s.name AS subject_name FROM timetable t
        JOIN subjects s ON t.subject_id = s.id
        WHERE t.id = %s
    """, (entry_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


def today_lectures_for_class(class_name):
    today_dow = datetime.now().strftime("%a")
    return get_timetable(class_name=class_name, day_of_week=today_dow)


# ---------------------------------------------------------------------
# Attendance (per subject, per lecture)
# ---------------------------------------------------------------------

def already_marked(user_id, subject_id, date_str=None):
    date_str = date_str or date.today().isoformat()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM attendance WHERE user_id=%s AND subject_id=%s AND date=%s",
        (user_id, subject_id, date_str),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row is not None


def mark_attendance(user_id, subject_id, confidence, lat=None, lng=None, distance_m=None, within_geofence=True):
    now = datetime.now()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT IGNORE INTO attendance
           (user_id, subject_id, date, time, status, confidence, location_lat, location_lng,
            distance_from_office_m, within_geofence)
           VALUES (%s, %s, %s, %s, 'Present', %s, %s, %s, %s, %s)""",
        (user_id, subject_id, date.today().isoformat(), now.strftime("%H:%M:%S"), confidence,
         lat, lng, distance_m, 1 if within_geofence else 0),
    )
    conn.commit()
    cur.close()
    conn.close()
    return now


def get_subject_total_sessions(subject_id, class_name):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT COUNT(DISTINCT a.date) FROM attendance a
           JOIN users u ON a.user_id = u.id
           WHERE a.subject_id=%s AND u.class_name=%s""",
        (subject_id, class_name),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else 0


def get_student_attended_count(user_id, subject_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM attendance WHERE user_id=%s AND subject_id=%s", (user_id, subject_id))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else 0


def get_student_subject_stats(user_id):
    user = get_user_by_id(user_id)
    if not user or not user.get("class_name"):
        return []

    subjects = get_subjects(class_name=user["class_name"])
    stats = []
    for subj in subjects:
        total = get_subject_total_sessions(subj["id"], user["class_name"])
        attended = get_student_attended_count(user_id, subj["id"])
        pct = round((attended / total) * 100, 1) if total > 0 else None
        stats.append({
            "subject_id": subj["id"],
            "subject_name": subj["name"],
            "attended": attended,
            "total": total,
            "percentage": pct,
        })
    return stats


def get_class_subject_stats(class_name):
    subjects = get_subjects(class_name=class_name)
    students = get_all_students(class_name=class_name)

    result = []
    for subj in subjects:
        total = get_subject_total_sessions(subj["id"], class_name)
        student_rows = []
        for st in students:
            attended = get_student_attended_count(st["id"], subj["id"])
            pct = round((attended / total) * 100, 1) if total > 0 else None
            student_rows.append({
                "user_id": st["id"],
                "name": st["name"],
                "id_number": st["id_number"],
                "attended": attended,
                "percentage": pct,
            })
        result.append({
            "subject_id": subj["id"],
            "subject_name": subj["name"],
            "total_sessions": total,
            "students": student_rows,
        })
    return result


def get_overall_percentage(user_id):
    stats = get_student_subject_stats(user_id)
    total_attended = sum(s["attended"] for s in stats)
    total_sessions = sum(s["total"] for s in stats)
    if total_sessions == 0:
        return None
    return round((total_attended / total_sessions) * 100, 1)


def get_attendance_log(class_name=None, subject_id=None, start_date=None, end_date=None, user_id=None):
    query = """
        SELECT a.date, a.time, u.name, u.id_number, u.class_name, s.name AS subject_name,
               a.status, a.confidence, a.within_geofence
        FROM attendance a
        JOIN users u ON a.user_id = u.id
        JOIN subjects s ON a.subject_id = s.id
        WHERE 1=1
    """
    params = []
    if class_name:
        query += " AND u.class_name = %s"
        params.append(class_name)
    if subject_id:
        query += " AND a.subject_id = %s"
        params.append(subject_id)
    if start_date:
        query += " AND a.date >= %s"
        params.append(start_date)
    if end_date:
        query += " AND a.date <= %s"
        params.append(end_date)
    if user_id:
        query += " AND a.user_id = %s"
        params.append(user_id)
    query += " ORDER BY a.date DESC, a.time DESC"

    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def get_today_summary():
    today = date.today().isoformat()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users WHERE role='student' AND active=1")
    total_students = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM attendance WHERE date=%s", (today,))
    marks_today = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM timetable WHERE day_of_week=%s", (datetime.now().strftime("%a"),))
    lectures_today = cur.fetchone()[0]
    cur.close()
    conn.close()
    return {
        "total_students": total_students,
        "marks_today": marks_today,
        "lectures_today": lectures_today,
    }
