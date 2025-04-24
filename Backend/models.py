# models.py - Further Refined database models for CodeQuizHub

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime
import enum
import json # For storing list of presented question IDs

# Assume 'db' is initialized in your Flask app (e.g., from . import db)
from . import db

# --- Enums ---

class UserRole(enum.Enum):
    ADMIN = 'Admin'
    ORGANIZATION = 'Organization'
    STUDENT = 'Student'
    USER = 'User'

class QuestionType(enum.Enum):
    MCQ = 'Multiple Choice'
    FILL_IN_BLANKS = 'Fill in the Blanks'
    SHORT_ANSWER = 'Short Answer'
    CODING = 'Coding'

class QuestionSelectionStrategy(enum.Enum):
    FIXED = 'Fixed Set'
    RANDOM = 'Random Pooling'

class OrgApprovalStatus(enum.Enum):
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'

# NEW: Quiz Lifecycle Status
class QuizStatus(enum.Enum):
    DRAFT = 'Draft'         # Created but not ready
    PUBLISHED = 'Published' # Ready to be taken/assigned
    ACTIVE = 'Active'       # Currently running (optional, based on start/end times)
    ARCHIVED = 'Archived'   # No longer active, kept for records

# NEW: Quiz Attempt Status
class QuizAttemptStatus(enum.Enum):
    STARTED = 'Started'
    SUBMITTED = 'Submitted'
    GRADED = 'Graded'
    TIMED_OUT = 'Timed Out' # If auto-submitted due to time limit

# NEW: Grading Status for individual answers
class GradingStatus(enum.Enum):
    PENDING = 'Pending'
    GRADED = 'Graded'
    ERROR = 'Error' # If auto-grading failed

# --- Association Tables ---

quiz_questions = db.Table('quiz_questions',
    db.Column('quiz_id', db.Integer, db.ForeignKey('quizzes.id'), primary_key=True),
    db.Column('question_id', db.Integer, db.ForeignKey('questions.id'), primary_key=True)
)

question_tags = db.Table('question_tags',
    db.Column('question_id', db.Integer, db.ForeignKey('questions.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id'), primary_key=True)
)

quiz_assignments = db.Table('quiz_assignments',
    db.Column('quiz_id', db.Integer, db.ForeignKey('quizzes.id'), primary_key=True),
    db.Column('student_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('assigned_at', db.DateTime, default=datetime.utcnow)
)

# NEW: Many-to-Many for User Badges (Gamification)
user_badges = db.Table('user_badges',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('badge_id', db.Integer, db.ForeignKey('badges.id'), primary_key=True),
    db.Column('earned_at', db.DateTime, default=datetime.utcnow)
)

# --- Main Models ---

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.Enum(UserRole), nullable=False, default=UserRole.USER)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    student_code = db.Column(db.String(50), nullable=True)
    enrollment_date = db.Column(db.DateTime, nullable=True)

    # NEW: Gamification fields
    gamification_points = db.Column(db.Integer, default=0)
    gamification_level = db.Column(db.Integer, default=1)

    # Relationships
    organization = db.relationship('Organization', back_populates='members', foreign_keys=[organization_id])
    quiz_attempts = db.relationship('QuizAttempt', back_populates='user', lazy='dynamic')
    assigned_quizzes = db.relationship('Quiz', secondary=quiz_assignments, back_populates='assigned_students', lazy='dynamic')
    managed_organization = db.relationship('Organization', back_populates='admin_user', foreign_keys='Organization.admin_user_id', uselist=False)
    # NEW: Badges earned by user
    badges = db.relationship('Badge', secondary=user_badges, back_populates='users', lazy='dynamic')
    # NEW: Notifications for user
    notifications = db.relationship('Notification', back_populates='user', lazy='dynamic', cascade="all, delete-orphan")


    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username} ({self.role.name})>'

class Organization(db.Model):
    __tablename__ = 'organizations'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    approval_status = db.Column(db.Enum(OrgApprovalStatus), default=OrgApprovalStatus.PENDING, nullable=False)
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime, nullable=True)
    approved_by_admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    admin_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=True)

    # Relationships
    admin_user = db.relationship('User', back_populates='managed_organization', foreign_keys=[admin_user_id])
    members = db.relationship('User', back_populates='organization', foreign_keys=[User.organization_id], lazy='dynamic')
    created_quizzes = db.relationship('Quiz', back_populates='organization', lazy='dynamic')
    questions = db.relationship('Question', back_populates='organization', lazy='dynamic') # Org owns questions

    def __repr__(self):
        return f'<Organization {self.name} ({self.approval_status.name})>'

class Tag(db.Model):
    __tablename__ = 'tags'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    questions = db.relationship('Question', secondary=question_tags, back_populates='tags', lazy='dynamic')

    def __repr__(self):
        return f'<Tag {self.name}>'

