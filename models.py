from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import json
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    full_name = db.Column(db.String(150))
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    class_level = db.Column(db.String(20))
    combination = db.Column(db.String(50))
    is_class_teacher = db.Column(db.Boolean, default=False)

    subjects = db.relationship(
        "TeacherSubject",
        back_populates="teacher",
        cascade="all, delete",
        lazy=True
    )

    profile = db.relationship(
        "StudentProfile",
        uselist=False,
        back_populates="student",
        cascade="all, delete-orphan"
    )

    # 🔥 ADD THIS (IMPORTANT)
    results = db.relationship(
        "StudentResult",
        backref="student",
        cascade="all, delete-orphan",
        passive_deletes=True
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

    student_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id', ondelete="CASCADE"),
        nullable=False
    )

    subject = db.Column(db.String(100), nullable=False)
    class_level = db.Column(db.String(20), nullable=False)

    # MUHIMU SANA
    term = db.Column(db.String(20), nullable=False)  
    academic_year = db.Column(db.Integer, nullable=False)

    # TESTS
    test1 = db.Column(db.Float, default=0.0)
    test2 = db.Column(db.Float, default=0.0)

    # FINAL EXAM
    exam_type = db.Column(db.String(50))  # Terminal / Annual
    exam_marks = db.Column(db.Float, nullable=True)

    # RESULTS
    total = db.Column(db.Float, default=0.0)
    average = db.Column(db.Float, default=0.0)
    grade = db.Column(db.String(5))

    approved = db.Column(db.Boolean, default=False)
# ✅ Student Profile Model
class StudentProfile(db.Model):
    __tablename__ = "student_profiles"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)

    # JSON data
    requirements = db.Column(db.Text)          
    dorm_items = db.Column(db.Text)            
    term = db.Column(db.String(20))

    # CHANGED: now TEXT instead of Integer
    school_fees = db.Column(db.Text)

    other_contributions = db.Column(db.Text)
    character_assessment = db.Column(db.Text)
    health_state = db.Column(db.Text)

    # NEW FIELD (Teacher Remarks)
    teacher_remarks = db.Column(db.Text)

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


class Subject(db.Model):
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)

    # art / science / both
    category = db.Column(db.String(20), nullable=False)

    # mfano: Form 1, Form 2, Form 3, Form 4
    class_level = db.Column(db.String(20), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)