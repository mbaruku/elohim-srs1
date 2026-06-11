from flask import Flask, render_template, request, redirect, session, flash, url_for
from flask import make_response, send_file, jsonify
from xhtml2pdf import pisa
from io import BytesIO
from datetime import datetime
import pdfkit
from collections import defaultdict
import io
from sqlalchemy import or_
import os
from sqlalchemy.orm import joinedload
import csv
from flask import Response
from collections import defaultdict
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy import inspect
from functools import wraps
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from collections import defaultdict
from flask_migrate import Migrate
from flask_login import LoginManager, current_user, login_required
import json

# Import models na db
from models import db, User, Subject, StudentResult, TeacherSubject, StudentProfile, Feedback, Resource, Event
app = Flask(__name__)

# SECRET KEY
app.secret_key = os.environ.get('SECRET_KEY', 'dev_secret_key')

# DATABASE
# app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_DATABASE_URI'] ='sqlite:///elohim.db'
# app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://myappuser:123456@localhost:5432/elohimdb"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)

# Migrate
# migrate = Migrate(app, db)
# @event.listens_for(Engine, "connect")
# def set_sqlite_pragma(dbapi_connection, connection_record):
#     cursor = dbapi_connection.cursor()
#     cursor.execute("PRAGMA foreign_keys=ON")
#     cursor.close()

# Login manager
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)


# Load user
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Admin decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'role' not in session or session['role'] != 'admin':
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# Create tables automatically
@app.before_request
def create_tables():
    with app.app_context():
        db.create_all()


# Run app


@app.route('/add_admin', methods=['GET', 'POST'])
def add_admin():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Angalia kama user tayari yupo
        if User.query.filter_by(username=username).first():
            flash("Admin huyu tayari yupo.", "danger")
            return redirect('/add_admin')

        hashed_password = generate_password_hash(password)
        new_admin = User(username=username, password_hash=hashed_password, role='admin')
        db.session.add(new_admin)
        db.session.commit()
        flash("Admin ameongezwa kikamilifu!", "success")
        return redirect('/add_admin')

    return render_template('add_admin.html')


@app.route('/')
def home():
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        # 🔹 tumia method ya model
        if user and user.check_password(password):
            # Save session or login_user
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            session['class_level'] = user.class_level
            session['is_class_teacher'] = user.is_class_teacher

            # Redirect kulingana na role
            if user.role == 'admin':
                return redirect('/admin')
            elif user.role == 'teacher':
                if user.is_class_teacher:
                    return redirect('/teacher/class-teacher-dashboard')
                else:
                    return redirect('/teacher')
            elif user.role == 'student':
                return redirect('/student')
            else:
                flash('Haijulikani aina ya mtumiaji.', 'danger')
                return redirect('/login')
        else:
            flash('Jina la mtumiaji au nenosiri si sahihi.', 'danger')
            return redirect('/login')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# Flask route
from sqlalchemy import or_
from collections import defaultdict
from datetime import datetime

@app.route('/admin')
@admin_required
def admin_dashboard():

    from collections import defaultdict
    from datetime import datetime

    term = request.args.get('term')
    exam_type = request.args.get('exam_type')
    year = request.args.get('year')

    academic_year = int(year) if year else None

    class_map = {
        "Form One": "Form1",
        "Form Two": "Form2",
        "Form Three": "Form3",
        "Form Four": "Form4"
    }

    grade_points = {'A': 1, 'B': 2, 'C': 3, 'D': 4, 'F': 5}

    class_results = {}

    for form in class_map.keys():

        students = User.query.filter_by(
            role='student',
            class_level=form
        ).all()

        # =========================
        # FILTER RESULTS
        # =========================
        query = StudentResult.query.filter(
            StudentResult.class_level == form
        )

        if term:
            query = query.filter(StudentResult.term == term)

        if exam_type:
            query = query.filter(StudentResult.exam_type == exam_type)

        if academic_year:
            query = query.filter(StudentResult.academic_year == academic_year)

        all_results = query.all()

        # =========================
        # GROUP BY STUDENT
        # =========================
        student_map = defaultdict(dict)

        for r in all_results:
            student_map[r.student_id][r.subject] = r

        rows = []
        subjects_map = {}

        for student in students:

            student_subjects = Subject.query.filter_by(
                class_level=student.class_level
            ).all()

            if student.combination:
                student_subjects = [
                    s for s in student_subjects
                    if (s.category or "").lower() in [
                        student.combination.lower(),
                        "both"
                    ]
                ]

            subject_names = [s.name for s in student_subjects]
            subjects_map[student.id] = subject_names

            marks = {}
            total_marks = 0
            count_subjects = 0
            subject_points = []

            student_results = student_map.get(student.id, {}).values()

            for subject in subject_names:

                r = student_map.get(student.id, {}).get(subject)

                if r:
                    avg = round(r.average or 0, 2)

                    marks[subject] = {
                        "marks": avg,
                        "grade": r.grade
                    }

                    total_marks += avg
                    count_subjects += 1

                    if r.grade in grade_points:
                        subject_points.append(grade_points[r.grade])
                else:
                    marks[subject] = None

            complete = all(
                marks[s] is not None for s in subject_names
            ) if subject_names else False

            average_marks = round(
                total_marks / count_subjects, 2
            ) if count_subjects else 0

            # =========================
            # DIVISION
            # =========================
            division = None
            total_points = None

            if len(subject_points) >= 7:
                best7 = sorted(subject_points)[:7]
                total_points = sum(best7)

                if 7 <= total_points <= 17:
                    division = "I"
                elif 18 <= total_points <= 21:
                    division = "II"
                elif 22 <= total_points <= 25:
                    division = "III"
                elif 26 <= total_points <= 33:
                    division = "IV"
                else:
                    division = "0"

            # =========================
            # 🔥 FIXED APPROVED LOGIC
            # =========================
            approved = False

            if student_results:
                approved = all(
                    r.approved for r in student_results if r
                )

            rows.append({
                "student": student,
                "marks": marks,
                "complete": complete,
                "average": average_marks,
                "aggregate": total_points,
                "division": division,
                "approved": approved,
            })

        # =========================
        # RANKING
        # =========================
        rows = sorted(rows, key=lambda x: x["average"], reverse=True)

        for i, r in enumerate(rows, start=1):
            r["position"] = i

        class_results[class_map[form]] = {
            "rows": rows,
            "subjects_map": subjects_map
        }

    now = datetime.now()

    return render_template(
        "admin/dashboard.html",
        class_results=class_results,
        subjects = Subject.query.order_by(Subject.id.asc()).all(),
        teachers=User.query.filter_by(role='teacher').count(),
        students=User.query.filter_by(role='student').count(),
        current_month=now.strftime("%B"),
        current_year=now.year,
        users=User.query.all()
    )
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')

