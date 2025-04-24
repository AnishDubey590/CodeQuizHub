# your_app/admin/routes.py
from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from ..models import db, User, Organization, UserRole, OrgApprovalStatus
# from ..decorators import admin_required # Optional: use decorator later

admin_bp = Blueprint('admin',
                     __name__,
                     url_prefix='/admin',
                     template_folder='../templates/admin')

@admin_bp.route('/dashboard')
@login_required
# @admin_required # Uncomment when decorator is implemented
def dashboard():
    # --- Manual Role Check (if not using decorator) ---
    if current_user.role != UserRole.ADMIN:
        flash('Admin access required.', 'danger')
        return redirect(url_for('main.dashboard')) # Redirect to dispatcher
    # --- End Manual Role Check ---

    # Fetch data for Admin Dashboard
    pending_org_count = Organization.query.filter_by(approval_status=OrgApprovalStatus.PENDING).count()
    approved_org_count = Organization.query.filter_by(approval_status=OrgApprovalStatus.APPROVED).count()
    total_user_count = User.query.count()
    # Add more stats as needed

    return render_template('dashboard.html',
                           pending_org_count=pending_org_count,
                           approved_org_count=approved_org_count,
                           total_user_count=total_user_count)

@admin_bp.route('/organizations')
@login_required
# @admin_required
def manage_organizations():
    if current_user.role != UserRole.ADMIN:
        flash('Admin access required.', 'danger')
        return redirect(url_for('main.dashboard'))

    orgs = Organization.query.order_by(Organization.requested_at.desc()).all()
    return render_template('manage_organizations.html', organizations=orgs) # Need this template

# TODO: Add routes for approving/rejecting orgs, managing users, viewing platform analytics etc.
# Example:
# @admin_bp.route('/organizations/approve/<int:org_id>', methods=['POST'])
# @login_required
# @admin_required
# def approve_organization(org_id): ...