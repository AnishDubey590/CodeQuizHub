# /your_app/teacher/routes.py
from flask import Blueprint, render_template, flash, redirect, url_for, request, abort, current_app
from flask_login import login_required, current_user

from .. import db
from ..models import User, Credentials, Organization, UserRole, Quiz, Question, QuizAssignment, QuizAttempt, StudentAnswer
from ..utils.decorators import teacher_required
# TODO: Import forms for Quiz/Question creation, Assignment

# Assuming teacher_bp is defined in teacher/__init__.py
from . import teacher_bp

# Helper to get teacher's organization
def get_teacher_org():
    if not current_user.is_authenticated or not current_user.user_profile:
        return None
    return current_user.user_profile.organization


@teacher_bp.route('/dashboard')
@login_required
@teacher_required
def dashboard():
    """Teacher Dashboard."""
    org = get_teacher_org()
    if not org:
        flash("Your account is not associated with an organization.", "warning")
        # Maybe redirect to profile or specific error page
        return redirect(url_for('main.view_profile'))

    teacher_profile_id = current_user.user_profile.id

    # Stats specific to this teacher
    my_students_count = User.query.join(Credentials).filter(User.organization_id == org.id, Credentials.role == UserRole.STUDENT).count() # TODO: Refine if teachers only manage specific students
    my_quizzes_count = Quiz.query.filter_by(creator_user_id=teacher_profile_id, organization_id=org.id).count()
    my_assignments_count = QuizAssignment.query.filter_by(assigned_by_user_id=teacher_profile_id).count()
    # TODO: Add recent activity/assignments

    return render_template('teacher/dashboard.html',
                           title="Teacher Dashboard",
                           org=org,
                           my_students_count=my_students_count,
                           my_quizzes_count=my_quizzes_count,
                           my_assignments_count=my_assignments_count
                           )

# --- Quiz Management ---

@teacher_bp.route('/quizzes')
@login_required
@teacher_required
def manage_quizzes():
    """View quizzes created by this teacher."""
    org = get_teacher_org()
    if not org: return redirect(url_for('.dashboard')) # Redirect if no org
    teacher_profile = current_user.user_profile

    quizzes = Quiz.query.filter_by(creator_user_id=teacher_profile.id, organization_id=org.id)\
        .order_by(Quiz.created_at.desc()).all()

    return render_template('teacher/manage_quizzes.html', title="My Quizzes", quizzes=quizzes, org=org)


@teacher_bp.route('/quizzes/create', methods=['GET', 'POST'])
@login_required
@teacher_required
def create_quiz():
    """Create a new quiz (linked to teacher and org)."""
    org = get_teacher_org()
    if not org: return redirect(url_for('.dashboard'))
    teacher_profile = current_user.user_profile

    # TODO: Create QuizForm
    # form = QuizForm()
    form = None # Placeholder

    # Add organization's questions + teacher's questions + public questions to choices?
    # available_questions = Question.query.filter(
    #     (Question.organization_id == org.id) | (Question.is_public == True)
    # ).order_by(Question.id).all()
    # form.questions.choices = [(q.id, f"Q{q.id} ({q.question_type.name}) - {q.question_text[:50]}...") for q in available_questions]


    # if form.validate_on_submit():
    #     try:
    #         new_quiz = Quiz(
    #             title=form.title.data,
    #             description=form.description.data,
    #             organization_id=org.id, # Link to teacher's org
    #             creator_user_id=teacher_profile.id, # Link to teacher
    #             duration_minutes=form.duration_minutes.data,
    #             # Set other fields: start_time, end_time, status, strategy, etc.
    #         )
    #         # TODO: Add selected questions to the quiz (handle quiz_questions relationship)
    #         # selected_q_ids = form.questions.data # Assuming MultiCheckboxField or similar
    #         # questions = Question.query.filter(Question.id.in_(selected_q_ids)).all()
    #         # new_quiz.questions.extend(questions)

    #         db.session.add(new_quiz)
    #         db.session.commit()
    #         flash('Quiz created successfully!', 'success')
    #         return redirect(url_for('.manage_quizzes'))
    #     except Exception as e:
    #         db.session.rollback()
    #         current_app.logger.error(f"Error creating quiz by teacher {teacher_profile.id}: {e}")
    #         flash(f"Error creating quiz: {e}", 'danger')

    # TODO: Create template teacher/create_quiz.html
    return render_template('teacher/create_edit_quiz.html', title="Create Quiz", form=form, org=org, quiz=None)

# TODO: Route to edit existing quizzes created by this teacher
# @teacher_bp.route('/quizzes/edit/<int:quiz_id>', methods=['GET', 'POST'])

# TODO: Route to delete quizzes


# --- Question Management ---

@teacher_bp.route('/questions')
@login_required
@teacher_required
def manage_questions():
     """View questions created by this teacher."""
     org = get_teacher_org()
     if not org: return redirect(url_for('.dashboard'))
     teacher_profile = current_user.user_profile

     questions = Question.query.filter_by(creator_user_id=teacher_profile.id, organization_id=org.id)\
        .order_by(Question.created_at.desc()).all()

     # TODO: Create template teacher/manage_questions.html
     return render_template('teacher/manage_questions.html', title="My Questions", questions=questions, org=org)


