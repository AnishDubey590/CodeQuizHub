# /your_app/organization/forms.py
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, TextAreaField, SubmitField, SelectField, SelectMultipleField, widgets
from wtforms.validators import DataRequired, Length, Email, Optional as WtformsOptional, ValidationError
from ..models import User, Organization, UserRole # For validation if needed

# Form previously defined in auth/forms.py, moving relevant parts here if needed,
# but better to keep InviteUserForm in auth or a shared location if used elsewhere.
# For now, assuming InviteUserForm remains in auth/forms.py as used by org routes.

class OrgProfileEditForm(FlaskForm):
    """Form for editing organization profile details."""
    # Prevent changing unique name easily? Or add specific validation.
    # name = StringField('Organization Name', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Organization Description', validators=[WtformsOptional(), Length(max=1000)])
    website_url = StringField('Website URL', validators=[WtformsOptional(), Length(max=512)]) # Add URL validator if desired
    # TODO: Add FileField for logo upload if implementing logo handling
    # logo = FileField('Upload Logo', validators=[FileAllowed(['jpg', 'png', 'jpeg', 'gif'], 'Images only!')])
    submit = SubmitField('Update Profile')

    # Add custom validation if needed (e.g., check if name already taken if allowing edits)


class BulkInviteForm(FlaskForm):
    """Form for uploading CSV/Excel file for bulk invitations."""
    file = FileField('Upload CSV or Excel File', validators=[
        FileRequired(),
        FileAllowed(['csv', 'xlsx', 'xls'], 'CSV or Excel files only!')
    ])
    # Optionally add a select field if you want the admin to specify the role for ALL users in the file
    # role = SelectField('Assign Role to All', choices=[(UserRole.TEACHER.value, 'Teacher'), (UserRole.STUDENT.value, 'Student')], default=UserRole.STUDENT.value)
    submit = SubmitField('Upload and Process Invitations')