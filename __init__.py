# your_app/__init__.py

import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from datetime import datetime

# 1. Unbound Extensions
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

# Flask-Login Configuration
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# 2. App Factory
def create_app(config_class=None):
    app = Flask(__name__, instance_relative_config=True)

    # 3. Load Configuration
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'a_very_default_insecure_secret_key'),
        SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL', 'sqlite:///codequizhub.db'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    # Optional: Load from instance/config.py
    # app.config.from_pyfile('config.py', silent=True)

    # 4. Initialize Extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    # 5. Import Models (after db initialized)
    from . import models

    # 6. User Loader
    @login_manager.user_loader
    def load_user(user_id):
        try:
            return models.User.query.get(int(user_id))
        except ValueError:
            return None

    # 7. Context Processors
    @app.context_processor
    def inject_now():
        return {'now': datetime.utcnow}

    @app.context_processor
    def inject_user_roles():
        return dict(UserRole=models.UserRole)

    # 8. Shell Context
    @app.shell_context_processor
    def make_shell_context():
        return {
            'db': db,
            'User': models.User,
            'Organization': models.Organization,
            'Quiz': models.Quiz,
            'Question': models.Question,
            'RoleRequest': models.RoleRequest,
            'StudentOrganization': models.StudentOrganization,
        }

    # 9. Register Blueprints
    from .main.routes import main_bp
    from .auth.routes import auth_bp
    from .admin.routes import admin_bp
    from .organization.routes import organization_bp
    from .student.routes import student_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(organization_bp, url_prefix='/org')
    app.register_blueprint(student_bp, url_prefix='/student')

    return app