class Question(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True) # Org that owns/created question
    question_type = db.Column(db.Enum(QuestionType), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.String(20), nullable=True)
    points = db.Column(db.Integer, default=1, nullable=False)
    correct_answer_text = db.Column(db.Text, nullable=True) # For fill-in/short answer
    explanation = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_ai_generated = db.Column(db.Boolean, default=False)
    # NEW: Store AI prompt if generated
    ai_prompt = db.Column(db.Text, nullable=True)

    # Relationships
    organization = db.relationship('Organization', back_populates='questions')
    options = db.relationship('QuestionOption', back_populates='question', cascade='all, delete-orphan', lazy=True)
    code_templates = db.relationship('CodeTemplate', back_populates='question', cascade='all, delete-orphan', lazy=True)
    test_cases = db.relationship('TestCase', back_populates='question', cascade='all, delete-orphan', lazy=True)
    tags = db.relationship('Tag', secondary=question_tags, back_populates='questions', lazy='dynamic')
    quizzes = db.relationship('Quiz', secondary=quiz_questions, back_populates='questions', lazy='dynamic')
    student_answers = db.relationship('StudentAnswer', back_populates='question', lazy='dynamic')

    def __repr__(self):
        return f'<Question {self.id} ({self.question_type.name})>'

class QuestionOption(db.Model):
    __tablename__ = 'question_options'
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    option_text = db.Column(db.Text, nullable=False)
    is_correct = db.Column(db.Boolean, default=False, nullable=False)
    question = db.relationship('Question', back_populates='options')
    def __repr__(self):
        return f'<Option {self.id} for Q{self.question_id} Correct:{self.is_correct}>'

class CodeTemplate(db.Model):
    __tablename__ = 'code_templates'
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    language = db.Column(db.String(50), nullable=False)
    template_code = db.Column(db.Text, nullable=True)
    question = db.relationship('Question', back_populates='code_templates')
    def __repr__(self):
        return f'<CodeTemplate {self.language} for Q{self.question_id}>'

class TestCase(db.Model):
    __tablename__ = 'test_cases'
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    input_data = db.Column(db.Text, nullable=True)
    expected_output = db.Column(db.Text, nullable=False)
    is_hidden = db.Column(db.Boolean, default=False, nullable=False)
    points = db.Column(db.Integer, default=1)
    question = db.relationship('Question', back_populates='test_cases')
    def __repr__(self):
        return f'<TestCase {self.id} for Q{self.question_id}>'

class Quiz(db.Model):
    __tablename__ = 'quizzes'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    duration_minutes = db.Column(db.Integer, nullable=False)
    is_public = db.Column(db.Boolean, default=False, nullable=False)
    selection_strategy = db.Column(db.Enum(QuestionSelectionStrategy), nullable=False, default=QuestionSelectionStrategy.FIXED)
    # NEW: Number of questions to select if strategy is RANDOM
    num_questions_to_pool = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # NEW: Quiz lifecycle status
    status = db.Column(db.Enum(QuizStatus), default=QuizStatus.DRAFT, nullable=False)
    # NEW: Max attempts (mainly for public quizzes, orgs might control via assignments)
    max_attempts = db.Column(db.Integer, default=1)
    # NEW: Basic flag for proctoring features
    proctoring_enabled = db.Column(db.Boolean, default=False)

    # Relationships
    organization = db.relationship('Organization', back_populates='created_quizzes')
    questions = db.relationship('Question', secondary=quiz_questions, back_populates='quizzes', lazy='dynamic')
    assigned_students = db.relationship('User', secondary=quiz_assignments, back_populates='assigned_quizzes', lazy='dynamic')
    attempts = db.relationship('QuizAttempt', back_populates='quiz', lazy='dynamic')

    def __repr__(self):
        org_name = self.organization.name if self.organization else "Public/Admin"
        return f'<Quiz {self.title} ({self.status.name}) (Org: {org_name})>'

