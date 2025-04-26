# models.py - Complete database models for CodeQuizHub with improvements and comments
# ===============================================================================
# This file defines the SQLAlchemy database models for the CodeQuizHub application.
# It includes user roles, organizations, quizzes, questions, answers, gamification
# elements, security logging, and relationships between these entities.
# ===============================================================================

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime
import enum
import json # For storing list of presented question IDs or other JSON data

# Assume 'db' is initialized in your Flask app
# Example:
# from flask_sqlalchemy import SQLAlchemy
# db = SQLAlchemy()
# OR if using Flask application factory pattern:
# from . import db
from . import db # Make sure db is imported correctly based on your project structure

# --- Enums ---
# Using Enums improves data integrity and readability for fixed sets of values.

class UserRole(enum.Enum):
    """ Defines the possible roles a user can have within the platform. """
    ADMIN = 'Admin'                 # Super user with full control
    ORGANIZATION = 'Organization'   # User representing/managing an organization
    STUDENT = 'Student'             # User belonging to an organization, taking assigned quizzes
    USER = 'User'                   # Individual user, not tied to an organization (can use public/friend features)

class QuestionType(enum.Enum):
    """ Defines the types of questions supported in quizzes. """
    MCQ = 'Multiple Choice'
    FILL_IN_BLANKS = 'Fill in the Blanks'
    SHORT_ANSWER = 'Short Answer'
    CODING = 'Coding'

class QuestionSelectionStrategy(enum.Enum):
    """ Defines how questions are selected for a specific quiz instance. """
    FIXED = 'Fixed Set'             # All users taking the quiz get the exact same set of questions
    RANDOM = 'Random Pooling'       # Questions are randomly selected from a larger pool based on tags/difficulty

class OrgApprovalStatus(enum.Enum):
    """ Defines the status of an organization's registration request. """
    PENDING = 'pending'             # Organization registration is awaiting admin approval
    APPROVED = 'approved'           # Organization registration has been approved by an admin
    REJECTED = 'rejected'           # Organization registration has been rejected by an admin

class QuizStatus(enum.Enum):
    """ Defines the lifecycle status of a quiz. """
    DRAFT = 'Draft'                 # Quiz is being created/edited, not yet available
    PUBLISHED = 'Published'         # Quiz is ready to be taken or assigned
    ACTIVE = 'Active'               # Quiz is currently running (optional, can be derived from start/end times)
    ARCHIVED = 'Archived'           # Quiz is no longer active but kept for historical records

class QuizAttemptStatus(enum.Enum):
    """ Defines the status of a user's attempt at taking a quiz. """
    STARTED = 'Started'             # User has begun the quiz attempt
    SUBMITTED = 'Submitted'         # User has finished and submitted the quiz
    GRADED = 'Graded'               # The submitted attempt has been fully graded (auto or manual)
    TIMED_OUT = 'Timed Out'         # The quiz attempt was automatically submitted due to the time limit expiring

class GradingStatus(enum.Enum):
    """ Defines the grading status for an individual answer within a quiz attempt. """
    PENDING = 'Pending'             # Answer has not yet been graded (relevant for manual/AI grading)
    GRADED = 'Graded'               # Answer has been graded
    ERROR = 'Error'                 # An error occurred during automatic grading

# --- Association Tables ---
# These tables manage many-to-many relationships between main models.

# Links Quizzes to the Questions they contain (for FIXED strategy or the pool for RANDOM)
quiz_questions = db.Table('quiz_questions',
    db.Column('quiz_id', db.Integer, db.ForeignKey('quizzes.id'), primary_key=True, doc="Foreign key to the Quiz"),
    db.Column('question_id', db.Integer, db.ForeignKey('questions.id'), primary_key=True, doc="Foreign key to the Question")
)

# Links Questions to descriptive Tags (e.g., 'DSA', 'Python', 'Easy')
question_tags = db.Table('question_tags',
    db.Column('question_id', db.Integer, db.ForeignKey('questions.id'), primary_key=True, doc="Foreign key to the Question"),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id'), primary_key=True, doc="Foreign key to the Tag")
)

