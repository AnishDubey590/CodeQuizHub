# /your_app/auth/__init__.py
from flask import Blueprint

auth_bp = Blueprint('auth', __name__)

# Import routes after blueprint definition to avoid circular imports
from . import routes
# /your_app/main/__init__.py
from flask import Blueprint

main_bp = Blueprint('main', __name__)

# Import routes after blueprint definition
from . import routes