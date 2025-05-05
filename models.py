# /your_app/models.py
# CORRECTED VERSION 6 - Uses Association Object for quiz_questions, info={'doc': ...}

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin # UserMixin belongs on Credentials
from datetime import datetime, timezone, timedelta
import enum
import json
from typing import List, Optional, Dict, Any # For type hinting

# Assume 'db' is initialized in your Flask app's __init__.py or extensions.py
from . import db # Or your actual import path for the db object


# --- Enums ---

class UserRole(enum.Enum):
    """ Defines the roles a user can have within the system. """
    ADMIN = 'Admin'
    ORGANIZATION = 'Organization'
    TEACHER = 'Teacher'
    STUDENT = 'Student'
    USER = 'User' # Individual User

class QuestionType(enum.Enum):
    """ Defines the types of questions available. """
    MCQ = 'Multiple Choice'
    FILL_IN_BLANKS = 'Fill in the Blanks'
    SHORT_ANSWER = 'Short Answer'
    CODING = 'Coding'

class QuestionSelectionStrategy(enum.Enum):
    """ Defines how questions are selected for a quiz attempt. """
    FIXED = 'Fixed Set'
    RANDOM = 'Random Pooling'

class OrgApprovalStatus(enum.Enum):
    """ Defines the approval state of an organization's registration request. """
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'

class InvitationStatus(enum.Enum):
    """ Status for user invitations to join an organization. """
    PENDING = 'pending'
    ACCEPTED = 'accepted'
    DECLINED = 'declined'
    EXPIRED = 'expired'

class QuizStatus(enum.Enum):
    """ Defines the lifecycle status of a quiz. """
    DRAFT = 'Draft'
    PUBLISHED = 'Published'
    ARCHIVED = 'Archived'

class QuizAttemptStatus(enum.Enum):
    """ Defines the status of a user's progress through a quiz attempt. """
    STARTED = 'Started'
    IN_PROGRESS = 'In Progress'
    SUBMITTED = 'Submitted'
    GRADED = 'Graded'
    TIMED_OUT = 'Timed Out'

class GradingStatus(enum.Enum):
    """ Defines the grading status of an individual StudentAnswer. """
    PENDING = 'Pending'
    GRADED = 'Graded'
    ERROR = 'Error'


# --- Association Tables (Defined ONLY ONCE) ---
# Using info={'doc': ...} for table-level documentation if needed.

# REMOVED: The db.Table definition for 'quiz_questions' is removed
#          as the QuizQuestion model now defines this table.

# Associates Tags with Questions for categorization (Many-to-Many)
question_tags = db.Table('question_tags', db.metadata,
    db.Column('question_id', db.Integer, db.ForeignKey('questions.id', ondelete='CASCADE'), primary_key=True, index=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True, index=True),
    info={'doc': "Associates Tags with Questions for categorization (Many-to-Many)"}
)

# Note: User-Badge and User-Friendship are defined below using Association Object patterns.
#       Quiz-StudentAssignment is also defined as an Association Object (QuizAssignment).


# --- Main Models ---

class Credentials(db.Model, UserMixin):
    """ Stores authentication data (login, password, role). Integrates with Flask-Login. """
    __tablename__ = 'credentials'

    id = db.Column(db.Integer, primary_key=True, info={'doc': "Unique ID for Flask-Login"})
    username = db.Column(db.String(80), unique=True, nullable=False, index=True, info={'doc': "Unique username for login"})
    password_hash = db.Column(db.String(256), nullable=False, info={'doc': "Hashed password for secure storage"})
    role = db.Column(db.Enum(UserRole), nullable=False, default=UserRole.USER, index=True, info={'doc': "Role defining user's permissions"})
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True, info={'doc': "Allows disabling login without deleting user"})
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, info={'doc': "Timestamp of credential creation"})
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True, info={'doc': "Timestamp of the last successful login"})

    # One-to-one link to the detailed user profile
    user_profile = db.relationship('User', back_populates='credentials', uselist=False, cascade="all, delete-orphan", passive_deletes=True)

    def set_password(self, password: str) -> None:
        """ Hashes the provided password and stores it. """
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """ Checks if the provided password matches the stored hash. """
        return check_password_hash(self.password_hash, password)

    def get_id(self) -> str: # Required by Flask-Login
        """ Returns the unique ID for Flask-Login (must be a string). """
        return str(self.id)

    def __repr__(self) -> str:
        """ String representation for Credentials object. """
        status = "Active" if self.is_active else "Inactive"
        role_name = self.role.name if self.role else "No Role"
        return f'<Credentials {self.id}: {self.username} ({role_name}) - {status}>'


