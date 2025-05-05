# app.py
# WARNING: Monolithic structure - Not recommended for maintainability.
# Combines Config, Models, Forms, Utils, Routes into one file.

import os
import enum
import json
import random
import requests
import time
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone, timedelta
from functools import wraps

from flask import (
    Flask, render_template, redirect, url_for, flash, request, abort, jsonify,
    Response, current_app
)
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user, current_user, login_required
)
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from wtforms import (
    StringField, PasswordField, BooleanField, SubmitField, TextAreaField,
    SelectField, IntegerField, FloatField, FieldList, FormField, HiddenField,
    SelectMultipleField
)
from wtforms.validators import (
    DataRequired, Length, Email, EqualTo, Optional as WtformsOptional,
    ValidationError, NumberRange, InputRequired
)
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func
from sqlalchemy.orm import joinedload, selectinload
from dotenv import load_dotenv

# --- Configuration ---
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env')) # Load .env from the directory containing app.py

class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'fallback-insecure-secret-key-for-dev'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = False
    TESTING = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'instance', 'codequizhub_minimal.db')

    JUDGE0_API_URL = os.environ.get('JUDGE0_API_URL')
    JUDGE0_API_KEY = os.environ.get('JUDGE0_API_KEY')
    JUDGE0_API_HOST = os.environ.get('JUDGE0_API_HOST')
    TAB_SWITCH_LOG_ENDPOINT = '/api/tab-switch-log' # Internal endpoint

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = False

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    LOGIN_DISABLED = True

class ProductionConfig(Config):
    if not Config.SQLALCHEMY_DATABASE_URI or 'instance/codequizhub_minimal.db' in Config.SQLALCHEMY_DATABASE_URI :
       print("WARNING: DATABASE_URL potentially not set correctly for Production") # Warn but don't crash import
    if Config.SECRET_KEY == 'fallback-insecure-secret-key-for-dev':
       print("WARNING: SECRET_KEY is not securely set for Production") # Warn

config_by_name = dict(dev=DevelopmentConfig, test=TestingConfig, prod=ProductionConfig)

# --- App Initialization ---
config_name = os.getenv('FLASK_CONFIG', 'dev')
app = Flask(__name__, instance_relative_config=False) # instance_relative=False needed if config is in same file? Check this.
app.instance_path = os.path.join(basedir, 'instance')
app.config.from_object(config_by_name.get(config_name, DevelopmentConfig))

# --- Extensions Initialization ---
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login' # Use function name directly
login_manager.login_message_category = 'info'
csrf = CSRFProtect(app)

# --- Database Models ---
class QuestionType(enum.Enum):
    MCQ = 'Multiple Choice'
    FILL_IN_BLANKS = 'Fill in the Blanks'
    CODING = 'Coding'

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    attempts = db.relationship('QuizAttempt', back_populates='user', lazy='dynamic', cascade="all, delete-orphan")
    tab_switch_logs = db.relationship('TabSwitchLog', back_populates='user', lazy='dynamic', cascade="all, delete-orphan")
    quizzes_created = db.relationship('Quiz', back_populates='creator', foreign_keys='Quiz.creator_id', lazy='dynamic') # For Admin

    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)
    def __repr__(self): role = "Admin" if self.is_admin else "Student"; return f'<User {self.username} (Role: {role})>'

