# /your_app/main/forms.py
# Forms related to general site-wide functionality like profile editing

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length, Email, Optional as WtformsOptional, ValidationError
from flask_login import current_user
from ..models import User # For validating email uniqueness if needed

class ProfileEditForm(FlaskForm):
    """Form for editing user profile details."""
    # Username changes might be complex, typically not allowed or handled separately
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    display_name = StringField('Display Name', validators=[WtformsOptional(), Length(max=100)])
    bio = TextAreaField('Bio', validators=[WtformsOptional(), Length(max=500)])
    # TODO: Add FileField for profile picture upload
    # profile_picture = FileField(...)
    submit = SubmitField('Update Profile')

    def validate_email(self, email):
        # Check if email is changed and if the new one is already taken
        if email.data != current_user.user_profile.email:
            user = User.query.filter_by(email=email.data).first()
            if user:
                raise ValidationError('That email address is already registered.')