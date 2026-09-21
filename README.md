# AI Attendance System — Login, Roles, Timetable & Subject-wise Attendance %

**This package uses MySQL, not SQLite.** See `MYSQL_SETUP.md` first —
it covers starting MySQL (e.g. via XAMPP), creating the
`attendance_system` database, and configuring credentials in
`database.py`. The `DB_CONFIG` in `database.py` is already set to
XAMPP's defaults (`root` user, no password) — if that matches your
setup, you only need to create the database itself before running
`python app.py`.

This is a full rebuild of your original v1 project, adding:
- Login/Signup with two account types: **Student** and **Admin** (Faculty / HOD / Principal)
- Students see only their own attendance; every admin type sees all students
- Admin-defined **weekly timetable** (subjects + lecture schedule per class)
- **Per-subject attendance percentage**, viewable by both student and admin
- Location/geofence check (kept from the previous update)

---

## ⚠️ IMPORTANT — Start with a fresh database

This version's data model (per-subject lecture attendance, with login)
is completely different from your original SQLite-based v1 project
(daily check-in/check-out, no login). Make sure the `attendance_system`
MySQL database is empty/freshly created before running this — see
`MYSQL_SETUP.md`. The app creates all 5 tables automatically on first
run.

---

## Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000` — first visit goes to **/setup** to create
the first Admin (Principal) account.

---

## How to set it all up (in order)

1. **`/setup`** — create the first Admin account (set up as Principal).
2. **Sign Up** more accounts as needed:
   - Students sign up themselves with Roll Number + Class (e.g. `TY-CE-A`).
   - Additional Faculty/HOD/Principal accounts can also sign up themselves
     — anyone can pick "Admin" at signup. (If you want to restrict who
     can become an Admin in a real deployment, you'd add an approval step
     — noted as a possible extension below.)
3. Every new signup is immediately sent to **face capture** — capture
   ~20 photos, train.
4. As Admin: go to **Subjects** → add subjects for each class (e.g.
   "DBMS" for "TY-CE-A"). A class only "exists" once at least one student
   has signed up with that class name.
5. As Admin: go to **Timetable** → select the class → add lectures (subject
   + day of week + time + optional faculty).
6. As Admin (optional): go to **Location** → set campus coordinates +
   allowed radius, if you want geofencing.
7. As Student: go to **Mark Attendance** — shows today's scheduled
   lectures for your class; click **Mark Present** on each (webcam
   verifies your face).
8. Check **Dashboard**:
   - Student view: subject-wise attendance % (highlighted if under 75%).
   - Admin view: every subject for a selected class, with a full
     per-student attendance % breakdown.

---

## How the attendance percentage is calculated

This is worth understanding for your viva:

> **Total lectures held for a subject** = the number of distinct dates on
> which *any* student in that class was marked present for that subject.
> A student's attendance % = *(their attended count) / (that total) × 100*.

This is a practical simplification: there's no separate "lecture
happened" log independent of attendance, so we infer it from the data
itself. It works correctly as long as at least one student attends each
lecture (true in virtually all real classes) — verified in testing with
a 3-student, 3-lecture scenario giving exactly the expected 66.7%
results for partial attendance.

**Possible extension for extra marks:** have faculty explicitly "open" a
lecture session (a button that logs "this lecture happened today"
independent of who attends), which would make the total lecture count
fully independent of attendance and correctly show 0% for a student who
missed every single class.

---

## Roles — how permissions work

- **`role`** controls what you can *do*: `student` or `admin`.
- **`admin_type`** (`faculty` / `hod` / `principal`) is a *label only* —
  every admin type has identical permissions (view all students, manage
  subjects/timetable, export reports). This matches what you described:
  "faculty, HOD, principal — all of them can see all students' data."
- If you later want *tiered* admin permissions (e.g. only HOD/Principal
  can remove a student, but Faculty cannot), that's a small change to
  `auth.py` — happy to add it if you need it.

---

## Project structure

```
app.py              # all routes
auth.py             # password hashing + role decorators
database.py         # schema + queries (see percentage-calc docstring)
face_utils.py        # face detection/training/recognition
templates/           # setup, signup, login, dashboards, timetable, subjects,
                      # students, reports, attendance, capture, location
static/js/           # capture.js, attendance.js (per-lecture "Mark Present")
static/css/style.css
```

---

## Known limitations (mention in your report)

- Attendance percentage relies on the "someone attended = lecture
  happened" inference described above, not an independent lecture log.
- Anyone can sign up as any admin type — no approval workflow for new
  admin accounts. Fine for a college demo; a real deployment would want
  an approval step (e.g., only Principal can approve new Faculty/HOD
  accounts) — this is a natural "future work" item to mention in your
  report.
- No liveness/anti-spoofing in this version (kept simple, matching your
  original v1 scope) — can be added back from the v2 build if wanted.
