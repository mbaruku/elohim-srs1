from flask import Flask, render_template, request, redirect, session, flash, url_for
from flask_sqlalchemy import SQLAlchemy
from flask import make_response
from xhtml2pdf import pisa
from io import BytesIO
from datetime import datetime
from flask import send_file
import pdfkit
import io
import os
from sqlalchemy import inspect
from functools import wraps
from werkzeug.utils import secure_filename
from flask import session, redirect, url_for
from flask import jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, SubjectAssignment,StudentResult, TeacherSubject,StudentProfile,Feedback,Resource,Event
from flask_migrate import Migrate
from collections import defaultdict
from flask_login import LoginManager,current_user, login_required
import json


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
    "English Literature",
    "Business Study",
    "Historia ya Tanzania na Maadili"
]

app = Flask(__name__)
# secret key kutoka environment
app.secret_key = os.environ.get('SECRET_KEY', 'dev_secret_key')

# database kutoka PostgreSQL (Render sets DATABASE_URL)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render sets PORT environment variable
    app.run(host="0.0.0.0", port=port)

login_manager = LoginManager()
login_manager.login_view = "login"  # route ya login
login_manager.init_app(app)

#  user_loader function
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'role' not in session or session['role'] != 'admin':
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function    

db.init_app(app)

migrate = Migrate(app, db)


@app.before_request
def create_tables():
    db.create_all()


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
@app.route('/admin')
@admin_required
def admin_dashboard():
    # Map DB class names to frontend keys
    class_map = {
        "Form One": "Form1",
        "Form Two": "Form2",
        "Form Three": "Form3",
        "Form Four": "Form4"
    }

    forms = list(class_map.keys())
    class_results = {}

    for form in forms:
        frontend_class = class_map[form]

        students = User.query.filter_by(role='student', class_level=form).all()

        # All subjects assigned for this class
        subjects_query = db.session.query(TeacherSubject.subject)\
            .filter_by(class_level=form).distinct().all()
        subjects = [s[0] for s in subjects_query]

        rows = []
        for student in students:
            marks = {}
            total_points = 0
            valid_grades_count = 0

            for subject in subjects:
                r = StudentResult.query.filter_by(
                    student_id=student.id,
                    subject=subject,
                    class_level=form,
                    approved=False
                ).first()
                if r:
                    marks[subject] = r
                    grade_points = {'A':1,'B':2,'C':3,'D':4,'F':5}
                    if r.grade in grade_points:
                        total_points += grade_points[r.grade]
                        valid_grades_count += 1
                else:
                    marks[subject] = None

            complete = all(marks[s] is not None for s in subjects) and len(subjects) > 0

            if complete and valid_grades_count > 0:
                if 7 <= total_points <= 17:
                    division = "I"
                elif 18 <= total_points <= 22:
                    division = "II"
                elif 23 <= total_points <= 25:
                    division = "III"
                elif 26 <= total_points <= 33:
                    division = "IV"
                elif 34 <= total_points <= 35:
                    division = "V"
                else:
                    division = "0"
            else:
                division = None

            rows.append({
                "student": student,
                "marks": marks,
                "complete": complete,
                "division": division
            })

        class_results[frontend_class] = {
            "subjects": subjects,
            "rows": rows
        }

    # Hapa tunatengeneza current month na year
    now = datetime.now()
    current_month = now.strftime("%B")
    current_year = now.year

    # ✅ Hapa tunaongeza users wote ili search/reset password iweze
    users = User.query.all()

    return render_template(
        "admin/dashboard.html",
        class_results=class_results,
        teachers=User.query.filter_by(role='teacher').count(),
        students=User.query.filter_by(role='student').count(),
        current_month=current_month,
        current_year=current_year,
        users=users  # <<--- hii ni muhimu kwa table ya reset password
    )

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_PDF = {'pdf'}
ALLOWED_VIDEO = {'mp4','mov','avi','mkv'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename, allowed):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in allowed  



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
    combination = request.form.get("combination", "")
    subjects = request.form.getlist("subjects[]")

    # Hakiki username
    if User.query.filter_by(username=username).first():
        flash("Mwanafunzi huyo tayari yupo", "danger")
        return redirect("/admin")

    user = User(username=username, role="student", class_level=class_level, combination=combination)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    # Hifadhi masomo
    for sub in subjects:
        ts = TeacherSubject(teacher_id=user.id, subject=sub, class_level=class_level)
        db.session.add(ts)
    db.session.commit()

    flash("Mwanafunzi ameongezwa pamoja na masomo yake", "success")
    return redirect("/admin")

