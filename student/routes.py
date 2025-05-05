# /your_app/student/routes.py
# CORRECTED VERSION 4 - Addresses Pylance errors from previous snippet.

from flask import Blueprint, render_template, flash, redirect, url_for, request, abort, current_app
from flask_login import login_required, current_user
from datetime import datetime, timezone, timedelta
import json
import random # Needed for random.sample

from .. import db
from ..models import (
    User, Credentials, Organization, UserRole, Quiz, Question, QuizAssignment,
    QuizAttempt, StudentAnswer, QuizAttemptStatus, QuestionType, QuestionOption,
    GradingStatus, QuestionSelectionStrategy, QuizQuestion, # Added QuizQuestion import
    QuizStatus # Added QuizStatus import
)
# Assuming the utils folder structure is correct relative to this file
from ..utils.decorators import student_required # Import the specific decorator

# Assuming student_bp is defined in student/__init__.py
from . import student_bp

# Helper to get student's organization
def get_student_org(): # Fixed: Added colon
    """Helper function to get the student's organization."""
    if not current_user.is_authenticated or not hasattr(current_user, 'user_profile') or not current_user.user_profile:
        return None
    return current_user.user_profile.organization

# Helper to get student's user profile
def get_student_profile():
    """Helper function to get the student's user profile."""
    if not current_user.is_authenticated or not hasattr(current_user, 'user_profile'):
        return None
    return current_user.user_profile


@student_bp.route('/dashboard')
@login_required
@student_required
def dashboard():
    """Student Dashboard."""
    student_profile = get_student_profile()
    if not student_profile: abort(403)

    org = get_student_org()
    if not org:
        flash("Error: Your account is not currently linked to an organization.", "warning")
        return redirect(url_for('main.view_profile'))

    # --- Fetch active assignments ---
    now = datetime.now(timezone.utc)
    active_assignments_query = QuizAssignment.query.join(Quiz)\
        .filter(QuizAssignment.student_user_id == student_profile.id)\
        .filter(Quiz.status == QuizStatus.PUBLISHED)\
        .filter( (Quiz.start_time == None) | (Quiz.start_time <= now) ) \
        .filter( (Quiz.end_time == None) | (Quiz.end_time >= now) ) \
        .options(db.joinedload(QuizAssignment.quiz))

    active_assignments = active_assignments_query.order_by(
        db.case(
             (QuizAssignment.due_date != None, QuizAssignment.due_date)
        ).asc().nulls_last(),
        Quiz.end_time.asc().nulls_last()
    ).all()

    # --- Check status of active assignments (Optimized) ---
    assignment_quiz_ids = [a.quiz_id for a in active_assignments]
    latest_attempts_map = {}
    if assignment_quiz_ids:
        latest_attempts_subq = db.session.query(
                QuizAttempt.quiz_id,
                db.func.max(QuizAttempt.id).label('latest_attempt_id')
            ).filter(QuizAttempt.quiz_id.in_(assignment_quiz_ids), QuizAttempt.user_id == student_profile.id)\
            .group_by(QuizAttempt.quiz_id).subquery()
        attempts_details = db.session.query(QuizAttempt).join(
                latest_attempts_subq, QuizAttempt.id == latest_attempts_subq.c.latest_attempt_id # Corrected join syntax
            ).all()
        latest_attempts_map = {attempt.quiz_id: attempt for attempt in attempts_details}

    assignments_with_status = []
    for assign in active_assignments:
         attempt = latest_attempts_map.get(assign.quiz_id)
         status = "Not Started"
         attempt_id = None
         can_start_or_resume = True

         if attempt:
              if attempt.status in [QuizAttemptStatus.SUBMITTED, QuizAttemptStatus.GRADED, QuizAttemptStatus.TIMED_OUT]:
                   status = "Completed"
                   can_start_or_resume = False
              elif attempt.status in [QuizAttemptStatus.STARTED, QuizAttemptStatus.IN_PROGRESS]:
                   status = "In Progress"
                   attempt_id = attempt.id
                   if attempt.deadline and now > attempt.deadline:
                        status = "Timed Out (Needs Submit)"
                        can_start_or_resume = False

         if status == "Not Started" and assign.quiz.max_attempts > 0:
            attempt_count = QuizAttempt.query.with_entities(db.func.count(QuizAttempt.id)).filter_by(quiz_id=assign.quiz_id, user_id=student_profile.id).scalar()
            if attempt_count >= assign.quiz.max_attempts:
                 status = f"Max Attempts ({assign.quiz.max_attempts}) Reached"
                 can_start_or_resume = False

         assignments_with_status.append({
             'assignment': assign,
             'quiz': assign.quiz,
             'status': status,
             'can_start_or_resume': can_start_or_resume,
             'attempt_id': attempt_id
         })

    # --- Fetch recent finalized attempts ---
    recent_attempts = QuizAttempt.query.filter_by(user_id=student_profile.id)\
        .filter(QuizAttempt.status.in_([QuizAttemptStatus.SUBMITTED, QuizAttemptStatus.GRADED, QuizAttemptStatus.TIMED_OUT]))\
        .order_by(QuizAttempt.submit_time.desc())\
        .limit(5).all()

    return render_template('student/dashboard.html',
                            title="Student Dashboard",
                            org=org,
                            assignments=assignments_with_status,
                            recent_attempts=recent_attempts,
                            student_profile=student_profile)