class User(db.Model):
    """ Stores user profile data (non-authentication details). Linked one-to-one with Credentials. """
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, info={'doc': "Unique ID for the User Profile"})
    credentials_id = db.Column(db.Integer, db.ForeignKey('credentials.id', ondelete='CASCADE'), unique=True, nullable=False, index=True, info={'doc': "FK to the credentials for this user"})
    email = db.Column(db.String(120), unique=True, nullable=False, index=True, info={'doc': "Unique email address for communication/recovery"})
    display_name = db.Column(db.String(100), nullable=True, info={'doc': "Optional user-chosen display name"})
    profile_picture_url = db.Column(db.String(512), nullable=True, info={'doc': "URL to the user's profile picture"})
    bio = db.Column(db.Text, nullable=True, info={'doc': "Short user biography"})
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True, index=True, info={'doc': "FK linking student/teacher/org roles to their organization"})
    student_code = db.Column(db.String(50), nullable=True, index=True, info={'doc': "e.g., Roll Number, Employee ID"})
    enrollment_date = db.Column(db.DateTime(timezone=True), nullable=True, info={'doc': "Date when user joined the organization"})
    gamification_points = db.Column(db.Integer, default=0, nullable=False, info={'doc': "Points accumulated by the user"})
    gamification_level = db.Column(db.Integer, default=1, nullable=False, info={'doc': "Level achieved by the user based on points"})
    profile_created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    profile_updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    credentials = db.relationship('Credentials', back_populates='user_profile', uselist=False)
    organization = db.relationship('Organization', back_populates='members', foreign_keys=[organization_id])
    quiz_attempts = db.relationship('QuizAttempt', back_populates='user', lazy='dynamic', foreign_keys='QuizAttempt.user_id', cascade="all, delete-orphan", passive_deletes=True)
    assignments_for_student = db.relationship('QuizAssignment', back_populates='student', foreign_keys='QuizAssignment.student_user_id', lazy='dynamic', cascade="all, delete-orphan")
    managed_organization = db.relationship('Organization', back_populates='admin_user', foreign_keys='Organization.admin_user_id', uselist=False)
    # Use the UserBadge association object for the many-to-many link
    badges_earned = db.relationship('UserBadge', back_populates='user', lazy='dynamic', cascade="all, delete-orphan")
    notifications = db.relationship('Notification', back_populates='user', lazy='dynamic', foreign_keys='Notification.user_id', cascade="all, delete-orphan", passive_deletes=True)
    friends_initiated = db.relationship('Friendship', foreign_keys='Friendship.user_id', back_populates='user', lazy='dynamic', cascade="all, delete-orphan")
    friends_received = db.relationship('Friendship', foreign_keys='Friendship.friend_user_id', back_populates='friend', lazy='dynamic', cascade="all, delete-orphan")
    created_quizzes = db.relationship('Quiz', back_populates='creator', foreign_keys='Quiz.creator_user_id', lazy='dynamic')
    created_questions = db.relationship('Question', back_populates='creator', foreign_keys='Question.creator_user_id', lazy='dynamic')
    graded_answers = db.relationship('StudentAnswer', back_populates='grader', foreign_keys='StudentAnswer.graded_by_user_id', lazy='dynamic')
    audit_logs_created = db.relationship('AuditLog', back_populates='admin_user', foreign_keys='AuditLog.admin_user_id', lazy='dynamic')
    certificates = db.relationship('Certificate', back_populates='user', lazy='dynamic', foreign_keys='Certificate.user_id')
    cheating_logs = db.relationship('CheatingLog', back_populates='user', lazy='dynamic', foreign_keys='CheatingLog.user_id')
    invitations_received = db.relationship('OrganizationInvitation', back_populates='invitee_profile', foreign_keys='OrganizationInvitation.accepted_by_user_id', lazy='dynamic')
    invitations_sent = db.relationship('OrganizationInvitation', back_populates='inviter', foreign_keys='OrganizationInvitation.inviter_user_id', lazy='dynamic')
    assignments_created = db.relationship('QuizAssignment', back_populates='assigner', foreign_keys='QuizAssignment.assigned_by_user_id', lazy='dynamic')

    def __repr__(self) -> str:
        """ String representation for User profile object. """
        # ... (repr implementation) ...


