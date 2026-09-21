# Switching to MySQL — Setup Guide

This replaces SQLite (`attendance.db` file) with a real MySQL database.
Tested end-to-end against MySQL 8.0 — schema creation, signup, login,
timetable, attendance marking, and the percentage calculation all
verified to produce identical results to the SQLite version.

---

## 1. Install MySQL Server (if not already installed)

1. Download MySQL Community Server: https://dev.mysql.com/downloads/installer/
2. Run the installer, choose **"Developer Default"**
3. When asked, set a **root password** — remember it, you'll need it once
4. Finish the installer (it starts MySQL as a background service automatically)

**Verify it's installed:** open a new Command Prompt/PowerShell and run:
```
mysql --version
```
If that's not recognized, MySQL's `bin` folder isn't on your PATH — you
can also use **MySQL Workbench** (installed alongside it) instead of the
command line for the next step.

---

## 2. Create the database and a dedicated user

Open a terminal and log in as root:
```
mysql -u root -p
```
(enter the root password you set during install)

Then run these SQL commands (paste all of them, one by one or together):

```sql
CREATE DATABASE attendance_system;
CREATE USER 'attendance_user'@'localhost' IDENTIFIED BY 'your_password_here';
GRANT ALL PRIVILEGES ON attendance_system.* TO 'attendance_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

Replace `'your_password_here'` with a password of your choice — you'll
enter this same password in Step 4 below.

**Why a separate user instead of using root everywhere?** Good practice
— the app only gets access to this one database, not your whole MySQL
server. Worth a line in your project report.

---

## 3. Replace your project's `database.py`

Swap in the new `database.py` (attached) — it has the exact same
function names as before, so `app.py`, `auth.py`, and every template
keep working unchanged. Only the internals (how it talks to the
database) changed.

Also replace `requirements.txt` with the updated one (adds
`mysql-connector-python`).

---

## 4. Configure your credentials

Open the new `database.py`, find this near the top:

```python
DB_CONFIG = {
    "host": "localhost",
    "user": "attendance_user",
    "password": "password123",   # change this to your actual MySQL password
    "database": "attendance_system",
}
```

Change `"password123"` to the password you set in Step 2.

---

## 5. Install and run

```
pip install -r requirements.txt
python app.py
```

The app will automatically create all 5 tables (`users`, `settings`,
`subjects`, `timetable`, `attendance`) in your MySQL database the first
time it runs — same as SQLite did, just in MySQL now.

---

## 6. Verify it worked (optional but reassuring)

```
mysql -u attendance_user -p attendance_system
SHOW TABLES;
```
You should see all 5 tables listed.

---

## What changed internally (for your report / viva)

| | SQLite (before) | MySQL (now) |
|---|---|---|
| Connection | `sqlite3.connect('attendance.db')` | `mysql.connector` connection pool |
| Placeholders | `?` | `%s` |
| Auto-increment | `INTEGER PRIMARY KEY AUTOINCREMENT` | `INT AUTO_INCREMENT PRIMARY KEY` |
| Role/status fields | `CHECK(role IN (...))` | `ENUM('student','admin')` |
| Duplicate-safe insert | `INSERT OR IGNORE` | `INSERT IGNORE` |
| Row format | `sqlite3.Row` (dict-like) | `cursor(dictionary=True)` |
| Storage | Single file (`attendance.db`) | Dedicated server process |

**Why this matters for a real deployment:** SQLite is a single file — 
fine for one person using the app, but it can only handle one write at
a time. MySQL properly supports multiple students marking attendance
simultaneously without conflicts, which matters once this is a real
multi-user college system rather than a demo.

## Backup, with MySQL

The backup approach from before changes slightly — instead of copying
`attendance.db`, you export the database:
```
mysqldump -u attendance_user -p attendance_system > backup.sql
```
Still back up `known_faces/` and `trainer/trainer.yml` the same way as
before (plain file copy).