# Links Quizzes to the Students (Users) who are assigned to take them (primarily for Org quizzes)
quiz_assignments = db.Table('quiz_assignments',
    db.Column('quiz_id', db.Integer, db.ForeignKey('quizzes.id'), primary_key=True, doc="Foreign key to the assigned Quiz"),
    db.Column('student_id', db.Integer, db.ForeignKey('users.id'), primary_key=True, doc="Foreign key to the assigned Student (User)"),
    db.Column('assigned_at', db.DateTime, default=datetime.utcnow, doc="Timestamp when the quiz was assigned")
)

# Links Users to the Badges they have earned (Gamification)
user_badges = db.Table('user_badges',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True, doc="Foreign key to the User who earned the badge"),
    db.Column('badge_id', db.Integer, db.ForeignKey('badges.id'), primary_key=True, doc="Foreign key to the Badge earned"),
    db.Column('earned_at', db.DateTime, default=datetime.utcnow, doc="Timestamp when the badge was earned")
)

# Links Users to other Users representing friendships (Self-referential Many-to-Many)
friendships = db.Table('friendships',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True, doc="Foreign key to the User initiating the friendship"),
    db.Column('friend_id', db.Integer, db.ForeignKey('users.id'), primary_key=True, doc="Foreign key to the User being added as a friend"),
    db.Column('established_at', db.DateTime, default=datetime.utcnow, doc="Timestamp when the friendship was established"),
    # Optional: Add a 'status' column here (e.g., 'pending', 'accepted') if friend requests need approval
    # db.Column('status', db.String(20), default='accepted', nullable=False)
)


# --- Main Models ---

class User(db.Model, UserMixin):
    """ Represents a user in the system. Can be an Admin, Org rep, Student, or Individual User. """
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True, doc="Unique identifier for the user")
    username = db.Column(db.String(80), unique=True, nullable=False, doc="Unique username for login")
    email = db.Column(db.String(120), unique=True, nullable=False, doc="Unique email address for communication and potentially login/recovery")
    password_hash = db.Column(db.String(256), nullable=False, doc="Hashed password for secure storage")
    role = db.Column(db.Enum(UserRole), nullable=False, default=UserRole.USER, doc="Role defining user's permissions and capabilities (default is Individual User)")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, doc="Timestamp of user account creation")
    is_active = db.Column(db.Boolean, default=True, doc="Flag indicating if the user account is active (can be used for disabling accounts)")
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True, doc="Foreign key linking student/org roles to their organization (null for Admin/Individual Users)")
    student_code = db.Column(db.String(50), nullable=True, doc="Optional unique identifier for a student within an organization (e.g., roll number)")
    enrollment_date = db.Column(db.DateTime, nullable=True, doc="Date when a student was enrolled in an organization")

    # Gamification fields
    gamification_points = db.Column(db.Integer, default=0, doc="Points accumulated by the user through activities (taking quizzes, achievements)")
    gamification_level = db.Column(db.Integer, default=1, doc="Level achieved by the user based on points")

    # Relationships
    # If the user is part of an organization (Student or Org role managing it)
    organization = db.relationship('Organization', back_populates='members', foreign_keys=[organization_id], doc="Link to the Organization this user belongs to")
    # Quiz attempts made by this user
    quiz_attempts = db.relationship('QuizAttempt', back_populates='user', lazy='dynamic', doc="Attempts made by this user on various quizzes")
    # Quizzes specifically assigned to this user (Student role)
    assigned_quizzes = db.relationship('Quiz', secondary=quiz_assignments, back_populates='assigned_students', lazy='dynamic', doc="Quizzes assigned directly to this student")
    # If this user is an Organization role, this links to the Org they manage
    managed_organization = db.relationship('Organization', back_populates='admin_user', foreign_keys='Organization.admin_user_id', uselist=False, doc="The Organization managed by this user (if role is Organization)")
    # Badges earned by this user
    badges = db.relationship('Badge', secondary=user_badges, back_populates='users', lazy='dynamic', doc="Badges awarded to this user")
    # Notifications intended for this user
    notifications = db.relationship('Notification', back_populates='user', lazy='dynamic', cascade="all, delete-orphan", doc="Notifications sent to this user")
    # Friendships established by this user (symmetric relationship managed via friendships table)
    # 'friends' gives users who have added this user as a friend.
    # 'added_friends' gives users this user has added as friends.
    # Use `user.friends` to get friends who added this user, and `user.friend_of` to get users this user added.
    # Application logic might be needed to present a unified "friends list".
    friends = db.relationship(
        'User', secondary=friendships,
        primaryjoin=(friendships.c.friend_id == id),
        secondaryjoin=(friendships.c.user_id == id),
        backref=db.backref('friend_of', lazy='dynamic'), # Allows access via user.friend_of
        lazy='dynamic',
        doc="Relationship defining friends (users who added this user)"
    )
    # Quizzes created by this user (if they are an Individual User creating public/friend quizzes)
    created_quizzes = db.relationship('Quiz', back_populates='creator', foreign_keys='Quiz.creator_user_id', lazy='dynamic')
    # Audit logs generated by this user (if they are an Admin)
    audit_logs_created = db.relationship('AuditLog', back_populates='admin_user', foreign_keys='AuditLog.admin_user_id', lazy='dynamic')


    def set_password(self, password):
        """ Hashes the provided password and stores it. """
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """ Checks if the provided password matches the stored hash. """
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        """ String representation for User object, useful for debugging. """
        org_info = f", OrgID: {self.organization_id}" if self.organization_id else ""
        return f'<User {self.id}: {self.username} ({self.role.name}){org_info}>'


