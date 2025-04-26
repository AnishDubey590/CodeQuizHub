# models.py - Comprehensive Database Model for CodeQuizHub v3
# ===============================================================================
# This version separates Credentials (Auth) from User (Profile), includes an
# explicit Teacher role within Organizations, and aims for a logical structure
# reflecting a college/teacher/student scenario alongside individual users.
# Focuses on data integrity, clear relationships, and supporting core features.
# ===============================================================================

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin # UserMixin belongs on Credentials for Flask-Login integration
from datetime import datetime, timezone, timedelta # Use timezone-aware datetimes and timedelta
import enum
import json
from typing import List, Optional, Dict, Any # For type hinting helper methods

# Assume 'db' is initialized in your Flask app's __init__.py or extensions.py
from . import db # Or your actual import path for the db object


# --- Enums ---
# Controlled vocabularies for specific fields, improving data integrity.

class UserRole(enum.Enum):
    """ Defines the roles a user can have within the system. """
    ADMIN = 'Admin'             # Superuser, full system access
    ORGANIZATION = 'Organization' # Primary admin/manager for an organization's account
    TEACHER = 'Teacher'         # Creates/manages quizzes/students *within* an organization
    STUDENT = 'Student'         # Takes quizzes, belongs to an organization
    USER = 'User'               # General individual user, operates outside organizations

class QuestionType(enum.Enum):
    """ Defines the types of questions available. """
    MCQ = 'Multiple Choice'             # Standard multiple choice
    FILL_IN_BLANKS = 'Fill in the Blanks' # Answer is one or more specific strings
    SHORT_ANSWER = 'Short Answer'         # Free text answer, often requires manual grading
    CODING = 'Coding'                     # Requires code submission and execution against test cases

class QuestionSelectionStrategy(enum.Enum):
    """ Defines how questions are selected for a quiz attempt. """
    FIXED = 'Fixed Set'          # All predefined questions are used in order
    RANDOM = 'Random Pooling'    # A specified number of questions are randomly chosen from the pool

class OrgApprovalStatus(enum.Enum):
    """ Defines the approval state of an organization's registration request. """
    PENDING = 'pending'          # Awaiting administrator review
    APPROVED = 'approved'        # Registration accepted
    REJECTED = 'rejected'        # Registration denied

class InvitationStatus(enum.Enum):
    """ Status for user invitations to join an organization. """
    PENDING = 'pending'     # Invitation sent, awaiting user action
    ACCEPTED = 'accepted'   # User accepted the invitation
    DECLINED = 'declined'   # User declined the invitation
    EXPIRED = 'expired'     # Invitation link expired

class QuizStatus(enum.Enum):
    """ Defines the lifecycle status of a quiz. """
    DRAFT = 'Draft'         # In creation/editing, not visible/usable yet
    PUBLISHED = 'Published' # Ready, potentially assignable or active
    ARCHIVED = 'Archived'   # No longer active, kept for historical records/analysis

class QuizAttemptStatus(enum.Enum):
    """ Defines the status of a user's progress through a quiz attempt. """
    STARTED = 'Started'     # User has begun the attempt
    IN_PROGRESS = 'In Progress' # User is actively working (optional, can infer)
    SUBMITTED = 'Submitted' # User finalized their answers manually
    GRADED = 'Graded'       # Scoring is complete (automatic or manual)
    TIMED_OUT = 'Timed Out' # Attempt automatically ended due to time limit

class GradingStatus(enum.Enum):
    """ Defines the grading status of an individual StudentAnswer. """
    PENDING = 'Pending'     # Awaiting grading (relevant for non-auto-graded types)
    GRADED = 'Graded'       # Grading complete
    ERROR = 'Error'         # An error occurred during automatic grading


# --- Association Tables ---
# Manage many-to-many relationships. Using indexes and sensible ON DELETE clauses.

quiz_questions = db.Table('quiz_questions',
    db.Column('quiz_id', db.Integer, db.ForeignKey('quizzes.id', ondelete='CASCADE'), primary_key=True, index=True),
    db.Column('question_id', db.Integer, db.ForeignKey('questions.id', ondelete='RESTRICT'), primary_key=True, index=True),
    # RESTRICT on question prevents deleting a question if it's actively used in a quiz.
    doc="Maps Questions included in a specific Quiz (Many-to-Many)"
)

question_tags = db.Table('question_tags',
    db.Column('question_id', db.Integer, db.ForeignKey('questions.id', ondelete='CASCADE'), primary_key=True, index=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True, index=True),
    doc="Associates Tags with Questions for categorization (Many-to-Many)"
)

