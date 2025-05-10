# File: CodeQuizHub/admin/routes.py
from flask import (
    Blueprint, render_template, flash, redirect, url_for, request, abort, current_app
)
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func # Needed for count aggregates
from .. import db
from ..models import (
    User, Credentials, Organization, OrgApprovalStatus, UserRole,
    Quiz, QuizAssignment, QuizStatus, # Import all necessary models
    Question # Import if needed for deeper quiz info
)
from ..utils.decorators import admin_required

from . import admin_bp
# Import forms if they exist (for CSRF) - Create admin/forms.py if needed
try:
    from .forms import OrgApprovalForm, UserActivationForm, AdminEditUserForm
except ImportError:
    # If forms don't exist, create dummy placeholders OR use csrf_token() in templates
    class MockForm:
        def validate_on_submit(self): return True # Always pass validation if form only for CSRF
        def hidden_tag(self): return "" # Render nothing if form doesn't exist
    OrgApprovalForm = UserActivationForm = AdminEditUserForm = MockForm
    current_app.logger.warning("Admin forms not found. CSRF checks in admin routes relying on forms will pass by default.")


@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Admin dashboard with statistics."""
    pending_orgs = []
    stats = {}
    approval_form = OrgApprovalForm() # Instantiate form for CSRF in template

    try:
        # Fetch pending organizations
        # Corrected model attribute access
        pending_orgs = Organization.query.filter_by(approval_status=OrgApprovalStatus.PENDING)\
                                         .order_by(Organization.requested_at.desc()).limit(5).all()

        # Calculate Statistics - uses Credentials and Organization models
        stats['total_users'] = Credentials.query.count()
        stats['student_users'] = Credentials.query.filter_by(role=UserRole.STUDENT).count()
        stats['teacher_users'] = Credentials.query.filter_by(role=UserRole.TEACHER).count()
        stats['org_admins'] = Credentials.query.filter_by(role=UserRole.ORGANIZATION).count()
        stats['total_orgs'] = Organization.query.count()
        stats['approved_orgs'] = Organization.query.filter_by(approval_status=OrgApprovalStatus.APPROVED).count()
        stats['total_quizzes'] = Quiz.query.count()
        # Count distinct attempts rather than individual answers for submission count
        stats['total_submissions'] = db.session.query(func.count(db.distinct(QuizAssignment.student_user_id, QuizAssignment.quiz_id))).scalar()
        # Or count QuizAttempt if that model represents a unique attempt:
        # from ..models import QuizAttempt # Assuming QuizAttempt model exists
        # stats['total_submissions'] = QuizAttempt.query.count()


    except AttributeError as e:
        # Log specific attribute errors
        current_app.logger.error(f"Admin dashboard query error: Missing attribute - {e}")
        flash("Error loading dashboard data: A required model attribute might be missing. Check model definitions and migrations.", "danger")
    except Exception as e:
        current_app.logger.error(f"Admin dashboard query error: {e}")
        flash(f"An unexpected error occurred while loading dashboard data.", "danger")

    # Data for user roles chart
    chart_data = None
    if stats:
        chart_data = {
            'labels': [role.name for role in UserRole if role != UserRole.ADMIN],
            'data': [ Credentials.query.filter_by(role=role).count() for role in UserRole if role != UserRole.ADMIN ]
        }

    return render_template('admin/dashboard.html',
                           title='Admin Dashboard',
                           pending_orgs=pending_orgs,
                           stats=stats,
                           chart_data=chart_data,
                           approval_form=approval_form) # Pass form for CSRF in template

# --- Organization Management ---

@admin_bp.route('/organizations')
@login_required
@admin_required
def view_organizations():
    """List all organizations with pagination and search/filter."""
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('ADMIN_ITEMS_PER_PAGE', 10)
    q = request.args.get('q', '')
    status_filter = request.args.get('status', '')

    organizations_query = Organization.query

    if q:
        search = f'%{q}%'
        organizations_query = organizations_query.filter(Organization.name.ilike(search))

    # Filter by status using the OrgApprovalStatus enum correctly
    if status_filter and hasattr(OrgApprovalStatus, status_filter.upper()):
         org_status_enum = OrgApprovalStatus[status_filter.upper()]
         organizations_query = organizations_query.filter_by(approval_status=org_status_enum)

    pagination = organizations_query.order_by(Organization.name.asc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    organizations = pagination.items
    approval_form = OrgApprovalForm()

    return render_template('admin/view_organizations.html',
                           title='Manage Organizations',
                           organizations=organizations,
                           pagination=pagination,
                           approval_form=approval_form,
                           q=q,
                           status_filter=status_filter,
                           OrgApprovalStatus=OrgApprovalStatus) # Pass enum for filter dropdown

@admin_bp.route('/organizations/approve/<int:org_id>', methods=['POST'])
@login_required
@admin_required
def approve_organization(org_id):
    """Approve a pending organization."""
    form = OrgApprovalForm()
    # Validate CSRF using the form even if it has no other fields
    if form.validate_on_submit():
        org = Organization.query.get_or_404(org_id)
        if org.approval_status == OrgApprovalStatus.PENDING:
            try:
                org.approval_status = OrgApprovalStatus.APPROVED
                org.approved_at = db.func.now() # Use DB func for timestamp

                # CORRECTED: Access admin's User ID via current_user.user_profile.id
                # (Since current_user is Credentials, and it has user_profile relationship)
                if current_user.user_profile:
                    org.approved_by_admin_id = current_user.user_profile.id
                else:
                    current_app.logger.warning(f"Admin approval by Credentials ID {current_user.id} which has no linked User record (user_profile) for approved_by_admin_id.")

                # CORRECTED: Access org's admin User via admin_user relationship, then credentials
                if org.admin_user and org.admin_user.credentials:
                    org.admin_user.credentials.is_active = True

                db.session.commit()
                flash(f'Organization "{org.name}" approved successfully.', 'success')
                # TODO: Send notification email
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error approving organization {org_id}: {e}")
                flash(f'Error approving organization: {str(e)}', 'danger')
        else:
            flash('Organization is not pending approval.', 'warning')
    else:
        current_app.logger.warning(f"CSRF validation failed for approve org {org_id}. Form errors: {form.errors}")
        flash('Could not approve organization due to a form validation or security error.', 'danger') # More specific CSRF message

    # Redirect back to the list page, preserving filters/page if possible
    return redirect(request.referrer or url_for('admin.view_organizations'))

@admin_bp.route('/organizations/reject/<int:org_id>', methods=['POST'])
@login_required
@admin_required
def reject_organization(org_id):
    """Reject a pending organization."""
    form = OrgApprovalForm()
    if form.validate_on_submit(): # Validate CSRF
        org = Organization.query.get_or_404(org_id)
        if org.approval_status == OrgApprovalStatus.PENDING:
            try:
                org.approval_status = OrgApprovalStatus.REJECTED
                # Also nullify approval fields
                org.approved_at = None
                org.approved_by_admin_id = None

                # CORRECTED: Access org's admin User via admin_user relationship, then credentials
                if org.admin_user and org.admin_user.credentials:
                    org.admin_user.credentials.is_active = False # Deactivate org admin

                db.session.commit()
                flash(f'Organization "{org.name}" rejected.', 'info')
                # TODO: Send notification email
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error rejecting organization {org_id}: {e}")
                flash(f'Error rejecting organization: {str(e)}', 'danger')
        else:
            flash('Organization is not pending approval.', 'warning')
    else:
        current_app.logger.warning(f"CSRF validation failed for reject org {org_id}. Form errors: {form.errors}")
        flash('Could not reject organization due to a form validation or security error.', 'danger')

    return redirect(request.referrer or url_for('admin.view_organizations'))

# --- User Management ---

@admin_bp.route('/users')
@login_required
@admin_required
def view_users():
    """List all users (credentials) with pagination and search/filter."""
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('ADMIN_ITEMS_PER_PAGE', 15)
    q = request.args.get('q', '')
    role_filter = request.args.get('role', '')
    active_filter = request.args.get('active', '')

    # Join User for filtering/display - Use credentials.user_profile relationship
    credentials_query = db.session.query(Credentials).outerjoin(User, Credentials.user_profile)

    if q:
        search = f'%{q}%'
        # Filter on username, email, or display_name
        credentials_query = credentials_query.filter(
            db.or_(Credentials.username.ilike(search), User.email.ilike(search), User.display_name.ilike(search))
        )
    # Filter by role using the UserRole enum
    if role_filter and hasattr(UserRole, role_filter.upper()):
        user_role_enum = UserRole[role_filter.upper()]
        credentials_query = credentials_query.filter(Credentials.role == user_role_enum)
    # Filter by active status
    if active_filter in ['true', 'false']:
         credentials_query = credentials_query.filter(Credentials.is_active == (active_filter == 'true'))

    pagination = credentials_query.order_by(Credentials.username.asc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    user_credentials_list = pagination.items
    activation_form = UserActivationForm() # Form for CSRF

    return render_template('admin/view_users.html',
                           title='Manage Users',
                           user_credentials_list=user_credentials_list,
                           pagination=pagination,
                           activation_form=activation_form,
                           q=q,
                           role_filter=role_filter,
                           active_filter=active_filter,
                           UserRole=UserRole) # Pass enum for filter dropdown

@admin_bp.route('/users/toggle_active/<int:creds_id>', methods=['POST'])
@login_required
@admin_required
def toggle_user_active(creds_id):
    """Toggle the active status of a user's credentials."""
    form = UserActivationForm()
    page = request.args.get('page', 1, type=int) # Get page number to return to
    q = request.args.get('q', '')
    role_filter = request.args.get('role', '')
    active_filter = request.args.get('active', '')

    if form.validate_on_submit(): # Validate CSRF
        creds_to_toggle = Credentials.query.get_or_404(creds_id)
        if creds_to_toggle.id == current_user.id:
            flash("You cannot change the active status of your own account.", "danger")
        else:
            try:
                creds_to_toggle.is_active = not creds_to_toggle.is_active
                db.session.commit()
                status = "activated" if creds_to_toggle.is_active else "deactivated"
                flash(f"User '{creds_to_toggle.username}' has been {status}.", "success")
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error updating user status for {creds_to_toggle.username}: {e}")
                flash(f"Error updating user status: {str(e)}", "danger")
    else:
        current_app.logger.warning(f"CSRF validation failed for toggle user {creds_id}. Form errors: {form.errors}")
        flash('Could not toggle user status due to a form validation or security error.', 'danger')

    # Redirect back to the user list, preserving filters and page
    return redirect(url_for('admin.view_users', page=page, q=q, role=role_filter, active=active_filter))

