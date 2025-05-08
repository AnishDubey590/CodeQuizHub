# /your_app/__init__.py
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_mail import Mail # Import Flask-Mail
from .app_config import config_by_name # Note the leading dot
from datetime import datetime # <--- Make sure this import is at the top of the file


db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login' # Blueprint name.route name
login_manager.login_message_category = 'info' # Bootstrap category for flash messages
csrf = CSRFProtect()
mail = Mail() # Initialize Mail

# Import models here AFTER db is defined to avoid circular imports during model definition
# but BEFORE they are needed by load_user or blueprints
# from .models import Credentials, User, Organization  # etc.

# --- User Loader for Flask-Login ---
@login_manager.user_loader
def load_user(user_id):
    """Loads user by ID (which is Credentials.id)."""
    from .models import Credentials # Import inside function
    # Flask-Login passes the ID stored in the session
    return Credentials.query.get(int(user_id))

from flask_wtf.csrf import CSRFProtect
# ...
csrf = CSRFProtect() # Create instance

# --- Application Factory ---
def create_app(config_name=None):
    """Application factory pattern."""
    if config_name is None:
        config_name = os.getenv('FLASK_CONFIG', 'dev') # Default to 'dev'

    app = Flask(__name__, instance_relative_config=False) # instance_relative_config=False if config.py is at root

    # Load configuration
    app.config.from_object(config_by_name[config_name])
    csrf.init_app(app) # Initialize with app
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)

    # Register blueprints
    from .auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from .main import main_bp
    app.register_blueprint(main_bp)

    from .admin import admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    from .organization import org_bp
    app.register_blueprint(org_bp, url_prefix='/organization')

    from .teacher import teacher_bp
    app.register_blueprint(teacher_bp, url_prefix='/teacher')

    from .student import student_bp
    app.register_blueprint(student_bp, url_prefix='/student')

    from .user import user_bp # For individual users
    app.register_blueprint(user_bp, url_prefix='/user')

    # Optional: Setup logging, error handlers, context processors here

    # Create instance folder if it doesn't exist, especially for SQLite
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass # Already exists

    # Example Context Processor to make UserRole available in templates
    from .models import UserRole
    @app.context_processor
    def inject_user_roles():
        return dict(UserRole=UserRole)

    print(f" * Running in {config_name} mode")
    print(f" * Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")

    return app
# /CodeQuizHub/__init__.py
# ... (imports and extension initializations) ...

def create_app(config_name=None):
    """Application factory pattern."""
    if config_name is None:
        config_name = os.getenv('FLASK_CONFIG', 'dev')

    app = Flask(__name__, instance_relative_config=False) # Assuming app_config is inside package

    try:
        selected_config = config_by_name[config_name]
    except KeyError:
        # Handle case where an invalid config_name is provided
        print(f"ERROR: Invalid configuration name '{config_name}'. Defaulting to 'dev'.")
        config_name = 'dev'
        selected_config = config_by_name[config_name]

    app.config.from_object(selected_config)

    # --- ADD VALIDATION CHECKS *AFTER* LOADING CONFIG ---
    if config_name == 'prod':
        # Check critical production settings only when running in production
        if not app.config.get('SQLALCHEMY_DATABASE_URI'):
            raise ValueError("FATAL ERROR: DATABASE_URL environment variable is not set for Production environment.")
        # Check if using the default insecure secret key in production
        default_testing_key = 'you-should-really-change-this-secret-key'
        if not app.config.get('SECRET_KEY') or app.config.get('SECRET_KEY') == default_testing_key:
            raise ValueError("FATAL ERROR: SECRET_KEY is not securely set for Production environment.")
        # Add checks for other essential prod settings (e.g., MAIL_SERVER if required)
        # if not app.config.get('MAIL_SERVER'):
        #      raise ValueError("FATAL ERROR: MAIL_SERVER not configured for Production.")

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)
    @app.context_processor
    def inject_now():
        return {'now': datetime.utcnow}
    # Register blueprints
    from .auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from .main import main_bp
    app.register_blueprint(main_bp)

    # ... (register OTHER blueprints: admin, organization, teacher, student, user) ...
    from .admin import admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')
    from .organization import org_bp
    app.register_blueprint(org_bp, url_prefix='/organization')
    from .teacher import teacher_bp
    app.register_blueprint(teacher_bp, url_prefix='/teacher')
    from .student import student_bp
    app.register_blueprint(student_bp, url_prefix='/student')
    from .user import user_bp
    app.register_blueprint(user_bp, url_prefix='/user')


    # Optional: Setup logging, error handlers, context processors here

    # Example Context Processor
    from .models import UserRole
    @app.context_processor
    def inject_user_roles():
        return dict(UserRole=UserRole)

    print(f" * Running in {config_name} mode")
    # Only print DB URI in non-prod for security
    if config_name != 'prod':
        print(f" * Database URI: {app.config.get('SQLALCHEMY_DATABASE_URI', 'Not Set')}")

    return app