class Quiz(db.Model):
    __tablename__ = 'quizzes'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    time_limit_minutes = db.Column(db.Integer, nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    creator = db.relationship('User', back_populates='quizzes_created')
    questions = db.relationship('Question', back_populates='quiz', lazy='dynamic', cascade="all, delete-orphan")
    attempts = db.relationship('QuizAttempt', back_populates='quiz', lazy='dynamic', cascade="all, delete-orphan")
    tab_switch_logs = db.relationship('TabSwitchLog', back_populates='quiz', lazy='dynamic', cascade="all, delete-orphan")
    def __repr__(self): return f'<Quiz {self.id}: {self.title}>'

class Question(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id', ondelete='CASCADE'), nullable=False, index=True)
    question_type = db.Column(db.Enum(QuestionType), nullable=False, index=True)
    text = db.Column(db.Text, nullable=False)
    points = db.Column(db.Float, nullable=False, default=1.0)
    order = db.Column(db.Integer, default=0, nullable=False)
    correct_answer_text = db.Column(db.Text, nullable=True) # Fill-in
    sample_input = db.Column(db.Text, nullable=True)    # Coding
    sample_output = db.Column(db.Text, nullable=True)   # Coding
    quiz = db.relationship('Quiz', back_populates='questions')
    options = db.relationship('QuestionOption', back_populates='question', cascade="all, delete-orphan", lazy='dynamic')
    student_answers = db.relationship('StudentAnswer', back_populates='question', lazy='dynamic')
    def __repr__(self): return f'<Question {self.id} ({self.question_type.name}) for Quiz {self.quiz_id}>'

class QuestionOption(db.Model):
    __tablename__ = 'question_options'
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False, index=True)
    option_text = db.Column(db.Text, nullable=False)
    is_correct = db.Column(db.Boolean, default=False, nullable=False)
    question = db.relationship('Question', back_populates='options')
    def __repr__(self): return f'<Option {self.id} for Q{self.question_id}>'

class QuizAttempt(db.Model):
    __tablename__ = 'quiz_attempts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id', ondelete='CASCADE'), nullable=False, index=True)
    start_time = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    submit_time = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    score = db.Column(db.Float, nullable=True)
    max_score = db.Column(db.Float, nullable=True)
    is_graded = db.Column(db.Boolean, default=False, nullable=False, index=True)
    user = db.relationship('User', back_populates='attempts')
    quiz = db.relationship('Quiz', back_populates='attempts')
    answers = db.relationship('StudentAnswer', back_populates='attempt', lazy='dynamic', cascade="all, delete-orphan")
    def __repr__(self): status = "Graded" if self.is_graded else ("Submitted" if self.submit_time else "Started"); return f'<QuizAttempt {self.id} by User {self.user_id} for Quiz {self.quiz_id} ({status})>'

class StudentAnswer(db.Model):
    __tablename__ = 'student_answers'
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('quiz_attempts.id', ondelete='CASCADE'), nullable=False, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False, index=True)
    answered_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    selected_option_id = db.Column(db.Integer, db.ForeignKey('question_options.id'), nullable=True) # MCQ
    answer_text = db.Column(db.Text, nullable=True) # Fill-in
    submitted_code = db.Column(db.Text, nullable=True) # Coding
    code_language_id = db.Column(db.Integer, nullable=True) # Coding
    is_correct = db.Column(db.Boolean, nullable=True)
    points_awarded = db.Column(db.Float, nullable=True)
    judge0_token = db.Column(db.String(100), nullable=True, index=True)
    judge0_status_id = db.Column(db.Integer, nullable=True)
    judge0_output = db.Column(db.Text, nullable=True)
    judge0_time = db.Column(db.Float, nullable=True)
    judge0_memory = db.Column(db.Integer, nullable=True)
    attempt = db.relationship('QuizAttempt', back_populates='answers')
    question = db.relationship('Question', back_populates='student_answers')
    selected_option = db.relationship('QuestionOption')
    def __repr__(self): return f'<StudentAnswer {self.id} for Q{self.question_id} in Attempt {self.attempt_id}>'

class TabSwitchLog(db.Model):
    __tablename__ = 'tab_switch_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id', ondelete='CASCADE'), nullable=False, index=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('quiz_attempts.id', ondelete='CASCADE'), nullable=True, index=True) # Changed CASCADE
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    user = db.relationship('User', back_populates='tab_switch_logs')
    quiz = db.relationship('Quiz', back_populates='tab_switch_logs')
    def __repr__(self): return f'<TabSwitchLog User:{self.user_id} Quiz:{self.quiz_id} at {self.timestamp}>'

# --- Flask-Login User Loader ---
@login_manager.user_loader
def load_user(user_id):
    """Loads user by primary key ID."""
    return User.query.get(int(user_id))

# --- Forms ---
class RegistrationForm(FlaskForm):
    """Form for user registration (Admin/Student)."""
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    is_admin = BooleanField('Register as Admin?')
    submit = SubmitField('Register')
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user: raise ValidationError('That username is already taken.')

class LoginForm(FlaskForm):
    """Form for user login."""
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Login')