@student_bp.route('/assignments')
@login_required
@student_required
def my_assignments():
    """List all assignments (active and past)."""
    student_profile = get_student_profile()
    if not student_profile: abort(403)

    assignments = QuizAssignment.query.filter_by(student_user_id=student_profile.id)\
        .join(Quiz).options(db.joinedload(QuizAssignment.quiz))\
        .order_by(QuizAssignment.assigned_at.desc()).all()

    # --- Check status of all assignments (Optimized) ---
    assignment_quiz_ids = [a.quiz_id for a in assignments]
    latest_attempts_map = {} # Defined here
    if assignment_quiz_ids:
        latest_attempts_subq = db.session.query(
                QuizAttempt.quiz_id,
                db.func.max(QuizAttempt.id).label('latest_attempt_id')
            ).filter(QuizAttempt.quiz_id.in_(assignment_quiz_ids), QuizAttempt.user_id == student_profile.id)\
            .group_by(QuizAttempt.quiz_id).subquery()
        attempts_details = db.session.query(QuizAttempt).join(
                latest_attempts_subq, QuizAttempt.id == latest_attempts_subq.c.latest_attempt_id # Corrected join syntax
            ).all()
        latest_attempts_map = {attempt.quiz_id: attempt for attempt in attempts_details} # Populate map

    assignments_with_status = []
    for assign in assignments:
         attempt = latest_attempts_map.get(assign.quiz_id) # Use the map
         status = "Not Started"
         if attempt:
             status = attempt.status.name.replace('_', ' ').title()

         if status == "Not Started" and assign.quiz.max_attempts > 0:
            attempt_count = QuizAttempt.query.with_entities(db.func.count(QuizAttempt.id)).filter_by(quiz_id=assign.quiz_id, user_id=student_profile.id).scalar()
            if attempt_count >= assign.quiz.max_attempts:
                 status = f"Max Attempts ({assign.quiz.max_attempts}) Reached"

         assignments_with_status.append({ 'assignment': assign, 'quiz': assign.quiz, 'status': status})

    return render_template('student/my_assignments.html', title="My Assignments", assignments=assignments_with_status)


