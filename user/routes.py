# /your_app/user/routes.py
from flask import Blueprint, render_template, flash, redirect, url_for, request, abort
from flask_login import login_required, current_user

from .. import db
from ..models import User, Credentials, UserRole, Quiz, QuizStatus, Friendship
from ..utils.decorators import individual_user_required

# Assuming user_bp is defined in user/__init__.py
from . import user_bp

def get_user_profile():
    if not current_user.is_authenticated: return None
    return current_user.user_profile


@user_bp.route('/dashboard')
@login_required
@individual_user_required
def dashboard():
    """Individual User Dashboard."""
    user_profile = get_user_profile()
    if not user_profile: abort(403)

    # TODO: Show stats like public quizzes taken, friends, points etc.
    public_quizzes_taken = 0 # Placeholder
    friend_count = 0 # Placeholder

    return render_template('user/dashboard.html',
                           title="User Dashboard",
                           user_profile=user_profile,
                           public_quizzes_taken=public_quizzes_taken,
                           friend_count=friend_count)


@user_bp.route('/quizzes')
@login_required
@individual_user_required
def public_quizzes():
     """List available public quizzes."""
     # TODO: Add pagination
     quizzes = Quiz.query.filter_by(is_public=True, status=QuizStatus.PUBLISHED)\
          .order_by(Quiz.created_at.desc()).all()
     # TODO: Create Template user/public_quizzes.html
     return render_template('user/quiz_list.html', title="Public Quizzes", quizzes=quizzes)

# TODO: Need routes to take public quizzes (similar to student flow but access control differs)
# Example: /user/quiz/take/<int:quiz_id>
# Example: /user/quiz/submit/<int:attempt_id>
# Example: /user/results (results for public quizzes taken)


# --- Friend System (Simplified Placeholders) ---

@user_bp.route('/friends')
@login_required
@individual_user_required
def friends_list():
    """Display user's friends list."""
    user_profile = get_user_profile()
    if not user_profile: abort(403)

    # Fetching friends (simplified symmetric view)
    # This gets complicated with the association object. Need careful querying.
    friends1 = db.session.query(User).join(Friendship, User.id == Friendship.friend_user_id).filter(Friendship.user_id == user_profile.id).all()
    friends2 = db.session.query(User).join(Friendship, User.id == Friendship.user_id).filter(Friendship.friend_user_id == user_profile.id).all()
    all_friends = list(set(friends1 + friends2)) # Combine and remove duplicates

    # TODO: Create template user/friends_list.html
    return render_template('user/friends_list.html', title="My Friends", friends=all_friends)


@user_bp.route('/friends/add', methods=['POST']) # Typically done via profile pages
@login_required
@individual_user_required
def add_friend():
    """Add another user as a friend."""
    user_profile = get_user_profile()
    if not user_profile: abort(403)

    friend_username = request.form.get('friend_username')
    if not friend_username:
        flash("Please enter a username to add as a friend.", "warning")
        return redirect(request.referrer or url_for('.friends_list'))

    if friend_username == current_user.username:
         flash("You cannot add yourself as a friend.", "warning")
         return redirect(request.referrer or url_for('.friends_list'))

    friend_creds = Credentials.query.filter_by(username=friend_username).first()
    if not friend_creds or not friend_creds.user_profile:
        flash(f"User '{friend_username}' not found.", "danger")
        return redirect(request.referrer or url_for('.friends_list'))

    friend_profile = friend_creds.user_profile

    # Only allow adding other individual users? Or any user? Assuming individual for now.
    if friend_creds.role != UserRole.USER:
         flash(f"You can only add individual users as friends.", "warning")
         return redirect(request.referrer or url_for('.friends_list'))

    # Check if already friends
    existing_friendship = Friendship.query.filter(
        ((Friendship.user_id == user_profile.id) & (Friendship.friend_user_id == friend_profile.id)) |
        ((Friendship.user_id == friend_profile.id) & (Friendship.friend_user_id == user_profile.id))
    ).first()

    if existing_friendship:
        flash(f"You are already friends with {friend_username}.", "info")
        return redirect(request.referrer or url_for('.friends_list'))

    try:
        # Create friendship record (assuming immediate acceptance, no requests)
        new_friendship = Friendship(user_id=user_profile.id, friend_user_id=friend_profile.id)
        db.session.add(new_friendship)
        db.session.commit()
        flash(f"{friend_username} added as a friend!", "success")
        # TODO: Send notification to the friend?
    except Exception as e:
        db.session.rollback()
        flash(f"Error adding friend: {e}", "danger")

    return redirect(request.referrer or url_for('.friends_list'))

# TODO: Route to remove a friend
# TODO: Route/logic for friend-based quizzes ('Common Test')