class Organization(db.Model):
    """ Represents an educational institution or company using the platform. """
    __tablename__ = 'organizations'
    id = db.Column(db.Integer, primary_key=True, doc="Unique identifier for the organization")
    name = db.Column(db.String(100), unique=True, nullable=False, doc="Name of the organization")
    description = db.Column(db.Text, nullable=True, doc="Optional description of the organization")
    approval_status = db.Column(db.Enum(OrgApprovalStatus), default=OrgApprovalStatus.PENDING, nullable=False, doc="Status of the organization's registration request")
    requested_at = db.Column(db.DateTime, default=datetime.utcnow, doc="Timestamp when the organization registration was requested")
    approved_at = db.Column(db.DateTime, nullable=True, doc="Timestamp when the registration was approved by an admin")
    approved_by_admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, doc="Foreign key to the Admin User who approved the registration")
    admin_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=True, doc="Foreign key to the User (role=Organization) who manages this organization account")

    # Relationships
    # The User who manages this organization's account on the platform
    admin_user = db.relationship('User', back_populates='managed_organization', foreign_keys=[admin_user_id], doc="The primary user managing this organization")
    # Members (Students and potentially other Org users) belonging to this organization
    members = db.relationship('User', back_populates='organization', foreign_keys=[User.organization_id], lazy='dynamic', doc="Users (typically Students) belonging to this organization")
    # Quizzes created by this organization
    created_quizzes = db.relationship('Quiz', back_populates='organization', lazy='dynamic', foreign_keys='Quiz.organization_id', doc="Quizzes created and owned by this organization")
    # Questions created and owned by this organization
    questions = db.relationship('Question', back_populates='organization', lazy='dynamic', doc="Question bank owned by this organization")
    # Admin user who approved this org (can be null if system generated or pre-approved)
    approving_admin = db.relationship('User', foreign_keys=[approved_by_admin_id], doc="The Admin user who approved this organization")

    def __repr__(self):
        """ String representation for Organization object. """
        return f'<Organization {self.id}: {self.name} ({self.approval_status.name})>'


class Tag(db.Model):
    """ Represents a tag that can be applied to questions for categorization (e.g., topic, difficulty). """
    __tablename__ = 'tags'
    id = db.Column(db.Integer, primary_key=True, doc="Unique identifier for the tag")
    name = db.Column(db.String(50), unique=True, nullable=False, doc="The name of the tag (e.g., 'Data Structures', 'Beginner', 'Python')")
    # Relationship back to questions associated with this tag
    questions = db.relationship('Question', secondary=question_tags, back_populates='tags', lazy='dynamic', doc="Questions associated with this tag")

    def __repr__(self):
        """ String representation for Tag object. """
        return f'<Tag {self.id}: {self.name}>'