@app.route('/admin/delete-user', methods=['POST'])
@admin_required
def delete_user():
    username = request.form['username']
    user = User.query.filter_by(username=username).first()

    if not user:
        flash('Mtumiaji hakupatikana', 'danger')
    else:
        db.session.delete(user)  # 🚀 Automatically inafuta na subjects zake kama ni mwalimu
        db.session.commit()
        flash(f'Mtumiaji {username} amefutwa', 'success')

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
    teacher = User.query.get(teacher_id)

 

    # Vuta masomo yote ya mwalimu huyu kutoka TeacherSubject
    subjects = TeacherSubject.query.filter_by(teacher_id=teacher_id).all()

  

    # Patikana wanafunzi wa madarasa anayofundisha
    class_levels = list(set([s.class_level for s in subjects]))
    students = User.query.filter(
        User.role == "student", User.class_level.in_(class_levels)
    ).all()
    
    print("Mwalimu:", teacher.username)
    print("Class level:", class_levels)
    print("Students found:", [s.username for s in students])

    return render_template(
        "teacher/dashboard.html", teacher=teacher, subjects=subjects, students=students,
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
    if 'role' not in session or session['role'] != 'teacher':
        return redirect('/login')

    teacher_id = session['user_id']
    
    student_ids = request.form.getlist('student_ids[]')

    for sid in student_ids:
        test1 = float(request.form.get(f'test1_{sid}', 0))
        test2 = float(request.form.get(f'test2_{sid}', 0))
        exam_type = request.form.get(f'exam_type_{sid}', '')
        exam_marks = float(request.form.get(f'exam_marks_{sid}', 0))

        total = test1 + test2 + exam_marks
        average = total / 3
        # simple grading
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

        # Assume we know class_level & subject for this teacher
        # Here you need to pass it in the form or get from teacher assignment
        subject = request.form.get('subject')  # You must add hidden input for this
        class_level = request.form.get('class_level')  # add hidden input

        # Create or update result
        result = StudentResult.query.filter_by(
            student_id=sid,
            subject=subject,
            class_level=class_level
        ).first()

        if not result:
            result = StudentResult(
                student_id=sid,
                subject=subject,
                class_level=class_level
            )
            db.session.add(result)

        result.test1 = test1
        result.test2 = test2
        result.exam_type = exam_type
        result.exam_marks = exam_marks
        result.total = total
        result.average = average
        result.grade = grade
        result.approved = False  # default not approved

    db.session.commit()
    flash("Matokeo yamehifadhiwa kikamilifu!", "success")
    return redirect('/teacher')  # au redirect back to dashboard
from datetime import datetime

@app.route('/student')
def student_dashboard():
    if 'role' not in session or session['role'] != 'student':
        return redirect('/login')

    student_id = session['user_id']
    student = User.query.get(student_id)

    # Matokeo
    results = StudentResult.query.filter_by(student_id=student_id).all()
    approved = any(r.approved for r in results)
    exam_type = next((r.exam_type for r in results if r.exam_type), None)

    # Rank
    total_students = User.query.filter_by(class_level=student.class_level, role='student').count()
    class_results = StudentResult.query.filter_by(class_level=student.class_level, approved=True).all()
    scores_by_student = {}
    for r in class_results:
        scores_by_student.setdefault(r.student_id, 0)
        scores_by_student[r.student_id] += r.total or 0
    sorted_students = sorted(scores_by_student.items(), key=lambda x: x[1], reverse=True)
    rank = next((i+1 for i,(sid,_) in enumerate(sorted_students) if sid==student_id), None)

    # Remarks & division
    grade_remarks = {"A":"Excellent","B":"Very Good","C":"Good","D":"Fair","F":"Fail"}
    for r in results:
        r.remarks = grade_remarks.get(r.grade, "-")
        r.can_view = r.approved

    points_map = {"A":1,"B":2,"C":3,"D":4,"F":5}
    total_points = sum([points_map.get(r.grade,0) for r in results if r.approved])
    if 7 <= total_points <= 17: division="I"
    elif 18 <= total_points <= 22: division="II"
    elif 23 <= total_points <= 25: division="III"
    elif 26 <= total_points <= 33: division="IV"
    elif total_points >= 34: division="V"
    else: division=None

    # PROFILE
    profile_data = {
        "requirements": json.loads(student.profile.requirements or "[]") if student.profile else [],
        "dorm_items": json.loads(student.profile.dorm_items or "[]") if student.profile else [],
        "term": student.profile.term if student.profile else None,
        "school_fees": student.profile.school_fees if student.profile else None,
        "other_contributions": student.profile.other_contributions if student.profile else "",
        "character_assessment": json.loads(student.profile.character_assessment or "{}") if student.profile else {},
        "health_state": student.profile.health_state if student.profile else ""
    }

    # Resources & Events
    resources = Resource.query.all()   # PDF resources
    events = Event.query.order_by(Event.created_at.desc()).all()  # Latest videos first

    # Month & Year
    now = datetime.now()
    exam_month = now.strftime("%B")
    exam_year = now.year

    return render_template(
        'student/dashboard.html',
        student=student,
        results=results,
        approved=approved,
        rank=rank,
        total_students=total_students,
        division=division,
        profile=profile_data,
        exam_type=exam_type,
        exam_month=exam_month,
        exam_year=exam_year,
        resources=resources,   # << New
        events=events          # << New
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





@app.route('/student-report')
def download_report():

    if 'role' not in session or session['role'] != 'student':
        return redirect('/login')

    student_id = session['user_id']

    student = User.query.get_or_404(student_id)

    results = StudentResult.query.filter_by(student_id=student_id).all()

    # Jumla ya wanafunzi wa darasa hilo
    total_students = User.query.filter_by(
        role='student',
        class_level=student.class_level
    ).count()

    # Hesabu rank
    all_students = User.query.filter_by(
        role='student',
        class_level=student.class_level
    ).all()

    scores = []

    for s in all_students:

        student_results = StudentResult.query.filter_by(student_id=s.id).all()

        total_score = sum([r.total or 0 for r in student_results])

        scores.append((s.id, total_score))

    scores.sort(key=lambda x: x[1], reverse=True)

    rank = None

    for i, s_tuple in enumerate(scores):
        if s_tuple[0] == student_id:
            rank = i + 1
            break

    # Render template
    html = render_template(
        'student/student-report.html',
        student=student,
        results=results,
        rank=rank,
        total_students=total_students
    )

    pdf = BytesIO()

    pisa_status = pisa.CreatePDF(
        html,
        dest=pdf
    )

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

    # Hakikisha user ana-login
    if "role" not in session or session["role"] != "teacher":
        return redirect("/login")

    # Hakikisha mwalimu ni class teacher
    if not session.get("is_class_teacher", False):
        return "You are not a class teacher.", 403

    teacher_id = session.get("user_id")
    teacher = User.query.get(teacher_id)

    # Masomo anayofundisha
    subjects = TeacherSubject.query.filter_by(teacher_id=teacher_id).all()

    # Madarasa anayofundisha
    class_levels = list(set([s.class_level for s in subjects]))

    # Wanafunzi wa madarasa hayo
    students = User.query.filter(
        User.role == "student",
        User.class_level.in_(class_levels)
    ).all()

    # ⭐ PATA FEEDBACK ZA WANAFUNZI
    student_ids = [s.id for s in students]

    feedbacks = Feedback.query.filter(
        Feedback.student_id.in_(student_ids)
    ).order_by(Feedback.created_at.desc()).all()

    # ⭐ HESABU FEEDBACK MPYA (NOTIFICATION)
    unread_feedback = Feedback.query.filter(
        Feedback.student_id.in_(student_ids),
        Feedback.is_read == False
    ).count()

    # ⭐ MARK FEEDBACK ZOTE ZIWE READ
    for fb in feedbacks:
        fb.is_read = True

    db.session.commit()

    return render_template(
        "teacher/class-teacher-dashboard.html",
        teacher=teacher,
        subjects=subjects,
        students=students,
        feedbacks=feedbacks,
        unread_feedback=unread_feedback,
        class_teacher=True
    )
@app.route('/admin/approve-student/<int:student_id>', methods=['POST'])
def approve_student(student_id):
    # pata matokeo yote ya student hayajapewa approve
    results = StudentResult.query.filter_by(student_id=student_id, approved=False).all()

    if not results:
        return jsonify({"error": "No results to approve"}), 404

    # pata exam_type kutoka request
    exam_type = request.form.get('exam_type') or request.json.get('exam_type')

    for r in results:
        r.approved = True
        if exam_type:
            r.exam_type = exam_type  # save exam type

    db.session.commit()  # commit DB

    return jsonify({"success": True})


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

    # School Fees
    term = request.form.get("term")
    school_fees = request.form.get("school_fees")
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

    # Hifadhi kwenye database
    profile = StudentProfile.query.filter_by(student_id=student.id).first()
    if not profile:
        profile = StudentProfile(student_id=student.id)
        db.session.add(profile)

    profile.requirements = json.dumps(requirements)
    profile.dorm_items = json.dumps(dorm_items)
    profile.term = term
    profile.school_fees = school_fees
    profile.other_contributions = other_contributions
    profile.character_assessment = json.dumps(char_assess)
    profile.health_state = health_state

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




if __name__ == "__main__":
    app.run(debug=True)
