# File: CodeQuizHub/admin/__init__.py
from flask import Blueprint,Flask

admin_bp = Blueprint(
    'admin',
    __name__,
    template_folder='templates'
    # If setting url_prefix here, remove it from create_app registration
    # url_prefix='/admin'
)
def create_app(config_name=None):
    # ...
    app = Flask(__name__, instance_relative_config=False)

    # --- ENABLE JINJA EXTENSIONS HERE ---
    app.jinja_env.add_extension('jinja2.ext.do') # Add this line

    # ... rest of config loading ...
    # ... extension initializations (db.init_app, etc) ...
    # ... blueprint registrations ...
    # ... context processors ...

    return app
# Ensure routes and forms (if any directly used by __init__) are imported last
from . import routes
from . import forms # Import forms if needed globally within blueprint, otherwise just needed by routes