# Links Quizzes specifically assigned to Students (User profiles)
quiz_assignments = db.Table('quiz_assignments',
    db.Column('quiz_id', db.Integer, db.ForeignKey('quizzes.id', ondelete='CASCADE'), primary_key=True, index=True),
    db.Column('student_user_id', db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True, index=True, doc="FK -> User profile ID of the assigned Student"),
    db.Column('assigned_at', db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)),
    db.Column('assigned_by_user_id', db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True, doc="FK -> User profile ID of the Teacher/Admin who assigned"),
    doc="Records specific Quiz assignments to Student User profiles"
)

# Links User profiles to earned Badges
user_badges = db.Table('user_badges',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True, index=True, doc="FK -> User profile ID"),
    db.Column('badge_id', db.Integer, db.ForeignKey('badges.id', ondelete='CASCADE'), primary_key=True, index=True),
    db.Column('earned_at', db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)),
    doc="Records Badges earned by User profiles (Many-to-Many)"
)

# Links User profiles for Friendships (for Individual Users)
friendships = db.Table('friendships',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True, index=True, doc="FK -> Initiating User profile ID"),
    db.Column('friend_user_id', db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True, index=True, doc="FK -> Friend's User profile ID"),
    db.Column('established_at', db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)),
    # Consider 'status' (pending, accepted) if friend requests needed
    doc="Represents friendships between Individual User profiles (Many-to-Many)"
)


# --- Main Models ---

class Credentials(db.Model, UserMixin):
    """ Stores authentication data (login, password, role). Integrates with Flask-Login. """
    __tablename__ = 'credentials'

    id = db.Column(db.Integer, primary_key=True, doc="Unique ID for Flask-Login")
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.Enum(UserRole), nullable=False, default=UserRole.USER, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True, doc="Allows disabling login without deleting user")
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # One-to-one link to the detailed user profile
    # cascade: Deleting credentials removes the associated user profile.
    user_profile = db.relationship('User', back_populates='credentials', uselist=False, cascade="all, delete-orphan", passive_deletes=True)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def get_id(self) -> str: # Required by Flask-Login
        return str(self.id)

    def __repr__(self) -> str:
        status = "Active" if self.is_active else "Inactive"
        role_name = self.role.name if self.role else "No Role"
        return f'<Credentials {self.id}: {self.username} ({role_name}) - {status}>'


