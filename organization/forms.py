# File: CodeQuizHub/organization/forms.py
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, TextAreaField, SubmitField, SelectField
from wtforms.validators import DataRequired, Length, Email, Optional as WtformsOptional, URL, ValidationError
from ..models import User, Organization, UserRole

class InviteUserForm(FlaskForm):
    # ... (definition as before) ...
    email = StringField('Invitee Email Address', validators=[DataRequired(message="Email address is required."), Email(message="Invalid email address format."), Length(max=120)])
    role = SelectField('Assign Role', choices=[(UserRole.TEACHER.name, UserRole.TEACHER.value), (UserRole.STUDENT.name, UserRole.STUDENT.value)], validators=[DataRequired(message="Please select a role.")])
    submit = SubmitField('Send Invitation')

class BulkInviteForm(FlaskForm):
    # ... (definition as before) ...
    file = FileField('Upload Member File (CSV/Excel)', validators=[FileRequired(message="Please select a file to upload."), FileAllowed(['csv', 'xlsx', 'xls'], 'Only CSV or Excel (.csv, .xlsx, .xls) files are allowed!')])
    submit = SubmitField('Upload and Send Invitations')

class OrgProfileEditForm(FlaskForm):
    # ... (definition as before) ...
    name = StringField('Organization Name', validators=[DataRequired(message="Organization name cannot be empty."), Length(max=100)])
    description = TextAreaField('Organization Description', validators=[WtformsOptional(), Length(max=1000)])
    website_url = StringField('Website URL', validators=[WtformsOptional(), URL(message="Please enter a valid URL (e.g., https://example.com)."), Length(max=512)])
    submit = SubmitField('Update Organization Profile')
# File: CodeQuizHub/organization/forms.py
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, TextAreaField, SubmitField, SelectField, PasswordField
from wtforms.validators import DataRequired, Length, Email, Optional as WtformsOptional, URL, EqualTo, ValidationError
from ..models import User, Organization, UserRole, Credentials # Added Credentials

# --- Form for an Organization Admin to Create a New User (Teacher or Student) ---
class CreateOrgUserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email Address', validators=[DataRequired(), Email(), Length(max=120)])
    display_name = StringField('Display Name (Optional)', validators=[WtformsOptional(), Length(max=100)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password', message='Passwords must match.')])
    role = SelectField('Assign Role', choices=[
                            (UserRole.TEACHER.name, UserRole.TEACHER.value),
                            (UserRole.STUDENT.name, UserRole.STUDENT.value)
                         ], validators=[DataRequired()])
    # Add student_code if applicable for students
    student_code = StringField('Student Code (Optional)', validators=[WtformsOptional(), Length(max=50)])
    submit = SubmitField('Create User Account')

    def validate_username(self, username):
        # Check if username already exists in Credentials
        if Credentials.query.filter_by(username=username.data).first():
            raise ValidationError('That username is already taken. Please choose a different one.')

    def validate_email(self, email):
        # Check if email already exists in User table (globally, or within org based on policy)
        # For simplicity, checking globally for now.
        if User.query.filter_by(email=email.data).first():
            raise ValidationError('That email address is already registered. Please use a different one.')



# --- Form for Bulk Invitation/Creation Upload (modified for creation) ---
class BulkUserCreateForm(FlaskForm):
    file = FileField('Upload Member File (CSV/Excel)', validators=[
        FileRequired(message="Please select a file to upload."),
        FileAllowed(['csv', 'xlsx', 'xls'], 'Only CSV or Excel (.csv, .xlsx, .xls) files are allowed!')
    ])
    # Role will be specified in the file
    submit = SubmitField('Upload and Create Accounts')

