# your_app/main/routes.py
from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
# Import Enums and potentially public quiz models if needed for index
from ..models import UserRole, Quiz, QuizStatus, QuizAttempt

main_bp = Blueprint('main',
                    __name__,
                    template_folder='../templates') # Points to the main templates folder

# Public Homepage
@main_bp.route('/')
def index():
    # Fetch public quizzes if you want to display them here
    public_quizzes = Quiz.query.filter_by(is_public=True, status=QuizStatus.PUBLISHED).order_by(Quiz.created_at.desc()).limit(10).all()
    return render_template('main/dashboard.html', public_quizzes=public_quizzes)

# Central Dashboard Dispatcher
@main_bp.route('/dashboard')
@login_required
def dashboard():
    """Redirects logged-in users to their specific dashboard."""
    if current_user.role == UserRole.ADMIN:
        return redirect(url_for('admin.dashboard')) # admin blueprint, dashboard function

    elif current_user.role == UserRole.ORGANIZATION:
        # Ensure the organization admin user is linked correctly
        if not current_user.managed_organization:
             flash('Organization account not fully set up or found. Please contact support.', 'warning')
             # Maybe redirect to a profile setup page or logout
             return redirect(url_for('auth.logout')) # Or main.index
        if not current_user.managed_organization.is_approved and current_user.managed_organization.approval_status != 'pending':
             # Check if org exists and is approved (or pending)
              flash('Your organization registration requires approval or was rejected.', 'warning')
              # Render a specific waiting page or redirect
              return render_template('main/org_pending.html', organization=current_user.managed_organization) # Need this template
        return redirect(url_for('organization.dashboard')) # organization blueprint, dashboard function

    elif current_user.role == UserRole.STUDENT:
         # Ensure student is associated with an organization
         if not current_user.organization_id or not current_user.organization:
             flash('Student account not linked to an organization.', 'warning')
             return redirect(url_for('auth.logout')) # Or main.index
         # Check if the student's organization is approved
         if not current_user.organization.is_approved:
             flash(f'Your organization ({current_user.organization.name}) is awaiting admin approval.', 'info')
             # Render a simple info page, or just let them see their dashboard with limited actions
             # For now, redirect to student dashboard, but routes inside should check org approval status
             pass # Allow access to dashboard, but maybe limit actions inside routes

         return redirect(url_for('student.dashboard')) # student blueprint, dashboard function

    elif current_user.role == UserRole.USER:
        # General User - redirect to a specific simple dashboard or back to index
        # flash('Welcome back!', 'success')
        # return redirect(url_for('main.index')) # Option 1: Back to public index

        # Option 2: Redirect to a simple user-specific dashboard
        return redirect(url_for('main.user_dashboard'))

    else:
        flash('Invalid user role detected.', 'danger')
        return redirect(url_for('auth.logout'))

# Simple Dashboard for General Users (Role = USER)
@main_bp.route('/user/dashboard')
@login_required
def user_dashboard():
    if current_user.role != UserRole.USER:
        flash('Access denied.', 'danger')
        return redirect(url_for('main.dashboard')) # Redirect to dispatcher

    # Fetch data relevant to general users: public quizzes, recent attempts, leaderboard stats etc.
    recent_attempts = QuizAttempt.query.filter_by(user_id=current_user.id)\
                                      .order_by(QuizAttempt.start_time.desc())\
                                      .limit(5).all()
    public_quizzes = Quiz.query.filter_by(is_public=True, status=QuizStatus.PUBLISHED)\
                                .order_by(Quiz.created_at.desc())\
                                .limit(10).all() # Example: show available public quizzes

    return render_template('main/dashboard.html',
                           recent_attempts=recent_attempts,
                           public_quizzes=public_quizzes)