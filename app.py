"""
app.py
------
AI Attendance System — login-based, role-based (Student / Admin), with
subject-wise timetable and per-lecture attendance percentage tracking.

Run with:
    python app.py
Then open http://127.0.0.1:5000
"""

import io
from datetime import date, datetime

import pandas as pd
from flask import (
    Flask, render_template, request, redirect, url_for, jsonify, flash, send_file, session
)

import database as db
import face_utils
import auth

app = Flask(__name__)
app.secret_key = "college-project-secret-key-change-me"

MIN_SAMPLES_REQUIRED = 20

db.init_db()


# ---------------------------------------------------------------------
# First-run setup: create the first Admin (Principal) account
# ---------------------------------------------------------------------

@app.route("/setup", methods=["GET", "POST"])
def first_time_setup():
    if db.any_users_exist():
        flash("Setup already completed. Please log in.", "error")
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not all([name, email, password]):
            flash("All fields are required.", "error")
            return redirect(url_for("first_time_setup"))

        uid = db.add_user(
            name, email, auth.hash_password(password), "admin",
            id_number="PRINCIPAL001", class_name="Administration", admin_type="principal",
        )
        user = db.get_user_by_id(uid)
        auth.login_user(user)
        flash("Admin account created! You can now add faculty, students, subjects, and a timetable.", "success")
        return redirect(url_for("dashboard"))

    return render_template("setup.html")


