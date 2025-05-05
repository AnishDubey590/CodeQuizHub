# /your_app/utils/decorators.py
from functools import wraps
from flask import abort
from flask_login import current_user
from ..models import UserRole

# --- Role Required Decorators ---

def role_required(role):
    """Decorator to require a specific user role."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                # This should normally be caught by @login_required first
                abort(401) # Unauthorized
            if current_user.role != role:
                abort(403) # Forbidden
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def roles_required(*roles):
    """Decorator to require one of several user roles."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Specific role decorators
admin_required = role_required(UserRole.ADMIN)
organization_required = role_required(UserRole.ORGANIZATION)
teacher_required = role_required(UserRole.TEACHER)
student_required = role_required(UserRole.STUDENT)
individual_user_required = role_required(UserRole.USER)

# Decorator to check if user belongs to a specific organization
# IMPORTANT: This decorator expects an argument like 'organization_id'
# in the route's URL parameters to check against.
def belongs_to_organization(param_name='organization_id'):
     """Decorator to check if the current user belongs to the org specified in URL."""
     def decorator(f):
          @wraps(f)
          def decorated_function(*args, **kwargs):
               if not current_user.is_authenticated or not hasattr(current_user, 'user_profile'):
                    abort(401)

               org_id_from_url = kwargs.get(param_name)
               if org_id_from_url is None:
                    abort(500, f"Organization ID parameter '{param_name}' missing in route.")

               user_org_id = current_user.user_profile.organization_id

               # Allow Platform Admins access to anything
               if current_user.role == UserRole.ADMIN:
                    return f(*args, **kwargs)

               # Check if the user is part of the specified organization
               if not user_org_id or user_org_id != int(org_id_from_url):
                    abort(403) # Forbidden - doesn't belong to this org

               return f(*args, **kwargs)
          return decorated_function
     return decorator

# Decorator to check if the current user is the admin of the target organization
def is_organization_admin(param_name='organization_id'):
     """Decorator to ensure current user is the admin of the target org."""
     def decorator(f):
          @wraps(f)
          def decorated_function(*args, **kwargs):
               if not current_user.is_authenticated or not hasattr(current_user, 'user_profile'):
                    abort(401)

               # Platform admin can always manage
               if current_user.role == UserRole.ADMIN:
                    return f(*args, **kwargs)

               # Must have the ORGANIZATION role
               if current_user.role != UserRole.ORGANIZATION:
                    abort(403)

               target_org_id = kwargs.get(param_name)
               if target_org_id is None:
                    abort(500, f"Organization ID parameter '{param_name}' missing.")

               managed_org = current_user.user_profile.managed_organization
               if not managed_org or managed_org.id != int(target_org_id):
                    abort(403) # Not the admin of *this* specific organization

               return f(*args, **kwargs)
          return decorated_function
     return decorator