class Organization(db.Model):
    """ Represents an entity like a college, university, or company using the platform. """
    __tablename__ = 'organizations'
    # ... (Columns: id, name, description, etc. as before) ...
    id = db.Column(db.Integer, primary_key=True, info={'doc': "Unique identifier for the organization"})
    name = db.Column(db.String(100), unique=True, nullable=False, index=True, info={'doc': "Name of the organization"})
    description = db.Column(db.Text, nullable=True, info={'doc': "Optional description of the organization"})
    website_url = db.Column(db.String(512), nullable=True, info={'doc': "Optional website URL"})
    logo_url = db.Column(db.String(512), nullable=True, info={'doc': "Optional logo URL"})
    approval_status = db.Column(db.Enum(OrgApprovalStatus), default=OrgApprovalStatus.PENDING, nullable=False, index=True, info={'doc': "Approval status (pending, approved, rejected)"})
    requested_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, info={'doc': "Timestamp when registration was requested"})
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True, info={'doc': "Timestamp when registration was approved"})
    approved_by_admin_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True, info={'doc': "Admin User Profile who approved"})
    admin_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), unique=True, nullable=True, index=True, info={'doc': "Primary admin User Profile for this org"})
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


    # --- Relationships ---
    admin_user = db.relationship('User', back_populates='managed_organization', foreign_keys=[admin_user_id])
    members = db.relationship('User', back_populates='organization', foreign_keys=[User.organization_id], lazy='dynamic', order_by='User.display_name')
    created_quizzes = db.relationship('Quiz', back_populates='organization', lazy='dynamic', foreign_keys='Quiz.organization_id', cascade="all, delete-orphan", passive_deletes=True)
    questions = db.relationship('Question', back_populates='organization', lazy='dynamic', foreign_keys='Question.organization_id', cascade="all, delete-orphan", passive_deletes=True)
    approving_admin = db.relationship('User', foreign_keys=[approved_by_admin_id])
    invitations = db.relationship('OrganizationInvitation', back_populates='organization', foreign_keys='OrganizationInvitation.organization_id', lazy='dynamic', cascade="all, delete-orphan", passive_deletes=True)

    def __repr__(self) -> str:
        """ String representation for Organization object. """
        # ... (repr implementation) ...


class Tag(db.Model):
    """ Category tags for Questions. """
    __tablename__ = 'tags'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True, info={'doc': "Optional description of the tag"})
    # Use the association table name for secondary relationship
    questions = db.relationship('Question', secondary='question_tags', back_populates='tags', lazy='dynamic')
    def __repr__(self) -> str: return f'<Tag {self.id}: {self.name}>'


class Question(db.Model):
    """ A single question (MCQ, Coding, etc.). Can be owned by Org or User. """
    __tablename__ = 'questions'
    # ... (Columns: id, organization_id, creator_user_id, etc. as before) ...
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=True, index=True, info={'doc': "FK -> Owning Organization (if org-owned)"})
    creator_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True, info={'doc': "FK -> User Profile ID of creator (Teacher, Admin, User)"})
    is_public = db.Column(db.Boolean, default=False, nullable=False, index=True, info={'doc': "Is visible/usable outside the owner's context?"})
    question_type = db.Column(db.Enum(QuestionType), nullable=False, index=True, info={'doc': "Type of the question (MCQ, CODING, etc.)"})
    question_text = db.Column(db.Text, nullable=False, info={'doc': "The main text/prompt of the question"})
    difficulty = db.Column(db.String(20), nullable=True, index=True, info={'doc': "e.g., Easy, Medium, Hard"})
    points = db.Column(db.Float, default=1.0, nullable=False, info={'doc': "Number of points awarded for a correct answer"})
    correct_answer_text = db.Column(db.Text, nullable=True, info={'doc': "Correct answer for Fill-in-blanks, Short Answer"})
    explanation = db.Column(db.Text, nullable=True, info={'doc': "Explanation shown after answering"})
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    is_ai_generated = db.Column(db.Boolean, default=False, nullable=False, info={'doc': "Was this question generated by AI?"})
    ai_prompt = db.Column(db.Text, nullable=True, info={'doc': "The prompt used if AI generated"})


    # --- Relationships ---
    organization = db.relationship('Organization', back_populates='questions', foreign_keys=[organization_id])
    creator = db.relationship('User', back_populates='created_questions', foreign_keys=[creator_user_id])
    options = db.relationship('QuestionOption', back_populates='question', cascade='all, delete-orphan', passive_deletes=True, lazy='dynamic', order_by='QuestionOption.display_order')
    code_templates = db.relationship('CodeTemplate', back_populates='question', cascade='all, delete-orphan', passive_deletes=True, lazy='dynamic')
    test_cases = db.relationship('TestCase', back_populates='question', cascade='all, delete-orphan', passive_deletes=True, lazy='dynamic')
    # Use the association table name for secondary relationship
    tags = db.relationship('Tag', secondary='question_tags', back_populates='questions', lazy='dynamic')

    # Relationship to Quizzes (using secondary table name, marked viewonly)
    quizzes = db.relationship(
        'Quiz',
        secondary='quiz_questions',
        back_populates='questions',
        lazy='dynamic',
        viewonly=True # Read-only access; manage via Quiz.quiz_question_associations
    )
    student_answers = db.relationship('StudentAnswer', back_populates='question', lazy='dynamic', foreign_keys='StudentAnswer.question_id')

    def __repr__(self) -> str:
        """ String representation for Question object. """
        # ... (repr implementation) ...


