# File: CodeQuizHub/admin/__init__.py
from flask import Blueprint

admin_bp = Blueprint(
    'admin',
    __name__,
    template_folder='templates',
    # url_prefix='/admin' is usually set when registering the blueprint in the app factory,
    # but can also be set here. If it's in create_app(), no need for it here.
    # static_folder='static', # If you have admin-specific static files
    # static_url_path='/admin/static'
)

# Crucial: Import routes AFTER the blueprint object is created
from . import routes