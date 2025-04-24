# your_app/organization/routes.py
from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from ..models import db, User, Organization, Quiz, UserRole, QuizStatus, OrgApprovalStatus
# from ..decorators import organization_required # Optional: use decorator later

organization_bp = Blueprint('organization',
                            __name__,
                            url_prefix='/org',
                            template_folder='../templates/organization')

@organization_bp.route('/dashboard')
@login_required
# @organization_required # Uncomment when decorator is implemented
def dashboard():
    # --- Manual Role & Org Check ---
    if current_user.role != UserRole.ORGANIZATION:
        flash('Organization access required.', 'danger')
        return redirect(url_for('main.dashboard')) # Redirect to dispatcher

    org = current_user.managed_organization
    if not org:
         flash('Organization data not found for your account.', 'danger')
         return redirect(url_for('auth.logout'))

    # Redirect if not approved yet (handled also by main dispatcher, but good practice here too)
    if org.approval_status == OrgApprovalStatus.PENDING:
         flash('Your organization registration is pending approval.', 'info')
         return render_template('pending_approval.html', organization=org) # Need this template

    if org.approval_status == OrgApprovalStatus.REJECTED:
         flash('Your organization registration was rejected.', 'danger')
         return render_template('rejected.html', organization=org) # Need this template
    # --- End Manual Check ---

    # Fetch data for Organization Dashboard
    student_count = User.query.filter_by(organization_id=org.id, role=UserRole.STUDENT).count()
    quiz_count = Quiz.query.filter_by(organization_id=org.id).count()
    recent_quizzes = Quiz.query.filter_by(organization_id=org.id)\
                                .order_by(Quiz.created_at.desc())\
                                .limit(5).all()
    # Add more stats: active quizzes, average scores, etc.

    return render_template('dashboard.html',
                           organization=org,
                           student_count=student_count,
                           quiz_count=quiz_count,
                           recent_quizzes=recent_quizzes)

# TODO: Add routes for managing students (add/view), creating/managing quizzes, viewing analytics
# Example Placeholders:
# @organization_bp.route('/students')
# @login_required
# @organization_required
# def manage_students(): ...

# @organization_bp.route('/quizzes')
# @login_required
# @organization_required
# def list_quizzes(): ...

# @organization_bp.route('/quizzes/create', methods=['GET', 'POST'])
# @login_required
# @organization_required
# def create_quiz(): ...

# @organization_bp.route('/analytics')
# @login_required
# @organization_required
# def view_analytics(): ...