class QuestionOptionSubForm(FlaskForm):
    """Subform for one MCQ option (used within QuestionForm)."""
    id = HiddenField('Option ID')
    option_text = StringField('Option Text', validators=[WtformsOptional()]) # Changed to optional for flexibility
    is_correct = BooleanField('Correct?')

class QuestionForm(FlaskForm):
    """Form for adding/editing a question."""
    quiz_id = HiddenField() # To associate with the quiz
    question_type = SelectField('Question Type', choices=[(t.name, t.value) for t in QuestionType], validators=[DataRequired()])
    text = TextAreaField('Question Text / Problem Statement', validators=[DataRequired()], render_kw={"rows": 5})
    points = FloatField('Points', default=1.0, validators=[DataRequired(), NumberRange(min=0.1)])
    order = IntegerField('Display Order', default=0)
    # --- Type Specific Fields ---
    # MCQ Options - Use FieldList for dynamic handling
    options = FieldList(FormField(QuestionOptionSubForm), min_entries=4, max_entries=6, label="MCQ Options")
    # Fill-in-the-Blanks
    correct_answer_text = StringField('Correct Answer(s) (Fill-in, separate with |)', validators=[WtformsOptional()])
    # Coding
    sample_input = TextAreaField('Sample Input (Coding)', validators=[WtformsOptional()], render_kw={"rows": 3})
    sample_output = TextAreaField('Sample Output (Coding)', validators=[WtformsOptional()], render_kw={"rows": 3})
    # Language ID selection will be separate (e.g., during quiz taking or fixed per question?)

    submit = SubmitField('Save Question')

    # Custom validation if needed (e.g., ensure at least 2 options for MCQ, 1 correct)
    def validate(self, extra_validators=None):
        if not super(QuestionForm, self).validate(extra_validators):
            return False
        if self.question_type.data == QuestionType.MCQ.name:
            valid_options_count = 0
            correct_count = 0
            for option_field in self.options:
                if option_field.form.option_text.data.strip():
                    valid_options_count += 1
                    if option_field.form.is_correct.data:
                        correct_count += 1
            if valid_options_count < 2:
                self.options.errors.append("MCQ requires at least 2 non-empty options.")
                return False
            if correct_count != 1:
                self.options.errors.append("MCQ requires exactly one correct option.")
                return False
        elif self.question_type.data == QuestionType.FILL_IN_BLANKS.name:
            if not self.correct_answer_text.data or not self.correct_answer_text.data.strip():
                self.correct_answer_text.errors.append("Correct answer is required for Fill-in-the-Blanks.")
                return False
        return True


class QuizForm(FlaskForm):
    """Form for creating/editing the main quiz details."""
    title = StringField('Quiz Title', validators=[DataRequired(), Length(max=150)])
    description = TextAreaField('Description', validators=[WtformsOptional()])
    time_limit_minutes = IntegerField('Time Limit (Minutes)', default=30, validators=[DataRequired(), NumberRange(min=1)])
    is_active = BooleanField("Make Quiz Active?", default=True)
    submit = SubmitField('Save Quiz Details')

