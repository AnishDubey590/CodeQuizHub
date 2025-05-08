# File: CodeQuizHub/admin/routes.py
from flask import (
    Blueprint, render_template, flash, redirect, url_for, request, abort, current_app
)
from flask_login import login_required, current_user
from .. import db  # Assuming your db instance is imported from the parent __init__
from ..models import (
    User, Credentials, Organization, OrgApprovalStatus, UserRole
) # Ensure all necessary models and enums are imported
from ..utils.decorators import admin_required  # Your custom admin decorator

# Import the blueprint object defined in CodeQuizHub/admin/__init__.py
from . import admin_bp
# Import forms defined for the admin blueprint
from .forms import OrgApprovalForm, UserActivationForm


@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Admin dashboard."""
    pending_orgs = []
    recent_users_creds = []
    approval_form = OrgApprovalForm() # Instantiate form for CSRF in template

    try:
        # Ensure Organization model has 'approval_status' and 'requested_at'
        # Ensure OrgApprovalStatus enum has 'PENDING'
        pending_orgs = Organization.query.filter_by(approval_status=OrgApprovalStatus.PENDING)\
                                         .order_by(Organization.requested_at.desc()).all()

        # Ensure Credentials model has 'created_at'
        recent_users_creds = Credentials.query.order_by(Credentials.created_at.desc()).limit(5).all()

    except AttributeError as e:
        current_app.logger.error(f"Admin dashboard query error: Missing attribute - {e}")
        flash("Error loading dashboard data: A model attribute might be missing. Check server logs.", "danger")
    except Exception as e:
        current_app.logger.error(f"Admin dashboard query error: {e}")
        flash(f"An unexpected error occurred while loading dashboard data: {e}", "danger")

    return render_template('admin/dashboard.html',
                           title='Admin Dashboard',
                           pending_orgs=pending_orgs,
                           recent_users_creds=recent_users_creds,
                           approval_form=approval_form) # Pass the form for CSRF

@admin_bp.route('/organizations')
@login_required
@admin_required
def view_organizations():
    """List all organizations with pagination."""
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('ADMIN_ITEMS_PER_PAGE', 10) # Use a config value or default
    
    organizations_query = Organization.query.order_by(Organization.name.asc())
    pagination = organizations_query.paginate(page=page, per_page=per_page, error_out=False)
    organizations = pagination.items
    
    approval_form = OrgApprovalForm() # Form for CSRF tokens on this page as well

    return render_template('admin/view_organizations.html',
                           title='Manage Organizations',
                           organizations=organizations,
                           pagination=pagination,
                           approval_form=approval_form) # Pass form for CSRF

@admin_bp.route('/organizations/approve/<int:org_id>', methods=['POST'])
@login_required
@admin_required
def approve_organization(org_id):
    """Approve a pending organization."""
    org = Organization.query.get_or_404(org_id)
    if org.approval_status != OrgApprovalStatus.PENDING:
        flash('Organization is not pending approval or has already been actioned.', 'warning')
        return redirect(url_for('admin.view_organizations'))

    try:
        org.approval_status = OrgApprovalStatus.APPROVED
        org.approved_at = db.func.now()
        if current_user.user: # current_user is Credentials, user is the User model instance
            org.approved_by_admin_id = current_user.user.id
        else:
            current_app.logger.warning(f"Admin approval by Credentials ID {current_user.id} which has no linked User record for approved_by_admin_id.")
            # org.approved_by_admin_id = None # Or handle as an error

        # Activate the organization's primary admin user
        if org.admin_user and org.admin_user.credentials:
            org.admin_user.credentials.is_active = True
        
        db.session.commit()
        flash(f'Organization "{org.name}" approved successfully.', 'success')
        # TODO: Send notification email to org admin
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error approving organization {org_id}: {e}")
        flash(f'Error approving organization: {str(e)}', 'danger')

    return redirect(request.referrer or url_for('admin.dashboard'))


@admin_bp.route('/organizations/reject/<int:org_id>', methods=['POST'])
@login_required
@admin_required
def reject_organization(org_id):
    """Reject a pending organization."""
    org = Organization.query.get_or_404(org_id)
    if org.approval_status != OrgApprovalStatus.PENDING:
        flash('Organization is not pending approval or has already been actioned.', 'warning')
        return redirect(url_for('admin.view_organizations'))

    try:
        org.approval_status = OrgApprovalStatus.REJECTED
        # Optionally record who rejected and when
        # org.rejected_at = db.func.now()
        # if current_user.user:
        #     org.rejected_by_admin_id = current_user.user.id

        # Deactivate the organization's primary admin user upon rejection
        if org.admin_user and org.admin_user.credentials:
            org.admin_user.credentials.is_active = False
        
        db.session.commit()
        flash(f'Organization "{org.name}" rejected.', 'info')
        # TODO: Send notification email to org admin
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error rejecting organization {org_id}: {e}")
        flash(f'Error rejecting organization: {str(e)}', 'danger')

    return redirect(request.referrer or url_for('admin.dashboard'))


@admin_bp.route('/users')
@login_required
@admin_required
def view_users():
    """List all users (credentials) with pagination."""
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('ADMIN_ITEMS_PER_PAGE', 15) # Use a config value or default
    
    # Query Credentials, and join with User to be able to sort by email or display user details
    # Order by username for now
    credentials_query = Credentials.query.order_by(Credentials.username.asc())
    pagination = credentials_query.paginate(page=page, per_page=per_page, error_out=False)
    user_credentials_list = pagination.items
    
    activation_form = UserActivationForm() # Form for CSRF tokens on this page

    return render_template('admin/view_users.html',
                           title='Manage Users',
                           user_credentials_list=user_credentials_list,
                           pagination=pagination,
                           activation_form=activation_form) # Pass form for CSRF


@admin_bp.route('/users/toggle_active/<int:creds_id>', methods=['POST'])
@login_required
@admin_required
def toggle_user_active(creds_id):
    """Toggle the active status of a user's credentials."""
    creds_to_toggle = Credentials.query.get_or_404(creds_id)

    if creds_to_toggle.id == current_user.id:
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
        flash(f"Error updating user status: {str(e)}", "danger")
    return redirect(url_for('admin.view_users'))

# TODO:
# - Route to view individual organization details (admin.view_organization_details)
# - Route to view individual user details (admin.view_user_details)
# - Route to edit user roles
# - Potentially delete users/organizations (with care and confirmation)
# - Site settings page