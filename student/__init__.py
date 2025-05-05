# /your_app/student/__init__.py
from flask import Blueprint

student_bp = Blueprint('student', __name__)

# Import routes after blueprint definition
from . import routes