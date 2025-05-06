# File: CodeQuizHub/admin/routes.py
from flask import Blueprint, render_template, flash, redirect, url_for, request, abort, current_app
from flask_login import login_required, current_user
from .. import db # Assuming your db instance is imported from the parent __init__
from ..models import User, Credentials, Organization, OrgApprovalStatus, UserRole # Ensure all are imported
from ..utils.decorators import admin_required # Use the decorator

# Assuming admin_bp is defined in admin/__init__.py
from . import admin_bp

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Admin dashboard."""
    try:
        # Ensure Organization model has 'approval_status' and 'requested_at'
        # Ensure OrgApprovalStatus enum has 'PENDING'
        pending_orgs = Organization.query.filter_by(approval_status=OrgApprovalStatus.PENDING)\
                                         .order_by(Organization.requested_at.desc()).all()

        # Ensure Credentials model has 'created_at'
        recent_users_creds = Credentials.query.order_by(Credentials.created_at.desc()).limit(5).all()

    except AttributeError as e:
        # This can happen if a model is missing an expected attribute (column)
        current_app.logger.error(f"Admin dashboard query error: Missing attribute - {e}")
        flash("Error loading dashboard data: A model attribute might be missing. Check server logs.", "danger")
        # Render a simpler dashboard or redirect to an error page
        pending_orgs = []
        recent_users_creds = []
        # return render_template('admin/dashboard_error.html', error_message=str(e)) # Or similar

    except Exception as e:
        # Catch other potential database query errors
        current_app.logger.error(f"Admin dashboard query error: {e}")
        flash(f"An unexpected error occurred while loading dashboard data: {e}", "danger")
        pending_orgs = []
        recent_users_creds = []

    return render_template('admin/dashboard.html',
                           title='Admin Dashboard',
                           pending_orgs=pending_orgs,
                           recent_users_creds=recent_users_creds) # Pass credentials list

@admin_bp.route('/organizations')
@login_required
@admin_required
def view_organizations():
    """List all organizations."""
    page = request.args.get('page', 1, type=int)
    # Assuming your app config has POSTS_PER_PAGE or use a default
    per_page = current_app.config.get('POSTS_PER_PAGE', 10)
    pagination = Organization.query.order_by(Organization.name.asc()).paginate(page=page, per_page=per_page, error_out=False)
    organizations = pagination.items
    return render_template('admin/view_organizations.html', title='Manage Organizations', organizations=organizations, pagination=pagination)

@admin_bp.route('/organizations/approve/<int:org_id>', methods=['POST'])
@login_required
@admin_required
def approve_organization(org_id):
    """Approve a pending organization."""
    org = Organization.query.get_or_404(org_id)
    if org.approval_status != OrgApprovalStatus.PENDING:
        flash('Organization is not pending approval.', 'warning')
        return redirect(url_for('admin.view_organizations'))

    try:
        org.approval_status = OrgApprovalStatus.APPROVED
        org.approved_at = db.func.now() # Use DB function for timestamp

        # **MODIFICATION HERE:** current_user is Credentials, linked to User via 'user' relationship
        if current_user.user: # Ensure the admin's Credentials record is linked to a User record
            org.approved_by_admin_id = current_user.user.id # ID of the admin's User record
        else:
            # This case should ideally not happen for a logged-in admin if data is consistent
            current_app.logger.warning(f"Admin '{current_user.username}' (Credentials ID: {current_user.id}) performing approval has no associated User record.")
            # Decide on fallback: org.approved_by_admin_id = None or raise error/flash message

        # Activate the org admin user if they weren't already
        # This assumes Organization has an 'admin_user' relationship to a User model,
        # and User has a 'credentials' backref to the Credentials model.
        if org.admin_user and org.admin_user.credentials:
            org.admin_user.credentials.is_active = True
        db.session.commit()
        flash(f'Organization "{org.name}" approved successfully.', 'success')
        # TODO: Send notification email to org admin
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error approving organization {org_id}: {e}")
        flash(f'Error approving organization: {e}', 'danger')

    return redirect(request.referrer or url_for('admin.dashboard'))


@admin_bp.route('/organizations/reject/<int:org_id>', methods=['POST'])
@login_required
@admin_required
def reject_organization(org_id):
    """Reject a pending organization."""
    org = Organization.query.get_or_404(org_id)
    if org.approval_status != OrgApprovalStatus.PENDING:
        flash('Organization is not pending approval.', 'warning')
        return redirect(url_for('admin.view_organizations'))

    try:
        org.approval_status = OrgApprovalStatus.REJECTED
        # org.approved_at = None # Or some other logic for rejection timestamp/by
        # org.approved_by_admin_id = None
        # Optionally deactivate the associated admin user?
        if org.admin_user and org.admin_user.credentials:
            org.admin_user.credentials.is_active = False # Example: Deactivate org admin on rejection
        db.session.commit()
        flash(f'Organization "{org.name}" rejected.', 'info')
         # TODO: Send notification email to org admin
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error rejecting organization {org_id}: {e}")
        flash(f'Error rejecting organization: {e}', 'danger')

    return redirect(request.referrer or url_for('admin.dashboard'))


@admin_bp.route('/users')
@login_required
@admin_required
def view_users():
    """List all users (credentials)."""
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('POSTS_PER_PAGE', 15)
    # Order by username for consistency
    pagination = Credentials.query.order_by(Credentials.username.asc()).paginate(page=page, per_page=per_page, error_out=False)
    user_credentials_list = pagination.items # Renamed to avoid conflict with a 'users' variable if used elsewhere
    return render_template('admin/view_users.html', title='Manage Users', user_credentials_list=user_credentials_list, pagination=pagination)

# File: CodeQuizHub/admin/routes.py
# ... (other imports and routes) ...

@admin_bp.route('/organizations/details/<int:org_id>') # Or just /organizations/<int:org_id>
@login_required
@admin_required
def view_organization_details(org_id):
    org = Organization.query.get_or_404(org_id)
    # You might want to fetch related data, e.g., members of the org, quizzes by the org, etc.
    # org_members = User.query.filter_by(organization_id=org.id).all()
    return render_template('admin/organization_details.html', title=f"Details for {org.name}", organization=org)


@admin_bp.route('/users/toggle_active/<int:creds_id>', methods=['POST'])
@login_required
@admin_required
def toggle_user_active(creds_id):
    creds_to_toggle = Credentials.query.get_or_404(creds_id) # Renamed to avoid confusion with current_user

    if creds_to_toggle.id == current_user.id: # current_user is the admin's Credentials
         flash("You cannot deactivate your own account.", "danger")
         return redirect(url_for('admin.view_users'))
    try:
        creds_to_toggle.is_active = not creds_to_toggle.is_active
        db.session.commit()
        status = "activated" if creds_to_toggle.is_active else "deactivated"
        flash(f"User '{creds_to_toggle.username}' has been {status}.", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating user status for {creds_to_toggle.username}: {e}")
        flash(f"Error updating user status: {e}", "danger")
    return redirect(url_for('admin.view_users'))

# Add other admin routes as needed (view user details, edit roles, site settings, etc.)