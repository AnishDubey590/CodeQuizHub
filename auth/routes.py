# your_app/auth/routes.py
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
# Removed generate_password_hash as it's handled by user.set_password()
# Removed check_password_hash as it's handled by user.check_password()
from ..models import db, User, UserRole, Organization, OrgApprovalStatus # Import necessary models

# --- Recommendation: Use Flask-WTF for Forms ---
# from flask_wtf import FlaskForm
# from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField
# from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
# from ..models import User, Organization # Import models for custom validators if needed
#
# class RegistrationForm(FlaskForm):
#     username = StringField('Username', validators=[DataRequired(), Length(min=4, max=80)])
#     email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
#     password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
#     confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
#     submit = SubmitField('Register')
#
#     def validate_username(self, username):
#         user = User.query.filter_by(username=username.data).first()
#         if user:
#             raise ValidationError('That username is already taken. Please choose a different one.')
#
#     def validate_email(self, email):
#         user = User.query.filter_by(email=email.data).first()
#         if user:
#             raise ValidationError('That email is already in use. Please choose a different one.')
#
# class OrganizationRegistrationForm(FlaskForm):
#     org_name = StringField('Organization Name', validators=[DataRequired(), Length(max=100)])
#     org_description = TextAreaField('Organization Description', validators=[Length(max=500)]) # Optional field length limit
#     admin_username = StringField('Administrator Username', validators=[DataRequired(), Length(min=4, max=80)])
#     admin_email = StringField('Administrator Email', validators=[DataRequired(), Email(), Length(max=120)])
#     admin_password = PasswordField('Administrator Password', validators=[DataRequired(), Length(min=6)])
#     admin_confirm_password = PasswordField('Confirm Administrator Password', validators=[DataRequired(), EqualTo('admin_password')])
#     submit = SubmitField('Request Registration')
#
#     def validate_org_name(self, org_name):
#         org = Organization.query.filter_by(name=org_name.data).first()
#         if org:
#             raise ValidationError('An organization with that name already exists.')
#
#     def validate_admin_username(self, admin_username):
#         user = User.query.filter_by(username=admin_username.data).first()
#         if user:
#             raise ValidationError('That administrator username is already taken.')
#
#     def validate_admin_email(self, admin_email):
#         user = User.query.filter_by(email=admin_email.data).first()
#         if user:
#             raise ValidationError('That administrator email is already in use.')
# --- End WTForms Recommendation ---


