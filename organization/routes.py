# /your_app/organization/routes.py
from flask import Blueprint, render_template, flash, redirect, url_for, request, abort, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import pandas as pd
from datetime import datetime, timezone
from secrets import token_urlsafe

from .. import db, mail
from ..models import (
    User, Credentials, Organization, UserRole, OrganizationInvitation,
    InvitationStatus, Quiz, Question
)
from ..utils.decorators import organization_required, is_organization_admin
# Corrected Import:
from ..auth.forms import InviteUserForm  # Import from the auth blueprint's forms
from .forms import BulkInviteForm        # Import BulkInviteForm from the local org forms# from ..utils.email import send_invitation_email # TODO: Implement email sending
# from ..utils.tokens import generate_token # TODO: Implement token generation

# Assuming org_bp is defined in organization/__init__.py
from . import org_bp

@org_bp.route('/dashboard')
@login_required
@organization_required
def dashboard():
    """Organization Admin Dashboard."""
    # Organization admin's profile is current_user.user_profile
    org = current_user.user_profile.managed_organization
    if not org:
        # This case might happen if the org was deleted or link broken, but shouldn't normally
        flash("Organization not found for your account.", "danger")
        return redirect(url_for('auth.logout')) # Log out potentially

    # Fetch some stats for the dashboard
    member_count = User.query.filter_by(organization_id=org.id).count()
    teacher_count = User.query.join(Credentials).filter(User.organization_id == org.id, Credentials.role == UserRole.TEACHER).count()
    student_count = User.query.join(Credentials).filter(User.organization_id == org.id, Credentials.role == UserRole.STUDENT).count()
    quiz_count = Quiz.query.filter_by(organization_id=org.id).count()
    pending_invites = OrganizationInvitation.query.filter_by(organization_id=org.id, status=InvitationStatus.PENDING).count()

    return render_template('organization/dashboard.html',
                           title=f"{org.name} Dashboard",
                           org=org,
                           member_count=member_count,
                           teacher_count=teacher_count,
                           student_count=student_count,
                           quiz_count=quiz_count,
                           pending_invites=pending_invites)


@org_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
@organization_required
def edit_org_profile():
    """Edit Organization Profile details."""
    org = current_user.user_profile.managed_organization
    if not org:
         abort(404)
    # TODO: Create OrgProfileEditForm
    # form = OrgProfileEditForm(obj=org)
    form = None # Placeholder
    # if form.validate_on_submit():
    #     try:
    #         org.name = form.name.data # Careful with name changes if used elsewhere heavily
    #         org.description = form.description.data
    #         org.website_url = form.website_url.data
    #         # Handle logo upload
    #         db.session.commit()
    #         flash('Organization profile updated.', 'success')
    #         return redirect(url_for('.dashboard'))
    #     except Exception as e:
    #         db.session.rollback()
    #         flash(f'Error updating profile: {e}', 'danger')
    return render_template('organization/edit_profile.html', title="Edit Organization Profile", form=form, org=org)


@org_bp.route('/members')
@login_required
@organization_required
def manage_members():
    """View and manage organization members (Teachers & Students)."""
    org = current_user.user_profile.managed_organization
    if not org: abort(404)

    page = request.args.get('page', 1, type=int)
    # Query users belonging to this org, join with credentials to get role/status
    pagination = User.query.join(Credentials, User.credentials_id == Credentials.id)\
        .filter(User.organization_id == org.id)\
        .order_by(Credentials.role, User.display_name)\
        .paginate(page=page, per_page=15, error_out=False)
    members = pagination.items

    invite_form = InviteUserForm() # For single invite form on page

    return render_template('organization/manage_members.html',
                           title="Manage Members",
                           org=org,
                           members=members,
                           pagination=pagination,
                           invite_form=invite_form)


