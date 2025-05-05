# /your_app/admin/routes.py
from flask import Blueprint, render_template, flash, redirect, url_for, request, abort
from flask_login import login_required, current_user
from .. import db
from ..models import User, Credentials, Organization, OrgApprovalStatus, UserRole
from ..utils.decorators import admin_required # Use the decorator

# Assuming admin_bp is defined in admin/__init__.py
from . import admin_bp

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Admin dashboard."""
    pending_orgs = Organization.query.filter_by(approval_status=OrgApprovalStatus.PENDING).order_by(Organization.requested_at.desc()).all()
    recent_users = Credentials.query.order_by(Credentials.created_at.desc()).limit(5).all()
    return render_template('admin/dashboard.html', title='Admin Dashboard', pending_orgs=pending_orgs, recent_users=recent_users)

@admin_bp.route('/organizations')
@login_required
@admin_required
def view_organizations():
    """List all organizations."""
    page = request.args.get('page', 1, type=int)
    # TODO: Replace with Config value POSTS_PER_PAGE
    pagination = Organization.query.order_by(Organization.name).paginate(page=page, per_page=10, error_out=False)
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
        org.approved_by_admin_id = current_user.user_profile.id # Link approver's PROFILE ID
        # Activate the org admin user if they weren't already
        if org.admin_user and org.admin_user.credentials:
            org.admin_user.credentials.is_active = True
        db.session.commit()
        flash(f'Organization "{org.name}" approved successfully.', 'success')
        # TODO: Send notification email to org admin
    except Exception as e:
        db.session.rollback()
        flash(f'Error approving organization: {e}', 'danger')

    # Redirect back to pending list or main list?
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
        # Optionally deactivate the associated admin user?
        # if org.admin_user and org.admin_user.credentials:
        #     org.admin_user.credentials.is_active = False
        db.session.commit()
        flash(f'Organization "{org.name}" rejected.', 'info')
         # TODO: Send notification email to org admin
    except Exception as e:
        db.session.rollback()
        flash(f'Error rejecting organization: {e}', 'danger')

    return redirect(request.referrer or url_for('admin.dashboard'))


@admin_bp.route('/users')
@login_required
@admin_required
def view_users():
    """List all users (credentials)."""
    page = request.args.get('page', 1, type=int)
    # TODO: Add filtering/searching
    pagination = Credentials.query.order_by(Credentials.username).paginate(page=page, per_page=15, error_out=False)
    user_credentials = pagination.items
    return render_template('admin/view_users.html', title='Manage Users', users=user_credentials, pagination=pagination)

# TODO: Routes for activating/deactivating users, changing roles, viewing profiles etc.
# Example:
@admin_bp.route('/users/toggle_active/<int:creds_id>', methods=['POST'])
@login_required
@admin_required
def toggle_user_active(creds_id):
    creds = Credentials.query.get_or_404(creds_id)
    # Prevent admin from deactivating themselves?
    if creds.id == current_user.id:
         flash("You cannot deactivate your own account.", "danger")
         return redirect(url_for('admin.view_users'))
    try:
        creds.is_active = not creds.is_active
        db.session.commit()
        status = "activated" if creds.is_active else "deactivated"
        flash(f"User '{creds.username}' has been {status}.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating user status: {e}", "danger")
    return redirect(url_for('admin.view_users'))

# TODO: Route to view/edit user profile details as admin
# TODO: Route to potentially delete users (handle consequences carefully)