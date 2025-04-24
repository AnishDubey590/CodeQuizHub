# your_app/auth/routes.py
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from ..models import db, User, UserRole, Organization, OrgApprovalStatus # Import necessary models
# You'll likely want WTForms for validation, import your forms here
# from .forms import LoginForm, RegistrationForm

auth_bp = Blueprint('auth', __name__, template_folder='../templates/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    # Replace with your actual form handling (e.g., WTForms)
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash('Invalid email or password. Please try again.', 'danger')
            return redirect(url_for('auth.login'))

        if not user.is_active:
             flash('Account deactivated. Please contact support.', 'warning')
             return redirect(url_for('auth.login'))

        # Check if Org user's org is approved (allow pending to login but see pending page)
        if user.role == UserRole.ORGANIZATION:
            org = Organization.query.filter_by(admin_user_id=user.id).first()
            if org and org.approval_status == OrgApprovalStatus.REJECTED:
                 flash('Your organization registration was rejected. Please contact support or register again.', 'danger')
                 return redirect(url_for('auth.login'))
             # Allow PENDING or APPROVED to log in, main.dashboard will handle redirection

        login_user(user, remember=remember)
        flash('Login successful!', 'success')
        # Redirect to the central dispatcher, which figures out the correct dashboard
        next_page = request.args.get('next')
        return redirect(next_page or url_for('main.dashboard'))

    return render_template('login.html') # Your login form template


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    # Replace with your actual form handling (e.g., WTForms)
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash('Username or email already exists.', 'danger')
            return redirect(url_for('auth.register'))
        # --- End Basic Validation ---

        # Create General User by default
        new_user = User(username=username, email=email, role=UserRole.USER) # Default role
        new_user.set_password(password)

        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please login.', 'success')
            # login_user(new_user) # Option: Log in immediately
            # return redirect(url_for('main.dashboard')) # Option: Redirect to dashboard
            return redirect(url_for('auth.login')) # Redirect to login page
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred during registration: {e}', 'danger') # Log this error properly
            return redirect(url_for('auth.register'))

    return render_template('register.html') # Your registration form template

# TODO: Add route for Organization Registration (/register/organization)
# This route would create a User with role ORGANIZATION and an associated Organization entry with status PENDING.

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))