@student_bp.route('/quiz/take/<int:quiz_id>', methods=['GET'])
@login_required
@student_required
def take_quiz_start(quiz_id):
    """Initiates or resumes a quiz attempt."""
    student_profile = get_student_profile()
    if not student_profile: abort(403)
    now = datetime.now(timezone.utc)

    assignment = QuizAssignment.query.filter_by(quiz_id=quiz_id, student_user_id=student_profile.id).first()
    quiz = Quiz.query.get_or_404(quiz_id)

    is_assigned = assignment is not None
    can_take = is_assigned # Students currently MUST be assigned

    if not can_take:
        abort(403, "You do not have permission to take this quiz or it is not available.")

    if is_assigned:
        if quiz.status != QuizStatus.PUBLISHED: abort(403, "The assigned quiz is not currently active.")
        if quiz.start_time and now < quiz.start_time: abort(403, f"The assigned quiz starts at {quiz.start_time.strftime('%Y-%m-%d %H:%M %Z')}.")
        if quiz.end_time and now > quiz.end_time: abort(403, f"The assigned quiz ended at {quiz.end_time.strftime('%Y-%m-%d %H:%M %Z')}.")
        if assignment.due_date and now > assignment.due_date:
             abort(403, f"The due date ({assignment.due_date.strftime('%Y-%m-%d %H:%M %Z')}) for this assignment has passed.")

    latest_attempt = QuizAttempt.query.filter_by(quiz_id=quiz_id, user_id=student_profile.id)\
                       .order_by(QuizAttempt.start_time.desc()).first()

    can_start_new = True
    if quiz.max_attempts > 0:
        attempt_count = QuizAttempt.query.with_entities(db.func.count(QuizAttempt.id)).filter_by(quiz_id=quiz_id, user_id=student_profile.id).scalar()
        if attempt_count >= quiz.max_attempts:
             if not latest_attempt or latest_attempt.status != QuizAttemptStatus.STARTED \
                or (latest_attempt.deadline and now > latest_attempt.deadline):
                 can_start_new = False

    if latest_attempt and latest_attempt.status in [QuizAttemptStatus.STARTED, QuizAttemptStatus.IN_PROGRESS]:
        if latest_attempt.deadline and now > latest_attempt.deadline:
             flash("Your previous attempt timed out. Submitting now.", "warning")
             return redirect(url_for('.submit_quiz', attempt_id=latest_attempt.id, force='true'))
        else:
             return redirect(url_for('.take_quiz_attempt', attempt_id=latest_attempt.id))
    elif not can_start_new:
         flash(f"You have reached the maximum number of attempts ({quiz.max_attempts}) for this quiz.", "warning")
         return redirect(url_for('.dashboard'))
    else:
        try:
            deadline = now + timedelta(minutes=quiz.duration_minutes) if quiz.duration_minutes > 0 else None
            new_attempt = QuizAttempt(
                quiz_id=quiz.id,
                user_id=student_profile.id,
                start_time=now,
                deadline=deadline,
                status=QuizAttemptStatus.STARTED,
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string
            )

            selected_q_ids = []
            if quiz.selection_strategy == QuestionSelectionStrategy.RANDOM and quiz.num_questions_to_pool:
                 pool_size = quiz.num_questions_to_pool
                 available_q_ids = [q.question_id for q in QuizQuestion.query.filter_by(quiz_id=quiz.id).all()] # Fixed: Uses QuizQuestion
                 if len(available_q_ids) >= pool_size:
                      selected_q_ids = random.sample(available_q_ids, pool_size)
                 else:
                      current_app.logger.warning(f"Quiz {quiz_id} needs {pool_size} questions for random pool, but only {len(available_q_ids)} linked.")
                      flash("Cannot start quiz: Not enough questions available in the pool.", "danger")
                      return redirect(url_for('.dashboard'))

            # Corrected FIXED strategy logic - relies on QuizQuestion association object if used for ordering
            elif quiz.selection_strategy == QuestionSelectionStrategy.FIXED:
                 ordered_quiz_questions = QuizQuestion.query.filter_by(quiz_id=quiz.id)\
                                           .order_by(QuizQuestion.question_order, QuizQuestion.question_id).all() # Fixed: Query QuizQuestion
                 selected_q_ids = [qq.question_id for qq in ordered_quiz_questions]
                 # Fallback if no specific order set via QuizQuestion
                 if not selected_q_ids:
                      # Fallback using the relationship + Question ID order
                      selected_q_ids = [q.id for q in quiz.questions.order_by(Question.id)] # Changed q->question
            else: # Default to fixed
                ordered_quiz_questions = QuizQuestion.query.filter_by(quiz_id=quiz.id)\
                                           .order_by(QuizQuestion.question_order, QuizQuestion.question_id).all() # Fixed: Query QuizQuestion
                selected_q_ids = [qq.question_id for qq in ordered_quiz_questions]
                if not selected_q_ids:
                     # Fallback using the relationship + Question ID order
                     selected_q_ids = [q.id for q in quiz.questions.order_by(Question.id)] # Changed q->question


            if not selected_q_ids:
                flash("Cannot start quiz: No questions found for this quiz.", "danger")
                return redirect(url_for('.dashboard'))

            new_attempt.set_presented_questions(selected_q_ids)

            max_score = db.session.query(db.func.sum(Question.points))\
                          .filter(Question.id.in_(selected_q_ids)).scalar() or 0.0
            new_attempt.max_score_possible = max_score

            db.session.add(new_attempt)
            db.session.commit()
            return redirect(url_for('.take_quiz_attempt', attempt_id=new_attempt.id))

        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Error starting quiz attempt for quiz {quiz_id}, user {student_profile.id}: {e}")
            flash("An error occurred while starting the quiz.", "danger")
            return redirect(url_for('.dashboard'))


