from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import json
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model, UserMixin):  # 🔹 Ongeza UserMixin hapa
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    full_name = db.Column(db.String(150))  # Optional
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'admin', 'teacher', 'student'
    class_level = db.Column(db.String(20))          # Kwa mwanafunzi & mwalimu wa darasa
    combination = db.Column(db.String(50))          # Kwa mwanafunzi pekee
    is_class_teacher = db.Column(db.Boolean, default=False)

    # Relationships
    subjects = db.relationship(
        "TeacherSubject", back_populates="teacher", cascade="all, delete", lazy=True
    )

    profile = db.relationship(
        "StudentProfile", uselist=False, back_populates="student", cascade="all, delete"
    )

    # 🔒 Password helpers
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class SubjectAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    class_level = db.Column(db.String(50), nullable=False)
    subjects = db.Column(db.String(200), nullable=False)


class TeacherSubject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(50), nullable=False)
    class_level = db.Column(db.String(10), nullable=False)

    teacher = db.relationship("User", back_populates="subjects")


class StudentResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    class_level = db.Column(db.String(20), nullable=False)
    test1 = db.Column(db.Float, default=0.0)
    test2 = db.Column(db.Float, default=0.0)
    exam_type = db.Column(db.String(50))
    exam_marks = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, default=0.0)
    average = db.Column(db.Float, default=0.0)
    grade = db.Column(db.String(5))
    approved = db.Column(db.Boolean, default=False)

    # ✅ Add these two
    exam_month = db.Column(db.String(20))
    exam_year = db.Column(db.Integer)

    student = db.relationship('User', backref='results')

# ✅ Student Profile Model
class StudentProfile(db.Model):
    __tablename__ = "student_profiles"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)

    # Hapa tunahifadhi JSON kwa ease
    requirements = db.Column(db.Text)          # ["Textbooks","Rim",...]
    dorm_items = db.Column(db.Text)            # ["Mosquito net", "Bucket", ...]
    term = db.Column(db.String(20))
    school_fees = db.Column(db.Integer)
    other_contributions = db.Column(db.Text)
    character_assessment = db.Column(db.Text)  # {"discipline":"Good", ...}
    health_state = db.Column(db.Text)

    student = db.relationship("User", back_populates="profile")

class Feedback(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    student_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    message = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # relationship ya mwanafunzi
    student = db.relationship("User", backref="feedbacks")

      # notification status
    is_read = db.Column(db.Boolean, default=False)


class Resource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    file_url = db.Column(db.String(300), nullable=False)  # URL ya PDF
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    video_url = db.Column(db.String(300), nullable=False)  # URL ya video (mp4 / YouTube)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)