class QuizAttempt(db.Model):
    __tablename__ = 'quiz_attempts'
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    submit_time = db.Column(db.DateTime, nullable=True)
    score = db.Column(db.Float, nullable=True)
    # NEW: Store max possible score for this attempt (useful if points vary or pooling)
    max_score_possible = db.Column(db.Float, nullable=True)
    is_completed = db.Column(db.Boolean, default=False) # Keep simple completion flag
    # NEW: More detailed status
    status = db.Column(db.Enum(QuizAttemptStatus), default=QuizAttemptStatus.STARTED, nullable=False)
    cheating_flags = db.Column(db.Integer, default=0)
    # NEW: Counter for proctoring violations logged
    proctoring_violations = db.Column(db.Integer, default=0)
    presented_question_ids = db.Column(db.Text, nullable=True) # Store JSON list '[1, 5, 12]'

    # Relationships
    quiz = db.relationship('Quiz', back_populates='attempts')
    user = db.relationship('User', back_populates='quiz_attempts')
    answers = db.relationship('StudentAnswer', back_populates='attempt', cascade='all, delete-orphan', lazy='dynamic')
    # NEW: Link to generated certificate
    certificate = db.relationship('Certificate', back_populates='attempt', uselist=False)
    # NEW: Link to cheating logs for this attempt
    cheating_logs = db.relationship('CheatingLog', back_populates='attempt', lazy='dynamic')


    def set_presented_questions(self, question_ids):
        """Helper to store presented question IDs as JSON."""
        self.presented_question_ids = json.dumps(question_ids)

    def get_presented_questions(self):
        """Helper to retrieve presented question IDs."""
        if self.presented_question_ids:
            try:
                return json.loads(self.presented_question_ids)
            except json.JSONDecodeError:
                return []
        return []

    def __repr__(self):
        return f'<QuizAttempt ID:{self.id} by User:{self.user_id} for Quiz:{self.quiz_id} ({self.status.name})>'

class StudentAnswer(db.Model):
    __tablename__ = 'student_answers'
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('quiz_attempts.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    selected_option_id = db.Column(db.Integer, db.ForeignKey('question_options.id'), nullable=True)
    answer_text = db.Column(db.Text, nullable=True)
    submitted_code = db.Column(db.Text, nullable=True)
    is_correct = db.Column(db.Boolean, nullable=True)
    points_awarded = db.Column(db.Float, default=0, nullable=True)
    time_spent_seconds = db.Column(db.Integer, nullable=True)
    feedback = db.Column(db.Text, nullable=True)
    answered_at = db.Column(db.DateTime, default=datetime.utcnow)
    # NEW: Grading status
    grading_status = db.Column(db.Enum(GradingStatus), default=GradingStatus.PENDING, nullable=False)

    # Relationships
    attempt = db.relationship('QuizAttempt', back_populates='answers')
    question = db.relationship('Question', back_populates='student_answers')
    selected_option = db.relationship('QuestionOption')

    def __repr__(self):
        return f'<StudentAnswer {self.id} for Q{self.question_id} in Attempt {self.attempt_id} ({self.grading_status.name})>'

class CheatingLog(db.Model):
    __tablename__ = 'cheating_logs'
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('quiz_attempts.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False) # Store user ID for easier querying
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    event_type = db.Column(db.String(50), nullable=False)
    details = db.Column(db.Text, nullable=True)

    # NEW: Relationship back to attempt
    attempt = db.relationship('QuizAttempt', back_populates='cheating_logs')
    # Keep user relationship simple if mostly accessing log -> user
    user = db.relationship('User')

    def __repr__(self):
        return f'<CheatingLog {self.id} for Attempt {self.attempt_id} ({self.event_type})>'

# --- NEW Models ---

class Badge(db.Model):
    """ Gamification Badges """
    __tablename__ = 'badges'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=False)
    icon_url = db.Column(db.String(255), nullable=True) # URL to badge image
    criteria = db.Column(db.Text, nullable=True) # Description of how to earn

    # Relationship back to users who earned it
    users = db.relationship('User', secondary=user_badges, back_populates='badges', lazy='dynamic')

    def __repr__(self):
        return f'<Badge {self.name}>'

class Certificate(db.Model):
    """ Certificates generated for quiz completions """
    __tablename__ = 'certificates'
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('quiz_attempts.id'), unique=True, nullable=False) # Link to one specific attempt
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    unique_code = db.Column(db.String(100), unique=True, nullable=False) # For verification
    # Store relevant data snapshot at time of generation
    user_name = db.Column(db.String(100))
    quiz_title = db.Column(db.String(100))
    final_score = db.Column(db.Float)
    # pdf_url = db.Column(db.String(255), nullable=True) # Optional: If storing generated PDF location

    attempt = db.relationship('QuizAttempt', back_populates='certificate')
    user = db.relationship('User') # Simple relationship
    quiz = db.relationship('Quiz') # Simple relationship

    def __repr__(self):
        return f'<Certificate {self.unique_code} for User {self.user_id} on Quiz {self.quiz_id}>'

class Notification(db.Model):
    """ User Notifications """
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Optional: Link to related object (e.g., quiz, badge)
    related_object_type = db.Column(db.String(50), nullable=True) # e.g., 'Quiz', 'Badge'
    related_object_id = db.Column(db.Integer, nullable=True)

    user = db.relationship('User', back_populates='notifications')

    def __repr__(self):
        read_status = "Read" if self.is_read else "Unread"
        return f'<Notification {self.id} for User {self.user_id} ({read_status})>'

# --- End of refined models.py ---