@student_bp.route('/quiz/attempt/<int:attempt_id>', methods=['GET'])
@login_required
@student_required
def take_quiz_attempt(attempt_id):
    """Displays the quiz taking interface for an active attempt."""
    student_profile = get_student_profile()
    if not student_profile: abort(403)
    now = datetime.now(timezone.utc)

    attempt = QuizAttempt.query.filter_by(id=attempt_id, user_id=student_profile.id)\
                .options(db.joinedload(QuizAttempt.quiz)).first_or_404()

    if attempt.status not in [QuizAttemptStatus.STARTED, QuizAttemptStatus.IN_PROGRESS]:
        flash("This quiz attempt is no longer active.", "warning")
        return redirect(url_for('.my_results_detail', attempt_id=attempt.id))

    if attempt.deadline and now > attempt.deadline:
         flash("Time limit reached. Please submit your attempt.", "warning")

    quiz = attempt.quiz

    presented_q_ids = attempt.get_presented_questions()
    if not presented_q_ids:
         flash("Error loading questions for this attempt.", "danger")
         return redirect(url_for('.dashboard'))

    questions_query = Question.query.filter(Question.id.in_(presented_q_ids))\
                              .options(db.selectinload(Question.options),
                                       db.selectinload(Question.test_cases),
                                       db.selectinload(Question.code_templates))

    questions = questions_query.all()
    question_map = {q.id: q for q in questions}
    ordered_questions = [question_map.get(qid) for qid in presented_q_ids if question_map.get(qid)]

    if len(ordered_questions) != len(presented_q_ids):
         current_app.logger.error(f"Mismatch loading questions for attempt {attempt_id}.")
         flash("Error loading all questions for the quiz. Some may be missing.", "warning")

    existing_answers = {}
    if quiz.allow_navigation:
        answers_list = StudentAnswer.query.filter_by(attempt_id=attempt.id).all()
        existing_answers = {ans.question_id: ans for ans in answers_list}

    time_remaining_seconds = None
    if attempt.deadline:
         time_remaining = attempt.deadline - now
         time_remaining_seconds = max(0, int(time_remaining.total_seconds()))

    return render_template('student/quiz_attempt.html',
                            title=f"Taking Quiz: {quiz.title}",
                            attempt=attempt,
                            quiz=quiz,
                            questions=ordered_questions,
                            existing_answers=existing_answers,
                            time_remaining_seconds=time_remaining_seconds)