class Question(db.Model):
    """ Represents a single question within the system, of various types. """
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True, doc="Unique identifier for the question")
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True, doc="Foreign key to the Organization that owns this question (null if public/admin created)")
    creator_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, doc="Foreign key to the User who created this question (if not owned by an org)") # TODO: Consider adding this if needed
    question_type = db.Column(db.Enum(QuestionType), nullable=False, doc="The type of the question (e.g., MCQ, Coding)")
    question_text = db.Column(db.Text, nullable=False, doc="The main text or prompt of the question")
    difficulty = db.Column(db.String(20), nullable=True, doc="Optional difficulty level (e.g., 'Easy', 'Medium', 'Hard')")
    points = db.Column(db.Integer, default=1, nullable=False, doc="Default points awarded for answering this question correctly")
    correct_answer_text = db.Column(db.Text, nullable=True, doc="Correct answer text (for Fill-in-blanks, Short Answer)")
    explanation = db.Column(db.Text, nullable=True, doc="Optional explanation shown to users after attempting the question")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, doc="Timestamp when the question was created")
    is_ai_generated = db.Column(db.Boolean, default=False, doc="Flag indicating if this question was generated by AI")
    ai_prompt = db.Column(db.Text, nullable=True, doc="The prompt used to generate this question via AI (if applicable)")

    # Relationships
    # Organization that owns this question
    organization = db.relationship('Organization', back_populates='questions', doc="The organization owning this question")
    # Options for MCQ questions (one-to-many)
    options = db.relationship('QuestionOption', back_populates='question', cascade='all, delete-orphan', lazy='dynamic', doc="Options associated with this question (if MCQ)")
    # Code templates for coding questions (one-to-many)
    code_templates = db.relationship('CodeTemplate', back_populates='question', cascade='all, delete-orphan', lazy='dynamic', doc="Starter code templates for different languages (if Coding)")
    # Test cases for coding questions (one-to-many)
    test_cases = db.relationship('TestCase', back_populates='question', cascade='all, delete-orphan', lazy='dynamic', doc="Test cases used to evaluate coding question submissions")
    # Tags associated with this question (many-to-many)
    tags = db.relationship('Tag', secondary=question_tags, back_populates='questions', lazy='dynamic', doc="Tags categorizing this question")
    # Quizzes that include this question (many-to-many)
    quizzes = db.relationship('Quiz', secondary=quiz_questions, back_populates='questions', lazy='dynamic', doc="Quizzes that contain this question")
    # Answers submitted by students for this question across all attempts
    student_answers = db.relationship('StudentAnswer', back_populates='question', lazy='dynamic', doc="All student answers submitted for this question")

    def __repr__(self):
        """ String representation for Question object. """
        org_info = f"Org: {self.organization_id}" if self.organization_id else "Public"
        return f'<Question {self.id} ({self.question_type.name}) Points: {self.points} ({org_info})>'


class QuestionOption(db.Model):
    """ Represents a single option for a Multiple Choice Question (MCQ). """
    __tablename__ = 'question_options'
    id = db.Column(db.Integer, primary_key=True, doc="Unique identifier for the option")
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False, doc="Foreign key to the Question this option belongs to")
    option_text = db.Column(db.Text, nullable=False, doc="The text content of the option")
    is_correct = db.Column(db.Boolean, default=False, nullable=False, doc="Flag indicating if this is the correct option for the MCQ")
    # Relationship back to the parent question
    question = db.relationship('Question', back_populates='options', doc="The Question this option belongs to")

    def __repr__(self):
        """ String representation for QuestionOption object. """
        return f'<Option {self.id} for Q{self.question_id} Correct:{self.is_correct}>'


class CodeTemplate(db.Model):
    """ Represents starter code template for a specific language for a Coding Question. """
    __tablename__ = 'code_templates'
    id = db.Column(db.Integer, primary_key=True, doc="Unique identifier for the code template")
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False, doc="Foreign key to the Coding Question this template is for")
    language = db.Column(db.String(50), nullable=False, doc="The programming language of the template (e.g., 'Python', 'Java', 'C++')")
    template_code = db.Column(db.Text, nullable=True, doc="The starter code provided to the user")
    # Relationship back to the parent question
    question = db.relationship('Question', back_populates='code_templates', doc="The Question this template belongs to")

    def __repr__(self):
        """ String representation for CodeTemplate object. """
        return f'<CodeTemplate {self.id}: {self.language} for Q{self.question_id}>'