@org_bp.route('/members/invite', methods=['POST'])
@login_required
@organization_required
def invite_member():
    """Handle single user invitation."""
    org = current_user.user_profile.managed_organization
    if not org: abort(403)

    form = InviteUserForm()
    if form.validate_on_submit():
        email = form.email.data
        role_value = form.role.data
        role = UserRole(role_value) # Convert string back to Enum

        # Check if user with this email already exists and is in *this* org
        existing_member = User.query.filter_by(email=email, organization_id=org.id).first()
        if existing_member:
            flash(f"{email} is already a member of this organization.", 'warning')
            return redirect(url_for('.manage_members'))

        # Check if there's already a pending invitation for this email to this org
        existing_invitation = OrganizationInvitation.query.filter_by(
            organization_id=org.id,
            invitee_email=email,
            status=InvitationStatus.PENDING
        ).first()
        if existing_invitation:
            flash(f"An invitation has already been sent to {email} and is pending.", 'warning')
            # Optionally resend? Or just inform admin.
            return redirect(url_for('.manage_members'))

        try:
            token = token_urlsafe(32) # Generate a secure random token
            invite = OrganizationInvitation(
                organization_id=org.id,
                invitee_email=email,
                inviter_user_id=current_user.user_profile.id,
                invited_as_role=role,
                invitation_token=token,
                status=InvitationStatus.PENDING,
                # expires_at is set by default in model
            )
            db.session.add(invite)
            db.session.commit()

            # TODO: Send invitation email using Flask-Mail
            # invitation_link = url_for('auth.accept_invitation', token=token, _external=True)
            # send_invitation_email(recipient=email, inviter_name=current_user.user_profile.display_name or current_user.username, org_name=org.name, role_name=role.value, link=invitation_link)

            flash(f"Invitation sent successfully to {email}.", 'success')

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error sending invitation for {email} to org {org.id}: {e}")
            flash('An error occurred while sending the invitation.', 'danger')

    else:
        # Form validation failed - flash errors (WTForms does this by default through template)
        flash('Please correct the errors in the invitation form.', 'warning') # Generic message

    return redirect(url_for('.manage_members')) # Redirect back anyway


@org_bp.route('/members/bulk_invite', methods=['GET', 'POST'])
@login_required
@organization_required
def bulk_invite_members():
    """Handle bulk user invitation via CSV/Excel upload."""
    org = current_user.user_profile.managed_organization
    if not org: abort(403)

    # TODO: Create BulkInviteForm with FileField
    # form = BulkInviteForm()
    form = None # Placeholder

    # if form.validate_on_submit():
    #     file = form.file.data
    #     filename = secure_filename(file.filename)
    #     # TODO: Save file temporarily or process in memory
    #     # filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    #     # file.save(filepath)

    #     invited_count = 0
    #     skipped_count = 0
    #     error_count = 0
    #     processed_emails = set() # Track emails in the current file

    #     try:
    #         # Use pandas to read CSV or Excel
    #         if filename.endswith('.csv'):
    #             df = pd.read_csv(file.stream) # Read directly from stream
    #         elif filename.endswith(('.xls', '.xlsx')):
    #             df = pd.read_excel(file.stream)
    #         else:
    #             flash('Invalid file type. Please upload CSV or Excel.', 'danger')
    #             return redirect(url_for('.manage_members'))

    #         # EXPECTED COLUMNS: 'email', 'role' (optional 'student_code'?)
    #         if 'email' not in df.columns or 'role' not in df.columns:
    #             flash("CSV/Excel must contain 'email' and 'role' columns.", 'danger')
    #             return redirect(url_for('.manage_members'))

    #         for index, row in df.iterrows():
    #             email = str(row['email']).strip().lower()
    #             role_str = str(row['role']).strip().capitalize()

    #             # Basic validation
    #             if not email or not role_str:
    #                 skipped_count += 1
    #                 continue # Skip rows with missing data

    #             if email in processed_emails:
    #                  skipped_count +=1 # Avoid duplicate processing within the file
    #                  continue
    #             processed_emails.add(email)

    #             try:
    #                 role = UserRole(role_str)
    #                 if role not in [UserRole.TEACHER, UserRole.STUDENT]:
    #                      raise ValueError("Invalid role for invitation")
    #             except ValueError:
    #                 skipped_count += 1 # Skip invalid roles
    #                 continue

    #             # Check existing members / pending invites (similar to single invite)
    #             if User.query.filter_by(email=email, organization_id=org.id).first() or \
    #                OrganizationInvitation.query.filter_by(invitee_email=email, organization_id=org.id, status=InvitationStatus.PENDING).first():
    #                 skipped_count += 1
    #                 continue

    #             # Create invitation record
    #             try:
    #                 token = token_urlsafe(32)
    #                 invite = OrganizationInvitation(
    #                     organization_id=org.id,
    #                     invitee_email=email,
    #                     inviter_user_id=current_user.user_profile.id,
    #                     invited_as_role=role,
    #                     invitation_token=token,
    #                     status=InvitationStatus.PENDING
    #                 )
    #                 db.session.add(invite)
    #                 invited_count += 1

    #                 # TODO: Queue email sending for bulk invites rather than sending synchronously
    #                 # invitation_link = url_for('auth.accept_invitation', token=token, _external=True)
    #                 # send_invitation_email(...)


    #             except Exception as inner_e:
    #                 error_count += 1
    #                 db.session.rollback() # Rollback only this specific invite on error
    #                 current_app.logger.error(f"Error creating bulk invite for {email}: {inner_e}")
    #                 # Continue to next row

    #         db.session.commit() # Commit all successful invites
    #         flash(f"Bulk invite processed: {invited_count} invitations sent, {skipped_count} skipped, {error_count} errors.", 'info')

    #     except Exception as e:
    #         db.session.rollback()
    #         current_app.logger.error(f"Error processing bulk invite file {filename}: {e}")
    #         flash('An error occurred processing the bulk invite file.', 'danger')

    #     # TODO: Delete temporary file if saved
    #     # if os.path.exists(filepath): os.remove(filepath)

    #     return redirect(url_for('.manage_members'))
    # else:
    #     # GET request or form validation failed
    #     pass # Render the template below

    # TODO: Create template for bulk invite upload form
    return render_template('organization/bulk_invite.html', title="Bulk Invite Members", form=form, org=org)