# --- Utility Functions ---
def submit_to_judge0(source_code: str, language_id: int, stdin: str = None, expected_output: str = None):
    """ Submits code to Judge0 API. Returns results dict or error dict. """
    api_url = current_app.config.get('JUDGE0_API_URL')
    api_key = current_app.config.get('JUDGE0_API_KEY')
    api_host = current_app.config.get('JUDGE0_API_HOST')

    if not api_url:
        current_app.logger.error("JUDGE0_API_URL not configured.")
        return {"error": "Judge0 API URL not configured.", "stderr": None, "status_id": -1}

    headers = {"content-type": "application/json", "Content-Type": "application/json"}
    if api_key: headers["X-RapidAPI-Key"] = api_key
    if api_host: headers["X-RapidAPI-Host"] = api_host

    payload = {
        "language_id": language_id,
        "source_code": source_code,
        "stdin": stdin,
        "cpu_time_limit": 5, # Increased time limit
        "memory_limit": 256000, # Increased memory limit (256MB)
    }

    submission_url = f"{api_url}/submissions?base64_encoded=false&wait=true&fields=*" # Use wait=true, get all fields
    current_app.logger.debug(f"Posting to Judge0: {submission_url} with lang {language_id}")

    try:
        response = requests.post(submission_url, headers=headers, json=payload, timeout=20) # Increased timeout
        response.raise_for_status() # Check for HTTP errors
        result_data = response.json()
        current_app.logger.info(f"Judge0 Result: {result_data.get('status', {}).get('description')}, Token: {result_data.get('token')}")
        # Process and return relevant fields
        return {
             "token": result_data.get('token'),
             "status_id": result_data.get('status', {}).get('id'),
             "status_description": result_data.get('status', {}).get('description'),
             "stdout": result_data.get('stdout'),
             "stderr": result_data.get('stderr'),
             "compile_output": result_data.get('compile_output'),
             "message": result_data.get('message'),
             "time": float(result_data.get('time', 0)) if result_data.get('time') else None,
             "memory": result_data.get('memory'), # In KB
        }

    except requests.exceptions.Timeout:
        current_app.logger.error(f"Timeout connecting to Judge0 API: {submission_url}")
        return {"error": "API timeout error", "stderr": "Connection timed out", "status_id": -1}
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Error communicating with Judge0 API: {e}")
        return {"error": f"API communication error: {e}", "stderr": str(e), "status_id": -1}
    except Exception as e:
        current_app.logger.exception(f"Unhandled exception during Judge0 interaction: {e}")
        return {"error": f"An unexpected error occurred: {e}", "stderr": str(e), "status_id": -1}

# --- Helper Decorators (Simplified) ---
def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def student_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.is_admin: # Admins cannot be students in this model
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# --- Routes ---

# --- Main Routes ---
@app.route('/')
@app.route('/index')
def index():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))
    return render_template('index.html', title='Welcome')

# --- Auth Routes ---
@app.route('/auth/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            user = User(username=form.username.data, is_admin=form.is_admin.data)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login')) # Use function name
        except IntegrityError:
             db.session.rollback(); flash('Username already exists.', 'danger')
        except Exception as e:
             db.session.rollback(); flash(f'Registration error: {e}', 'danger')
    return render_template('auth/register.html', title='Register', form=form)

