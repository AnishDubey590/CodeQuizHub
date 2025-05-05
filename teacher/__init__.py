# File: CodeQuizHub/teacher/__init__.py

from flask import Blueprint

# Define the blueprint FIRST
# (Ensure your actual variable name matches what's expected/imported elsewhere)
teacher_bp = Blueprint(
    'teacher',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/teacher/static' # Example: Ensure static path is unique if needed
)

# Import routes and forms LAST, after the blueprint object ('teacher_bp') is created
from . import routes, forms