class QuestionOption(db.Model):
    """ An option for an MCQ Question. """
    __tablename__ = 'question_options'
    # ... (Columns: id, question_id, option_text, etc. as before) ...
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False, index=True)
    option_text = db.Column(db.Text, nullable=False)
    is_correct = db.Column(db.Boolean, default=False, nullable=False, index=True)
    display_order = db.Column(db.Integer, default=0, nullable=False, info={'doc': "Order in which options should be displayed"})
    feedback = db.Column(db.Text, nullable=True, info={'doc': "Specific feedback if this option is chosen"})
    question = db.relationship('Question', back_populates='options')
    def __repr__(self) -> str: return f'<Option {self.id} for Q{self.question_id} Correct:{self.is_correct}>'


class CodeTemplate(db.Model):
    """ Starter code for a Coding Question. """
    __tablename__ = 'code_templates'
    # ... (Columns: id, question_id, language, template_code as before) ...
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False, index=True)
    language = db.Column(db.String(50), nullable=False, index=True, info={'doc': "e.g., python, java, cpp"})
    template_code = db.Column(db.Text, nullable=True)
    question = db.relationship('Question', back_populates='code_templates')
    def __repr__(self) -> str: return f'<CodeTemplate {self.id}: {self.language} for Q{self.question_id}>'


class TestCase(db.Model):
    """ Test case for a Coding Question. """
    __tablename__ = 'test_cases'
    # ... (Columns: id, question_id, input_data, etc. as before) ...
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False, index=True)
    input_data = db.Column(db.Text, nullable=True, info={'doc': "Input for the test case (stdin)"})
    expected_output = db.Column(db.Text, nullable=False, info={'doc': "Expected output (stdout)"})
    is_hidden = db.Column(db.Boolean, default=False, nullable=False, info={'doc': "Whether the input/output is visible to the student"})
    points = db.Column(db.Float, default=1.0, nullable=False, info={'doc': "Points awarded if this test case passes"})
    description = db.Column(db.Text, nullable=True, info={'doc': "Optional description of the test case's purpose"})
    time_limit_ms = db.Column(db.Integer, nullable=True, info={'doc': "Optional time limit in milliseconds"})
    memory_limit_kb = db.Column(db.Integer, nullable=True, info={'doc': "Optional memory limit in kilobytes"})
    question = db.relationship('Question', back_populates='test_cases')
    def __repr__(self) -> str: visibility = "Hidden" if self.is_hidden else "Visible"; return f'<TestCase {self.id} for Q{self.question_id} ({visibility} - {self.points}pts)>'