# Assuming your blueprint setup is correct:
# auth_bp = Blueprint('auth', __name__, template_folder='../templates/auth')
# If templates are in 'your_app/templates/auth/', use:
auth_bp = Blueprint('auth', __name__, template_folder='templates/auth', url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        # Redirect based on role after login check in main dashboard route
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        # Basic Validation (Consider WTForms for robustness)
        if not email or not password:
            flash('Email and password are required.', 'warning')
            return redirect(url_for('auth.login'))

        user = User.query.filter_by(email=email).first()

        # Check password and user existence
        if not user or not user.check_password(password):
            flash('Invalid email or password. Please try again.', 'danger')
            return redirect(url_for('auth.login'))

        # Check if account is active
        if not user.is_active:
             flash('Account deactivated. Please contact support.', 'warning')
             return redirect(url_for('auth.login'))

        # Check if Org user's org is approved (allow pending to login but show pending status page)
        if user.role == UserRole.ORGANIZATION:
            # Fetch the organization this user administers
            org = Organization.query.filter_by(admin_user_id=user.id).first()
            # It's possible the org doesn't exist if something went wrong, or if deleted
            if org and org.approval_status == OrgApprovalStatus.REJECTED:
                 flash('Your organization registration was rejected. Please contact support or register again.', 'danger')
                 return redirect(url_for('auth.login'))
            # PENDING or APPROVED users can proceed. The dashboard route should handle PENDING status display.

        login_user(user, remember=remember)
        flash('Login successful!', 'success')

        # Redirect to the intended page or the main dashboard
        next_page = request.args.get('next')
        # Use url_for('main.dashboard') which should handle role-based redirection
        return redirect(next_page or url_for('main.dashboard'))

    # Render the login form for GET requests
    return render_template('auth/login.html')


@auth_bp.route('/register/individual', methods=['GET', 'POST'])
def individual_register():
    """ Handles registration for INDIVIDUAL users (role=UserRole.USER). """
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # --- Basic Server-Side Validation (Replace/Enhance with WTForms) ---
        error = False
        if not username or not email or not password or not confirm_password:
            flash('All fields are required.', 'warning')
            error = True
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            error = True

        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash('Username or email already exists.', 'danger')
            error = True

        if error:
             # Re-render form, potentially passing back submitted values (safer with WTForms)
             return render_template('individual_register.html', username=username, email=email)
        # --- End Basic Validation ---

        # Create Individual User
        new_user = User(username=username, email=email, role=UserRole.USER) # Explicitly set role
        new_user.set_password(password)

        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            print(f"Error during individual registration: {e}") # Log the actual error
            flash('An error occurred during registration. Please try again later.', 'danger')
            # Re-render form on database error
            return render_template('individual_register.html', username=username, email=email)

    # Render the individual registration form for GET requests
    return render_template('individual_register.html')


@auth_bp.route('/register/organization', methods=['GET', 'POST'])
def organization_register():
    """ Handles registration request for ORGANIZATIONS. """
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        # Organization Details
        org_name = request.form.get('org_name')
        org_description = request.form.get('org_description') # Optional

        # Administrator Details
        admin_username = request.form.get('admin_username')
        admin_email = request.form.get('admin_email')
        admin_password = request.form.get('admin_password')
        admin_confirm_password = request.form.get('admin_confirm_password')

        # --- Basic Server-Side Validation (Replace/Enhance with WTForms) ---
        error = False
        required_fields = {
            'Organization Name': org_name,
            'Administrator Username': admin_username,
            'Administrator Email': admin_email,
            'Administrator Password': admin_password,
            'Confirm Administrator Password': admin_confirm_password
        }
        for field_name, value in required_fields.items():
            if not value:
                flash(f'{field_name} is required.', 'warning')
                error = True

        if not error and admin_password != admin_confirm_password:
            flash('Administrator passwords do not match.', 'danger')
            error = True

        # Check Uniqueness (only if basic fields are present)
        if not error:
            existing_user = User.query.filter((User.username == admin_username) | (User.email == admin_email)).first()
            if existing_user:
                flash('Administrator username or email already exists.', 'danger')
                error = True

            existing_org = Organization.query.filter(Organization.name == org_name).first()
            if existing_org:
                flash('An organization with this name already exists or is pending approval.', 'danger')
                error = True

        if error:
            # Re-render form, passing back submitted values to repopulate
            # Note: Passwords should NOT be passed back for security.
            return render_template('organization_register.html',
                                   org_name=org_name,
                                   org_description=org_description,
                                   admin_username=admin_username,
                                   admin_email=admin_email)
        # --- End Basic Validation ---

        # Create Organization Admin User and Organization record within a transaction
        try:
            # 1. Create the Admin User for the Organization
            new_admin_user = User(
                username=admin_username,
                email=admin_email,
                role=UserRole.ORGANIZATION # Set the correct role
            )
            new_admin_user.set_password(admin_password)
            # Don't add/commit yet, do it together with the org

            # 2. Create the Organization record
            new_org = Organization(
                name=org_name,
                description=org_description,
                approval_status=OrgApprovalStatus.PENDING, # Default status
                # Link the admin user object directly - SQLAlchemy handles the ID
                admin_user=new_admin_user
            )

            # 3. Add both to session and commit transactionally
            db.session.add(new_admin_user)
            db.session.add(new_org)
            db.session.commit()

            flash('Organization registration request submitted successfully! An administrator will review it shortly.', 'success')
            return redirect(url_for('auth.login')) # Redirect to login after successful request

        except Exception as e:
            db.session.rollback()
            print(f"Error during organization registration: {e}") # Log the actual error
            flash('An error occurred during registration. Please check your details and try again.', 'danger')
            # Re-render form on database error
            return render_template('organization_register.html',
                                   org_name=org_name,
                                   org_description=org_description,
                                   admin_username=admin_username,
                                   admin_email=admin_email)

    # Render the organization registration form for GET requests
    return render_template('auth/organization_register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    # Redirect to a public landing page or login page
    return redirect(url_for('main.index')) # Assuming 'main.index' is your landing page