class User(db.Model):
    """ Stores user profile data (non-authentication details). Linked one-to-one with Credentials. """
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, doc="Unique ID for the User Profile")
    # Foreign key linking back to the Credentials table
    credentials_id = db.Column(db.Integer, db.ForeignKey('credentials.id', ondelete='CASCADE'), unique=True, nullable=False, index=True)

    # --- Profile Fields ---
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(100), nullable=True)
    profile_picture_url = db.Column(db.String(512), nullable=True)
    bio = db.Column(db.Text, nullable=True)

    # --- Organization Membership ---
    # Nullable because Admins and Individual Users ('USER' role) don't belong to one.
    # ondelete='SET NULL': If an org is deleted, members become unaffiliated rather than deleted.
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True, index=True)
    # Specific fields for students/staff within an organization
    student_code = db.Column(db.String(50), nullable=True, index=True, doc="e.g., Roll Number, Employee ID")
    enrollment_date = db.Column(db.DateTime(timezone=True), nullable=True)

    # --- Gamification ---
    gamification_points = db.Column(db.Integer, default=0, nullable=False)
    gamification_level = db.Column(db.Integer, default=1, nullable=False)

    # --- Timestamps ---
    profile_created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    profile_updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # --- Relationships ---

    # Link back to credentials (One-to-One)
    credentials = db.relationship('Credentials', back_populates='user_profile', uselist=False)

    # Organization this user profile belongs to (if Student/Teacher/Org Admin)
    organization = db.relationship('Organization', back_populates='members', foreign_keys=[organization_id])

    # Attempts made by this user profile (Student, User)
    quiz_attempts = db.relationship('QuizAttempt', back_populates='user', lazy='dynamic', foreign_keys='QuizAttempt.user_id', cascade="all, delete-orphan", passive_deletes=True)

    # Quizzes assigned to this user profile (Student)
    assigned_quizzes = db.relationship('Quiz', secondary=quiz_assignments, primaryjoin=(id == quiz_assignments.c.student_user_id), back_populates='assigned_students', lazy='dynamic')

    # Organization managed *by* this user profile (if Credentials.role == ORGANIZATION)
    managed_organization = db.relationship('Organization', back_populates='admin_user', foreign_keys='Organization.admin_user_id', uselist=False)

    # Badges earned by this user profile
    badges = db.relationship('Badge', secondary=user_badges, back_populates='users', lazy='dynamic')

    # Notifications received by this user profile
    notifications = db.relationship('Notification', back_populates='user', lazy='dynamic', foreign_keys='Notification.user_id', cascade="all, delete-orphan", passive_deletes=True)

    # Friendships (Individual Users) - symmetric view
    friends = db.relationship('User', secondary=friendships, primaryjoin=(id == friendships.c.user_id), secondaryjoin=(id == friendships.c.friend_user_id), lazy='dynamic') # Simplified symmetric view

    # Quizzes created *by* this user profile (Teacher, Admin, User)
    created_quizzes = db.relationship('Quiz', back_populates='creator', foreign_keys='Quiz.creator_user_id', lazy='dynamic')

    # Questions created *by* this user profile (Teacher, Admin, User)
    created_questions = db.relationship('Question', back_populates='creator', foreign_keys='Question.creator_user_id', lazy='dynamic')

    # Answers graded *by* this user profile (Teacher, Admin)
    graded_answers = db.relationship('StudentAnswer', back_populates='grader', foreign_keys='StudentAnswer.graded_by_user_id', lazy='dynamic')

    # Audit logs initiated *by* this user profile (Admin)
    audit_logs_created = db.relationship('AuditLog', back_populates='admin_user', foreign_keys='AuditLog.admin_user_id', lazy='dynamic')

    # Certificates awarded *to* this user profile
    certificates = db.relationship('Certificate', back_populates='user', lazy='dynamic', foreign_keys='Certificate.user_id')

    # Cheating logs related to this user profile (useful for direct lookup)
    cheating_logs = db.relationship('CheatingLog', back_populates='user', lazy='dynamic', foreign_keys='CheatingLog.user_id')

    # Invitations received or sent by this user (if implementing invitations)
    invitations_received = db.relationship('OrganizationInvitation', back_populates='invitee', foreign_keys='OrganizationInvitation.invitee_email', primaryjoin='User.email == OrganizationInvitation.invitee_email', lazy='dynamic') # Join on email before user exists
    invitations_sent = db.relationship('OrganizationInvitation', back_populates='inviter', foreign_keys='OrganizationInvitation.inviter_user_id', lazy='dynamic')

    # Assignments assigned by this user profile (if Teacher/Admin)
    assignments_created = db.relationship('QuizAssignment', back_populates='assigner', foreign_keys='QuizAssignment.assigned_by_user_id', lazy='dynamic')


    def __repr__(self) -> str:
        username = self.credentials.username if self.credentials else "N/A"
        role = self.credentials.role.name if self.credentials and self.credentials.role else "N/A"
        org_info = f" (OrgID: {self.organization_id})" if self.organization_id else ""
        return f'<User {self.id}: {self.email} (Login: {username}, Role: {role}){org_info}>'


class Organization(db.Model):
    """ Represents an entity like a college, university, or company using the platform. """
    __tablename__ = 'organizations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    website_url = db.Column(db.String(512), nullable=True)
    logo_url = db.Column(db.String(512), nullable=True)

    # Approval Workflow
    approval_status = db.Column(db.Enum(OrgApprovalStatus), default=OrgApprovalStatus.PENDING, nullable=False, index=True)
    requested_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    # FKs point to User *profile* IDs (users.id)
    approved_by_admin_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True, doc="Admin User Profile who approved")
    # This user MUST have Credentials.role == ORGANIZATION
    admin_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), unique=True, nullable=True, index=True, doc="Primary admin User Profile for this org")

    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # --- Relationships ---
    # User profile managing this organization (Role: ORGANIZATION)
    admin_user = db.relationship('User', back_populates='managed_organization', foreign_keys=[admin_user_id])

    # User profiles belonging to this organization (Roles: TEACHER, STUDENT)
    members = db.relationship('User', back_populates='organization', foreign_keys=[User.organization_id], lazy='dynamic', order_by='User.display_name')

    # Quizzes owned/created *by* the organization itself (distinct from teacher-created)
    created_quizzes = db.relationship('Quiz', back_populates='organization', lazy='dynamic', foreign_keys='Quiz.organization_id', cascade="all, delete-orphan", passive_deletes=True)

    # Questions owned *by* the organization
    questions = db.relationship('Question', back_populates='organization', lazy='dynamic', foreign_keys='Question.organization_id', cascade="all, delete-orphan", passive_deletes=True)

    # The admin User profile who approved this org
    approving_admin = db.relationship('User', foreign_keys=[approved_by_admin_id])

    # Invitations sent *by* this organization (potentially by admin or teachers)
    invitations = db.relationship('OrganizationInvitation', back_populates='organization', foreign_keys='OrganizationInvitation.organization_id', lazy='dynamic', cascade="all, delete-orphan", passive_deletes=True)


    def __repr__(self) -> str:
        admin_username = "None"
        if self.admin_user and self.admin_user.credentials:
            admin_username = self.admin_user.credentials.username
        status = self.approval_status.name if self.approval_status else "N/A"
        return f'<Organization {self.id}: {self.name} ({status}), Admin: {admin_username}>'


