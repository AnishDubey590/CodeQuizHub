# /your_app/user/__init__.py
from flask import Blueprint

user_bp = Blueprint('user', __name__)

# Import routes after blueprint definition
from . import routes