class TestCase(db.Model):
    """ Represents a test case used to evaluate a submission for a Coding Question. """
    __tablename__ = 'test_cases'
    id = db.Column(db.Integer, primary_key=True, doc="Unique identifier for the test case")
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False, doc="Foreign key to the Coding Question this test case belongs to")
    input_data = db.Column(db.Text, nullable=True, doc="Input data to be fed to the user's code (stdin)")
    expected_output = db.Column(db.Text, nullable=False, doc="The expected output (stdout) for the given input")
    is_hidden = db.Column(db.Boolean, default=False, nullable=False, doc="Flag indicating if the input/output is hidden from the user during testing (used for final grading)")
    points = db.Column(db.Integer, default=1, doc="Points awarded if the user's code passes this test case")
    # Relationship back to the parent question
    question = db.relationship('Question', back_populates='test_cases', doc="The Question this test case belongs to")

    def __repr__(self):
        """ String representation for TestCase object. """
        visibility = "Hidden" if self.is_hidden else "Visible"
        return f'<TestCase {self.id} for Q{self.question_id} ({visibility} - {self.points}pts)>'


class Quiz(db.Model):
    """ Represents a quiz or coding competition event. """
    __tablename__ = 'quizzes'
    id = db.Column(db.Integer, primary_key=True, doc="Unique identifier for the quiz")
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True, doc="Foreign key to the Organization that created/owns this quiz (null if public, friend-based, or admin created)")
    creator_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, doc="Foreign key to the Individual User who created this quiz (if not org-owned)")
    title = db.Column(db.String(100), nullable=False, doc="The title of the quiz")
    description = db.Column(db.Text, nullable=True, doc="Optional description or instructions for the quiz")
    start_time = db.Column(db.DateTime, nullable=True, doc="Optional start time when the quiz becomes available")
    end_time = db.Column(db.DateTime, nullable=True, doc="Optional end time after which the quiz cannot be started/submitted")
    duration_minutes = db.Column(db.Integer, nullable=False, doc="The maximum time allowed in minutes to complete the quiz once started")
    is_public = db.Column(db.Boolean, default=False, nullable=False, doc="Flag indicating if the quiz is available to all logged-in users (Individual Users)")
    selection_strategy = db.Column(db.Enum(QuestionSelectionStrategy), nullable=False, default=QuestionSelectionStrategy.FIXED, doc="Method used to select questions for attempts (Fixed set or Random pool)")
    num_questions_to_pool = db.Column(db.Integer, nullable=True, doc="Number of questions to randomly select if strategy is RANDOM")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, doc="Timestamp when the quiz was created")
    status = db.Column(db.Enum(QuizStatus), default=QuizStatus.DRAFT, nullable=False, doc="Current lifecycle status of the quiz (Draft, Published, Archived)")
    max_attempts = db.Column(db.Integer, default=1, doc="Maximum number of times a user can attempt this quiz (usually 1 for org/formal quizzes)")
    proctoring_enabled = db.Column(db.Boolean, default=False, doc="Flag indicating if proctoring features (camera, mic, screen sharing - with consent) are enabled for this quiz")
    # Note: Actual proctoring data (streams/recordings) would likely be stored externally (e.g., S3), not directly in this DB. This flag indicates if the feature *should* be active.

    # Relationships
    # The organization that created this quiz
    organization = db.relationship('Organization', back_populates='created_quizzes', foreign_keys=[organization_id], doc="The Organization that created this quiz")
    # The individual user who created this quiz (if applicable)
    creator = db.relationship('User', back_populates='created_quizzes', foreign_keys=[creator_user_id], doc="The Individual User who created this quiz")
    # The questions included in this quiz (either fixed set or the pool for random selection)
    questions = db.relationship('Question', secondary=quiz_questions, back_populates='quizzes', lazy='dynamic', doc="Questions associated with this quiz")
    # Students specifically assigned to take this quiz
    assigned_students = db.relationship('User', secondary=quiz_assignments, back_populates='assigned_quizzes', lazy='dynamic', doc="Students assigned to take this quiz")
    # All attempts made on this quiz by various users
    attempts = db.relationship('QuizAttempt', back_populates='quiz', lazy='dynamic', doc="All attempts made on this quiz")
    # Certificates generated for successful completions of this quiz
    certificates = db.relationship('Certificate', back_populates='quiz', lazy='dynamic') # Added backref

    def __repr__(self):
        """ String representation for Quiz object. """
        creator_info = ""
        if self.organization:
            creator_info = f"Org: {self.organization.name}"
        elif self.creator:
             creator_info = f"User: {self.creator.username}"
        else:
             creator_info = "Public/Admin"
        return f'<Quiz {self.id}: {self.title} ({self.status.name}) ({creator_info})>'