class Tag(db.Model):
    """ Category tags for Questions. """
    __tablename__ = 'tags'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    # Many-to-many relationship with Question
    questions = db.relationship('Question', secondary=question_tags, back_populates='tags', lazy='dynamic')
    def __repr__(self) -> str: return f'<Tag {self.id}: {self.name}>'


class Question(db.Model):
    """ A single question (MCQ, Coding, etc.). Can be owned by Org or User. """
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True)

    # --- Ownership & Visibility ---
    # If org-owned, org ID is set. If user-created, creator ID is set.
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=True, index=True, doc="FK -> Owning Organization (if org-owned)")
    creator_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True, doc="FK -> User Profile ID of creator (Teacher, Admin, User)")
    is_public = db.Column(db.Boolean, default=False, nullable=False, index=True, doc="Is visible/usable outside the owner's context?")

    # --- Content & Type ---
    question_type = db.Column(db.Enum(QuestionType), nullable=False, index=True)
    question_text = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.String(20), nullable=True, index=True) # Consider Enum
    points = db.Column(db.Float, default=1.0, nullable=False) # Use Float for potential partial points
    correct_answer_text = db.Column(db.Text, nullable=True) # For Fill-in-blanks, Short Answer
    explanation = db.Column(db.Text, nullable=True)

    # --- Metadata ---
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    is_ai_generated = db.Column(db.Boolean, default=False, nullable=False)
    ai_prompt = db.Column(db.Text, nullable=True)

    # --- Relationships ---
    organization = db.relationship('Organization', back_populates='questions', foreign_keys=[organization_id])
    creator = db.relationship('User', back_populates='created_questions', foreign_keys=[creator_user_id]) # Links to User profile

    options = db.relationship('QuestionOption', back_populates='question', cascade='all, delete-orphan', passive_deletes=True, lazy='dynamic', order_by='QuestionOption.display_order')
    code_templates = db.relationship('CodeTemplate', back_populates='question', cascade='all, delete-orphan', passive_deletes=True, lazy='dynamic')
    test_cases = db.relationship('TestCase', back_populates='question', cascade='all, delete-orphan', passive_deletes=True, lazy='dynamic')
    tags = db.relationship('Tag', secondary=question_tags, back_populates='questions', lazy='dynamic')
    # Quizzes that *include* this question
    quizzes = db.relationship('Quiz', secondary=quiz_questions, back_populates='questions', lazy='dynamic')
    # All answers submitted for this question across all attempts
    student_answers = db.relationship('StudentAnswer', back_populates='question', lazy='dynamic', foreign_keys='StudentAnswer.question_id')

    def __repr__(self) -> str:
        owner_info = "Public/Admin"
        if self.organization_id: owner_info = f"OrgID: {self.organization_id}"
        elif self.creator_user_id: owner_info = f"UserID: {self.creator_user_id}"
        q_type = self.question_type.name if self.question_type else "N/A"
        return f'<Question {self.id} ({q_type}) Owner:({owner_info})>'


class QuestionOption(db.Model):
    """ An option for an MCQ Question. """
    __tablename__ = 'question_options'
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False, index=True)
    option_text = db.Column(db.Text, nullable=False)
    is_correct = db.Column(db.Boolean, default=False, nullable=False, index=True)
    display_order = db.Column(db.Integer, default=0, nullable=False)
    feedback = db.Column(db.Text, nullable=True, doc="Specific feedback if this option is chosen") # Option-specific feedback
    question = db.relationship('Question', back_populates='options')
    def __repr__(self) -> str: return f'<Option {self.id} for Q{self.question_id} Correct:{self.is_correct}>'


