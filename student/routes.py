# your_app/student/routes.py
from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import not_
from ..models import db, User, Quiz, QuizAttempt, UserRole, QuizStatus, QuizAttemptStatus
# from ..decorators import student_required # Optional: use decorator later

student_bp = Blueprint('student',
                       __name__,
                       url_prefix='/student',
                       template_folder='../templates/student')

@student_bp.route('/dashboard')
@login_required
# @student_required # Uncomment when decorator is implemented
def dashboard():
    # --- Manual Role Check ---
    if current_user.role != UserRole.STUDENT:
        flash('Student access required.', 'danger')
        return redirect(url_for('main.dashboard')) # Redirect to dispatcher
    # --- End Manual Check ---

    # Check if organization is approved (info shown by dispatcher, but maybe restrict actions here)
    if not current_user.organization or not current_user.organization.is_approved:
        flash('Your organization is not yet approved. Some features may be limited.', 'info')
        # Allow viewing dashboard, but actions inside might be restricted

    # Fetch data for Student Dashboard

    # Get assigned quizzes that are published/active and haven't been completed by the student
    # This query needs refinement based on how assignments vs attempts are tracked
    # Simple version: Get assigned quizzes and filter out completed ones
    assigned_quiz_ids = [q.id for q in current_user.assigned_quizzes.all()] # Get IDs of assigned quizzes

    completed_attempt_quiz_ids = db.session.query(QuizAttempt.quiz_id)\
                                        .filter(QuizAttempt.user_id == current_user.id)\
                                        .filter(QuizAttempt.status.in_([QuizAttemptStatus.SUBMITTED, QuizAttemptStatus.GRADED, QuizAttemptStatus.TIMED_OUT]))\
                                        .distinct().all()
    completed_quiz_ids = [item[0] for item in completed_attempt_quiz_ids] # Flatten list

    available_quizzes = Quiz.query.filter(
                            Quiz.id.in_(assigned_quiz_ids),
                            Quiz.status.in_([QuizStatus.PUBLISHED, QuizStatus.ACTIVE]),
                            not_(Quiz.id.in_(completed_quiz_ids)) # Filter out completed ones
                        ).order_by(Quiz.start_time).all() # Needs check against current time too

    # Get recent attempts
    recent_attempts = QuizAttempt.query.filter_by(user_id=current_user.id)\
                                      .order_by(QuizAttempt.start_time.desc())\
                                      .limit(5).all()

    return render_template('dashboard.html',
                           available_quizzes=available_quizzes,
                           recent_attempts=recent_attempts)


# TODO: Add routes for viewing all quizzes (assigned/completed), viewing quiz details, taking a quiz, viewing history/analytics
# Example Placeholders:
# @student_bp.route('/quizzes')
# @login_required
# @student_required
# def list_quizzes(): ... # Show all assigned/taken quizzes

# @student_bp.route('/quiz/<int:quiz_id>')
# @login_required
# @student_required
# def view_quiz(quiz_id): ... # Show quiz details, button to start if available

# @student_bp.route('/quiz/<int:quiz_id>/take')
# @login_required
# @student_required
# def take_quiz(quiz_id): ... # The actual quiz taking interface

# @student_bp.route('/history')
# @login_required
# @student_required
# def view_history(): ... # Show all past attempts and results