# ---------------------------------------------------------------------
# Public signup (Student or Admin)
# ---------------------------------------------------------------------

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if not db.any_users_exist():
        return redirect(url_for("first_time_setup"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "student")
        admin_type = request.form.get("admin_type") if role == "admin" else None
        id_number = request.form.get("id_number", "").strip()
        class_name = request.form.get("class_name", "").strip()

        if not all([name, email, password, id_number]):
            flash("Name, email, password, and ID/Roll number are required.", "error")
            return redirect(url_for("signup"))

        if role == "admin" and admin_type not in ("faculty", "hod", "principal"):
            flash("Please select a valid admin type.", "error")
            return redirect(url_for("signup"))

        if db.email_exists(email):
            flash("An account with this email already exists. Please log in.", "error")
            return redirect(url_for("login"))

        if db.id_number_exists(id_number):
            flash("That ID/Roll number is already registered.", "error")
            return redirect(url_for("signup"))

        uid = db.add_user(
            name, email, auth.hash_password(password), role, id_number, class_name, admin_type
        )
        user = db.get_user_by_id(uid)
        auth.login_user(user)
        flash("Account created! Now capture your face for attendance recognition.", "success")
        return redirect(url_for("capture", user_id=uid))

    return render_template("signup.html")


# ---------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if not db.any_users_exist():
        return redirect(url_for("first_time_setup"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = db.get_user_by_email(email)

        if not user or not auth.verify_password(password, user["password_hash"]):
            flash("Invalid email or password.", "error")
            return redirect(url_for("login"))
        if not user["active"]:
            flash("This account has been deactivated by an admin.", "error")
            return redirect(url_for("login"))

        auth.login_user(user)
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    auth.logout_user()
    flash("Logged out.", "success")
    return redirect(url_for("login"))


@app.route("/")
def home():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


# ---------------------------------------------------------------------
# Location / geofence settings (admin only)
# ---------------------------------------------------------------------

@app.route("/location", methods=["GET", "POST"])
@auth.admin_required
def location_setup():
    if request.method == "POST":
        lat = float(request.form.get("lat"))
        lng = float(request.form.get("lng"))
        radius = int(request.form.get("radius", 100))
        db.update_settings(lat, lng, radius)
        flash("Location & allowed radius saved.", "success")
        return redirect(url_for("location_setup"))

    settings = db.get_settings()
    return render_template("location.html", settings=settings)


# ---------------------------------------------------------------------
# Subjects (admin only)
# ---------------------------------------------------------------------

@app.route("/subjects", methods=["GET", "POST"])
@auth.admin_required
def manage_subjects():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        class_name = request.form.get("class_name", "").strip()
        if name and class_name:
            db.add_subject(name, class_name)
            flash(f"Subject '{name}' added for {class_name}.", "success")
        return redirect(url_for("manage_subjects"))

    subjects = db.get_subjects()
    class_names = db.get_all_class_names()
    return render_template("subjects.html", subjects=subjects, class_names=class_names)


# ---------------------------------------------------------------------
# Timetable (admin only)
# ---------------------------------------------------------------------

@app.route("/timetable", methods=["GET", "POST"])
@auth.admin_required
def manage_timetable():
    if request.method == "POST":
        subject_id = request.form.get("subject_id")
        class_name = request.form.get("class_name", "").strip()
        day_of_week = request.form.get("day_of_week")
        start_time = request.form.get("start_time")
        end_time = request.form.get("end_time")
        faculty_id = request.form.get("faculty_id") or None

        db.add_timetable_entry(subject_id, class_name, day_of_week, start_time, end_time, faculty_id)
        flash("Lecture added to timetable.", "success")
        return redirect(url_for("manage_timetable"))

    class_names = db.get_all_class_names()
    selected_class = request.args.get("class_name") or (class_names[0] if class_names else None)
    subjects = db.get_subjects(class_name=selected_class) if selected_class else []
    faculty = db.get_all_faculty()
    timetable = db.get_timetable(class_name=selected_class) if selected_class else []

    return render_template(
        "timetable.html",
        class_names=class_names, selected_class=selected_class,
        subjects=subjects, faculty=faculty, timetable=timetable,
        days=db.DAYS_OF_WEEK,
    )


# ---------------------------------------------------------------------
# Face capture (registration step 2)
# ---------------------------------------------------------------------

@app.route("/capture/<int:user_id>")
@auth.login_required
def capture(user_id):
    user = db.get_user_by_id(user_id)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("dashboard"))
    if session.get("user_id") != user_id and session.get("role") != "admin":
        flash("You can only capture your own face.", "error")
        return redirect(url_for("dashboard"))
    return render_template("capture.html", target_user=user, min_samples=MIN_SAMPLES_REQUIRED)


@app.route("/api/save_sample", methods=["POST"])
@auth.login_required
def api_save_sample():
    data = request.get_json(force=True)
    label = data.get("label")
    image_b64 = data.get("image")

    if label is None or not image_b64:
        return jsonify({"ok": False, "message": "Missing label or image."}), 400

    image_bgr = face_utils.decode_base64_image(image_b64)
    if image_bgr is None:
        return jsonify({"ok": False, "message": "Could not decode image."}), 400

    existing = face_utils.count_samples(label)
    saved = face_utils.save_face_sample(label, image_bgr, existing + 1)

    if not saved:
        return jsonify({"ok": False, "message": "No face detected. Look at the camera."}), 200

    return jsonify({"ok": True, "count": face_utils.count_samples(label)})


@app.route("/api/finish_registration", methods=["POST"])
@auth.login_required
def api_finish_registration():
    data = request.get_json(force=True)
    label = data.get("label")

    if face_utils.count_samples(label) < 5:
        return jsonify({"ok": False, "message": "Not enough face samples captured."}), 400

    if not face_utils.train_model():
        return jsonify({"ok": False, "message": "Training failed."}), 500

    db.mark_face_registered(label)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------
# Mark attendance (per subject / lecture)
# ---------------------------------------------------------------------

@app.route("/attendance")
@auth.login_required
def attendance_page():
    if session.get("role") != "student":
        flash("Only students mark their own attendance here. Admins can view reports instead.", "error")
        return redirect(url_for("dashboard"))

    class_name = session.get("class_name")
    lectures = db.today_lectures_for_class(class_name) if class_name else []
    for lec in lectures:
        lec["marked"] = db.already_marked(session["user_id"], lec["subject_id"])

    settings = db.get_settings()
    geofence_enabled = bool(settings and settings.get("office_lat") and settings.get("office_lng"))
    return render_template("attendance.html", lectures=lectures, geofence_enabled=geofence_enabled)


@app.route("/api/recognize", methods=["POST"])
@auth.login_required
def api_recognize():
    if not face_utils.model_exists():
        return jsonify({"ok": False, "message": "No trained faces yet. Register your face first."})

    data = request.get_json(force=True)
    subject_id = data.get("subject_id")
    image_b64 = data.get("image")
    lat = data.get("lat")
    lng = data.get("lng")

    if not subject_id:
        return jsonify({"ok": False, "message": "No lecture/subject specified."})

    image_bgr = face_utils.decode_base64_image(image_b64)
    if image_bgr is None:
        return jsonify({"ok": False, "message": "Could not decode image."})

    result = face_utils.recognize_face(image_bgr)
    if result is None:
        return jsonify({"ok": False, "message": "No face detected."})

    label = result["label"]
    confidence = result["confidence"]
    if not face_utils.is_match_acceptable(confidence):
        return jsonify({"ok": False, "message": "Face not recognized confidently. Try again."})

    if label != session["user_id"]:
        return jsonify({"ok": False, "message": "Face does not match the logged-in account."})

    user = db.get_user_by_id(label)
    if not user or not user["active"]:
        return jsonify({"ok": False, "message": "This account is not active."})

    # --- Geofence check ---
    settings = db.get_settings()
    within_geofence = True
    distance_m = None
    if settings and settings.get("office_lat") and settings.get("office_lng"):
        if lat is None or lng is None:
            return jsonify({"ok": False, "message": "Location access is required to mark attendance."})
        distance_m = db.haversine_distance_m(settings["office_lat"], settings["office_lng"], lat, lng)
        within_geofence = distance_m is not None and distance_m <= settings["radius_m"]
        if not within_geofence:
            return jsonify({
                "ok": False,
                "message": f"You are {round(distance_m)}m away — outside the {settings['radius_m']}m allowed radius."
            })

    if db.already_marked(user["id"], subject_id):
        subject = db.get_subject(subject_id)
        return jsonify({"ok": True, "already": True,
                         "message": f"Already marked present for {subject['name'] if subject else 'this subject'} today."})

    db.mark_attendance(user["id"], subject_id, confidence, lat, lng, distance_m, within_geofence)
    subject = db.get_subject(subject_id)
    return jsonify({"ok": True, "already": False,
                     "message": f"Attendance marked for {subject['name'] if subject else 'subject'}!"})


# ---------------------------------------------------------------------
# Dashboards (role-aware)
# ---------------------------------------------------------------------

@app.route("/dashboard")
@auth.login_required
def dashboard():
    if session.get("role") == "student":
        stats = db.get_student_subject_stats(session["user_id"])
        overall_pct = db.get_overall_percentage(session["user_id"])
        return render_template("dashboard_student.html", stats=stats, overall_pct=overall_pct)
    else:
        summary = db.get_today_summary()
        class_names = db.get_all_class_names()
        selected_class = request.args.get("class_name") or (class_names[0] if class_names else None)
        class_stats = db.get_class_subject_stats(selected_class) if selected_class else []
        return render_template(
            "dashboard_admin.html", summary=summary, class_names=class_names,
            selected_class=selected_class, class_stats=class_stats,
        )


# ---------------------------------------------------------------------
# Student management (admin only)
# ---------------------------------------------------------------------

@app.route("/students")
@auth.admin_required
def manage_students():
    class_names = db.get_all_class_names()
    selected_class = request.args.get("class_name")
    students = db.get_all_students(class_name=selected_class)
    faculty = db.get_all_faculty()
    return render_template(
        "students.html", students=students, faculty=faculty,
        class_names=class_names, selected_class=selected_class,
    )


@app.route("/students/remove/<int:user_id>", methods=["POST"])
@auth.admin_required
def remove_student(user_id):
    if user_id == session.get("user_id"):
        flash("You cannot remove your own account.", "error")
        return redirect(url_for("manage_students"))
    db.deactivate_user(user_id)
    flash("User removed (deactivated). Their attendance history is preserved.", "success")
    return redirect(url_for("manage_students"))


@app.route("/students/restore/<int:user_id>", methods=["POST"])
@auth.admin_required
def restore_student(user_id):
    db.reactivate_user(user_id)
    flash("User re-activated.", "success")
    return redirect(url_for("manage_students"))


# ---------------------------------------------------------------------
# Reports & export (admin only)
# ---------------------------------------------------------------------

@app.route("/reports")
@auth.admin_required
def reports():
    class_name = request.args.get("class_name") or None
    subject_id = request.args.get("subject_id") or None
    start_date = request.args.get("start_date") or None
    end_date = request.args.get("end_date") or None

    records = db.get_attendance_log(class_name, subject_id, start_date, end_date)
    class_names = db.get_all_class_names()
    subjects = db.get_subjects(class_name=class_name) if class_name else db.get_subjects()

    return render_template(
        "reports.html", records=records, class_names=class_names, subjects=subjects,
        filters={"class_name": class_name or "", "subject_id": subject_id or "",
                 "start_date": start_date or "", "end_date": end_date or ""},
    )


def _report_dataframe():
    class_name = request.args.get("class_name") or None
    subject_id = request.args.get("subject_id") or None
    start_date = request.args.get("start_date") or None
    end_date = request.args.get("end_date") or None
    records = db.get_attendance_log(class_name, subject_id, start_date, end_date)
    df = pd.DataFrame(records)
    if df.empty:
        df = pd.DataFrame(columns=["date", "time", "name", "id_number", "class_name", "subject_name", "status"])
    return df


@app.route("/export/excel")
@auth.admin_required
def export_excel():
    df = _report_dataframe()
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Attendance")
    buffer.seek(0)
    return send_file(buffer, as_attachment=True,
                      download_name=f"attendance_report_{date.today().isoformat()}.xlsx",
                      mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/export/csv")
@auth.admin_required
def export_csv():
    df = _report_dataframe()
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    mem = io.BytesIO(buffer.getvalue().encode("utf-8"))
    return send_file(mem, as_attachment=True,
                      download_name=f"attendance_report_{date.today().isoformat()}.csv",
                      mimetype="text/csv")


if __name__ == "__main__":
    app.run(debug=True)