class CodeTemplate(db.Model):
    """ Starter code for a Coding Question. """
    __tablename__ = 'code_templates'
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False, index=True)
    language = db.Column(db.String(50), nullable=False, index=True) # e.g., python, java
    template_code = db.Column(db.Text, nullable=True)
    question = db.relationship('Question', back_populates='code_templates')
    def __repr__(self) -> str: return f'<CodeTemplate {self.id}: {self.language} for Q{self.question_id}>'


class TestCase(db.Model):
    """ Test case for a Coding Question. """
    __tablename__ = 'test_cases'
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False, index=True)
    input_data = db.Column(db.Text, nullable=True)
    expected_output = db.Column(db.Text, nullable=False)
    is_hidden = db.Column(db.Boolean, default=False, nullable=False)
    points = db.Column(db.Float, default=1.0, nullable=False) # Allow float for partial points per test case
    description = db.Column(db.Text, nullable=True)
    time_limit_ms = db.Column(db.Integer, nullable=True, doc="Optional time limit in milliseconds for this test case")
    memory_limit_kb = db.Column(db.Integer, nullable=True, doc="Optional memory limit in kilobytes for this test case")
    question = db.relationship('Question', back_populates='test_cases')
    def __repr__(self) -> str: visibility = "Hidden" if self.is_hidden else "Visible"; return f'<TestCase {self.id} for Q{self.question_id} ({visibility} - {self.points}pts)>'