class QuizAttempt(db.Model):
    """ Represents a single attempt by a user to take a specific quiz. """
    __tablename__ = 'quiz_attempts'
    id = db.Column(db.Integer, primary_key=True, doc="Unique identifier for this quiz attempt")
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False, doc="Foreign key to the Quiz being attempted")
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, doc="Foreign key to the User making the attempt")
    start_time = db.Column(db.DateTime, default=datetime.utcnow, doc="Timestamp when the user started the attempt")
    submit_time = db.Column(db.DateTime, nullable=True, doc="Timestamp when the user submitted the attempt (or when it timed out)")
    score = db.Column(db.Float, nullable=True, doc="Final calculated score for this attempt (null until graded)")
    max_score_possible = db.Column(db.Float, nullable=True, doc="Maximum possible score for the specific set of questions presented in this attempt (useful for pooled quizzes)")
    status = db.Column(db.Enum(QuizAttemptStatus), default=QuizAttemptStatus.STARTED, nullable=False, doc="Current status of the quiz attempt")
    cheating_flags = db.Column(db.Integer, default=0, doc="Counter for detected cheating events (e.g., tab switching, copy-paste), application logic defines meaning")
    proctoring_violations = db.Column(db.Integer, default=0, doc="Counter for logged proctoring violations (e.g., person missing, multiple people detected)")
    presented_question_ids = db.Column(db.Text, nullable=True, doc="JSON encoded list of Question IDs presented to the user in this specific attempt (especially important for random pooling)")

    # Relationships
    # The quiz associated with this attempt
    quiz = db.relationship('Quiz', back_populates='attempts', doc="The Quiz being attempted")
    # The user who made this attempt
    user = db.relationship('User', back_populates='quiz_attempts', doc="The User who made this attempt")
    # All answers submitted by the user during this attempt
    answers = db.relationship('StudentAnswer', back_populates='attempt', cascade='all, delete-orphan', lazy='dynamic', doc="Answers submitted during this attempt")
    # Certificate generated for this attempt (if successful, one-to-one)
    certificate = db.relationship('Certificate', back_populates='attempt', uselist=False, cascade="all, delete-orphan", doc="Certificate awarded for this attempt (if any)")
    # Detailed logs of cheating/proctoring events detected during this attempt
    cheating_logs = db.relationship('CheatingLog', back_populates='attempt', lazy='dynamic', cascade="all, delete-orphan", doc="Logs related to cheating or proctoring events during this attempt")

    def set_presented_questions(self, question_ids: list):
        """ Helper method to store the list of presented question IDs as a JSON string. """
        if question_ids:
            self.presented_question_ids = json.dumps(sorted(list(set(question_ids)))) # Store sorted unique IDs
        else:
            self.presented_question_ids = None

    def get_presented_questions(self) -> list:
        """ Helper method to retrieve the list of presented question IDs from the JSON string. """
        if self.presented_question_ids:
            try:
                ids = json.loads(self.presented_question_ids)
                return ids if isinstance(ids, list) else []
            except json.JSONDecodeError:
                return [] # Return empty list if JSON is invalid
        return []

    def __repr__(self):
        """ String representation for QuizAttempt object. """
        score_info = f", Score: {self.score}" if self.score is not None else ""
        return f'<QuizAttempt ID:{self.id} by User:{self.user_id} for Quiz:{self.quiz_id} ({self.status.name}){score_info}>'