@student_bp.route('/quiz/submit/<int:attempt_id>', methods=['POST'])
@login_required
@student_required
def submit_quiz(attempt_id):
    """Handles the submission of the entire quiz attempt."""
    student_profile = get_student_profile()
    if not student_profile: abort(403)
    now = datetime.now(timezone.utc)
    is_forced_submit = request.args.get('force') == 'true'

    attempt = QuizAttempt.query.filter_by(id=attempt_id, user_id=student_profile.id).first_or_404()

    if attempt.status not in [QuizAttemptStatus.STARTED, QuizAttemptStatus.IN_PROGRESS] and not is_forced_submit:
        flash("This attempt has already been submitted or finalized.", "warning")
        return redirect(url_for('.my_results_detail', attempt_id=attempt.id))

    if not is_forced_submit and attempt.deadline and now > attempt.deadline:
         is_forced_submit = True
         flash("Submission time is past the deadline.", "warning")

    try:
        presented_q_ids = attempt.get_presented_questions()
        # Eager load necessary question data
        questions = Question.query.filter(Question.id.in_(presented_q_ids))\
                                  .options(db.selectinload(Question.options),
                                           db.selectinload(Question.test_cases)).all()
        question_map = {q.id: q for q in questions}

        existing_answers = {ans.question_id: ans for ans in attempt.answers}

        total_score = 0.0
        max_score = attempt.max_score_possible or \
                    sum(questions.points for qid in presented_q_ids if question_map.get(qid))
        needs_manual_grading = False

        for qid in presented_q_ids:
            question = question_map.get(qid)
            if not question: continue

            points_awarded = 0.0
            is_correct = None
            answer_needs_grading = False
            submitted_option_id = None
            submitted_text = None
            submitted_code = None
            code_language = None
            exec_result = None

            form_prefix = f"q_{qid}_"
            answer = existing_answers.get(qid)

            if not answer:
                answer = StudentAnswer(attempt_id=attempt.id, question_id=qid)
                db.session.add(answer)

            # --- Grade based on type ---
            if question.question_type == QuestionType.MCQ:
                selected_option_id_str = request.form.get(f"{form_prefix}option")
                if selected_option_id_str and selected_option_id_str.isdigit():
                    submitted_option_id = int(selected_option_id_str)
                    correct_option = next((opt for opt in question.options if opt.is_correct), None)
                    is_correct = (correct_option and submitted_option_id == correct_option.id)
                    if is_correct: points_awarded = question.points
                elif selected_option_id_str: is_correct = False

            elif question.question_type == QuestionType.FILL_IN_BLANKS:
                submitted_text = request.form.get(f"{form_prefix}text", "").strip()
                correct_answers = [ans.strip() for ans in (question.correct_answer_text or "").split('|') if ans.strip()]
                if submitted_text and correct_answers:
                     is_correct = submitted_text in correct_answers # Improve: case-insensitivity?
                     if is_correct: points_awarded = question.points
                elif submitted_text: is_correct = False

            elif question.question_type == QuestionType.SHORT_ANSWER:
                 submitted_text = request.form.get(f"{form_prefix}text", "").strip()
                 if submitted_text: answer_needs_grading = True

            elif question.question_type == QuestionType.CODING:
                 submitted_code = request.form.get(f"{form_prefix}code", "").strip()
                 code_language = request.form.get(f"{form_prefix}language", "").strip()
                 if submitted_code:
                     exec_result = {"status": "Execution Simulated"} # Placeholder
                     # TODO: Call actual code execution service and process results
                     points_awarded = 0
                     answer_needs_grading = True # Assume manual check needed or score based on execution

            # --- Update Answer Object ---
            answer.selected_option_id = submitted_option_id
            answer.answer_text = submitted_text
            answer.submitted_code = submitted_code
            answer.code_language = code_language
            answer.is_correct = is_correct if not answer_needs_grading else None
            answer.points_awarded = points_awarded if not answer_needs_grading and is_correct is True else 0.0
            answer.answered_at = now
            answer.execution_result = exec_result

            if answer_needs_grading:
                 answer.grading_status = GradingStatus.PENDING
                 needs_manual_grading = True
            elif is_correct is not None:
                 answer.grading_status = GradingStatus.GRADED
                 if is_correct: total_score += answer.points_awarded # Use actual points awarded
            else: # Not answered
                 answer.grading_status = GradingStatus.GRADED
                 answer.is_correct = False
                 answer.points_awarded = 0.0

        # --- Update Attempt ---
        attempt.submit_time = now
        attempt.score = total_score
        attempt.max_score_possible = max_score

        if is_forced_submit and attempt.status != QuizAttemptStatus.TIMED_OUT:
            attempt.status = QuizAttemptStatus.TIMED_OUT
        elif needs_manual_grading:
            attempt.status = QuizAttemptStatus.SUBMITTED
        else:
            attempt.status = QuizAttemptStatus.GRADED
            attempt.grading_completed_at = now

        db.session.commit()

        flash("Quiz submitted successfully!", "success")
        quiz = attempt.quiz # Get quiz for the redirect check
        if quiz.show_results_immediately and not needs_manual_grading: # Referenced quiz here
            return redirect(url_for('.my_results_detail', attempt_id=attempt.id))
        else:
            if needs_manual_grading: flash("Some answers require manual grading. Your final score will be available later.", "info")
            elif not quiz.show_results_immediately: flash("Results will be available later.", "info") # Referenced quiz here
            return redirect(url_for('.dashboard'))

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error submitting quiz attempt {attempt_id}: {e}")
        flash("An error occurred while submitting your quiz. Please try again.", "danger")
        return redirect(url_for('.take_quiz_attempt', attempt_id=attempt_id))