# --- Quiz Monitoring ---

@admin_bp.route('/quizzes')
@login_required
@admin_required
def view_quizzes():
    """List all quizzes created by any organization with pagination and search."""
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('ADMIN_ITEMS_PER_PAGE', 15)
    q = request.args.get('q', '') # Search quiz title or org name

    # Query Quiz, join Organization for name, calculate attempts via Assignments count
    # Use label for clarity when accessing joined fields
    quiz_query = db.session.query(
        Quiz,
        Organization.name.label('organization_name'),
        func.count(db.distinct(QuizAssignment.student_user_id)).label('attempt_count') # Count distinct students assigned
    ).select_from(Quiz)\
     .outerjoin(Organization, Quiz.organization_id == Organization.id)\
     .outerjoin(QuizAssignment, Quiz.id == QuizAssignment.quiz_id)\
     .group_by(Quiz.id, Organization.name) # Group by quiz and org name

    if q:
        search = f'%{q}%'
        quiz_query = quiz_query.filter(
            db.or_(Quiz.title.ilike(search), Organization.name.ilike(search))
        )

    pagination = quiz_query.order_by(Quiz.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    # quizzes_data will be a list of Row objects (like tuples) if using labels:
    # e.g., row.Quiz, row.organization_name, row.attempt_count
    quizzes_data = pagination.items

    return render_template('admin/view_quizzes.html',
                           title='Monitor Quizzes',
                           quizzes_data=quizzes_data,
                           pagination=pagination,
                           q=q,
                           QuizStatus=QuizStatus) # Pass enum for displaying status

# --- Routes for viewing/editing details (kept minimal) ---

@admin_bp.route('/users/details/<int:creds_id>')
@login_required
@admin_required
def view_user_details(creds_id):
    """View details for a specific user."""
    creds = Credentials.query.get_or_404(creds_id)
    if not creds.user_profile: # Use the correct relationship name
        flash(f"User profile data not found for credentials ID {creds_id}.", "warning")
        return redirect(url_for('admin.view_users'))

    # Reuse the profile template from main blueprint
    return render_template('profile/view_profile.html',
                          title=f"User Details: {creds.username}",
                          user_profile=creds.user_profile) # Pass the User object

@admin_bp.route('/users/edit/<int:creds_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(creds_id):
    """Edit user credentials and profile details."""
    creds_to_edit = Credentials.query.get_or_404(creds_id)
    user_profile = creds_to_edit.user_profile # Use the correct relationship name

    if not user_profile:
        flash(f"Cannot edit user '{creds_to_edit.username}' as they have no associated profile record.", "danger")
        return redirect(url_for('admin.view_users'))

    # Use obj for Credentials, data dictionary for User fields
    form = AdminEditUserForm(obj=creds_to_edit, data={'email': user_profile.email, 'display_name': user_profile.display_name})

    if form.validate_on_submit():
        # Check uniqueness excluding self
        username_check = Credentials.query.filter(Credentials.username == form.username.data, Credentials.id != creds_id).first()
        email_check = User.query.filter(User.email == form.email.data, User.id != user_profile.id).first()
        form_valid = True
        if username_check:
            form.username.errors.append("This username is already taken.")
            form_valid = False
        if email_check:
            form.email.errors.append("This email address is already registered.")
            form_valid = False

        if form_valid:
            try:
                creds_to_edit.username = form.username.data
                creds_to_edit.role = form.role.data
                creds_to_edit.is_active = form.is_active.data

                user_profile.email = form.email.data
                user_profile.display_name = form.display_name.data

                db.session.commit()
                flash(f"Details for user '{creds_to_edit.username}' updated.", 'success')
                return redirect(url_for('admin.view_users'))
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error editing user {creds_id}: {e}")
                flash(f"An error occurred while updating user: {str(e)}", 'danger')

    return render_template('admin/edit_user.html',
                           title=f"Edit User: {creds_to_edit.username}",
                           form=form,
                           creds_id=creds_id)