class StudentAnswer(db.Model):
    """ Represents a user's answer to a single question within a specific quiz attempt. """
    __tablename__ = 'student_answers'
    id = db.Column(db.Integer, primary_key=True, doc="Unique identifier for this specific answer")
    attempt_id = db.Column(db.Integer, db.ForeignKey('quiz_attempts.id'), nullable=False, doc="Foreign key to the Quiz Attempt this answer belongs to")
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False, doc="Foreign key to the Question being answered")
    selected_option_id = db.Column(db.Integer, db.ForeignKey('question_options.id'), nullable=True, doc="Foreign key to the Question Option selected by the user (for MCQs)")
    answer_text = db.Column(db.Text, nullable=True, doc="Text submitted by the user (for Fill-in-blanks, Short Answer)")
    submitted_code = db.Column(db.Text, nullable=True, doc="Code submitted by the user (for Coding questions)")
    is_correct = db.Column(db.Boolean, nullable=True, doc="Flag indicating if the answer was marked correct (null until graded)")
    points_awarded = db.Column(db.Float, default=0, nullable=True, doc="Points awarded for this specific answer (can be partial, null until graded)")
    time_spent_seconds = db.Column(db.Integer, nullable=True, doc="Optional: Time spent by the user on this specific question")
    feedback = db.Column(db.Text, nullable=True, doc="Feedback provided for this specific answer (manual or automated)")
    answered_at = db.Column(db.DateTime, default=datetime.utcnow, doc="Timestamp when this specific answer was submitted/saved")
    grading_status = db.Column(db.Enum(GradingStatus), default=GradingStatus.PENDING, nullable=False, doc="Status of the grading process for this answer")
    graded_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, doc="Foreign key to the User who manually graded this answer (if applicable)")

    # Relationships
    # The quiz attempt this answer is part of
    attempt = db.relationship('QuizAttempt', back_populates='answers', doc="The Quiz Attempt this answer belongs to")
    # The question being answered
    question = db.relationship('Question', back_populates='student_answers', doc="The Question being answered")
    # The MCQ option selected by the user (if applicable)
    selected_option = db.relationship('QuestionOption', doc="The MCQ option selected by the user")
    # The user who graded this answer (if manually graded)
    grader = db.relationship('User', foreign_keys=[graded_by_user_id], doc="The User who performed manual grading")

    def __repr__(self):
        """ String representation for StudentAnswer object. """
        grade_info = f"Correct: {self.is_correct}" if self.is_correct is not None else self.grading_status.name
        return f'<StudentAnswer {self.id} for Q{self.question_id} in Attempt {self.attempt_id} ({grade_info})>'


class CheatingLog(db.Model):
    """ Logs events related to potential cheating or proctoring violations during a quiz attempt. """
    __tablename__ = 'cheating_logs'
    id = db.Column(db.Integer, primary_key=True, doc="Unique identifier for the log entry")
    attempt_id = db.Column(db.Integer, db.ForeignKey('quiz_attempts.id'), nullable=False, doc="Foreign key to the Quiz Attempt during which the event occurred")
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, doc="Foreign key to the User associated with the event (redundant but useful for querying)")
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, doc="Timestamp when the event was logged")
    event_type = db.Column(db.String(50), nullable=False, doc="Type of event logged (e.g., 'TabSwitch', 'CopyPaste', 'FaceNotDetected', 'MultipleFaces')")
    details = db.Column(db.Text, nullable=True, doc="Additional details about the event (e.g., window title switched to, confidence score from AI detection)")

    # Relationships
    # The quiz attempt associated with this log
    attempt = db.relationship('QuizAttempt', back_populates='cheating_logs', doc="The Quiz Attempt related to this log")
    # The user associated with this log
    user = db.relationship('User', doc="The User related to this log") # Simple relationship for querying user info

    def __repr__(self):
        """ String representation for CheatingLog object. """
        return f'<CheatingLog {self.id} for Attempt {self.attempt_id} ({self.event_type}) at {self.timestamp}>'


class Badge(db.Model):
    """ Represents a gamification badge that users can earn for achievements. """
    __tablename__ = 'badges'
    id = db.Column(db.Integer, primary_key=True, doc="Unique identifier for the badge")
    name = db.Column(db.String(100), unique=True, nullable=False, doc="Name of the badge (e.g., 'Quiz Master', 'Speed Demon')")
    description = db.Column(db.Text, nullable=False, doc="Description explaining what the badge represents")
    icon_url = db.Column(db.String(255), nullable=True, doc="URL to an image/icon representing the badge")
    criteria = db.Column(db.Text, nullable=True, doc="Text describing the criteria for earning this badge")

    # Relationship back to users who have earned this badge
    users = db.relationship('User', secondary=user_badges, back_populates='badges', lazy='dynamic', doc="Users who have earned this badge")

    def __repr__(self):
        """ String representation for Badge object. """
        return f'<Badge {self.id}: {self.name}>'