ALLOWED_PDF = {'pdf'}
ALLOWED_VIDEO = {'mp4','mov','avi','mkv'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER    



@app.route("/admin/upload-resource", methods=["POST"])
def upload_resource():
    title = request.form['title']
    file = request.files['file']
    if file and allowed_file(file.filename, ALLOWED_PDF):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        url = url_for('static', filename=f'uploads/{filename}')
        res = Resource(title=title, file_url=url)
        db.session.add(res)
        db.session.commit()
        # Return JSON for AJAX
        return jsonify({"status":"success", "title": title, "file_url": url})
    return jsonify({"status":"error", "message":"Invalid file type. Only PDFs allowed."})


@app.route("/admin/upload-event", methods=["POST"])
def upload_event():
    title = request.form['title']
    description = request.form['description']
    file = request.files['file']
    if file and allowed_file(file.filename, ALLOWED_VIDEO):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        url = url_for('static', filename=f'uploads/{filename}')
        ev = Event(title=title, description=description, video_url=url)
        db.session.add(ev)
        db.session.commit()
        return jsonify({"status":"success", "title": title, "video_url": url, "description": description})
    return jsonify({"status":"error", "message":"Invalid file type. Only videos allowed."})       


@app.route("/admin/add-teacher", methods=["POST"])
@admin_required
def add_teacher():

    username = request.form["username"]
    class_level = request.form.get("class_level")
    is_class_teacher = True if request.form.get("is_class_teacher") else False

    subjects = request.form.getlist("subjects[]")
    classes = request.form.getlist("classes[]")

    print("Subjects:", subjects)
    print("Classes:", classes)

    # Hakikisha username ina majina matatu
    names = username.strip().split(" ")

    if len(names) != 3:
        flash("Username lazima iwe majina matatu mfano: Juma Ali Said", "danger")
        return redirect("/admin")

    # password = jina la tatu
    password = names[2]

    # Hakiki kama tayari yupo
    if User.query.filter_by(username=username).first():
        flash("Mwalimu huyu tayari yupo", "danger")
        return redirect("/admin")

    # Tengeneza mwalimu
    user = User(
        username=username,
        role="teacher",
        class_level=class_level,
        is_class_teacher=is_class_teacher
    )

    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    # Hifadhi subjects + classes
    for subject, cls in zip(subjects, classes):

        if subject and cls:

            ts = TeacherSubject(
                teacher_id=user.id,
                subject=subject,
                class_level=cls
            )

            db.session.add(ts)

    db.session.commit()

    flash("Mwalimu ameongezwa kikamilifu", "success")

    return redirect("/admin")

@app.route("/admin/add-student", methods=["POST"])
@admin_required
def add_student():

    username = request.form["username"].strip()
    password = request.form["password"].strip()
    class_level = request.form["class_level"]
    combination = request.form.get("combination", "").strip().lower()

    # CHECK USER
    if User.query.filter_by(username=username).first():
        flash("Mwanafunzi huyo tayari yupo", "danger")
        return redirect("/admin")

    # CREATE STUDENT
    user = User(
        username=username,
        role="student",
        class_level=class_level,
        combination=combination
    )

    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    # BASE QUERY
    valid_query = Subject.query.filter_by(class_level=class_level)

    # 🔥 APPLY FILTER ONLY IF COMBINATION EXISTS
    if combination:

        valid_query = valid_query.filter(
            db.or_(
                db.func.lower(Subject.category) == combination,
                db.func.lower(Subject.category) == "both"
            )
        )

    subjects = valid_query.all()

    # ASSIGN SUBJECTS
    for sub in subjects:
        ts = TeacherSubject(
            teacher_id=user.id,
            subject=sub.name,
            class_level=class_level
        )
        db.session.add(ts)

    db.session.commit()

    flash("Mwanafunzi ameongezwa na masomo sahihi", "success")
    return redirect("/admin")

    
@app.route('/admin/delete-user', methods=['POST'])
@admin_required
def delete_user():
    username = request.form['username']
    user = User.query.filter_by(username=username).first()

    if not user:
        flash('Mtumiaji hakupatikana', 'danger')
        return redirect('/admin')

    try:
        #  1. Delete student results (important safety net)
        StudentResult.query.filter_by(student_id=user.id).delete()

        #  2. Delete profile
        StudentProfile.query.filter_by(student_id=user.id).delete()

        #  3. Delete user itself
        db.session.delete(user)

        db.session.commit()
        flash(f'Mtumiaji {username} amefutwa', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')

    return redirect('/admin')


@app.route('/admin/all-classes')
@admin_required
def view_all_classes():
    # Pata wanafunzi wote
    students = User.query.filter_by(role='student').all()

    # Pangilia kwa darasa na combination
    grouped_students = {}
    for student in students:
        key = f"{student.class_level} - {student.combination}"
        if key not in grouped_students:
            grouped_students[key] = []
        grouped_students[key].append(student)

    return render_template('admin/classes.html', grouped_students=grouped_students)


@app.route('/admin/all-teachers')
@admin_required
def view_all_teachers():
    teachers = User.query.filter_by(role='teacher').all()
    return render_template('admin/teachers.html', teachers=teachers)


@app.route('/admin/edit-user/<int:id>', methods=['GET', 'POST'])
@admin_required
def edit_user(id):
    user = User.query.get_or_404(id)

    role = user.role  # 'teacher' au 'student'

    # Orodha ya masomo yote yanayopatikana (unaweza kuihamisha kwenye database kama unataka)
    ALL_SUBJECTS = [
        "Mathematics",
        "English",
        "Physics",
        "Chemistry",
        "Biology",
        "Geography",
        "History",
        "Civics",
        "Kiswahili",
        "Literature",
        "Islamic Knowledge",
        "Bible Knowledge",
        "Information and Computer Studies(ICT)",
        "French",
    ]

    current_subjects = []
    if role == 'teacher':
        current_subjects = [ts.subject for ts in TeacherSubject.query.filter_by(teacher_id=user.id).all()]

    if request.method == 'POST':
        user.username = request.form['username']
        user.class_level = request.form['class_level']
       

        if role == 'teacher':
            selected_subjects = request.form.getlist('subjects[]')
            TeacherSubject.query.filter_by(teacher_id=user.id).delete()
            for subject in selected_subjects:
                db.session.add(TeacherSubject(
                    teacher_id=user.id,
                    subject=subject,
                    class_level=user.class_level or "Unknown"
                ))

        db.session.commit()
        flash("Taarifa zimehifadhiwa", "success")
        return redirect(url_for('view_all_teachers'))

    return render_template('admin/edit_user.html',
                           user=user,
                           role=role,
                           all_subjects=ALL_SUBJECTS,
                           current_subjects=current_subjects)


@app.route("/teacher")
def teacher_dashboard():
    if "role" not in session or session["role"] != "teacher":
        return redirect("/login")

    teacher_id = session.get("user_id")
    teacher = db.session.get(User, teacher_id)

    # =====================
    # SUBJECTS
    # =====================
    subjects = TeacherSubject.query.filter_by(teacher_id=teacher_id).all()

    class_levels = list(set([s.class_level for s in subjects]))

    # =====================
    # STUDENTS
    # =====================
    all_students = User.query.filter(
        User.role == "student",
        User.class_level.in_(class_levels)
    ).all()

    subject_students_map = {}

    print("\n========== DEBUG START ==========")

    for sub in subjects:

        subject_obj = Subject.query.filter_by(
            name=sub.subject,
            class_level=sub.class_level
        ).first()

        subject_category = (
            subject_obj.category.strip().lower()
            if subject_obj and subject_obj.category
            else ""
        )

        print(f"\nSUBJECT: {sub.subject} | CLASS: {sub.class_level}")
        print("CATEGORY:", subject_category)

        filtered_students = []

        for student in all_students:

            if student.class_level != sub.class_level:
                continue

            student_combination = (student.combination or "").strip().lower()

            print(f"Checking -> {student.username} | {student_combination}")

            if subject_category == "both":
                filtered_students.append(student)

            elif subject_category and student_combination:
                if (
                    subject_category in student_combination
                    or student_combination in subject_category
                ):
                    filtered_students.append(student)

        # 🔥 IMPORTANT FIX (STABLE KEY)
        subject_students_map[sub.id] = filtered_students

        print("FINAL:", [s.username for s in filtered_students])

    print("========== DEBUG END ==========\n")

    return render_template(
        "teacher/dashboard.html",
        teacher=teacher,
        subjects=subjects,
        subject_students_map=subject_students_map
    )

@app.route("/test-subjects/<username>")
def test_subjects(username):
    teacher = User.query.filter_by(username=username).first()
    if not teacher:
        return "Mwalimu hayupo"

    subjects = TeacherSubject.query.filter_by(teacher_id=teacher.id).all()
    return (
        "<br>".join([f"{s.subject} - {s.class_level}" for s in subjects])
        or "Hakuna masomo"
    )


# 🔹 Function ya kuhesabu grade na remarks
def get_grade_and_remarks(total):
    if total >= 80:
        return "A", "Excellent"
    elif total >= 70:
        return "B", "Very Good"
    elif total >= 60:
        return "C", "Good"
    elif total >= 50:
        return "D", "Average"
    elif total >= 40:
        return "E", "Pass"
    else:
        return "F", "Fail"

@app.route('/teacher/upload-result', methods=['POST'])
def upload_result():

    if session.get('role') != 'teacher':
        return redirect('/login')

    is_class_teacher = session.get('is_class_teacher', False)

    subject = request.form.get('subject')
    class_level = request.form.get('class_level')
    term = request.form.get('term')
    exam_type = request.form.get('exam_type')
    academic_year = request.form.get('academic_year')

    if not all([subject, class_level, term, exam_type, academic_year]):
        flash("Missing required fields!", "danger")
        return redirect('/teacher')

    try:
        academic_year = int(academic_year)
    except:
        flash("Invalid academic year!", "danger")
        return redirect('/teacher')

    subject_obj = Subject.query.filter_by(
        name=subject,
        class_level=class_level
    ).first()

    if not subject_obj:
        flash("Subject not found!", "danger")
        return redirect('/teacher')

    students = User.query.filter_by(
        role='student',
        class_level=class_level
    ).order_by(User.username.asc()).all()

    def safe_float(v):
        try:
            return float(v)
        except:
            return None

    for student in students:

        sid = student.id

        result = StudentResult.query.filter_by(
            student_id=sid,
            subject=subject,
            class_level=class_level,
            term=term,
            academic_year=academic_year,
            exam_type=exam_type
        ).first()

        if not result:
            result = StudentResult(
                student_id=sid,
                subject=subject,
                class_level=class_level,
                term=term,
                academic_year=academic_year,
                exam_type=exam_type
            )
            db.session.add(result)

        # ======================
        # GET INPUTS
        # ======================
        test1_raw = request.form.get(f'test1_{sid}')
        test2_raw = request.form.get(f'test2_{sid}')
        exam_raw = request.form.get(f'exam_{sid}')

        # ======================
        # UPDATE ONLY IF EXISTS
        # ======================
        if test1_raw not in [None, '']:
            result.test1 = safe_float(test1_raw)

        if test2_raw not in [None, '']:
            result.test2 = safe_float(test2_raw)

        if exam_raw not in [None, '']:
            result.exam_marks = safe_float(exam_raw)

        # ======================
        # RECALCULATE SAFELY
        # ======================
        marks = []

        if result.test1 is not None:
            marks.append(result.test1)

        if result.test2 is not None:
            marks.append(result.test2)

        if result.exam_marks is not None:
            marks.append(result.exam_marks)

        total = sum(marks)
        average = total / len(marks) if marks else 0

        result.total = total
        result.average = average

        # ======================
        # GRADE
        # ======================
        if average >= 75:
            result.grade = "A"
        elif average >= 65:
            result.grade = "B"
        elif average >= 45:
            result.grade = "C"
        elif average >= 30:
            result.grade = "D"
        else:
            result.grade = "F"

    db.session.commit()

    flash("Results saved successfully!", "success")

    if is_class_teacher:
        return redirect('/teacher/class-teacher-dashboard')

    return redirect('/teacher')

from flask import session, redirect, render_template
from datetime import datetime
from collections import defaultdict
@app.route('/student')
def student_dashboard():

    if 'role' not in session or session['role'] != 'student':
        return redirect('/login')

    student_id = session['user_id']
    student = User.query.get_or_404(student_id)

    # =========================
    # SUBJECT FILTER
    # =========================
    subjects_query = Subject.query.filter_by(
        class_level=student.class_level
    ).all()

    if student.combination:
        subjects_allowed = [
            s.name for s in subjects_query
            if s.category and s.category.lower() in [
                student.combination.lower(),
                "both"
            ]
        ]
    else:
        subjects_allowed = [s.name for s in subjects_query]

    # =========================
    # FILTERS
    # =========================
    selected_year = request.args.get('year')
    selected_term = request.args.get('term')
    selected_exam_type = request.args.get('exam_type')

    # =========================
    # RESULTS QUERY
    # =========================
    query = StudentResult.query.filter(
        StudentResult.student_id == student_id,
        StudentResult.subject.in_(subjects_allowed),
        StudentResult.approved == True
    )

    if selected_year:
        query = query.filter(StudentResult.academic_year == selected_year)

    if selected_term:
        query = query.filter(StudentResult.term == selected_term)

    if selected_exam_type:
        query = query.filter(StudentResult.exam_type == selected_exam_type)

    results = query.order_by(StudentResult.subject.asc()).all()

    approved = len(results) > 0

    # =========================
    # REMARKS
    # =========================
    grade_remarks = {
        "A": "Excellent",
        "B": "Very Good",
        "C": "Good",
        "D": "Fair",
        "F": "Poor"
    }

    for r in results:
        r.remarks = grade_remarks.get((r.grade or "").upper(), "-")

    # =========================
    # POINTS + DIVISION (FIXED)
    # =========================
    points_map = {
        "A": 1,
        "B": 2,
        "C": 3,
        "D": 4,
        "F": 5
    }

    subject_points = [
        points_map.get((r.grade or "").upper())
        for r in results
        if (r.grade or "").upper() in points_map
    ]

    total_points = None

    division_display = "Incomplete"

    if len(subject_points) >= 7:

        best7 = sorted(subject_points)[:7]
        total_points = sum(best7)

        if 7 <= total_points <= 17:
            division = "I"
        elif 18 <= total_points <= 21:
            division = "II"
        elif 22 <= total_points <= 25:
            division = "III"
        elif 26 <= total_points <= 33:
            division = "IV"
        else:
            division = "V"

        division_display = f"Division {division} - {total_points} Points"

    # =========================
    # CLASS RANK (FIXED)
    # =========================
    all_students = User.query.filter_by(
        role='student',
        class_level=student.class_level
    ).all()

    scores_by_student = {}

    for s in all_students:

        q = StudentResult.query.filter(
            StudentResult.student_id == s.id,
            StudentResult.approved == True
        )

        if selected_year:
            q = q.filter(StudentResult.academic_year == selected_year)

        if selected_term:
            q = q.filter(StudentResult.term == selected_term)

        if selected_exam_type:
            q = q.filter(StudentResult.exam_type == selected_exam_type)

        res = q.all()

        total = sum(r.total or 0 for r in res)

        scores_by_student[s.id] = total

    sorted_students = sorted(
        scores_by_student.items(),
        key=lambda x: x[1],
        reverse=True
    )

    rank = next(
        (i + 1 for i, (sid, _) in enumerate(sorted_students) if sid == student_id),
        None
    )

    total_students = len(scores_by_student)

    # =========================
    # PROFILE + OTHER DATA
    # =========================
    profile = student.profile

    profile_data = {
        "requirements": json.loads(profile.requirements or "[]") if profile else [],
        "dorm_items": json.loads(profile.dorm_items or "[]") if profile else [],
        "term": profile.term if profile else None,
        "school_fees": profile.school_fees if profile else None,
        "other_contributions": profile.other_contributions if profile else "",
        "character_assessment": json.loads(profile.character_assessment or "{}") if profile else {},
        "health_state": profile.health_state if profile else "",
        "teacher_remarks": profile.teacher_remarks if profile else ""
    }

    resources = Resource.query.all()
    events = Event.query.order_by(Event.created_at.desc()).all()

    now = datetime.now()

    return render_template(
        'student/dashboard.html',

        student=student,
        results=results,
        approved=approved,

        rank=rank,
        total_students=total_students,

        division=division_display,
        total_points=total_points,   # 👈 IMPORTANT ADDED

        profile=profile_data,
        resources=resources,
        events=events,

        years=sorted(list({r.academic_year for r in StudentResult.query.filter_by(student_id=student_id).all()}), reverse=True),
        terms=sorted(list({r.term for r in StudentResult.query.filter_by(student_id=student_id).all() if r.term})),
        exam_types=sorted(list({r.exam_type for r in StudentResult.query.filter_by(student_id=student_id).all() if r.exam_type})),

        selected_year=selected_year,
        selected_term=selected_term,
        selected_exam_type=selected_exam_type,

        exam_month=now.strftime("%B"),
        exam_year=now.year,

        combination=student.combination,
        subjects_allowed=subjects_allowed
    )
@app.route("/fix-students-set-class")
def fix_students_set_class():
    students = User.query.filter_by(role="student").all()
    for s in students:
        if not s.class_level:
            s.class_level = "Form One"  # Badilisha kama unataka Form Two, etc.
    db.session.commit()
    return "Class level zimeongezwa kwa wanafunzi"


@app.route('/check-class-students')
def check_class_students():
    output = []

    class_levels = ["Form One", "Form Two", "Form Three", "Form Four"]
    for cl in class_levels:
        students = User.query.filter_by(role='student', class_level=cl).all()
        output.append(f"<h4>{cl}</h4>")
        if students:
            for s in students:
                output.append(f"{s.username} - {s.class_level}<br>")
        else:
            output.append("<p>Hakuna mwanafunzi</p>")

    return "".join(output)


@app.route("/list-students")
def list_students():
    students = User.query.filter_by(role="student").all()
    output = ["<h3>Orodha ya Wanafunzi:</h3>"]
    for s in students:
        output.append(f"{s.username} - class_level: {s.class_level or 'Hakuna'}<br>")
    return "".join(output)


@app.route("/fix-class/<level>")
def fix_all_students_to_class(level):
    students = User.query.filter_by(role="student").all()
    for s in students:
        s.class_level = level
    db.session.commit()
    return f"Wanafunzi wote wamewekwa kwenye '{level}'"


@app.route("/normalize-classes")
def normalize_class_levels():
    mapping = {
        "F1": "Form One",
        "F2": "Form Two",
        "F3": "Form Three",
        "F4": "Form Four",
    }
    students = User.query.filter_by(role="student").all()
    for student in students:
        if student.class_level in mapping:
            student.class_level = mapping[student.class_level]
    db.session.commit()
    return "Class levels zimetengenezwa kikamilifu!"





from datetime import datetime
from io import BytesIO
from flask import render_template, request, session, redirect, make_response
from xhtml2pdf import pisa

@app.route('/student-report')
def download_report():

    if 'role' not in session or session['role'] != 'student':
        return redirect('/login')

    student_id = session['user_id']
    student = User.query.get_or_404(student_id)

    year = request.args.get('year')
    term = request.args.get('term')
    exam_type = request.args.get('exam_type')

    generated_date = datetime.now().strftime("%d %B %Y, %H:%M")

    # =========================
    # RESULTS
    # =========================
    query = StudentResult.query.filter(
        StudentResult.student_id == student_id,
        StudentResult.approved == True
    )

    if year:
        query = query.filter(StudentResult.academic_year == year)

    if term:
        query = query.filter(StudentResult.term == term)

    if exam_type:
        query = query.filter(StudentResult.exam_type == exam_type)

    results = query.all()

    # =========================
    # CLASS RANK
    # =========================
    all_students = User.query.filter_by(
        role='student',
        class_level=student.class_level
    ).all()

    scores_by_student = {}

    for s in all_students:

        q = StudentResult.query.filter(
            StudentResult.student_id == s.id,
            StudentResult.approved == True
        )

        if year:
            q = q.filter(StudentResult.academic_year == year)

        if term:
            q = q.filter(StudentResult.term == term)

        if exam_type:
            q = q.filter(StudentResult.exam_type == exam_type)

        res = q.all()

        total = sum(r.total or 0 for r in res)

        scores_by_student[s.id] = total

    sorted_students = sorted(
        scores_by_student.items(),
        key=lambda x: x[1],
        reverse=True
    )

    rank = next(
        (i + 1 for i, (sid, _) in enumerate(sorted_students) if sid == student_id),
        None
    )

    total_students = len(scores_by_student)

    # =========================
    # REMARKS
    # =========================
    grade_remarks = {
        "A": "Excellent",
        "B": "Very Good",
        "C": "Good",
        "D": "Fair",
        "F": "Fail"
    }

    for r in results:
        r.remarks = grade_remarks.get((r.grade or "").upper(), "-")

    # =========================
    # DIVISION (FIXED INDENTATION)
    # =========================
    points_map = {
        "A": 1,
        "B": 2,
        "C": 3,
        "D": 4,
        "F": 5
    }

    subject_points = [
        points_map.get((r.grade or "").upper())
        for r in results
        if (r.grade or "").upper() in points_map
    ]

    division_display = "Incomplete"

    if len(subject_points) >= 7:

        best7 = sorted(subject_points)[:7]
        total_points = sum(best7)

        if 7 <= total_points <= 17:
            division = "I"
        elif 18 <= total_points <= 21:
            division = "II"
        elif 22 <= total_points <= 25:
            division = "III"
        elif 26 <= total_points <= 33:
            division = "IV"
        else:
            division = "V"

        division_display = f"Division {division} - {total_points} Points"

    # =========================
    # RENDER PDF
    # =========================
    html = render_template(
        'student/student-report.html',
        student=student,
        results=results,
        rank=rank,
        total_students=total_students,
        division=division_display,
        year=year,
        term=term,
        exam_type=exam_type,
        generated_date=generated_date
    )

    pdf = BytesIO()
    pisa_status = pisa.CreatePDF(html, dest=pdf)

    if pisa_status.err:
        return "Hitilafu wakati wa kutengeneza PDF"

    response = make_response(pdf.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline; filename=student_report.pdf'

    return response
# Helper: check if current user is class teacher
def is_class_teacher():
    return session.get('role') == 'teacher' and session.get('is_class_teacher', False)



@app.route("/teacher/class-teacher-dashboard")
def class_teacher_dashboard():

    # =========================
    # AUTH CHECK
    # =========================
    if "role" not in session or session["role"] != "teacher":
        return redirect("/login")

    if not session.get("is_class_teacher"):
        return "You are not a class teacher.", 403

    teacher_id = session.get("user_id")
    teacher = db.session.get(User, teacher_id)

    # =========================
    # SUBJECTS
    # =========================
    subjects = TeacherSubject.query.filter_by(
        teacher_id=teacher_id
    ).all()

    class_levels = list(set([s.class_level for s in subjects]))

    # =========================
    # STUDENTS
    # =========================
    students = User.query.filter_by(
    role="student",
    class_level=teacher.class_level
).all()

    student_ids = [s.id for s in students]

    # =========================
    # FEEDBACK
    # =========================
    feedbacks = Feedback.query.filter(
        Feedback.student_id.in_(student_ids)
    ).order_by(Feedback.created_at.desc()).all()

    unread_feedback = Feedback.query.filter(
        Feedback.student_id.in_(student_ids),
        Feedback.is_read == False
    ).count()

    # =========================
    # MARK FEEDBACK AS READ
    # =========================
    for fb in feedbacks:
        if not fb.is_read:
            fb.is_read = True

    db.session.commit()

    # =========================
    # OPTIONAL: SUBJECT STUDENT MAP (FIX FOR FRONTEND)
    # =========================
    subject_students_map = {}

    for sub in subjects:

        subject_obj = Subject.query.filter_by(
            name=sub.subject,
            class_level=sub.class_level
        ).first()

        subject_category = (
            subject_obj.category.strip().lower()
            if subject_obj and subject_obj.category
            else ""
        )

        filtered_students = []

        for student in students:

            if student.class_level != sub.class_level:
                continue

            student_combination = (student.combination or "").strip().lower()

            if subject_category == "both":
                filtered_students.append(student)

            elif subject_category and student_combination:
                if (
                    subject_category in student_combination
                    or student_combination in subject_category
                ):
                    filtered_students.append(student)

        subject_students_map[sub.id] = filtered_students

    # =========================
    # FINAL RENDER (SAFE)
    # =========================
    return render_template(
        "teacher/class-teacher-dashboard.html",

        teacher=teacher,
        subjects=subjects,
        students=students,

        feedbacks=feedbacks,
        unread_feedback=unread_feedback,

        class_teacher=True,

        # 🔥 IMPORTANT FIX
        subject_students_map=subject_students_map
    )


@app.route('/admin/approve-student/<int:student_id>', methods=['POST'])
def approve_student(student_id):

    exam_type = request.form.get('exam_type')
    term = request.form.get('term')
    year = request.form.get('year')

    query = StudentResult.query.filter_by(student_id=student_id)

    if exam_type:
        query = query.filter(StudentResult.exam_type == exam_type)

    if term:
        query = query.filter(StudentResult.term == term)

    if year:
        query = query.filter(StudentResult.academic_year == int(year))

    results = query.all()

    if not results:
        return jsonify({"success": False, "message": "No results found"}), 404

    for r in results:
        r.approved = True

    db.session.commit()

    return jsonify({
        "success": True,
        "student_id": student_id,
        "approved": True
    })

@app.route("/teacher/save-student-requirements", methods=["POST"])
def save_student_requirements():
    if "role" not in session or session["role"] != "teacher":
        return redirect("/login")

    student_id = request.form.get("student_id")
    student = User.query.get(student_id)

    if not student:
        flash("Mwanafunzi haipo", "danger")
        return redirect(request.referrer)

    # Student Requirements
    requirements = request.form.getlist("requirements[]")
    dorm_items = request.form.getlist("dormitory_items[]")

    # School Fees (NOW TEXTAREA)
    term = request.form.get("term")
    school_fees = request.form.get("school_fees")  # text now
    other_contributions = request.form.get("other_contributions")

    # Character Assessment
    char_assess = {
        "discipline": request.form.get("character_discipline"),
        "participation": request.form.get("character_participation"),
        "behavior": request.form.get("character_behavior"),
        "leadership": request.form.get("character_leadership"),
        "punctuality": request.form.get("character_punctuality"),
    }

    # Health State
    health_state = request.form.get("health_state")

    # Teacher Remarks (NEW)
    teacher_remarks = request.form.get("teacher_remarks")

    # Get or create profile
    profile = StudentProfile.query.filter_by(student_id=student.id).first()

    if not profile:
        profile = StudentProfile(student_id=student.id)
        db.session.add(profile)

    # Save data
    profile.requirements = json.dumps(requirements)
    profile.dorm_items = json.dumps(dorm_items)
    profile.term = term
    profile.school_fees = school_fees
    profile.other_contributions = other_contributions
    profile.character_assessment = json.dumps(char_assess)
    profile.health_state = health_state

    # NEW FIELD
    profile.teacher_remarks = teacher_remarks

    db.session.commit()

    flash(f"Data ya {student.username} imehifadhiwa!", "success")
    return redirect(request.referrer)


@app.route("/send-feedback", methods=["POST"])
def send_feedback():

    if "user_id" not in session:
        return redirect("/login")

    message = request.form.get("message")

    feedback = Feedback(
        student_id=session["user_id"],
        message=message
    )

    db.session.add(feedback)
    db.session.commit()

    flash("Feedback imetumwa")

    return redirect("/student")


@app.route("/update-password", methods=["POST"])
def update_password():
    if 'user_id' not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for('login'))

    old_password = request.form.get("old_password")
    new_password = request.form.get("new_password")

    user = User.query.get(session['user_id'])  # 🔹 session-based

    # Angalia password ya sasa
    if not user.check_password(old_password):
        flash("Password ya sasa sio sahihi", "danger")
        return redirect(url_for("student_dashboard"))  # 🔹 function endpoint, sio template

    # Update password
    user.set_password(new_password)  # 🔹 hakikisha set_password inahifadhi hash
    db.session.commit()  # 🔹 commit lazima iwe hapa

    flash("Password imebadilishwa vizuri", "success")
    return redirect(url_for("student_dashboard"))



@app.route("/update-password", methods=["POST"])
def admin_update_password():

    if 'user_id' not in session:
        return redirect('/login')

    user = User.query.get(session['user_id'])

    old_password = request.form.get("old_password")
    new_password = request.form.get("new_password")

    if not user.check_password(old_password):
        flash("Password ya sasa sio sahihi")
        return redirect("/admin")

    user.set_password(new_password)
    db.session.commit()

    flash("Password imebadilishwa vizuri")

    return redirect("/admin")  


@app.route("/teacher/delete-feedback/<int:id>", methods=["POST"])
def delete_feedback(id):

    feedback = Feedback.query.get_or_404(id)

    db.session.delete(feedback)

    db.session.commit()

    flash("Feedback imefutwa")

    return redirect("/teacher/class-teacher-dashboard")  



@app.route("/admin/reset-password/<int:user_id>", methods=["POST"])
@admin_required
def admin_reset_password(user_id):
    user = User.query.get_or_404(user_id)

    # Tumia third name kama default password
    # Assuming full_name ina format "First Middle Last"
    third_name = user.full_name.split()[-1] if user.full_name else "password123"

    # Set new password
    user.set_password(third_name)
    db.session.commit()

    flash(f"Password ya {user.username} ime-reset kuwa '{third_name}'", "success")
    return redirect("/admin")


@app.route('/admin/add-subject-bulk', methods=['POST'])
def add_subject_bulk():

    subjects_text = request.form.get('subjects')
    classes = request.form.getlist('classes')
    category = request.form.get('category')

    subjects_list = [s.strip() for s in subjects_text.split('\n') if s.strip()]

    for subject_name in subjects_list:

        for class_level in classes:

            # avoid duplicates
            exists = Subject.query.filter_by(
                name=subject_name,
                class_level=class_level
            ).first()

            if not exists:

                new_subject = Subject(
                    name=subject_name,
                    class_level=class_level,
                    category=category
                )

                db.session.add(new_subject)

    db.session.commit()

    flash("Subjects added successfully!", "success")

    return redirect(request.referrer)

@app.route("/admin/delete-subject/<int:id>", methods=["POST"])
def delete_subject(id):

    try:
        subject = Subject.query.get_or_404(id)

        print("Deleting:", subject.id, subject.name, subject.class_level)

        db.session.delete(subject)
        db.session.commit()

        flash("Subject removed", "success")

    except Exception as e:
        db.session.rollback()
        print("DELETE ERROR:", str(e))
        flash(str(e), "danger")

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/get-subjects")
def get_subjects():

    class_level = (request.args.get("class_level") or "").strip()
    combination = (request.args.get("combination") or "").strip().lower()

    query = Subject.query.filter_by(class_level=class_level)

    # 🔥 APPLY FILTER KWA MADARASA YOTE KAMA COMBINATION IPO
    if combination:

        query = query.filter(
            db.or_(
                db.func.lower(Subject.category) == combination,
                db.func.lower(Subject.category) == "both"
            )
        )

    subjects = query.order_by(Subject.name).all()

    return {
        "subjects": [s.name for s in subjects]
    }
@app.route("/admin/get-all-subjects")
def get_all_subjects():

    subjects = Subject.query.order_by(Subject.name).all()

    return {
        "subjects": [s.name for s in subjects]
    }

@app.route("/admin/update-subject", methods=["POST"])
def update_subject():

    subject_id = request.form.get("subject_id")

    subject = Subject.query.get_or_404(subject_id)

    subject.name = request.form.get("subject_name")
    subject.class_level = request.form.get("class_level")
    subject.category = request.form.get("category")

    db.session.commit()

    flash("Subject updated successfully", "success")

    return redirect("/admin")
@app.route('/teacher/view-results')
def view_results():

    if session.get('role') != 'teacher':
        return redirect('/login')

    subject = request.args.get('subject')
    class_level = request.args.get('class_level')
    term = request.args.get('term')
    exam_type = request.args.get('exam_type')
    year = request.args.get('year')

    try:
        academic_year = int(year)
    except (TypeError, ValueError):
        academic_year = None

    all_results = StudentResult.query.filter_by(
        subject=subject,
        class_level=class_level,
        term=term,
        academic_year=academic_year,
        exam_type=exam_type
    ).all()

    final_results = []

    for r in all_results:

        # =========================
        # MARKS COLLECTION (SAFE)
        # =========================
        marks = []

        if r.test1 is not None:
            marks.append(float(r.test1))

        if r.test2 is not None:
            marks.append(float(r.test2))

        if r.exam_marks is not None:
            marks.append(float(r.exam_marks))

        # =========================
        # TOTAL
        # =========================
        total = sum(marks)

        # =========================
        # AVERAGE (SAFE)
        # =========================
        count = len(marks)
        average = total / count if count > 0 else 0

        # =========================
        # GRADE
        # =========================
        if average >= 75:
            grade = "A"
        elif average >= 65:
            grade = "B"
        elif average >= 45:
            grade = "C"
        elif average >= 30:
            grade = "D"
        else:
            grade = "F"

        # =========================
        # APPEND
        # =========================
        final_results.append({
            "student": r.student,
            "test1": r.test1,
            "test2": r.test2,
            "exam_marks": r.exam_marks,
            "total": total,
            "average": round(average, 2),
            "grade": grade
        })

    # =========================
    # SORT BY AVERAGE (DESC)
    # =========================
    final_results.sort(
        key=lambda x: x["average"],
        reverse=True
    )

    return render_template(
        'teacher/view_results.html',
        results=final_results,
        subject=subject,
        class_level=class_level,
        term=term,
        academic_year=academic_year,
        exam_type=exam_type
    )

@app.route('/teacher/download-results')
def download_result():

    if 'role' not in session or session['role'] != 'teacher':
        return redirect('/login')

    subject = request.args.get('subject')
    class_level = request.args.get('class_level')
    term = request.args.get('term')
    academic_year = request.args.get('academic_year')

    results = StudentResult.query.options(
        joinedload(StudentResult.student)
    ).filter_by(
        subject=subject,
        class_level=class_level,
        term=term,
        academic_year=academic_year
    ).order_by(StudentResult.average.desc()).all()

    def safe(v):
        return v if v is not None else 0

    def generate():

        # HEADER (corrected)
        yield "Position,Student,Test1,Test2,Exam,Total,Average,Grade\n"

        position = 1

        for r in results:

            test1 = safe(r.test1)
            test2 = safe(r.test2)
            exam = safe(r.exam_marks)
            total = safe(r.total)
            average = round(safe(r.average), 2)
            grade = r.grade or ""

            yield f"{position},{r.student.username},{test1},{test2},{exam},{total},{average},{grade}\n"

            position += 1

    return Response(
        generate(),
        mimetype='text/csv',
        headers={
            "Content-Disposition": "attachment; filename=results.csv"
        }
    )




@app.route('/teacher/edit-results')
def edit_results():

    subject = request.args.get('subject')
    class_level = request.args.get('class_level')
    term = request.args.get('term')
    year = request.args.get('year')

    results = StudentResult.query.filter_by(
        subject=subject,
        class_level=class_level,
        term=term,
        academic_year=year
    ).all()

    return render_template(
        "edit_results.html",
        results=results,
        subject=subject,
        class_level=class_level,
        term=term,
        academic_year=year
    )


@app.route('/teacher/update-results', methods=['POST'])
def update_results():

    subject = request.form.get('subject')
    class_level = request.form.get('class_level')
    term = request.form.get('term')
    academic_year = request.form.get('academic_year')

    result_ids = set()

    # pata result ids kutoka form
    for key in request.form.keys():
        if "_" in key:
            result_ids.add(key.split("_")[-1])

    for rid in result_ids:

        result = StudentResult.query.get(rid)

        if not result:
            continue

        # ===== INPUTS =====
        test1_input = request.form.get(f'test1_{rid}')
        test2_input = request.form.get(f'test2_{rid}')
        pretest_input = request.form.get(f'pretest_{rid}')
        exam_input = request.form.get(f'exam_{rid}')

        # ===== KEEP OLD VALUES =====
        test1 = float(test1_input) if test1_input else (result.test1 or 0)
        test2 = float(test2_input) if test2_input else (result.test2 or 0)
        pre_test = float(pretest_input) if pretest_input else (result.pre_test or 0)
        exam_marks = float(exam_input) if exam_input else (result.exam_marks or 0)

        # ===== SAVE MARKS =====
        result.test1 = test1
        result.test2 = test2
        result.pre_test = pre_test
        result.exam_marks = exam_marks

        # ===== CALCULATION =====
        combined_test = (test2 + pre_test) / 2
        total = test1 + combined_test + exam_marks
        average = total / 3

        # ===== GRADE =====
        if average >= 75:
            grade = "A"
        elif average >= 65:
            grade = "B"
        elif average >= 45:
            grade = "C"
        elif average >= 30:
            grade = "D"
        else:
            grade = "F"

        result.total = total
        result.average = average
        result.grade = grade

    db.session.commit()

    flash("Results updated successfully!", "success")

    return redirect(request.referrer)


@app.route('/admin/edit-subject', methods=['POST'])
def edit_subject():

    subject_id = request.form.get("subject_id")
    subject_name = request.form.get("subject_name")
    class_level = request.form.get("class_level")
    category = request.form.get("category")

    subject = Subject.query.get(subject_id)

    if subject:

        subject.name = subject_name
        subject.class_level = class_level
        subject.category = category

        db.session.commit()

        flash("Subject updated successfully", "success")

    else:

        flash("Subject not found", "danger")

    return redirect(url_for("admin_dashboard"))  



@app.route("/admin/filter-results")
def filter_results():

    try:
        form = request.args.get("form")
        term = request.args.get("term")
        exam_type = request.args.get("exam_type")
        year = request.args.get("year")

        print("FILTERS:", form, term, exam_type, year)

        query = StudentResult.query.filter_by(class_level=form)

        if term:
            query = query.filter(StudentResult.term == term)

        if exam_type:
            query = query.filter(StudentResult.exam_type == exam_type)

        if year:
            query = query.filter(StudentResult.academic_year == int(year))

        results = query.all()

        print("FOUND:", len(results))

        if not results:
            return "<tr><td colspan='10'>Hakuna matokeo</td></tr>"

        html = ""
        for r in results:
            html += f"""
            <tr>
                <td>{r.student.full_name or r.student.username}</td>
                <td>{r.subject}</td>
                <td>{r.total or '-'}</td>
                <td>{r.average or '-'}</td>
                <td>{r.grade or '-'}</td>
            </tr>
            """

        return html

    except Exception as e:
        print("ERROR:", e)
        return "Server error", 500
    

from flask import request, session, redirect, Response
import csv
from io import StringIO


# =========================
# EXPORT FUNCTION (SMART FIX)
# =========================
def get_class_results_for_export(class_level, term, exam_type, year):

    class_level = class_level.strip()
    term = term.strip()
    exam_type = exam_type.strip()
    year = int(year)

    students = User.query.filter_by(
        class_level=class_level,
        role="student"
    ).all()

    results = []

    for s in students:

        subject_results = StudentResult.query.filter(
            StudentResult.student_id == s.id,
            StudentResult.class_level.ilike(class_level),
            StudentResult.term.ilike(term),
            StudentResult.exam_type.ilike(exam_type),
            StudentResult.academic_year == year
        ).all()

        print(f"{s.full_name} -> {len(subject_results)} records found")

        marks = {}
        total = 0
        count = 0

        for r in subject_results:
            marks[r.subject] = {
                "marks": r.exam_marks,
                "grade": r.grade
            }

            if r.exam_marks is not None:
                total += r.exam_marks
                count += 1

        average = total / count if count > 0 else 0

        results.append({
            "student_name": s.full_name or s.username,
            "average": round(average, 2),
            "aggregate": total,
            "division": "",
            "position": "",
            "marks": marks
        })

    return results


# =========================
# DOWNLOAD ROUTE
# =========================
@app.route('/admin/download-results')
def download_results():

    if session.get('role') != 'admin':
        return redirect('/login')

    class_level = request.args.get('class')
    term = request.args.get('term')
    exam_type = request.args.get('exam_type')
    year = request.args.get('year')

    if not all([class_level, term, exam_type, year]):
        return "Missing filters", 400

    results = get_class_results_for_export(
        class_level, term, exam_type, year
    )

    if not results:
        return "No results found for selected filters", 404

    output = StringIO()
    writer = csv.writer(output)

    # =========================
    # HEADER
    # =========================
    first = results[0]
    subjects = first["marks"].keys() if first else []

    header = ["Student"]

    for subject in subjects:
        header.append(f"{subject} Marks")
        header.append(f"{subject} Grade")

    header += ["Average", "Aggregate", "Division", "Position"]

    writer.writerow(header)

    # =========================
    # ROWS
    # =========================
    for r in results:
        row = [r["student_name"]]

        for subject in subjects:
            mark_data = r["marks"].get(subject, {})
            row.append(mark_data.get("marks", ""))
            row.append(mark_data.get("grade", ""))

        row += [
            r["average"],
            r["aggregate"],
            r["division"],
            r["position"]
        ]

        writer.writerow(row)

    output.seek(0)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=Results_{class_level}_{term}_{exam_type}_{year}.csv"
        }
    )


if __name__ == "__main__": 
    app.run(debug=True)


# if __name__ == "__main__":
#     port = int(os.environ.get("PORT", 5000))
#     app.run(host="0.0.0.0", port=port)