class Quiz(db.Model):
    """ A collection of questions presented as a test or assessment. """
    __tablename__ = 'quizzes'
    # ... (Columns: id, organization_id, creator_user_id, title, etc. as before) ...
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=True, index=True, info={'doc': "FK -> Owning Organization"})
    creator_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True, info={'doc': "FK -> User Profile ID of creator"})
    is_public = db.Column(db.Boolean, default=False, nullable=False, index=True, info={'doc': "Accessible to any logged-in user?"})
    title = db.Column(db.String(150), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    start_time = db.Column(db.DateTime(timezone=True), nullable=True, index=True, info={'doc': "When the quiz becomes available (timezone aware)"})
    end_time = db.Column(db.DateTime(timezone=True), nullable=True, index=True, info={'doc': "When the quiz ceases to be available (timezone aware)"})
    duration_minutes = db.Column(db.Integer, nullable=False, info={'doc': "Time limit in minutes (0=unlimited)"})
    status = db.Column(db.Enum(QuizStatus), default=QuizStatus.DRAFT, nullable=False, index=True, info={'doc': "Lifecycle status (Draft, Published, Archived)"})
    max_attempts = db.Column(db.Integer, default=1, nullable=False, info={'doc': "Maximum attempts allowed (0=unlimited)"})
    selection_strategy = db.Column(db.Enum(QuestionSelectionStrategy), nullable=False, default=QuestionSelectionStrategy.FIXED, info={'doc': "How questions are selected (Fixed, Random)"})
    num_questions_to_pool = db.Column(db.Integer, nullable=True, info={'doc': "Number of questions to select if strategy is Random"})
    shuffle_questions = db.Column(db.Boolean, default=False, nullable=False, info={'doc': "Randomize question order per attempt?"})
    shuffle_options = db.Column(db.Boolean, default=False, nullable=False, info={'doc': "Randomize MCQ option order?"})
    show_results_immediately = db.Column(db.Boolean, default=True, nullable=False, info={'doc': "Show score right after submission?"})
    results_visibility_config = db.Column(db.JSON, nullable=True, info={'doc': "JSON settings for when/what results to show"})
    allow_navigation = db.Column(db.Boolean, default=True, nullable=False, info={'doc': "Allow moving between questions?"})
    proctoring_enabled = db.Column(db.Boolean, default=False, nullable=False, info={'doc': "Are proctoring features enabled?"})
    proctoring_config = db.Column(db.JSON, nullable=True, info={'doc': "JSON settings for proctoring (cam, mic, screen, etc.)"})
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    published_at = db.Column(db.DateTime(timezone=True), nullable=True, info={'doc': "Timestamp when moved to Published status"})


    # --- Relationships ---
    organization = db.relationship('Organization', back_populates='created_quizzes', foreign_keys=[organization_id])
    creator = db.relationship('User', back_populates='created_quizzes', foreign_keys=[creator_user_id])

    # Read-only secondary relationship to get Question objects directly
    questions = db.relationship(
        'Question',
        secondary='quiz_questions', # Use the table name (defined by QuizQuestion model)
        back_populates='quizzes',
        lazy='dynamic',
        # Order using the association object's attribute
        order_by='QuizQuestion.question_order',
        viewonly=True # Let quiz_question_associations handle modifications
    )
    # Writable relationship to the association object for managing the link + order
    quiz_question_associations = db.relationship('QuizQuestion', back_populates='quiz', cascade="all, delete-orphan", passive_deletes=True, order_by='QuizQuestion.question_order')

    assignments = db.relationship('QuizAssignment', back_populates='quiz', lazy='dynamic', foreign_keys='QuizAssignment.quiz_id', cascade="all, delete-orphan", passive_deletes=True)
    attempts = db.relationship('QuizAttempt', back_populates='quiz', lazy='dynamic', foreign_keys='QuizAttempt.quiz_id', cascade="all, delete-orphan", passive_deletes=True)
    certificates = db.relationship('Certificate', back_populates='quiz', lazy='dynamic', foreign_keys='Certificate.quiz_id')

    @property
    def assigned_students(self):
        """ Convenience property to get assigned User profiles. """
        return User.query.join(QuizAssignment, User.id == QuizAssignment.student_user_id).filter(QuizAssignment.quiz_id == self.id)

    def __repr__(self) -> str:
        """ String representation for Quiz object. """
        # ... (repr implementation) ...


# --- Association Object for Quiz <-> Question ---
class QuizQuestion(db.Model):
    """ Association Object for linking Quizzes and Questions, allowing ordering. """
    __tablename__ = 'quiz_questions' # *THIS* defines the table name
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id', ondelete='CASCADE'), primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete='RESTRICT'), primary_key=True)
    question_order = db.Column(db.Integer, default=0, nullable=False, info={'doc': "Order of the question within the quiz (for Fixed strategy)"})

    # Define relationships back to Quiz and Question
    quiz = db.relationship('Quiz', back_populates='quiz_question_associations')
    question = db.relationship('Question') # Simple relationship to Question


# --- Association Object for Quiz <-> Student Assignment ---
class QuizAssignment(db.Model):
    """ Association object for Quiz-to-Student assignments, allowing extra fields like assigner and due date. """
    __tablename__ = 'quiz_assignments'
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id', ondelete='CASCADE'), primary_key=True, index=True)
    student_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True, index=True, info={'doc': "FK -> User profile ID of assigned Student"})
    assigned_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    assigned_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True, info={'doc': "FK -> User profile ID of assigner (Teacher/Admin)"})
    due_date = db.Column(db.DateTime(timezone=True), nullable=True, index=True, info={'doc': "Optional due date for the assignment"})

    # Relationships
    quiz = db.relationship('Quiz', back_populates='assignments')
    student = db.relationship('User', back_populates='assignments_for_student', foreign_keys=[student_user_id])
    assigner = db.relationship('User', back_populates='assignments_created', foreign_keys=[assigned_by_user_id])

    def __repr__(self):
        print("mai solo sol karna janne")
        # ... (repr implementation) ...


