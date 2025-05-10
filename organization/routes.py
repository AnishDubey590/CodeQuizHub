# File: CodeQuizHub/organization/routes.py
from flask import Blueprint, render_template, flash, redirect, url_for, request, abort, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import pandas as pd
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_ # For OR conditions in SQLAlchemy queries
from .. import db
from ..models import (
    User, Credentials, Organization, UserRole, OrganizationInvitation,
    InvitationStatus, Quiz, Question, QuizStatus # Ensured all are here
)
from ..utils.decorators import organization_required # Assuming this checks role and org approval
# Import utilities
from ..utils.email import send_invitation_email # Assuming this exists and is configured
from ..utils.tokens import generate_token # Assuming this exists

# Import forms from THIS blueprint's forms.py
from .forms import InviteUserForm, BulkUserCreateForm, OrgProfileEditForm, CreateOrgUserForm
# Import OrgApprovalForm from ADMIN forms for the cancel_invitation CSRF
from ..admin.forms import OrgApprovalForm as CancelActionCSRFForm # Alias for clarity

from . import org_bp

# --- Helper function to get current user's organization ---
def get_current_org():
    """Gets the organization for the current user (Org Admin or Teacher/Student)."""
    org = None
    if current_user.is_authenticated and current_user.user_profile:
        if current_user.role == UserRole.ORGANIZATION:
            org = current_user.user_profile.managed_organization
        elif current_user.user_profile.organization: # For teachers/students linked to an org
            org = current_user.user_profile.organization
    return org

# --- Dashboard ---
@org_bp.route('/dashboard')
@login_required
@organization_required
def dashboard():
    org = get_current_org()
    if not org:
        flash("Organization details not found for your account.", "danger")
        return redirect(url_for('main.index'))

    try:
        member_query = User.query.filter_by(organization_id=org.id)
        member_count = member_query.count()
        # Correctly filter teacher/student counts by organization_id
        teacher_count = User.query.join(Credentials, User.credentials_id == Credentials.id)\
            .filter(User.organization_id == org.id, Credentials.role == UserRole.TEACHER).count()
        student_count = User.query.join(Credentials, User.credentials_id == Credentials.id)\
            .filter(User.organization_id == org.id, Credentials.role == UserRole.STUDENT).count()

        quiz_count = Quiz.query.filter_by(organization_id=org.id).count()
        published_quiz_count = Quiz.query.filter_by(organization_id=org.id, status=QuizStatus.PUBLISHED).count()
        pending_invites = OrganizationInvitation.query.filter_by(organization_id=org.id, status=InvitationStatus.PENDING).count()
    except Exception as e:
        current_app.logger.error(f"Error loading dashboard stats for org {org.id if org else 'N/A'}: {e}")
        flash("Could not load all dashboard statistics.", "warning")
        member_count = teacher_count = student_count = quiz_count = published_quiz_count = pending_invites = "Error"


    return render_template('organization/dashboard.html',
                           title=f"{org.name} Dashboard",
                           org=org,
                           member_count=member_count,
                           teacher_count=teacher_count,
                           student_count=student_count,
                           quiz_count=quiz_count,
                           published_quiz_count=published_quiz_count,
                           pending_invites=pending_invites)

# --- Organization Profile ---
@org_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
@organization_required
def edit_org_profile():
    if current_user.role != UserRole.ORGANIZATION:
         abort(403, "Only organization administrators can edit the organization profile.")

    org = current_user.user_profile.managed_organization
    if not org:
         flash("Could not find the organization you manage.", "danger")
         return redirect(url_for('.dashboard'))

    form = OrgProfileEditForm(obj=org)
    if form.validate_on_submit():
        name_check = Organization.query.filter(
            Organization.id != org.id,
            Organization.name.ilike(form.name.data) # Case-insensitive check
        ).first()
        if name_check:
             form.name.errors.append("An organization with this name already exists.")
        else:
            try:
                org.name = form.name.data
                org.description = form.description.data
                org.website_url = form.website_url.data
                # TODO: Implement logo upload:
                # if form.logo.data:
                #     filename = secure_filename(form.logo.data.filename)
                #     # Save file to a configured upload folder
                #     # org.logo_url = path_to_saved_logo
                db.session.commit()
                flash('Organization profile updated successfully.', 'success')
                return redirect(url_for('.dashboard'))
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error updating org profile for {org.id}: {e}")
                flash(f'Error updating organization profile: {str(e)}', 'danger')
    elif request.method == 'POST': # Catches validation errors not caught by WTForms by default if form.errors is not checked
        flash('Please correct the errors below.', 'danger')


    return render_template('organization/edit_profile.html', title="Edit Organization Profile", form=form, org=org)