@teacher_bp.route('/questions/create', methods=['GET', 'POST'])
@login_required
@teacher_required
def create_question():
    """Create a new question (linked to teacher and org)."""
    org = get_teacher_org()
    if not org: return redirect(url_for('.dashboard'))
    teacher_profile = current_user.user_profile

    # TODO: Create QuestionForm (likely needs dynamic fields based on question type)
    # form = QuestionForm()
    form = None # Placeholder

    # if form.validate_on_submit():
    #     try:
    #          # Determine question type and create appropriate objects (Options, TestCases)
    #          q_type = QuestionType(form.question_type.data)
    #          new_question = Question(
    #              organization_id=org.id,
    #              creator_user_id=teacher_profile.id,
    #              question_type=q_type,
    #              question_text=form.question_text.data,
    #              # ... other common fields ...
    #          )
    #          db.session.add(new_question)
    #          db.session.flush() # Get ID

    #          # Add options if MCQ, test cases if Coding, etc.
    #          # ... logic based on q_type ...

    #          db.session.commit()
    #          flash("Question created successfully!", 'success')
    #          return redirect(url_for('.manage_questions'))
    #     except Exception as e:
    #         db.session.rollback()
    #         flash(f"Error creating question: {e}", 'danger')

     # TODO: Create template teacher/create_edit_question.html
    return render_template('teacher/create_edit_question.html', title="Create Question", form=form, org=org, question=None)

# TODO: Routes to edit/delete questions


# --- Quiz Assignment ---

@teacher_bp.route('/assign/<int:quiz_id>', methods=['GET', 'POST'])
@login_required
@teacher_required
def assign_quiz(quiz_id):
    """Assign a quiz created by this teacher or owned by the org to students."""
    org = get_teacher_org()
    if not org: return redirect(url_for('.dashboard'))
    teacher_profile_id = current_user.user_profile.id

    quiz = Quiz.query.get_or_404(quiz_id)

    # Security Check: Ensure the teacher can assign THIS quiz
    # (They created it OR it belongs to their org and they have permission)
    if quiz.organization_id != org.id:
         abort(403) # Cannot assign quiz from another org
    # Optional: maybe only allow assigning quizzes they created?
    # if quiz.creator_user_id != teacher_profile_id and quiz.organization_id != org.id:
    #      abort(403)

    # TODO: Create AssignQuizForm, dynamically populate student choices
    # form = AssignQuizForm()
    form = None # Placeholder
    students = User.query.join(Credentials).filter(
        User.organization_id == org.id,
        Credentials.role == UserRole.STUDENT,
        Credentials.is_active == True
    ).order_by(User.display_name).all()
    # form.students.choices = [(s.id, s.display_name or s.credentials.username) for s in students]

    # if form.validate_on_submit():
    #     selected_student_ids = form.students.data # List of student profile IDs
    #     due_date = form.due_date.data # Optional due date
    #     assigned_count = 0
    #     skipped_count = 0
    #     try:
    #         for student_id in selected_student_ids:
    #             # Check if already assigned
    #             existing_assignment = QuizAssignment.query.filter_by(quiz_id=quiz_id, student_user_id=student_id).first()
    #             if not existing_assignment:
    #                 assignment = QuizAssignment(
    #                     quiz_id=quiz_id,
    #                     student_user_id=student_id,
    #                     assigned_by_user_id=teacher_profile_id,
    #                     due_date=due_date
    #                 )
    #                 db.session.add(assignment)
    #                 assigned_count += 1
    #             else:
    #                 skipped_count += 1

    #         db.session.commit()
    #         msg = f"Quiz '{quiz.title}' assigned to {assigned_count} student(s)."
    #         if skipped_count > 0:
    #             msg += f" {skipped_count} student(s) were already assigned."
    #         flash(msg, 'success')
    #         # TODO: Send notifications to students?
    #         return redirect(url_for('.view_assignments')) # Redirect to assignment list
    #     except Exception as e:
    #         db.session.rollback()
    #         flash(f"Error assigning quiz: {e}", 'danger')

    # TODO: Create template teacher/assign_quiz.html
    return render_template('teacher/assign_quiz.html', title=f"Assign Quiz: {quiz.title}", form=form, quiz=quiz, org=org)


@teacher_bp.route('/assignments')
@login_required
@teacher_required
def view_assignments():
    """View quizzes assigned by this teacher."""
    org = get_teacher_org()
    if not org: return redirect(url_for('.dashboard'))
    teacher_profile_id = current_user.user_profile.id

    assignments = QuizAssignment.query.filter_by(assigned_by_user_id=teacher_profile_id)\
        .join(Quiz).join(User, QuizAssignment.student_user_id == User.id)\
        .options(db.joinedload(QuizAssignment.quiz), db.joinedload(QuizAssignment.student).joinedload(User.credentials)) \
        .order_by(QuizAssignment.assigned_at.desc()).all()

    # TODO: Create template teacher/view_assignments.html
    return render_template('teacher/view_assignments.html', title="My Assignments", assignments=assignments, org=org)

# TODO: Route to view results/progress for a specific assignment


# --- Student Results Analysis ---

@teacher_bp.route('/results')
@login_required
@teacher_required
def view_student_results():
    """Entry point for viewing results of quizzes managed/assigned by teacher."""
    org = get_teacher_org()
    if not org: return redirect(url_for('.dashboard'))
    teacher_profile_id = current_user.user_profile.id

    # List quizzes assignable/created by this teacher for selection
    # Could be quizzes created by teacher OR org quizzes they have permission for
    relevant_quizzes = Quiz.query.filter(
        Quiz.organization_id == org.id, # Must be in teacher's org
        (Quiz.creator_user_id == teacher_profile_id) # | (Quiz.some_permission_flag == True) # Or teacher created it
    ).order_by(Quiz.title).all()

    # TODO: Template needs dropdown/list to select a quiz, then AJAX/redirect to view details per quiz
    return render_template('teacher/results_overview.html', title="Student Results", quizzes=relevant_quizzes, org=org)

# TODO: Routes to show aggregated results for a specific quiz or student
# Example: /results/quiz/<int:quiz_id>
# Example: /results/student/<int:student_user_id>