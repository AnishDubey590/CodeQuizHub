# /your_app/auth/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField, SelectField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError, Optional as WtformsOptional
from ..models import Credentials, User, Organization, UserRole # Import models for validation

class RegistrationForm(FlaskForm):
    """Form for individual user registration."""
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password', message='Passwords must match.')])
    display_name = StringField('Display Name (Optional)', validators=[WtformsOptional(), Length(max=100)])
    submit = SubmitField('Register')

    def validate_username(self, username):
        creds = Credentials.query.filter_by(username=username.data).first()
        if creds:
            raise ValidationError('That username is already taken.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('That email address is already registered.')

class LoginForm(FlaskForm):
    """Form for user login."""
    username = StringField('Username', validators=[DataRequired()]) # Allow login by username
    # OR email = StringField('Email', validators=[DataRequired(), Email()]) # If logging in by email
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Login')

class OrganizationRegistrationForm(FlaskForm):
    """Form for organization registration request."""
    org_name = StringField('Organization Name', validators=[DataRequired(), Length(max=100)])
    org_description = TextAreaField('Organization Description', validators=[WtformsOptional(), Length(max=1000)])
    website_url = StringField('Website URL (Optional)', validators=[WtformsOptional(), Length(max=512)]) # Add Optional validator if needed

    # Admin details
    admin_username = StringField('Administrator Username', validators=[DataRequired(), Length(min=3, max=80)])
    admin_email = StringField('Administrator Email', validators=[DataRequired(), Email(), Length(max=120)])
    admin_password = PasswordField('Administrator Password', validators=[DataRequired(), Length(min=8)])
    admin_confirm_password = PasswordField(
        'Confirm Administrator Password',
        validators=[DataRequired(), EqualTo('admin_password', message='Admin passwords must match.')]
    )
    admin_display_name = StringField('Administrator Display Name (Optional)', validators=[WtformsOptional(), Length(max=100)])

    submit = SubmitField('Request Registration')

    def validate_org_name(self, org_name):
        org = Organization.query.filter_by(name=org_name.data).first()
        if org:
            # Check if pending or approved, rejected might be okay to re-register
            if org.approval_status != 'rejected':
                 raise ValidationError('An organization with this name already exists or is pending approval.')

    def validate_admin_username(self, admin_username):
        creds = Credentials.query.filter_by(username=admin_username.data).first()
        if creds:
            raise ValidationError('That administrator username is already taken.')

    def validate_admin_email(self, admin_email):
        user = User.query.filter_by(email=admin_email.data).first()
        if user:
            raise ValidationError('That administrator email address is already registered.')


class InviteUserForm(FlaskForm):
    """Form for inviting users to an organization."""
    email = StringField('Email Address', validators=[DataRequired(), Email(), Length(max=120)])
    role = SelectField('Assign Role', choices=[(UserRole.TEACHER.value, 'Teacher'), (UserRole.STUDENT.value, 'Student')], validators=[DataRequired()])
    submit = SubmitField('Send Invitation')

    # You might add validation to check if email is already a member/invited


class AcceptInvitationForm(FlaskForm):
    """Form for users accepting organization invitations."""
    username = StringField('Choose a Username', validators=[DataRequired(), Length(min=3, max=80)])
    display_name = StringField('Display Name (Optional)', validators=[WtformsOptional(), Length(max=100)])
    password = PasswordField('Choose a Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password', message='Passwords must match.')])
    student_code = StringField('Student/Staff Code (Optional)', validators=[WtformsOptional(), Length(max=50)])
    submit = SubmitField('Accept Invitation & Create Account')

    def __init__(self, existing_user=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.existing_user = existing_user
        # If user already exists, don't show password fields? Or make them link account?
        # This complexity is handled in routes for now.

    def validate_username(self, username):
        # Only validate if creating a NEW user account
        if not self.existing_user:
            creds = Credentials.query.filter_by(username=username.data).first()
            if creds:
                raise ValidationError('That username is already taken.')


class RequestPasswordResetForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Request Password Reset')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if not user:
            raise ValidationError('There is no account with that email. You must register first.')


class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm New Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')