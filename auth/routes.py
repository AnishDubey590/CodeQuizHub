# /your_app/auth/routes.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone
from . import auth_bp
from .. import db, mail  # Assuming mail is initialized in __init__
from ..models import Credentials, User, UserRole, Organization, OrgApprovalStatus, OrganizationInvitation, InvitationStatus
from .forms import (
    LoginForm, RegistrationForm, OrganizationRegistrationForm,
    InviteUserForm, AcceptInvitationForm, RequestPasswordResetForm, ResetPasswordForm
)
# from ..utils.email import send_password_reset_email, send_invitation_email # TODO: Create email utility
# from ..utils.tokens import generate_token, verify_token # TODO: Create token utility



# --- Standard Login/Logout ---
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        # If already logged in, redirect to the central dashboard dispatcher
        return redirect(url_for('main.dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        creds = Credentials.query.filter_by(username=form.username.data).first()

        if creds and creds.check_password(form.password.data):
            if not creds.is_active:
                flash('Your account is inactive. Please contact support.', 'warning')
                return redirect(url_for('auth.login'))

            # Perform organization status checks for non-admin roles that require an approved org
            if creds.role in [UserRole.ORGANIZATION, UserRole.TEACHER, UserRole.STUDENT]:
                # Ensure user_profile relationship exists on Credentials model and links to User model
                # And User model has organization relationship
                user_profile = creds.user # Assuming 'user' is the relationship from Credentials to User
                if user_profile and user_profile.organization:
                    org = user_profile.organization
                    if org.approval_status == OrgApprovalStatus.REJECTED:
                        flash(f'The organization "{org.name}" registration was rejected.', 'danger')
                        return redirect(url_for('auth.login'))
                    # Allow Org Admin (who is UserRole.ORGANIZATION) to log in if PENDING
                    # But block Teacher/Student if Org is PENDING
                    if org.approval_status == OrgApprovalStatus.PENDING and \
                       creds.role in [UserRole.TEACHER, UserRole.STUDENT]:
                        flash(f'The organization "{org.name}" is still pending approval. Please wait for admin confirmation.', 'warning')
                        return redirect(url_for('auth.login'))
                elif creds.role in [UserRole.TEACHER, UserRole.STUDENT]: # Teacher/Student must have an org
                     flash('Account error: Organization link missing or organization not found. Please contact support.', 'danger')
                     return redirect(url_for('auth.login'))
            
            # If all checks pass, log in the user
            login_user(creds, remember=form.remember_me.data)

            # Update last login time
            # Ensure your Credentials model has 'last_login_at' and it's a DateTime column
            creds.last_login_at = datetime.now(timezone.utc) # Use timezone.utc
            try:
                db.session.commit()
            except Exception as e:
                 current_app.logger.error(f"Error updating last_login for {creds.username}: {e}")
                 db.session.rollback() # Rollback potential session issues

            flash('Login successful!', 'success')
            next_page = request.args.get('next')

            # Basic protection against open redirect
            if next_page and (not next_page.startswith('/') and not next_page.startswith(request.host_url)):
                current_app.logger.warning(f"Open redirect attempt to '{next_page}' blocked for user '{creds.username}'.")
                next_page = None # Discard unsafe next_page

            # Redirect to the central dispatcher (main.dashboard) or the intended next_page
            return redirect(next_page or url_for('main.dashboard'))
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('auth/login.html', title='Login', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index')) # Redirect to landing page


# --- Registration ---

@auth_bp.route('register/individual', methods=['GET', 'POST'])
def individual_register():
    """Handles registration for individual users (Role: USER)."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            # Create Credentials first
            new_credentials = Credentials(
                username=form.username.data,
                role=UserRole.USER # Individual user role
            )
            new_credentials.set_password(form.password.data)
            db.session.add(new_credentials)
            # Flush to get credentials ID without committing fully yet
            db.session.flush()

            # Create User Profile linked to Credentials
            new_user_profile = User(
                credentials_id=new_credentials.id,
                email=form.email.data,
                display_name=form.display_name.data or form.username.data # Default display name
            )
            db.session.add(new_user_profile)

            db.session.commit() # Commit both records together
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('auth.login'))

        except IntegrityError as e:
            db.session.rollback()
            current_app.logger.error(f"Integrity error during registration: {e}")
            # Specific checks might have been missed by WTForms validators (race condition?)
            if 'credentials_username_key' in str(e):
                 form.username.errors.append("Username already exists.")
            elif 'users_email_key' in str(e):
                 form.email.errors.append("Email already registered.")
            else:
                flash('A database error occurred. Please try again.', 'danger')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error during registration: {e}")
            flash('An error occurred during registration. Please try again.', 'danger')

    return render_template('auth/individual_register.html', title='Register', form=form)


@auth_bp.route('/register/organization', methods=['GET', 'POST'])
def organization_register():
    """Handles registration request for an Organization and its primary Admin."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    form = OrganizationRegistrationForm()
    if form.validate_on_submit():
        try:
            # 1. Create Credentials for the Org Admin
            org_admin_creds = Credentials(
                username=form.admin_username.data,
                role=UserRole.ORGANIZATION # Role for managing the org
            )
            org_admin_creds.set_password(form.admin_password.data)
            db.session.add(org_admin_creds)
            db.session.flush() # Get the ID

            # 2. Create User Profile for the Org Admin
            org_admin_profile = User(
                credentials_id=org_admin_creds.id,
                email=form.admin_email.data,
                display_name=form.admin_display_name.data or form.admin_username.data
                # Note: Organization ID is null initially, linked via Organization below
            )
            db.session.add(org_admin_profile)
            db.session.flush() # Get the ID

            # 3. Create the Organization, linking the admin profile
            new_org = Organization(
                name=form.org_name.data,
                description=form.org_description.data,
                website_url=form.website_url.data,
                approval_status=OrgApprovalStatus.PENDING,
                admin_user_id=org_admin_profile.id # Link the PROFILE ID
            )
            db.session.add(new_org)
            db.session.flush() # Get the ID

            # 4. IMPORTANT: Link the admin profile back to the organization
            #    This avoids needing a separate query later if accessing org from user profile
            org_admin_profile.organization_id = new_org.id

            # 5. Commit all changes transactionally
            db.session.commit()

            flash('Organization registration request submitted! An administrator will review it shortly.', 'success')
            # TODO: Send notification email to platform admins
            return redirect(url_for('auth.login'))

        except IntegrityError as e:
            db.session.rollback()
            current_app.logger.error(f"Integrity error during org registration: {e}")
            # Handle specific constraint violations if WTForms missed them
            if 'organizations_name_key' in str(e):
                form.org_name.errors.append("Organization name already exists or is pending.")
            elif 'credentials_username_key' in str(e):
                form.admin_username.errors.append("Admin username already taken.")
            elif 'users_email_key' in str(e):
                 form.admin_email.errors.append("Admin email already registered.")
            else:
                flash('A database error occurred (duplicate data likely). Please try again.', 'danger')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error during organization registration: {e}")
            flash('An unexpected error occurred. Please try again.', 'danger')

    return render_template('auth/organization_register.html', title='Register Organization', form=form)


# --- Organization Invitations ---

@auth_bp.route('/accept-invitation/<token>', methods=['GET', 'POST'])
def accept_invitation(token):
    """Handles users accepting an invitation to join an organization."""
    if current_user.is_authenticated:
        flash('Please logout to accept an invitation with a different account, or contact your org admin.', 'warning')
        return redirect(url_for('main.dashboard'))

    # TODO: Implement verify_token utility function
    # payload = verify_token(token, salt='org-invitation', max_age=current_app.config['INVITATION_TOKEN_MAX_AGE'])
    payload = None # Placeholder
    try:
        # Simulate token verification - REPLACE WITH ACTUAL VERIFICATION
        # Example payload: {'invitation_id': 1, 'email': 'invited@example.com', 'role': 'Student'}
        # This should come from a secure token verification function
        invitation_id = int(token.split('-')[0]) # VERY INSECURE PLACEHOLDER
        invitation = OrganizationInvitation.query.get_or_404(invitation_id)
        if invitation.status != InvitationStatus.PENDING:
             flash('This invitation is no longer valid (already used or expired).', 'warning')
             return redirect(url_for('main.index'))
        # Check expiry (simplified)
        if invitation.expires_at < datetime.now(timezone.utc):
            invitation.status = InvitationStatus.EXPIRED
            db.session.commit()
            flash('This invitation has expired.', 'danger')
            return redirect(url_for('main.index'))

        payload = {'invitation_id': invitation.id, 'email': invitation.invitee_email, 'role': invitation.invited_as_role.value}
    except Exception as e: # Catch token errors
        current_app.logger.error(f"Invalid or expired invitation token: {token} - {e}")
        flash('Invalid or expired invitation link.', 'danger')
        return redirect(url_for('main.index'))

    # If payload is valid, proceed
    invitation = OrganizationInvitation.query.get(payload['invitation_id'])
    if not invitation or invitation.status != InvitationStatus.PENDING:
        flash('Invitation not found or already used.', 'warning')
        return redirect(url_for('main.index'))

    # Check if email already exists in the system
    existing_user = User.query.filter_by(email=payload['email']).first()

    form = AcceptInvitationForm(existing_user=existing_user)

    if form.validate_on_submit():
        try:
            target_role = UserRole(payload['role']) # Convert string back to Enum

            if existing_user:
                # -- Link Existing Account --
                # Security Check: Ensure existing user isn't already in an org or has conflicting role? (Optional)
                if existing_user.organization_id:
                     flash('This email is already associated with another organization.', 'danger')
                     return render_template('auth/accept_invitation.html', title='Accept Invitation', form=form, invitation=invitation, existing_user=existing_user)

                # Update user's org ID and potentially commit other profile details
                existing_user.organization_id = invitation.organization_id
                existing_user.enrollment_date = datetime.now(timezone.utc)
                if form.student_code.data: # Update student code if provided
                      existing_user.student_code = form.student_code.data
                # Assign the invited role (IMPORTANT: Overwrites previous role if they were USER)
                if existing_user.credentials.role == UserRole.USER: # Only upgrade from individual user
                    existing_user.credentials.role = target_role
                elif existing_user.credentials.role != target_role:
                     flash(f'Account role mismatch. Invitation is for {target_role.value}, account has role {existing_user.credentials.role.value}.', 'warning')
                     return render_template('auth/accept_invitation.html', title='Accept Invitation', form=form, invitation=invitation, existing_user=existing_user)

                accepted_user_id = existing_user.id

            else:
                # -- Create New Account --
                # 1. Create Credentials
                new_credentials = Credentials(
                    username=form.username.data,
                    role=target_role
                )
                new_credentials.set_password(form.password.data)
                db.session.add(new_credentials)
                db.session.flush()

                # 2. Create User Profile
                new_user_profile = User(
                    credentials_id=new_credentials.id,
                    email=invitation.invitee_email, # Use the invited email
                    display_name=form.display_name.data or form.username.data,
                    organization_id=invitation.organization_id,
                    student_code=form.student_code.data,
                    enrollment_date=datetime.now(timezone.utc)
                )
                db.session.add(new_user_profile)
                db.session.flush()
                accepted_user_id = new_user_profile.id

            # Update invitation status
            invitation.status = InvitationStatus.ACCEPTED
            invitation.accepted_at = datetime.now(timezone.utc)
            invitation.accepted_by_user_id = accepted_user_id

            db.session.commit()

            flash(f'Invitation accepted! You are now part of {invitation.organization.name}. Please login.', 'success')
            return redirect(url_for('auth.login'))

        except IntegrityError as e:
             db.session.rollback()
             current_app.logger.error(f"Integrity error accepting invitation: {e}")
             if not existing_user and 'credentials_username_key' in str(e):
                 form.username.errors.append("Username already exists.")
             else:
                 flash('A database error occurred. Please try again.', 'danger')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error accepting invitation: {e}")
            flash('An unexpected error occurred. Please try again.', 'danger')

    # Prepare context for template
    org_name = Organization.query.get(invitation.organization_id).name or "the organization"

    return render_template('auth/accept_invitation.html',
                           title='Accept Invitation',
                           form=form,
                           invitation=invitation,
                           existing_user=existing_user,
                           invited_role=UserRole(payload['role']),
                           org_name=org_name,
                           token=token)


# --- Password Reset ---

@auth_bp.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    form = RequestPasswordResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            # Check if credentials exist and are active
            if not user.credentials:
                 flash('Credentials not found for this email.', 'warning')
            elif not user.credentials.is_active:
                 flash('Account associated with this email is inactive.', 'warning')
            else:
                 # TODO: Generate secure token (e.g., using itsdangerous)
                 # TODO: Send password reset email with token link
                 # send_password_reset_email(user) # Pass user object
                 flash('Check your email for instructions to reset your password.', 'info')
                 # Always redirect to prevent email enumeration where possible
                 return redirect(url_for('auth.login'))
        else:
            # Still show success message even if user not found to prevent enumeration
            flash('If an account with that email exists, you will receive reset instructions.', 'info')
            return redirect(url_for('auth.login'))

    return render_template('auth/reset_password_request.html',
                           title='Reset Password', form=form)


@auth_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    # TODO: Verify the token securely, get credentials ID
    # creds_id = verify_token(token, salt='password-reset', max_age=3600) # Example: 1 hour expiry
    # if not creds_id:
    #     flash('The password reset link is invalid or has expired.', 'warning')
    #     return redirect(url_for('auth.reset_password_request'))
    # creds = Credentials.query.get(creds_id)

    creds = None # Placeholder - Replace with actual token verification logic
    # --- TEMPORARY FOR DEMO --- REMOVE THIS ---
    try:
        temp_creds_id = int(token)
        creds = Credentials.query.get(temp_creds_id)
        if not creds : raise ValueError("User not found")
    except:
         flash('Invalid or expired password reset token.', 'warning')
         return redirect(url_for('auth.reset_password_request'))
    # --- END TEMPORARY ---

    if not creds:
        flash('Invalid user for password reset.', 'warning')
        return redirect(url_for('auth.reset_password_request'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        creds.set_password(form.password.data)
        try:
            db.session.commit()
            flash('Your password has been reset successfully. Please login.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error saving reset password for {creds.username}: {e}")
            flash('An error occurred while resetting the password.', 'danger')

    return render_template('auth/reset_password.html', title='Reset Password', form=form)