# --- Association Object for User <-> Badge ---
class UserBadge(db.Model):
    """ Association Object storing which User earned which Badge and when. """
    __tablename__ = 'user_badges'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    badge_id = db.Column(db.Integer, db.ForeignKey('badges.id', ondelete='CASCADE'), primary_key=True)
    earned_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', back_populates='badges_earned')
    badge = db.relationship('Badge', back_populates='user_assignments')

    def __repr__(self) -> str:
        return f'<UserBadge User:{self.user_id} -> Badge:{self.badge_id}>'


# --- Association Object for User <-> User Friendship ---
class Friendship(db.Model):
    """ Association Object storing friendship between two User profiles. """
    __tablename__ = 'friendships'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True, info={'doc': "FK to one user profile in the friendship"})
    friend_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True, info={'doc': "FK to the other user profile in the friendship"})
    established_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), info={'doc': "Timestamp when friendship was established"})
    # status = db.Column(db.Enum(FriendStatus), default='accepted') # If friend requests needed

    db.CheckConstraint('user_id <> friend_user_id', name='ck_friendship_not_self')

    user = db.relationship('User', foreign_keys=[user_id], back_populates='friends_initiated')
    friend = db.relationship('User', foreign_keys=[friend_user_id], back_populates='friends_received')

    def __repr__(self) -> str:
        return f'<Friendship User:{self.user_id} <-> Friend:{self.friend_user_id}>'


# ... (Rest of Models: QuizAttempt, StudentAnswer, CheatingLog, Badge, Certificate, Notification, AuditLog, OrganizationInvitation) ...
# (Paste the full definitions for these models from V5, ensuring info={'doc':...} is used for columns)

class QuizAttempt(db.Model):
    """ A single user's attempt at taking a quiz. """
    __tablename__ = 'quiz_attempts'
    # ... (All columns from V5 using info={'doc': ...}) ...
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True, info={'doc': "FK -> User Profile ID of participant"})
    start_time = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    submit_time = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    deadline = db.Column(db.DateTime(timezone=True), nullable=True, index=True, info={'doc': "Calculated time when the attempt should auto-submit"})
    score = db.Column(db.Float, nullable=True)
    max_score_possible = db.Column(db.Float, nullable=True, info={'doc': "Max score based on questions presented"})
    status = db.Column(db.Enum(QuizAttemptStatus), default=QuizAttemptStatus.STARTED, nullable=False, index=True)
    grading_completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    cheating_flags_json = db.Column(db.Text, nullable=True, info={'doc': "JSON object storing flags like {'tab_switches': 3}"})
    proctoring_violations = db.Column(db.Integer, default=0, nullable=False)
    ip_address = db.Column(db.String(45), nullable=True) # Supports IPv6
    user_agent = db.Column(db.String(255), nullable=True)
    presented_question_ids_json = db.Column(db.Text, default='[]', nullable=False, info={'doc': "JSON list of question IDs presented"})

    quiz = db.relationship('Quiz', back_populates='attempts', foreign_keys=[quiz_id])
    user = db.relationship('User', back_populates='quiz_attempts', foreign_keys=[user_id])
    answers = db.relationship('StudentAnswer', back_populates='attempt', cascade="all, delete-orphan", passive_deletes=True, lazy='dynamic', foreign_keys='StudentAnswer.attempt_id')
    certificate = db.relationship('Certificate', back_populates='attempt', uselist=False, cascade="all, delete-orphan", passive_deletes=True)
    cheating_logs = db.relationship('CheatingLog', back_populates='attempt', lazy='dynamic', cascade="all, delete-orphan", passive_deletes=True, foreign_keys='CheatingLog.attempt_id')
    # ... (Methods: set_presented_questions, get_presented_questions, repr) ...
    def set_presented_questions(self, question_ids: List[int]) -> None:
        """ Stores the list of presented question IDs as a JSON string. """
        self.presented_question_ids_json = json.dumps(sorted(list(set(question_ids)))) # Store unique sorted IDs

    def get_presented_questions(self) -> List[int]:
        """ Retrieves the list of presented question IDs from the JSON string. """
        try:
            ids = json.loads(self.presented_question_ids_json or '[]')
            return [int(id_val) for id_val in ids if isinstance(id_val, (int, str)) and str(id_val).isdigit()]
        except: return []

    def __repr__(self) -> str:
        """ String representation for QuizAttempt object. """
        username = self.user.credentials.username if self.user and self.user.credentials else "N/A"
        return f'<QuizAttempt ID:{self.id} by User:{username} (PID:{self.user_id}) for Quiz:{self.quiz_id} ({self.status.name if self.status else "N/A"})>'