class Quiz(db.Model):
    """ A collection of questions presented as a test or assessment. """
    __tablename__ = 'quizzes'
    id = db.Column(db.Integer, primary_key=True)

    # --- Ownership & Visibility ---
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=True, index=True, doc="FK -> Owning Organization")
    creator_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True, doc="FK -> User Profile ID of creator")
    is_public = db.Column(db.Boolean, default=False, nullable=False, index=True, doc="Accessible to any logged-in user?")

    # --- Content & Settings ---
    title = db.Column(db.String(150), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    start_time = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    end_time = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    duration_minutes = db.Column(db.Integer, nullable=False) # 0 or negative might mean unlimited
    status = db.Column(db.Enum(QuizStatus), default=QuizStatus.DRAFT, nullable=False, index=True)
    max_attempts = db.Column(db.Integer, default=1, nullable=False) # 0 for unlimited
    selection_strategy = db.Column(db.Enum(QuestionSelectionStrategy), nullable=False, default=QuestionSelectionStrategy.FIXED)
    num_questions_to_pool = db.Column(db.Integer, nullable=True) # Required if strategy is RANDOM
    shuffle_questions = db.Column(db.Boolean, default=False, nullable=False)
    shuffle_options = db.Column(db.Boolean, default=False, nullable=False) # Usually applied per-question during rendering
    show_results_immediately = db.Column(db.Boolean, default=True, nullable=False)
    # Added setting to control visibility of correct answers/explanations after attempt
    results_visibility_config = db.Column(db.JSON, nullable=True, doc="JSON detailing when/what results are visible (e.g., {'show_correct': true, 'show_explanation': true, 'after_submit': true, 'after_end_time': false})")
    allow_navigation = db.Column(db.Boolean, default=True, nullable=False) # Allow moving between questions?

    # --- Proctoring ---
    proctoring_enabled = db.Column(db.Boolean, default=False, nullable=False)
    proctoring_config = db.Column(db.JSON, nullable=True, doc="e.g., {'webcam': true, 'mic': false, 'screen': true, 'tab_switch_limit': 5}")

    # --- Timestamps ---
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    published_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # --- Relationships ---
    organization = db.relationship('Organization', back_populates='created_quizzes', foreign_keys=[organization_id])
    creator = db.relationship('User', back_populates='created_quizzes', foreign_keys=[creator_user_id]) # Links to User profile

    questions = db.relationship('Question', secondary=quiz_questions, back_populates='quizzes', lazy='dynamic', order_by='Question.id')
    assigned_students = db.relationship('User', secondary=quiz_assignments, primaryjoin=(id == quiz_assignments.c.quiz_id), back_populates='assigned_quizzes', lazy='dynamic')
    attempts = db.relationship('QuizAttempt', back_populates='quiz', lazy='dynamic', foreign_keys='QuizAttempt.quiz_id', cascade="all, delete-orphan", passive_deletes=True)
    certificates = db.relationship('Certificate', back_populates='quiz', lazy='dynamic', foreign_keys='Certificate.quiz_id')
    assignments = db.relationship('QuizAssignment', back_populates='quiz', lazy='dynamic', foreign_keys='QuizAssignment.quiz_id', cascade="all, delete-orphan", passive_deletes=True) # Relationship to the assignment records

    def __repr__(self) -> str:
        creator_info = "Unknown"
        if self.organization: creator_info = f"Org: {self.organization.name}"
        elif self.creator and self.creator.credentials: creator_info = f"User: {self.creator.credentials.username}"
        status = self.status.name if self.status else "N/A"
        return f'<Quiz {self.id}: "{self.title}" ({status}) By:({creator_info})>'


class QuizAttempt(db.Model):
    """ A single user's attempt at taking a quiz. """
    __tablename__ = 'quiz_attempts'
    id = db.Column(db.Integer, primary_key=True)

    # --- Core Links ---
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True, doc="FK -> User Profile ID")

    # --- Timing ---
    start_time = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    submit_time = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    deadline = db.Column(db.DateTime(timezone=True), nullable=True, index=True) # Auto-calculated on start

    # --- Results ---
    score = db.Column(db.Float, nullable=True)
    max_score_possible = db.Column(db.Float, nullable=True)
    status = db.Column(db.Enum(QuizAttemptStatus), default=QuizAttemptStatus.STARTED, nullable=False, index=True)
    grading_completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # --- Proctoring/Integrity ---
    cheating_flags_json = db.Column(db.Text, nullable=True, doc="JSON object storing flags: {'tab_switches': 3, 'copy_paste': true}")
    proctoring_violations = db.Column(db.Integer, default=0, nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)

    # --- Question Handling ---
    presented_question_ids_json = db.Column(db.Text, default='[]', nullable=False)

    # --- Relationships ---
    quiz = db.relationship('Quiz', back_populates='attempts', foreign_keys=[quiz_id])
    user = db.relationship('User', back_populates='quiz_attempts', foreign_keys=[user_id]) # Links to User profile
    answers = db.relationship('StudentAnswer', back_populates='attempt', cascade="all, delete-orphan", passive_deletes=True, lazy='dynamic', foreign_keys='StudentAnswer.attempt_id')
    certificate = db.relationship('Certificate', back_populates='attempt', uselist=False, cascade="all, delete-orphan", passive_deletes=True)
    cheating_logs = db.relationship('CheatingLog', back_populates='attempt', lazy='dynamic', cascade="all, delete-orphan", passive_deletes=True, foreign_keys='CheatingLog.attempt_id')

    def set_presented_questions(self, question_ids: List[int]) -> None:
        self.presented_question_ids_json = json.dumps(sorted(list(set(question_ids))))

    def get_presented_questions(self) -> List[int]:
        try:
            ids = json.loads(self.presented_question_ids_json or '[]')
            return [int(id_val) for id_val in ids if isinstance(id_val, (int, str)) and str(id_val).isdigit()]
        except: return []

    def __repr__(self) -> str:
        username = self.user.credentials.username if self.user and self.user.credentials else "N/A"
        return f'<QuizAttempt ID:{self.id} by User:{username} (PID:{self.user_id}) for Quiz:{self.quiz_id} ({self.status.name if self.status else "N/A"})>'


class StudentAnswer(db.Model):
    """ A user's answer to a specific question within an attempt. """
    __tablename__ = 'student_answers'
    id = db.Column(db.Integer, primary_key=True)

    # --- Core Links ---
    attempt_id = db.Column(db.Integer, db.ForeignKey('quiz_attempts.id', ondelete='CASCADE'), nullable=False, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False, index=True)

    # --- Answer Content ---
    selected_option_id = db.Column(db.Integer, db.ForeignKey('question_options.id', ondelete='SET NULL'), nullable=True, index=True)
    answer_text = db.Column(db.Text, nullable=True)
    submitted_code = db.Column(db.Text, nullable=True)
    code_language = db.Column(db.String(50), nullable=True)

    # --- Grading & Feedback ---
    is_correct = db.Column(db.Boolean, nullable=True, index=True)
    points_awarded = db.Column(db.Float, default=0, nullable=True)
    feedback = db.Column(db.Text, nullable=True)
    grading_status = db.Column(db.Enum(GradingStatus), default=GradingStatus.PENDING, nullable=False, index=True)
    # Changed FK target to users.id
    graded_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True, doc="FK -> User Profile ID of grader")
    graded_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # --- Metadata ---
    answered_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    time_spent_seconds = db.Column(db.Integer, nullable=True)
    execution_result = db.Column(db.JSON, nullable=True, doc="JSON: {stdout, stderr, error, time_ms, memory_kb, passed_tests, total_tests}")

    # --- Relationships ---
    attempt = db.relationship('QuizAttempt', back_populates='answers', foreign_keys=[attempt_id])
    question = db.relationship('Question', back_populates='student_answers', foreign_keys=[question_id])
    selected_option = db.relationship('QuestionOption', foreign_keys=[selected_option_id])
    grader = db.relationship('User', back_populates='graded_answers', foreign_keys=[graded_by_user_id]) # Links to User profile

    def __repr__(self) -> str:
        grade_info = f"Correct: {self.is_correct}" if self.is_correct is not None else self.grading_status.name
        return f'<StudentAnswer {self.id} for Q{self.question_id} in Attempt {self.attempt_id} ({grade_info})>'


