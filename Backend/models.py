from app import db
from sqlalchemy.dialects.sqlite import JSON
from datetime import datetime

# Friendship association table
friendship_table = db.Table('friendships',
    db.Column('user_id', db.String(50), db.ForeignKey('individual_details.username')),
    db.Column('friend_id', db.String(50), db.ForeignKey('individual_details.username'))
)

class IndividualDetails(db.Model):
    __tablename__ = 'individual_details'
    username = db.Column(db.String(50), primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50))
    email = db.Column(db.String(200))
    credential = db.relationship('Credential', backref='individual', uselist=False)

    friends = db.relationship(
        'IndividualDetails',
        secondary=friendship_table,
        primaryjoin=username == friendship_table.c.user_id,
        secondaryjoin=username == friendship_table.c.friend_id,
        backref='friend_of'
    )

    def __init__(self, username, first_name, last_name=None, email=None):
        self.username = username
        self.first_name = first_name
        self.last_name = last_name
        self.email = email

class Credential(db.Model):
    __tablename__ = 'credentials'
    username = db.Column(db.String(50), db.ForeignKey('individual_details.username'), primary_key=True)
    password = db.Column(db.String(100), nullable=False)
    flag = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(10), nullable=False)

    def __init__(self, username, password, flag, status='active'):
        self.username = username
        self.password = password
        self.flag = flag
        self.status = status

class QuestionPool(db.Model):
    __tablename__ = 'question_pools'
    pool_id = db.Column(db.String(50), primary_key=True)
    topic = db.Column(db.String(100), nullable=False)
    level = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255))
    question_type = db.Column(db.String(50), nullable=False)

    def __init__(self, pool_id, topic, level, question_type, description=None):
        self.pool_id = pool_id
        self.topic = topic
        self.level = level
        self.question_type = question_type
        self.description = description

class MCQQuestion(db.Model):
    __tablename__ = 'mcq_questions'
    id = db.Column(db.Integer, primary_key=True)
    pool_id = db.Column(db.String(50), db.ForeignKey('question_pools.pool_id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    options = db.Column(JSON, nullable=False)
    correct_answer = db.Column(db.String(200), nullable=False)

    def __init__(self, pool_id, question_text, options, correct_answer):
        self.pool_id = pool_id
        self.question_text = question_text
        self.options = options
        self.correct_answer = correct_answer

class CodingQuestion(db.Model):
    __tablename__ = 'coding_questions'
    id = db.Column(db.Integer, primary_key=True)
    pool_id = db.Column(db.String(50), db.ForeignKey('question_pools.pool_id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    input_format = db.Column(db.Text)
    output_format = db.Column(db.Text)
    public_test_cases = db.Column(JSON, nullable=False)
    private_test_cases = db.Column(JSON, nullable=False)

    def __init__(self, pool_id, question_text, public_test_cases, private_test_cases, input_format=None, output_format=None):
        self.pool_id = pool_id
        self.question_text = question_text
        self.input_format = input_format
        self.output_format = output_format
        self.public_test_cases = public_test_cases
        self.private_test_cases = private_test_cases

class FIBQuestion(db.Model):
    __tablename__ = 'fib_questions'
    id = db.Column(db.Integer, primary_key=True)
    pool_id = db.Column(db.String(50), db.ForeignKey('question_pools.pool_id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    answer = db.Column(db.String(255), nullable=False)

    def __init__(self, pool_id, question_text, answer):
        self.pool_id = pool_id
        self.question_text = question_text
        self.answer = answer

class Quiz(db.Model):
    __tablename__ = 'quizzes'
    quiz_id = db.Column(db.String(50), primary_key=True)
    created_by = db.Column(db.String(50), db.ForeignKey('individual_details.username'), nullable=False)
    topic = db.Column(db.String(100))
    level = db.Column(db.String(50))
    question_type = db.Column(db.String(50))
    question_ids = db.Column(JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, quiz_id, created_by, topic, level, question_type, question_ids):
        self.quiz_id = quiz_id
        self.created_by = created_by
        self.topic = topic
        self.level = level
        self.question_type = question_type
        self.question_ids = question_ids

class QuizAttempt(db.Model):
    __tablename__ = 'quiz_attempts'
    attempt_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), db.ForeignKey('individual_details.username'))
    quiz_id = db.Column(db.String(50), db.ForeignKey('quizzes.quiz_id'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    score = db.Column(db.Float)

    def __init__(self, username, quiz_id, score, timestamp=None):
        self.username = username
        self.quiz_id = quiz_id
        self.score = score
        self.timestamp = timestamp or datetime.utcnow()
