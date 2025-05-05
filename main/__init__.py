# /CodeQuizHub/main/__init__.py
from flask import Blueprint

# Create the Blueprint instance
main_bp = Blueprint('main', __name__)

# Import routes *after* the blueprint is defined to avoid circular imports
from . import routes