@app.route('/auth/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            flash('Login successful!', 'success')
            next_page = request.args.get('next')
            if user.is_admin: dest = url_for('admin_dashboard')
            else: dest = url_for('student_dashboard')
            return redirect(next_page or dest)
        else:
            flash('Invalid username or password.', 'danger')
    return render_template('auth/login.html', title='Login', form=form)

@app.route('/auth/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# --- Admin Routes ---
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    quiz_count = Quiz.query.filter_by(creator_id=current_user.id).count()
    attempt_count = QuizAttempt.query.join(Quiz).filter(Quiz.creator_id == current_user.id).count()
    log_count = TabSwitchLog.query.join(Quiz).filter(Quiz.creator_id == current_user.id).count()
    return render_template('admin/dashboard.html', title='Admin Dashboard',
                           quiz_count=quiz_count, attempt_count=attempt_count, log_count=log_count)

@app.route('/admin/quizzes')
@admin_required
def admin_quiz_list():
    quizzes = Quiz.query.filter_by(creator_id=current_user.id).order_by(Quiz.created_at.desc()).all()
    return render_template('admin/quiz_list.html', quizzes=quizzes, title='Manage Quizzes')

@app.route('/admin/quizzes/create', methods=['GET', 'POST'])
@admin_required
def admin_create_quiz():
    form = QuizForm()
    if form.validate_on_submit():
        try:
            new_quiz = Quiz(
                title=form.title.data, description=form.description.data,
                time_limit_minutes=form.time_limit_minutes.data,
                is_active=form.is_active.data, creator_id=current_user.id
            )
            db.session.add(new_quiz)
            db.session.commit()
            flash('Quiz created. Add questions now.', 'success')
            return redirect(url_for('admin_manage_questions', quiz_id=new_quiz.id)) # Use function name
        except Exception as e: db.session.rollback(); flash(f'Error: {e}', 'danger')
    return render_template('admin/create_edit_quiz.html', form=form, title='Create Quiz', quiz=None)

@app.route('/admin/quizzes/edit/<int:quiz_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_quiz(quiz_id):
    quiz = Quiz.query.filter_by(id=quiz_id, creator_id=current_user.id).first_or_404()
    form = QuizForm(obj=quiz)
    if form.validate_on_submit():
        try:
            quiz.title = form.title.data; quiz.description = form.description.data
            quiz.time_limit_minutes = form.time_limit_minutes.data; quiz.is_active = form.is_active.data
            db.session.commit()
            flash('Quiz updated.', 'success')
            return redirect(url_for('admin_quiz_list')) # Use function name
        except Exception as e: db.session.rollback(); flash(f'Error: {e}', 'danger')
    return render_template('admin/create_edit_quiz.html', form=form, title='Edit Quiz', quiz=quiz)

@app.route('/admin/quizzes/delete/<int:quiz_id>', methods=['POST'])
@admin_required
def admin_delete_quiz(quiz_id):
    quiz = Quiz.query.filter_by(id=quiz_id, creator_id=current_user.id).first_or_404()
    try:
        db.session.delete(quiz); db.session.commit()
        flash(f'Quiz "{quiz.title}" deleted.', 'success')
    except Exception as e: db.session.rollback(); flash(f'Error deleting quiz: {e}', 'danger')
    return redirect(url_for('admin_quiz_list'))

@app.route('/admin/quiz/<int:quiz_id>/questions', methods=['GET', 'POST'])
@admin_required
def admin_manage_questions(quiz_id):
    quiz = Quiz.query.filter_by(id=quiz_id, creator_id=current_user.id).first_or_404()
    form = QuestionForm() # Empty form for adding new
    if form.validate_on_submit():
        try:
            q_type = QuestionType[form.question_type.data]
            new_q = Question(
                quiz_id=quiz.id, question_type=q_type, text=form.text.data,
                points=form.points.data, order=form.order.data,
                correct_answer_text=form.correct_answer_text.data if q_type == QuestionType.FILL_IN_BLANKS else None,
                sample_input=form.sample_input.data if q_type == QuestionType.CODING else None,
                sample_output=form.sample_output.data if q_type == QuestionType.CODING else None
            )
            db.session.add(new_q); db.session.flush()

            if q_type == QuestionType.MCQ:
                for option_field in form.options:
                    if option_field.form.option_text.data.strip():
                         option = QuestionOption(
                            question_id=new_q.id,
                            option_text=option_field.form.option_text.data.strip(),
                            is_correct=option_field.form.is_correct.data
                         )
                         db.session.add(option)

            db.session.commit()
            flash('Question added.', 'success')
            return redirect(url_for('admin_manage_questions', quiz_id=quiz.id))
        except Exception as e: db.session.rollback(); flash(f'Error adding question: {e}', 'danger')

    questions = Question.query.filter_by(quiz_id=quiz.id).order_by(Question.order).all()
    return render_template('admin/manage_questions.html', quiz=quiz, questions=questions, form=form, title=f"Manage Qs: {quiz.title}", QuestionType=QuestionType)


@app.route('/admin/quiz/<int:quiz_id>/question/delete/<int:question_id>', methods=['POST'])
@admin_required
def admin_delete_question(quiz_id, question_id):
    question = Question.query.join(Quiz).filter(
        Question.id == question_id, Question.quiz_id == quiz_id, Quiz.creator_id == current_user.id
    ).first_or_404()
    try:
        db.session.delete(question); db.session.commit()
        flash('Question deleted.', 'success')
    except Exception as e: db.session.rollback(); flash(f'Error deleting question: {e}', 'danger')
    return redirect(url_for('admin_manage_questions', quiz_id=quiz_id))


@app.route('/admin/quiz/<int:quiz_id>/attempts')
@admin_required
def admin_view_attempts(quiz_id):
    quiz = Quiz.query.filter_by(id=quiz_id, creator_id=current_user.id).first_or_404()
    attempts = QuizAttempt.query.filter_by(quiz_id=quiz_id)\
               .options(joinedload(QuizAttempt.user))\
               .order_by(QuizAttempt.submit_time.desc(), QuizAttempt.start_time.desc())\
               .all()
    return render_template('admin/view_attempts.html', quiz=quiz, attempts=attempts, title=f"Attempts: {quiz.title}")

@app.route('/admin/quiz/<int:quiz_id>/logs')
@admin_required
def admin_view_logs(quiz_id):
    quiz = Quiz.query.filter_by(id=quiz_id, creator_id=current_user.id).first_or_404()
    logs = TabSwitchLog.query.filter_by(quiz_id=quiz_id)\
           .options(joinedload(TabSwitchLog.user))\
           .order_by(TabSwitchLog.timestamp.desc()).all()
    return render_template('admin/view_logs.html', quiz=quiz, logs=logs, title=f"Logs: {quiz.title}")


# --- Student Routes ---
@app.route('/student/dashboard')
@student_required
def student_dashboard():
    """Student dashboard - List available quizzes."""
    now = datetime.now(timezone.utc)
    # Find quizzes that are active AND the student hasn't fully completed yet
    completed_quiz_ids = db.session.query(QuizAttempt.quiz_id)\
                           .filter(QuizAttempt.user_id == current_user.id)\
                           .filter(QuizAttempt.submit_time != None).subquery()

    available_quizzes = Quiz.query.filter(
                            Quiz.is_active == True,
                            Quiz.id.notin_(completed_quiz_ids)
                           ).order_by(Quiz.created_at.desc()).all()
    return render_template('student/dashboard.html', quizzes=available_quizzes, title='Student Dashboard')

@app.route('/student/quiz/take/<int:quiz_id>')
@student_required
def student_take_quiz_start(quiz_id):
    """ Check eligibility and start/resume quiz """
    quiz = Quiz.query.filter_by(id=quiz_id, is_active=True).first_or_404("Quiz not found or not active.")
    attempt = QuizAttempt.query.filter_by(quiz_id=quiz.id, user_id=current_user.id).order_by(QuizAttempt.start_time.desc()).first()
    now = datetime.now(timezone.utc)

    if attempt and attempt.submit_time is None: # Resume
        deadline = attempt.start_time + timedelta(minutes=quiz.time_limit_minutes)
        if deadline < now:
             flash("Previous attempt timed out. Submitting.", "warning");
             # TODO: Force submit logic robustly
             try:
                 attempt.submit_time = deadline
                 attempt.is_graded = False # Needs checking
                 db.session.commit()
             except Exception as e: db.session.rollback()
             return redirect(url_for('student_results_detail', attempt_id=attempt.id))
        return redirect(url_for('student_take_quiz_attempt', attempt_id=attempt.id))
    elif attempt and attempt.submit_time is not None: # Completed
        flash("You have already completed this quiz.", "info"); return redirect(url_for('student_results_detail', attempt_id=attempt.id))
    else: # Start new
        try:
            new_attempt = QuizAttempt(user_id=current_user.id, quiz_id=quiz.id)
            db.session.add(new_attempt)
            max_score = db.session.query(db.func.sum(Question.points)).filter(Question.quiz_id == quiz.id).scalar()
            new_attempt.max_score = max_score if max_score else 0.0
            db.session.commit()
            return redirect(url_for('student_take_quiz_attempt', attempt_id=new_attempt.id))
        except Exception as e: db.session.rollback(); flash(f"Error starting quiz: {e}", "danger"); return redirect(url_for('student_dashboard'))

@app.route('/student/quiz/attempt/<int:attempt_id>', methods=['GET'])
@student_required
def student_take_quiz_attempt(attempt_id):
    """ Display quiz questions for an active attempt """
    attempt = QuizAttempt.query.filter_by(id=attempt_id, user_id=current_user.id).first_or_404()
    if attempt.submit_time is not None: return redirect(url_for('student_results_detail', attempt_id=attempt.id))

    quiz = Quiz.query.get_or_404(attempt.quiz_id)
    now = datetime.now(timezone.utc)
    deadline = attempt.start_time + timedelta(minutes=quiz.time_limit_minutes)
    time_remaining_seconds = max(0, int((deadline - now).total_seconds()))

    if time_remaining_seconds <= 0:
        flash ("Time expired for this attempt.", "warning")
        return redirect(url_for('student_submit_quiz', attempt_id=attempt.id, force='true'))

    questions = Question.query.filter_by(quiz_id=quiz.id)\
                      .options(selectinload(Question.options))\
                      .order_by(Question.order).all()

    return render_template('student/take_quiz.html',
                           quiz=quiz, attempt=attempt, questions=questions,
                           time_remaining=time_remaining_seconds, QuestionType=QuestionType)

@app.route('/student/quiz/submit/<int:attempt_id>', methods=['POST'])
@student_required
def student_submit_quiz(attempt_id):
    """ Process quiz submission """
    attempt = QuizAttempt.query.filter_by(id=attempt_id, user_id=current_user.id).first_or_404()
    if attempt.submit_time is not None: flash("Quiz already submitted.", "warning"); return redirect(url_for('student_results_detail', attempt_id=attempt.id))

    quiz = Quiz.query.get_or_404(attempt.quiz_id)
    now = datetime.now(timezone.utc)
    deadline = attempt.start_time + timedelta(minutes=quiz.time_limit_minutes)
    is_forced = request.args.get('force') == 'true'

    if now > deadline and not is_forced: flash("Time limit expired before submission.", "danger"); # Optionally still process

    total_score = 0
    max_score = attempt.max_score or sum(q.points for q in quiz.questions)
    needs_manual_grade = False # Simplified: assume auto-grade unless coding involved

    try:
        questions = Question.query.filter_by(quiz_id=quiz.id).options(selectinload(Question.options)).all()
        question_map = {q.id: q for q in questions}
        answers_to_save = []

        for question in questions:
            answer = StudentAnswer(attempt_id=attempt.id, question_id=question.id, answered_at=now)
            is_correct = None; points = 0.0 # Defaults

            if question.question_type == QuestionType.MCQ:
                selected_id_str = request.form.get(f'q_{question.id}_option')
                if selected_id_str and selected_id_str.isdigit():
                    answer.selected_option_id = int(selected_id_str)
                    correct_option = next((opt for opt in question.options if opt.is_correct), None)
                    is_correct = (correct_option and answer.selected_option_id == correct_option.id)
                    if is_correct: points = question.points
                elif selected_id_str: is_correct = False # Invalid selection

            elif question.question_type == QuestionType.FILL_IN_BLANKS:
                answer.answer_text = request.form.get(f'q_{question.id}_text', '').strip()
                correct = [a.strip() for a in (question.correct_answer_text or "").split('|') if a.strip()]
                if answer.answer_text and correct:
                    is_correct = answer.answer_text in correct # Basic check
                    if is_correct: points = question.points
                elif answer.answer_text: is_correct = False

            elif question.question_type == QuestionType.CODING:
                answer.submitted_code = request.form.get(f'q_{question.id}_code', '').strip()
                lang_id_str = request.form.get(f'q_{question.id}_lang')
                answer.code_language_id = int(lang_id_str) if lang_id_str and lang_id_str.isdigit() else None
                needs_manual_grade = True # Mark coding for later processing/manual review
                is_correct = None # Reset values until Judge0 runs
                points = 0
                if answer.submitted_code and answer.code_language_id:
                    # --- Initiate Judge0 Submission ---
                    # This is simplified: run immediately and store token/status
                    judge0_result = submit_to_judge0(
                        source_code=answer.submitted_code, language_id=answer.code_language_id,
                        stdin=question.sample_input, expected_output=question.sample_output) # Example usage
                    answer.judge0_token = judge0_result.get("token")
                    answer.judge0_status_id = judge0_result.get("status_id")
                    answer.judge0_output = judge0_result.get("stdout") or judge0_result.get("stderr") or judge0_result.get("compile_output") or judge0_result.get("message") or judge0_result.get("error")
                    answer.judge0_time = judge0_result.get("time")
                    answer.judge0_memory = judge0_result.get("memory")
                    # Basic success check (adjust based on Judge0/test case logic)
                    if answer.judge0_status_id == 3: # Judge0 Accepted
                        is_correct = True
                        points = question.points
                        needs_manual_grade = False # Auto-graded successfully
                    elif answer.judge0_status_id is not None and answer.judge0_status_id > 3:
                         is_correct = False
                         needs_manual_grade = False # Clearly wrong
                    # else: keep needs_manual_grade=True (e.g., compile error, runtime error, timeout)

            answer.is_correct = is_correct
            answer.points_awarded = points if is_correct else 0.0
            if is_correct is not None and not needs_manual_grade: total_score += answer.points_awarded
            answers_to_save.append(answer)

        # Save all answers at once
        db.session.add_all(answers_to_save)

        # Update Attempt
        attempt.submit_time = now
        attempt.score = total_score
        attempt.max_score = max_score
        attempt.is_graded = not needs_manual_grade # Mark as graded if no manual check needed

        db.session.commit()

        flash("Quiz submitted successfully!", "success")
        # Maybe only flash coding pending if that happened
        if needs_manual_grade: flash("Some coding questions are being evaluated or need review.", "info")
        return redirect(url_for('student_results_detail', attempt_id=attempt.id))

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error submitting quiz attempt {attempt_id}: {e}")
        flash("An error occurred while submitting your quiz.", "danger")
        return redirect(url_for('student_take_quiz_attempt', attempt_id=attempt_id))

@app.route('/student/results')
@student_required
def student_results_list():
    attempts = QuizAttempt.query.filter_by(user_id=current_user.id)\
               .filter(QuizAttempt.submit_time != None)\
               .join(Quiz).options(joinedload(QuizAttempt.quiz))\
               .order_by(QuizAttempt.submit_time.desc()).all()
    return render_template('student/results_list.html', attempts=attempts, title="My Results")

@app.route('/student/results/<int:attempt_id>')
@student_required
def student_results_detail(attempt_id):
    attempt = QuizAttempt.query.filter_by(id=attempt_id, user_id=current_user.id)\
        .options(joinedload(QuizAttempt.quiz),
                 selectinload(QuizAttempt.answers).selectinload(StudentAnswer.question).selectinload(Question.options),
                 selectinload(QuizAttempt.answers).selectinload(StudentAnswer.selected_option))\
        .first_or_404()
    answers_map = {ans.question_id: ans for ans in attempt.answers}
    questions = Question.query.filter_by(quiz_id=attempt.quiz_id).order_by(Question.order).all()
    return render_template('student/results_detail.html',
                           attempt=attempt, quiz=attempt.quiz, questions=questions,
                           answers_map=answers_map, QuestionType=QuestionType, title=f"Results: {attempt.quiz.title}")

# --- API Routes ---
@app.route('/api/tab-switch-log', methods=['POST'])
@csrf.exempt # Needs careful consideration: how to secure this JS call? Maybe require login session cookie?
@login_required
def api_log_tab_switch():
    if not request.is_json: return jsonify({"error": "JSON required"}), 400
    data = request.get_json()
    quiz_id = data.get('quiz_id')
    attempt_id = data.get('attempt_id')
    if not quiz_id: return jsonify({"error": "Missing quiz_id"}), 400
    try:
        log_entry = TabSwitchLog(user_id=current_user.id, quiz_id=int(quiz_id),
                                 attempt_id=int(attempt_id) if attempt_id else None)
        db.session.add(log_entry); db.session.commit()
        return jsonify({"message": "Log received"}), 201
    except Exception as e:
        db.session.rollback(); current_app.logger.error(f"Tab log error: {e}")
        return jsonify({"error": "Failed to log"}), 500

# --- Logging Config (Basic Example) ---
if not app.debug:
    if not os.path.exists('logs'): os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/codequizhub.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('CodeQuizHub startup')

# --- CLI Commands (Example - Use 'flask create-admin' after setting FLASK_APP) ---
@app.cli.command("create-admin")
def create_admin_command():
    """Creates the initial admin user."""
    from getpass import getpass
    import sys
    username = input("Enter admin username: ")
    if User.query.filter_by(username=username).first():
        print("Admin username already exists.")
        sys.exit(1)
    password = getpass("Enter admin password: ")
    confirm = getpass("Confirm admin password: ")
    if password != confirm: print("Passwords don't match."); sys.exit(1)
    try:
        admin = User(username=username, is_admin=True)
        admin.set_password(password)
        db.session.add(admin); db.session.commit()
        print(f"Admin user '{username}' created.")
    except Exception as e:
        db.session.rollback(); print(f"Error: {e}"); sys.exit(1)

# --- Run Block ---
if __name__ == '__main__':
    # Ensure instance folder exists for SQLite before running
    instance_path = os.path.join(basedir, 'instance')
    if not os.path.exists(instance_path):
        os.makedirs(instance_path)
        print(f"Created instance folder: {instance_path}")
    # Consider port from environment or default
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)