@org_bp.route('/invitations')
@login_required
@organization_required
def view_invitations():
     """View pending/past invitations for the organization."""
     org = current_user.user_profile.managed_organization
     if not org: abort(404)
     # TODO: Implement query and template to show invitations
     invitations = OrganizationInvitation.query.filter_by(organization_id=org.id)\
         .order_by(OrganizationInvitation.created_at.desc()).all()
     return render_template('organization/view_invitations.html', title="View Invitations", invitations=invitations, org=org)


@org_bp.route('/invitations/cancel/<int:invite_id>', methods=['POST'])
@login_required
@organization_required
def cancel_invitation(invite_id):
    """Cancel a pending invitation."""
    org = current_user.user_profile.managed_organization
    if not org: abort(403)

    invite = OrganizationInvitation.query.filter_by(id=invite_id, organization_id=org.id).first_or_404()

    if invite.status != InvitationStatus.PENDING:
        flash('This invitation is not pending and cannot be cancelled.', 'warning')
    else:
        try:
            # Could delete, or just mark as cancelled/revoked
            db.session.delete(invite)
            # invite.status = InvitationStatus.REVOKED # If adding a Revoked status
            db.session.commit()
            flash(f'Invitation for {invite.invitee_email} cancelled.', 'success')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error cancelling invitation {invite_id}: {e}")
            flash('An error occurred while cancelling the invitation.', 'danger')

    return redirect(url_for('.view_invitations'))


# --- Quiz and Question Management (Placeholders) ---

@org_bp.route('/quizzes')
@login_required
@organization_required
def manage_quizzes():
     org = current_user.user_profile.managed_organization
     if not org: abort(404)
     # TODO: Query quizzes created by the Org Admin *OR* Teachers within this Org
     quizzes = Quiz.query.filter_by(organization_id=org.id).order_by(Quiz.created_at.desc()).all()
     return render_template('organization/manage_quizzes.html', title="Manage Organization Quizzes", quizzes=quizzes, org=org)

@org_bp.route('/questions')
@login_required
@organization_required
def manage_questions():
     org = current_user.user_profile.managed_organization
     if not org: abort(404)
     # TODO: Query questions created by the Org Admin *OR* Teachers within this Org
     # Might need pagination
     questions = Question.query.filter_by(organization_id=org.id).order_by(Question.created_at.desc()).all()
     return render_template('organization/manage_questions.html', title="Manage Organization Questions", questions=questions, org=org)


# TODO: Add routes for Org Admin to view analytics/results across the whole org