# --- Member Management ---
@org_bp.route('/members')
@login_required
@organization_required # Org Admins and Teachers can view members
def manage_members():
    org = get_current_org()
    if not org: abort(404, "Organization not found for your account.")

    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('ITEMS_PER_PAGE', 15)
    q = request.args.get('q', '')
    role_filter = request.args.get('role', '')
    active_filter = request.args.get('active_filter', '') # For Credentials.is_active

    # Query users belonging to this org, join Credentials
    member_query = User.query.join(Credentials, User.credentials_id == Credentials.id)\
        .filter(User.organization_id == org.id)

    if q:
        search = f'%{q}%'
        member_query = member_query.filter(
            or_(User.display_name.ilike(search), User.email.ilike(search), Credentials.username.ilike(search))
        )
    if role_filter and hasattr(UserRole, role_filter.upper()):
        member_query = member_query.filter(Credentials.role == UserRole[role_filter.upper()])
    if active_filter in ['true', 'false']:
        member_query = member_query.filter(Credentials.is_active == (active_filter == 'true'))


    pagination = member_query.order_by(Credentials.role.asc(), User.display_name.asc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    members = pagination.items

    invite_form = InviteUserForm()
    create_user_form = CreateOrgUserForm() # Form for creating single user
    # activation_form is from admin.forms, used for toggling by admin, org admin may not have this permission directly
    # If org admin CAN toggle active status, then a form is needed here. For now, assume admin handles this.

    return render_template('organization/manage_members.html',
                           title="Manage Members",
                           org=org,
                           members=members,
                           pagination=pagination,
                           invite_form=invite_form,
                           create_user_form=create_user_form,
                           q=q,
                           role_filter=role_filter,
                           active_filter=active_filter, # Pass for filter persistence
                           UserRole=UserRole) # For dropdown


# --- Organization Admin: Create Single Teacher/Student Account ---
@org_bp.route('/members/create', methods=['POST']) # Usually from a modal
@login_required
@organization_required
def create_org_member():
    if current_user.role != UserRole.ORGANIZATION:
        abort(403, "Only organization administrators can directly create member accounts.")

    org = current_user.user_profile.managed_organization
    if not org:
        abort(403, "Organization not found to add member to.")

    form = CreateOrgUserForm() # This form will be submitted from the modal
    if form.validate_on_submit():
        try:
            username = form.username.data.strip()
            email = form.email.data.lower().strip()
            role_enum = UserRole[form.role.data] # Role comes as string 'TEACHER' or 'STUDENT'

            # Create Credentials
            new_credentials = Credentials(
                username=username,
                role=role_enum,
                is_active=True # New users active by default
            )
            new_credentials.set_password(form.password.data)
            db.session.add(new_credentials)
            db.session.flush() # Get ID for new_credentials

            # Create User (Profile) and link it
            new_user_profile = User(
                credentials_id=new_credentials.id,
                email=email,
                display_name=form.display_name.data.strip() or username,
                organization_id=org.id,
                student_code=form.student_code.data.strip() if role_enum == UserRole.STUDENT and form.student_code.data else None,
                enrollment_date=datetime.now(timezone.utc)
            )
            db.session.add(new_user_profile)
            db.session.commit()
            flash(f'{role_enum.value} account for "{username}" created successfully!', 'success')
        except IntegrityError as e:
            db.session.rollback()
            current_app.logger.error(f"Integrity error creating org user for org {org.id}: {e}")
            # Check which constraint failed. form.validate_username/email should catch most.
            flash("A user with that username or email already exists.", 'danger')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating org user for org {org.id}: {e}")
            flash(f"An unexpected error occurred: {str(e)}", 'danger')
    else:
        # Flash form errors if modal submission fails validation
        for fieldName, errorMessages in form.errors.items():
            for err in errorMessages:
                flash(f"Error in {getattr(form, fieldName).label.text}: {err}", 'danger')
    return redirect(url_for('.manage_members'))


# --- Organization Admin: Bulk Create Teacher/Student Accounts ---
@org_bp.route('/members/bulk_create', methods=['GET', 'POST'])
@login_required
@organization_required
def bulk_create_members():
    if current_user.role != UserRole.ORGANIZATION:
        abort(403, "Only organization administrators can bulk create accounts.")
    org = current_user.user_profile.managed_organization
    if not org: abort(403)

    form = BulkUserCreateForm()
    if form.validate_on_submit():
        file = form.file.data
        filename = secure_filename(file.filename)
        results_summary = [] # To store messages for each row

        try:
            df = None
            if filename.endswith('.csv'): df = pd.read_csv(file.stream)
            elif filename.endswith(('.xls', '.xlsx')): df = pd.read_excel(file.stream, engine='openpyxl')
            else:
                flash('Invalid file type. Please upload CSV or Excel.', 'danger')
                return redirect(url_for('.bulk_create_members'))

            required_cols = ['username', 'email', 'password', 'role']
            if not all(col in df.columns for col in required_cols):
                flash(f"File must contain columns: {', '.join(required_cols)}.", 'danger')
                return redirect(url_for('.bulk_create_members'))

            created_count = 0
            for index, row in df.iterrows():
                username = str(row.get('username', '')).strip()
                email = str(row.get('email', '')).strip().lower()
                password = str(row.get('password', '')) # Password must be present
                role_str = str(row.get('role', '')).strip().upper()
                display_name = str(row.get('display_name', '')).strip() or username
                student_code = str(row.get('student_code', '')).strip() or None

                if not (username and email and password and role_str):
                    results_summary.append(f"Row {index+2}: Skipped - Missing required data.")
                    continue
                try:
                    if role_str not in UserRole._member_names_: raise ValueError("Invalid role string")
                    role_enum = UserRole[role_str]
                    if role_enum not in [UserRole.TEACHER, UserRole.STUDENT]:
                        raise ValueError("Role must be Teacher or Student.")
                except ValueError as ve:
                    results_summary.append(f"Row {index+2} ({username}): Skipped - Invalid role '{row.get('role', '')}'.")
                    continue

                if Credentials.query.filter_by(username=username).first() or \
                   User.query.filter_by(email=email).first():
                    results_summary.append(f"Row {index+2} ({username}): Skipped - Username or email already exists.")
                    continue

                try:
                    new_credentials = Credentials(username=username, role=role_enum, is_active=True)
                    new_credentials.set_password(password)
                    db.session.add(new_credentials)
                    db.session.flush()

                    new_user_profile = User(
                        credentials_id=new_credentials.id, email=email, display_name=display_name,
                        organization_id=org.id,
                        student_code=student_code if role_enum == UserRole.STUDENT else None,
                        enrollment_date=datetime.now(timezone.utc)
                    )
                    db.session.add(new_user_profile)
                    # Batch commits are better, but for row-by-row feedback, flush might be an option
                    # For now, will commit at the end. If one fails, all in this batch fail unless handled per row.
                    created_count += 1
                    results_summary.append(f"Row {index+2} ({username}): Account queued for creation.")
                except Exception as e_create:
                    db.session.rollback() # Rollback the single failed user
                    results_summary.append(f"Row {index+2} ({username}): Error - {str(e_create)}")
                    current_app.logger.error(f"Bulk create error for {username}: {e_create}")
            
            db.session.commit() # Commit all successfully processed users
            flash(f"Bulk creation processed: {created_count} accounts successfully created.", "success")
            # For more detailed feedback, you could store results_summary in session or pass to a results page
            for summary_msg in results_summary:
                if "Error" in summary_msg or "Skipped" in summary_msg and "queued" not in summary_msg :
                     flash(summary_msg, "warning") # Use flash for each error/skip

        except pd.errors.EmptyDataError:
             flash("The uploaded file is empty.", "warning")
        except Exception as e_file:
            db.session.rollback()
            current_app.logger.error(f"Error processing bulk create file '{filename}': {e_file}")
            flash(f'An error occurred processing the file: {str(e_file)}', 'danger')
        return redirect(url_for('.manage_members'))

    return render_template('organization/bulk_create.html', title="Bulk Create Member Accounts", form=form, org=org)


# --- Invitations (Your Existing Logic - ensure forms and utils are correctly imported) ---
@org_bp.route('/members/invite', methods=['POST'])
@login_required
@organization_required
def invite_member():
    if current_user.role != UserRole.ORGANIZATION: abort(403)
    org = current_user.user_profile.managed_organization
    if not org: abort(403, "Cannot find organization to invite to.")
    form = InviteUserForm() # From .forms
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        role_name = form.role.data # This is the NAME (e.g., 'TEACHER')
        try:
            role = UserRole[role_name]
        except KeyError:
             flash("Invalid role selected for invitation.", "danger")
             return redirect(url_for('.manage_members'))

        existing_member = User.query.filter(User.email == email, User.organization_id == org.id).first()
        if existing_member:
            flash(f"'{email}' is already a member of {org.name}.", 'warning')
            return redirect(url_for('.manage_members'))
        existing_invitation = OrganizationInvitation.query.filter_by(
            organization_id=org.id, invitee_email=email, status=InvitationStatus.PENDING).first()
        if existing_invitation:
            flash(f"An invitation is already pending for '{email}'.", 'warning')
            return redirect(url_for('.manage_members'))
        try:
            token = generate_token() # from ..utils.tokens
            invite = OrganizationInvitation(
                organization_id=org.id, invitee_email=email,
                inviter_user_id=current_user.user_profile.id,
                invited_as_role=role, invitation_token=token,
                status=InvitationStatus.PENDING
            )
            db.session.add(invite)
            db.session.commit()
            try:
                invitation_link = url_for('auth.accept_invitation', token=token, _external=True)
                inviter_display_name = current_user.user_profile.display_name or current_user.username
                send_invitation_email( # from ..utils.email
                    recipient=email, inviter_name=inviter_display_name,
                    org_name=org.name, role_name=role.value,
                    invitation_link=invitation_link
                )
                flash(f"Invitation sent successfully to {email}.", 'success')
            except Exception as mail_e:
                current_app.logger.error(f"Invite for {email} created, but email send failed: {mail_e}")
                flash(f"Invitation for {email} created, but email could not be sent. Check mail config.", 'warning')
        except IntegrityError:
             db.session.rollback()
             flash('Database error creating invitation. Possible duplicate token.', 'danger')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating invitation for {email} to org {org.id}: {e}")
            flash('An error occurred creating the invitation.', 'danger')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in field '{getattr(form, field).label.text}': {error}", 'danger')
    return redirect(url_for('.manage_members'))

@org_bp.route('/invitations')
@login_required
@organization_required
def view_invitations():
     if current_user.role != UserRole.ORGANIZATION: abort(403)
     org = current_user.user_profile.managed_organization
     if not org: abort(404)
     page = request.args.get('page', 1, type=int)
     per_page = current_app.config.get('ITEMS_PER_PAGE', 15)
     invitations_query = OrganizationInvitation.query.filter_by(organization_id=org.id)\
                                                    .order_by(OrganizationInvitation.created_at.desc())
     pagination = invitations_query.paginate(page=page, per_page=per_page, error_out=False)
     invitations = pagination.items
     return render_template('organization/view_invitations.html',
                             title="View Sent Invitations",
                             invitations=invitations, org=org,
                             pagination=pagination, InvitationStatus=InvitationStatus)

@org_bp.route('/invitations/cancel/<int:invite_id>', methods=['POST'])
@login_required
@organization_required
def cancel_invitation(invite_id):
    if current_user.role != UserRole.ORGANIZATION: abort(403)
    org = current_user.user_profile.managed_organization
    if not org: abort(403)
    form = CancelActionCSRFForm() # Use the aliased form from admin.forms
    if form.validate_on_submit():
        invite = OrganizationInvitation.query.filter_by(id=invite_id, organization_id=org.id).first_or_404()
        if invite.status != InvitationStatus.PENDING:
            flash('This invitation is not pending and cannot be cancelled.', 'warning')
        else:
            try:
                db.session.delete(invite)
                db.session.commit()
                flash(f'Invitation for {invite.invitee_email} cancelled successfully.', 'success')
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error cancelling invitation {invite_id}: {e}")
                flash('An error occurred while cancelling the invitation.', 'danger')
    else:
         flash('Could not cancel invitation due to a security validation error.', 'danger')
    return redirect(url_for('.view_invitations'))


# --- Quiz and Question Management (as provided, ensure templates exist) ---
@org_bp.route('/quizzes')
@login_required
@organization_required
def manage_quizzes():
     org = get_current_org()
     if not org: abort(404)
     page = request.args.get('page', 1, type=int)
     per_page = current_app.config.get('ITEMS_PER_PAGE', 15)
     quiz_query = Quiz.query.filter_by(organization_id=org.id) # Show org's quizzes
     pagination = quiz_query.order_by(Quiz.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
     quizzes = pagination.items
     return render_template('organization/manage_quizzes.html',
                            title="Organization Quizzes", quizzes=quizzes, org=org,
                            pagination=pagination, QuizStatus=QuizStatus)

@org_bp.route('/questions')
@login_required
@organization_required
def manage_questions():
     org = get_current_org()
     if not org: abort(404)
     page = request.args.get('page', 1, type=int)
     per_page = current_app.config.get('ITEMS_PER_PAGE', 20)
     question_query = Question.query.filter_by(organization_id=org.id) # Show org's questions
     pagination = question_query.order_by(Question.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
     questions = pagination.items
     return render_template('organization/manage_questions.html',
                           title="Organization Question Bank", questions=questions, org=org,
                           pagination=pagination)
