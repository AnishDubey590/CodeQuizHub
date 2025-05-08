# File: CodeQuizHub/admin/forms.py
from flask_wtf import FlaskForm
# from wtforms import SubmitField # Not needed if no visible fields

class OrgApprovalForm(FlaskForm):
    """
    Minimal form used for CSRF protection on organization
    approve/reject actions triggered by buttons/links via POST.
    The hidden_tag() method will render the CSRF token.
    """
    pass # No fields required for this specific usage pattern

class UserActivationForm(FlaskForm):
    """
    Minimal form used for CSRF protection on user
    activation/deactivation actions triggered by buttons/links via POST.
    The hidden_tag() method will render the CSRF token.
    """
    pass # No fields required for this specific usage pattern

# Add other Admin-specific forms below if needed later, for example:
# class EditUserForm(FlaskForm):
#     username = StringField('Username', validators=[DataRequired()])
#     email = StringField('Email', validators=[DataRequired(), Email()])
#     role = SelectField('Role', choices=[(role.value, role.name) for role in UserRole], coerce=UserRole)
#     is_active = BooleanField('Active')
#     submit = SubmitField('Update User')