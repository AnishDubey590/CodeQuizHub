# /your_app/main/routes.py
from flask import Blueprint,flash
from flask_login import current_user, login_required
from . import main_bp 
from flask import render_template, redirect, url_for, abort, current_app
from flask_login import login_required, current_user
from ..models import User, UserRole, Credentials # Ensure all are imported

@main_bp.route('/')
@main_bp.route('/index')
def index():
    """Landing page."""
    if current_user.is_authenticated:
        # If logged in, redirect to role-specific dashboard immediately
        return redirect(url_for('main.dashboard'))
    return render_template('main/dashboard.html', title='Welcome')

@main_bp.route('/dashboard')
@login_required
def dashboard():
    """Dispatcher: Redirects logged-in users to their appropriate dashboard."""
    # current_user is the Credentials object from load_user
    if not current_user or not hasattr(current_user, 'role'):
          abort(500, "User credentials or role not loaded correctly.") # Should not happen

    if current_user.role == UserRole.ADMIN:
        return redirect(url_for('admin.dashboard'))
    elif current_user.role == UserRole.ORGANIZATION:
        return redirect(url_for('organization.dashboard'))
    elif current_user.role == UserRole.TEACHER:
        return redirect(url_for('teacher.dashboard'))
    elif current_user.role == UserRole.STUDENT:
        return redirect(url_for('student.dashboard'))
    elif current_user.role == UserRole.USER:
        return redirect(url_for('user.dashboard'))
    else:
        # Fallback or error - maybe log them out or show generic page
        abort(403, "Unknown user role.")

@main_bp.route('/profile')
@login_required
def view_profile():
    """Displays the current user's profile."""
    # Access profile data via the relationship
    user_profile = current_user.user_profile
    if not user_profile:
         abort(500, "User profile not found for current credentials.") # Data integrity issue
    # TODO: Create profile view template
    return render_template('profile/view_profile.html', title="My Profile", user_profile=user_profile)

@main_bp.route('/profile/view/<int:user_id>')
@login_required
def view_user_profile_by_id(user_id):
    user_profile_to_view = User.query.get_or_404(user_id)
    can_view = False
    if current_user.user_profile and current_user.user_profile.id == user_profile_to_view.id:
        can_view = True
    elif current_user.role == UserRole.ADMIN:
        can_view = True
    elif current_user.role == UserRole.ORGANIZATION:
        managed_org = current_user.user_profile.managed_organization
        if managed_org and user_profile_to_view.organization_id == managed_org.id:
            can_view = True
    elif current_user.role == UserRole.TEACHER:
        teacher_org = current_user.user_profile.organization
        if teacher_org and user_profile_to_view.organization_id == teacher_org.id:
            can_view = True
    if not can_view:
        current_app.logger.warning(
            f"Forbidden attempt by user '{current_user.username}' (Role: {current_user.role.value}) "
            f"to view profile of User ID {user_id} ('{user_profile_to_view.credentials.username}')."
        )
        abort(403)
    return render_template('profile/view_profile.html',
                           title=f"Profile: {user_profile_to_view.display_name or user_profile_to_view.credentials.username}",
                           user_profile=user_profile_to_view)


@main_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    # ... your edit profile logic ...
    user_profile = current_user.user_profile
    if not user_profile: abort(500)
    # form = ...
    # if form.validate_on_submit(): ...
    flash("Profile editing is not yet implemented.", "info")
    return redirect(url_for('main.view_profile'))
    # if form.validate_on_submit():
    #     try:
    #         user_profile.display_name = form.display_name.data
    #         user_profile.bio = form.bio.data
    #         # Handle profile picture upload if implemented
    #         db.session.commit()
    #         flash('Your profile has been updated.', 'success')
    #         return redirect(url_for('main.view_profile'))
    #     except Exception as e:
    #         db.session.rollback()
    #         current_app.logger.error(f"Error updating profile for user {user_profile.id}: {e}")
    #         flash('An error occurred while updating your profile.', 'danger')

    # TODO: Create profile edit template
    return render_template('profile/edit_profile.html', title="Edit Profile", form=form, user_profile=user_profile)