class StudentAnswer(db.Model):
    """ A user's answer to a specific question within an attempt. """
    __tablename__ = 'student_answers'
    # ... (All columns from V5 using info={'doc': ...}) ...
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('quiz_attempts.id', ondelete='CASCADE'), nullable=False, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False, index=True)
    selected_option_id = db.Column(db.Integer, db.ForeignKey('question_options.id', ondelete='SET NULL'), nullable=True, index=True, info={'doc': "FK to chosen MCQ option"})
    answer_text = db.Column(db.Text, nullable=True, info={'doc': "Answer for text-based questions"})
    submitted_code = db.Column(db.Text, nullable=True, info={'doc': "Submitted code for coding questions"})
    code_language = db.Column(db.String(50), nullable=True, info={'doc': "Language of submitted code"})
    is_correct = db.Column(db.Boolean, nullable=True, index=True, info={'doc': "Result of grading"})
    points_awarded = db.Column(db.Float, default=0.0, nullable=True, info={'doc': "Points received for this answer"}) # Allow nullable for pending
    feedback = db.Column(db.Text, nullable=True, info={'doc': "Manual or automatic feedback"})
    grading_status = db.Column(db.Enum(GradingStatus), default=GradingStatus.PENDING, nullable=False, index=True)
    graded_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True, info={'doc': "FK -> User Profile ID of grader"})
    graded_at = db.Column(db.DateTime(timezone=True), nullable=True)
    answered_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    time_spent_seconds = db.Column(db.Integer, nullable=True, info={'doc': "Time spent on this question (if tracked)"})
    execution_result = db.Column(db.JSON, nullable=True, info={'doc': "JSON results from code execution service"})

    attempt = db.relationship('QuizAttempt', back_populates='answers', foreign_keys=[attempt_id])
    question = db.relationship('Question', back_populates='student_answers', foreign_keys=[question_id])
    selected_option = db.relationship('QuestionOption', foreign_keys=[selected_option_id])
    grader = db.relationship('User', back_populates='graded_answers', foreign_keys=[graded_by_user_id])
    # ... (repr Method) ...
    def __repr__(self) -> str:
        """ String representation for StudentAnswer object. """
        grade_info = f"Correct: {self.is_correct}" if self.is_correct is not None else self.grading_status.name
        return f'<StudentAnswer {self.id} for Q{self.question_id} in Attempt {self.attempt_id} ({grade_info})>'


class CheatingLog(db.Model):
    """ Log entry for a suspected cheating event. """
    __tablename__ = 'cheating_logs'
    # ... (All columns from V5 using info={'doc': ...}) ...
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('quiz_attempts.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True, info={'doc': "FK -> User Profile ID"})
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    event_type = db.Column(db.String(50), nullable=False, index=True, info={'doc': "e.g., TAB_SWITCH, COPY_PASTE"})
    details = db.Column(db.Text, nullable=True, info={'doc': "Additional context about the event"})
    severity = db.Column(db.String(20), nullable=True, info={'doc': "e.g., Low, Medium, High"})

    attempt = db.relationship('QuizAttempt', back_populates='cheating_logs', foreign_keys=[attempt_id])
    user = db.relationship('User', back_populates='cheating_logs', foreign_keys=[user_id])
    # ... (repr Method) ...
    def __repr__(self) -> str:
        """ String representation for CheatingLog object. """
        ts = self.timestamp.strftime('%Y-%m-%d %H:%M:%S %Z') if self.timestamp else "N/A"
        return f'<CheatingLog {self.id} for Attempt {self.attempt_id} (UserPID:{self.user_id}) ({self.event_type} @ {ts})>'


class Badge(db.Model):
    """ Gamification achievement badge. """
    __tablename__ = 'badges'
    # ... (All columns from V5 using info={'doc': ...}) ...
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    icon_url = db.Column(db.String(512), nullable=True)
    criteria_text = db.Column(db.Text, nullable=True, info={'doc': "Human-readable criteria"})
    criteria_config = db.Column(db.JSON, nullable=True, info={'doc': "Machine-readable criteria for automation"})
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user_assignments = db.relationship('UserBadge', back_populates='badge', lazy='dynamic', cascade="all, delete-orphan")
    def __repr__(self) -> str: return f'<Badge {self.id}: {self.name}>'


class Certificate(db.Model):
    """ Verifiable certificate awarded for quiz completion. """
    __tablename__ = 'certificates'
    # ... (All columns from V5 using info={'doc': ...}) ...
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('quiz_attempts.id', ondelete='CASCADE'), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True, info={'doc': "FK -> User Profile ID"})
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id', ondelete='CASCADE'), nullable=False, index=True)
    generated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    unique_code = db.Column(db.String(100), unique=True, nullable=False, index=True, info={'doc': "Unique verifiable code"})
    user_display_name = db.Column(db.String(100))
    user_email = db.Column(db.String(120))
    quiz_title = db.Column(db.String(150))
    final_score = db.Column(db.Float)
    issued_by_name = db.Column(db.String(150), default="CodeQuizHub")
    pdf_url = db.Column(db.String(512), nullable=True, info={'doc': "URL to the generated PDF certificate file"})

    attempt = db.relationship('QuizAttempt', back_populates='certificate', foreign_keys=[attempt_id])
    user = db.relationship('User', back_populates='certificates', foreign_keys=[user_id])
    quiz = db.relationship('Quiz', back_populates='certificates', foreign_keys=[quiz_id])
    def __repr__(self) -> str: return f'<Certificate {self.id} ({self.unique_code}) for UserPID:{self.user_id}, Quiz:{self.quiz_id}>'


