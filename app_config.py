# /config.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file (optional)
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-should-really-change-this-secret-key'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = False
    TESTING = False
    # Use environment variables for sensitive data like DB URI
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'instance', 'codequizhub.db') # Default to SQLite in instance folder

    # Flask-Mail Configuration (Example - configure as needed)
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 25)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') is not None
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or '"CodeQuiz Hub Admin" <noreply@example.com>'

    # Add other configurations like API keys, etc.
    # COMPILER_API_URL = os.environ.get('COMPILER_API_URL')
    # COMPILER_API_KEY = os.environ.get('COMPILER_API_KEY')

    # Pagination
    POSTS_PER_PAGE = 10 # Example for potential pagination

    # Invitation Token Max Age (in seconds) - e.g., 7 days
    INVITATION_TOKEN_MAX_AGE = 60 * 60 * 24 * 7


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    SQLALCHEMY_ECHO = False # Set to True to see SQL queries
    # Ensure instance folder exists for SQLite
    instance_path = os.path.join(basedir, 'instance')
    if not os.path.exists(instance_path):
        os.makedirs(instance_path)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        'sqlite:///' + os.path.join(instance_path, 'dev_codequizhub.db')


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or \
        'sqlite:///:memory:' # Use in-memory SQLite for tests
    WTF_CSRF_ENABLED = False # Disable CSRF for simpler testing


#/CodeQuizHub/app_config.py

# ... (other Config classes) ...

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False # Ensure Debug is False for prod
    TESTING = False

    # Set attributes from environment variables
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') # No default for prod DB

    # REMOVE OR COMMENT OUT THE IMMEDIATE CHECK HERE:
    # if not SQLALCHEMY_DATABASE_URI:
    #     raise ValueError("No DATABASE_URL set for Production application")
    # if not os.environ.get('SECRET_KEY'):
    #      raise ValueError("No SECRET_KEY set for Production application")

    # You might still want warnings printed during import if keys are missing,
    # but avoid raising errors that stop the import.
    if not os.environ.get('SECRET_KEY'):
         print("WARNING: SECRET_KEY environment variable not set. Using default or none.")
    if not SQLALCHEMY_DATABASE_URI:
         print("WARNING: DATABASE_URL environment variable not set.")

# ... (config_by_name dictionary) ...

# Dictionary to access configurations by name
config_by_name = dict(
    dev=DevelopmentConfig,
    test=TestingConfig,
    prod=ProductionConfig
)

key = Config.SECRET_KEY