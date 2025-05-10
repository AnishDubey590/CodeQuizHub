# File: CodeQuizHub/admin/forms.py
from flask_wtf import FlaskForm
from wtforms import SubmitField, StringField, SelectField, BooleanField
from wtforms.validators import DataRequired, Email, Length, Optional
from ..models import UserRole # Import UserRole if needed for editing roles

# Simple forms primarily for CSRF protection on POST actions via buttons
class OrgApprovalForm(FlaskForm):
    """Minimal form for CSRF protection on org approve/reject actions."""
    pass

class UserActivationForm(FlaskForm):
    """Minimal form for CSRF protection on user activate/deactivate actions."""
    pass

# Example form for editing user details (you can expand this)
# This would be used by a future edit_user route
class AdminEditUserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=80)])
    email = StringField('Email (User Profile)', validators=[DataRequired(), Email(), Length(max=120)])
    display_name = StringField('Display Name', validators=[Optional(), Length(max=100)])
    # Coercing to the enum object itself
    role = SelectField('Role', choices=[(role.name, role.value) for role in UserRole], coerce=UserRole)
    is_active = BooleanField('Credentials Active')
    # Add organization selector if needed
    # organization_id = SelectField('Organization', coerce=int, validators=[Optional()])
    submit = SubmitField('Update User Details')

    # You might add custom validators here, e.g., to check if username/email is unique excluding the current user