class Notification(db.Model):
    """ In-app notification for users. """
    __tablename__ = 'notifications'
    # ... (All columns from V5 using info={'doc': ...}) ...
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True, info={'doc': "FK -> User Profile ID of recipient"})
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    read_at = db.Column(db.DateTime(timezone=True), nullable=True)
    notification_type = db.Column(db.String(50), nullable=True, index=True, info={'doc': "e.g., ASSIGNMENT, GRADE_UPDATE"})
    related_object_type = db.Column(db.String(50), nullable=True, index=True, info={'doc': "Type of related object (e.g., Quiz)"})
    related_object_id = db.Column(db.Integer, nullable=True, index=True, info={'doc': "ID of related object"})
    link_url = db.Column(db.String(512), nullable=True, info={'doc': "Direct navigation URL"})

    user = db.relationship('User', back_populates='notifications', foreign_keys=[user_id])
    def __repr__(self) -> str: read_status = "Read" if self.is_read else "Unread"; return f'<Notification {self.id} for UserPID:{self.user_id} ({read_status}) Type:{self.notification_type}>'


class AuditLog(db.Model):
    """ Record of significant actions, primarily by Admins. """
    __tablename__ = 'audit_logs'
    # ... (All columns from V5 using info={'doc': ...}) ...
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    admin_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True, info={'doc': "FK -> Admin's User Profile ID"})
    action = db.Column(db.String(255), nullable=False, index=True, info={'doc': "Description of action (e.g., APPROVE_ORG)"})
    target_type = db.Column(db.String(50), nullable=True, index=True, info={'doc': "Type of object acted upon (e.g., Organization)"})
    target_id = db.Column(db.Integer, nullable=True, index=True, info={'doc': "ID of object acted upon"})
    details = db.Column(db.Text, nullable=True, info={'doc': "Additional details (e.g., JSON diff)"})
    ip_address = db.Column(db.String(45), nullable=True)

    admin_user = db.relationship('User', back_populates='audit_logs_created', foreign_keys=[admin_user_id])
    def __repr__(self) -> str: target_info = f" ({self.target_type} ID:{self.target_id})" if self.target_type and self.target_id else ""; return f'<AuditLog {self.id} by AdminPID:{self.admin_user_id} @ {self.timestamp} - Action:{self.action}{target_info}>'

class OrganizationInvitation(db.Model):
    """ Records invitations sent to users to join an organization. """
    __tablename__ = 'organization_invitations'
    # ... (All columns from V5 using info={'doc': ...}) ...
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True)
    invitee_email = db.Column(db.String(120), nullable=False, index=True, info={'doc': "Email address of the invited user"})
    invited_as_role = db.Column(db.Enum(UserRole), nullable=False, default=UserRole.STUDENT, info={'doc': "Role the user is invited to join as"})
    invitation_token = db.Column(db.String(100), unique=True, nullable=False, index=True, info={'doc': "Secure token for the invitation link"})
    status = db.Column(db.Enum(InvitationStatus), default=InvitationStatus.PENDING, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc) + timedelta(days=7))
    inviter_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True, info={'doc': "User profile ID of the inviter"})
    accepted_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True, info={'doc': "User profile ID of the user who accepted"})
    accepted_at = db.Column(db.DateTime(timezone=True), nullable=True)

    organization = db.relationship('Organization', back_populates='invitations', foreign_keys=[organization_id])
    inviter = db.relationship('User', back_populates='invitations_sent', foreign_keys=[inviter_user_id])
    invitee_profile = db.relationship('User', back_populates='invitations_received', foreign_keys=[accepted_by_user_id])
    def __repr__(self) -> str:
        """ String representation for OrganizationInvitation object. """
        status = self.status.name if self.status else "N/A"
        return f'<OrgInvitation {self.id} for {self.invitee_email} to OrgID:{self.organization_id} ({status})>'


# --- End of models.py ---