class Certificate(db.Model):
    """ Represents a certificate generated upon successful completion of a quiz attempt. """
    __tablename__ = 'certificates'
    id = db.Column(db.Integer, primary_key=True, doc="Unique identifier for the certificate")
    attempt_id = db.Column(db.Integer, db.ForeignKey('quiz_attempts.id'), unique=True, nullable=False, doc="Foreign key linking to the specific Quiz Attempt this certificate is for")
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, doc="Foreign key to the User who earned the certificate")
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False, doc="Foreign key to the Quiz for which the certificate was earned")
    generated_at = db.Column(db.DateTime, default=datetime.utcnow, doc="Timestamp when the certificate was generated")
    unique_code = db.Column(db.String(100), unique=True, nullable=False, doc="Unique code for verification purposes")
    # Snapshot of key data at the time of generation
    user_name = db.Column(db.String(100), doc="User's name as it appears on the certificate")
    quiz_title = db.Column(db.String(100), doc="Quiz title as it appears on the certificate")
    final_score = db.Column(db.Float, doc="Final score achieved, as shown on the certificate")
    # pdf_url = db.Column(db.String(255), nullable=True) # Optional: If storing a link to a generated PDF file

    # Relationships
    # The specific quiz attempt that earned this certificate
    attempt = db.relationship('QuizAttempt', back_populates='certificate', doc="The Quiz Attempt that resulted in this certificate")
    # The user who earned the certificate
    user = db.relationship('User', doc="The User who earned this certificate") # Simple relationship
    # The quiz associated with the certificate
    quiz = db.relationship('Quiz', back_populates='certificates', doc="The Quiz for which this certificate was issued") # Simple relationship

    def __repr__(self):
        """ String representation for Certificate object. """
        return f'<Certificate {self.id} ({self.unique_code}) for User:{self.user_id}, Quiz:{self.quiz_id}>'


class Notification(db.Model):
    """ Represents a notification sent to a user within the platform. """
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True, doc="Unique identifier for the notification")
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, doc="Foreign key to the User who should receive this notification")
    message = db.Column(db.Text, nullable=False, doc="The content of the notification message")
    is_read = db.Column(db.Boolean, default=False, nullable=False, doc="Flag indicating if the user has read the notification")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, doc="Timestamp when the notification was created")
    # Optional fields to link the notification to a relevant object
    related_object_type = db.Column(db.String(50), nullable=True, doc="Type of the related object (e.g., 'Quiz', 'Badge', 'FriendRequest')")
    related_object_id = db.Column(db.Integer, nullable=True, doc="ID of the related object")
    link_url = db.Column(db.String(512), nullable=True, doc="Optional URL to navigate to when the notification is clicked")

    # Relationship back to the user
    user = db.relationship('User', back_populates='notifications', doc="The User this notification belongs to")

    def __repr__(self):
        """ String representation for Notification object. """
        read_status = "Read" if self.is_read else "Unread"
        return f'<Notification {self.id} for User:{self.user_id} ({read_status}) - {self.message[:30]}...>'


class AuditLog(db.Model):
    """ Logs significant actions performed by administrators for auditing purposes. """
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True, doc="Unique identifier for the audit log entry")
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, doc="Timestamp when the action occurred")
    admin_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, doc="Foreign key to the Admin User who performed the action")
    action = db.Column(db.String(255), nullable=False, doc="Description of the action performed (e.g., 'approve_organization', 'delete_user', 'update_quiz_status')")
    target_type = db.Column(db.String(50), nullable=True, doc="Type of the object affected by the action (e.g., 'Organization', 'User', 'Quiz')")
    target_id = db.Column(db.Integer, nullable=True, doc="ID of the object affected by the action")
    details = db.Column(db.Text, nullable=True, doc="Optional additional details, potentially JSON containing old/new values or context")

    # Relationship to the Admin user who performed the action
    admin_user = db.relationship('User', back_populates='audit_logs_created', foreign_keys=[admin_user_id], doc="The Admin User who performed the logged action")

    def __repr__(self):
        """ String representation for AuditLog object. """
        target_info = f" ({self.target_type} ID:{self.target_id})" if self.target_type else ""
        return f'<AuditLog {self.id} at {self.timestamp} by Admin:{self.admin_user_id} - Action: {self.action}{target_info}>'


# --- End of refined models.py ---