class CheatingLog(db.Model):
    """ Log entry for a suspected cheating event. """
    __tablename__ = 'cheating_logs'
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('quiz_attempts.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True, doc="FK -> User Profile ID") # Direct link useful for queries
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    event_type = db.Column(db.String(50), nullable=False, index=True)
    details = db.Column(db.Text, nullable=True)
    severity = db.Column(db.String(20), nullable=True) # Consider Enum

    # --- Relationships ---
    attempt = db.relationship('QuizAttempt', back_populates='cheating_logs', foreign_keys=[attempt_id])
    user = db.relationship('User', back_populates='cheating_logs', foreign_keys=[user_id]) # Links to User profile

    def __repr__(self) -> str:
        return f'<CheatingLog {self.id} for Attempt {self.attempt_id} (UserPID:{self.user_id}) ({self.event_type})>'


class Badge(db.Model):
    """ Gamification achievement badge. """
    __tablename__ = 'badges'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    icon_url = db.Column(db.String(512), nullable=True)
    criteria_text = db.Column(db.Text, nullable=True) # Human-readable criteria
    criteria_config = db.Column(db.JSON, nullable=True) # Machine-readable criteria for automation
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    users = db.relationship('User', secondary=user_badges, back_populates='badges', lazy='dynamic') # Links User profiles
    def __repr__(self) -> str: return f'<Badge {self.id}: {self.name}>'


class Certificate(db.Model):
    """ Verifiable certificate awarded for quiz completion. """
    __tablename__ = 'certificates'
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('quiz_attempts.id', ondelete='CASCADE'), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True, doc="FK -> User Profile ID")
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id', ondelete='CASCADE'), nullable=False, index=True)
    generated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    unique_code = db.Column(db.String(100), unique=True, nullable=False, index=True)
    # Snapshot data
    user_display_name = db.Column(db.String(100))
    user_email = db.Column(db.String(120))
    quiz_title = db.Column(db.String(150))
    final_score = db.Column(db.Float)
    issued_by_name = db.Column(db.String(150), default="CodeQuizHub")
    pdf_url = db.Column(db.String(512), nullable=True)

    # --- Relationships ---
    attempt = db.relationship('QuizAttempt', back_populates='certificate', foreign_keys=[attempt_id])
    user = db.relationship('User', back_populates='certificates', foreign_keys=[user_id]) # Links to User profile
    quiz = db.relationship('Quiz', back_populates='certificates', foreign_keys=[quiz_id])

    def __repr__(self) -> str: return f'<Certificate {self.id} ({self.unique_code}) for UserPID:{self.user_id}, Quiz:{self.quiz_id}>'


class Notification(db.Model):
    """ In-app notification for users. """
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True, doc="FK -> User Profile ID")
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    read_at = db.Column(db.DateTime(timezone=True), nullable=True)
    notification_type = db.Column(db.String(50), nullable=True, index=True) # Consider Enum
    # Generic Linking - store type and ID of related object
    related_object_type = db.Column(db.String(50), nullable=True, index=True)
    related_object_id = db.Column(db.Integer, nullable=True, index=True)
    link_url = db.Column(db.String(512), nullable=True) # Direct navigation URL
    user = db.relationship('User', back_populates='notifications', foreign_keys=[user_id]) # Links to User profile
    def __repr__(self) -> str: read_status = "Read" if self.is_read else "Unread"; return f'<Notification {self.id} for UserPID:{self.user_id} ({read_status}) Type:{self.notification_type}>'


