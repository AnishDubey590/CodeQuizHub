from flask import Blueprint

org_bp = Blueprint('organization', __name__)


# Import routes after blueprint definition
from . import routes
main_bp = Blueprint('main', __name__)

# Import routes after blueprint definition
from . import routes