@student_bp.route('/results')
@login_required
@student_required
def my_results():
    """List past quiz attempts and results."""
    student_profile = get_student_profile()
    if not student_profile: abort(403)

    attempts = QuizAttempt.query.filter_by(user_id=student_profile.id)\
        .filter(QuizAttempt.status.in_([QuizAttemptStatus.SUBMITTED, QuizAttemptStatus.GRADED, QuizAttemptStatus.TIMED_OUT]))\
        .join(Quiz).options(db.joinedload(QuizAttempt.quiz))\
        .order_by(QuizAttempt.submit_time.desc()).all()

    return render_template('student/my_results_list.html', title="My Results", attempts=attempts)


@student_bp.route('/results/<int:attempt_id>')
@login_required
@student_required
def my_results_detail(attempt_id):
    """Show detailed results for a specific attempt."""
    student_profile = get_student_profile()
    if not student_profile: abort(403)

    attempt = QuizAttempt.query.filter_by(id=attempt_id, user_id=student_profile.id)\
        .options(
            db.joinedload(QuizAttempt.quiz),
            db.selectinload(QuizAttempt.answers)
                .selectinload(StudentAnswer.question)
                .selectinload(Question.options),
            db.selectinload(QuizAttempt.answers)
                .selectinload(StudentAnswer.selected_option)
        ).first_or_404()

    quiz = attempt.quiz
    now = datetime.now(timezone.utc)
    can_view_results = False
    results_config = {}
    if quiz.results_visibility_config:
        try: results_config = json.loads(quiz.results_visibility_config)
        except json.JSONDecodeError: pass

    final_statuses = [QuizAttemptStatus.GRADED, QuizAttemptStatus.SUBMITTED, QuizAttemptStatus.TIMED_OUT]
    if attempt.status in final_statuses:
        default_visibility = quiz.show_results_immediately
        if results_config.get('after_submit', default_visibility): can_view_results = True
        if results_config.get('after_quiz_end') and quiz.end_time and now > quiz.end_time: can_view_results = True
        if results_config.get('after_grading') and attempt.status == QuizAttemptStatus.GRADED: can_view_results = True

    if not can_view_results:
         flash("Results are not yet available for this quiz attempt.", "info")
         return redirect(url_for('.my_results'))

    answers_map = {ans.question_id: ans for ans in attempt.answers}
    presented_q_ids = attempt.get_presented_questions()
    questions = Question.query.filter(Question.id.in_(presented_q_ids))\
        .options(db.selectinload(Question.options)).all()
    question_map = {q.id: q for q in questions}
    ordered_questions = [question_map.get(qid) for qid in presented_q_ids if question_map.get(qid)]

    show_correct = results_config.get('show_correct', True)
    show_explanation = results_config.get('show_explanation', True)

    return render_template('student/my_results_detail.html',
                            title=f"Results: {quiz.title}",
                            attempt=attempt,
                            quiz=quiz,
                            ordered_questions=ordered_questions,
                            answers_map=answers_map,
                            show_correct=show_correct,
                            show_explanation=show_explanation)