class AuditLog(db.Model):
    """ Record of significant actions, primarily by Admins. """
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    admin_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True, doc="FK -> Admin's User Profile ID (Nullable if system action or user deleted)")
    action = db.Column(db.String(255), nullable=False, index=True)
    target_type = db.Column(db.String(50), nullable=True, index=True)
    target_id = db.Column(db.Integer, nullable=True, index=True)
    details = db.Column(db.Text, nullable=True) # Can store JSON diffs or context
    ip_address = db.Column(db.String(45), nullable=True)
    admin_user = db.relationship('User', back_populates='audit_logs_created', foreign_keys=[admin_user_id]) # Links to User profile
    def __repr__(self) -> str: target_info = f" ({self.target_type} ID:{self.target_id})" if self.target_type and self.target_id else ""; return f'<AuditLog {self.id} by AdminPID:{self.admin_user_id} @ {self.timestamp} - Action: {self.action}{target_info}>'


# --- New Table: Organization Invitations ---
# Handles inviting users (teachers, students) to join an organization.

class OrganizationInvitation(db.Model):
    """ Records invitations sent to users to join an organization. """
    __tablename__ = 'organization_invitations'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True)
    # Email is used because the user might not exist yet
    invitee_email = db.Column(db.String(120), nullable=False, index=True)
    # Store the role the user is being invited *as*
    invited_as_role = db.Column(db.Enum(UserRole), nullable=False, default=UserRole.STUDENT)
    invitation_token = db.Column(db.String(100), unique=True, nullable=False, index=True, doc="Secure token for the invitation link")
    status = db.Column(db.Enum(InvitationStatus), default=InvitationStatus.PENDING, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc) + timedelta(days=7)) # Example: 7-day expiry
    # Who sent the invite? (Org Admin or Teacher)
    inviter_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True, doc="User profile ID of the inviter")
    # When accepted, link to the actual user profile created/linked
    accepted_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True, doc="User profile ID of the user who accepted")
    accepted_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Relationships
    organization = db.relationship('Organization', back_populates='invitations', foreign_keys=[organization_id])
    # Link to the user profile that sent the invitation
    inviter = db.relationship('User', back_populates='invitations_sent', foreign_keys=[inviter_user_id])
    # Link to the user profile that accepted (use email to find potential existing user first)
    # Relationship for accepted_by_user_id is less direct, often handled in logic
    # invitee = db.relationship('User', foreign_keys=[accepted_by_user_id]) # Can add if needed

    # Relationship to find User via email (handled in application logic or a complex primaryjoin)
    invitee = db.relationship('User', back_populates='invitations_received', foreign_keys='OrganizationInvitation.invitee_email', primaryjoin='foreign(OrganizationInvitation.invitee_email) == User.email', viewonly=True)


    def __repr__(self) -> str:
        status = self.status.name if self.status else "N/A"
        return f'<OrgInvitation {self.id} for {self.invitee_email} to OrgID:{self.organization_id} ({status})>'


# --- New Model Wrapper for quiz_assignments Association Object ---
# Allows adding more attributes to the assignment itself (like assigned_by)

class QuizAssignment(db.Model):
    """ Association object for Quiz-to-Student assignments, allowing extra fields. """
    __tablename__ = 'quiz_assignments' # Reuse the association table name

    # Composite primary key from the association table definition
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id', ondelete='CASCADE'), primary_key=True, index=True)
    student_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True, index=True, doc="FK -> User profile ID of the assigned Student")

    # Additional fields compared to the simple association table
    assigned_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    assigned_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True, doc="FK -> User profile ID of the Teacher/Admin who assigned")
    due_date = db.Column(db.DateTime(timezone=True), nullable=True, index=True, doc="Optional due date for the assignment")

    # --- Relationships ---
    # Many-to-One back to Quiz
    quiz = db.relationship('Quiz', back_populates='assignments')
    # Many-to-One back to Student User profile
    student = db.relationship('User', foreign_keys=[student_user_id]) # No backref needed here as User.assigned_quizzes covers it
    # Many-to-One back to the assigner User profile
    assigner = db.relationship('User', back_populates='assignments_created', foreign_keys=[assigned_by_user_id])

    def __repr__(self):
        return f'<QuizAssignment Quiz:{self.quiz_id} to Student:{self.student_user_id} by User:{self.assigned_by_user_id}>'


# --- End of models.py ---