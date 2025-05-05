# /your_app/teacher/forms.py
from flask_wtf import FlaskForm
from wtforms import (
    StringField, TextAreaField, SubmitField, SelectField, IntegerField,
    BooleanField, SelectMultipleField, widgets, FieldList, FormField, HiddenField,
    DateTimeField # For start/end times if using WTForms-Alchemy or similar helpers
)
# Use DateTimeLocalField for browser native picker with wtforms 3+
# from wtforms.fields import DateTimeLocalField
from wtforms.validators import DataRequired, Length, NumberRange, Optional as WtformsOptional, ValidationError, InputRequired
from ..models import Question, User, UserRole, QuestionType, QuestionSelectionStrategy, QuizStatus

# Helper widget for SelectMultipleField with checkboxes
class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


class QuestionOptionForm(FlaskForm):
    """Subform for MCQ options."""
    id = HiddenField('Option ID') # For editing existing options
    option_text = StringField('Option Text', validators=[DataRequired()])
    is_correct = BooleanField('Correct Answer')
    # display_order = IntegerField('Order', default=0) # Optional ordering


class TestCaseForm(FlaskForm):
    """Subform for Coding Test Cases."""
    id = HiddenField('Test Case ID')
    input_data = TextAreaField('Input')
    expected_output = TextAreaField('Expected Output', validators=[DataRequired()])
    is_hidden = BooleanField('Hidden from Student')
    points = IntegerField('Points', default=1, validators=[NumberRange(min=0)])
    description = StringField('Description (Optional)')
    # time_limit_ms = IntegerField('Time Limit (ms)', validators=[WtformsOptional(), NumberRange(min=0)])
    # memory_limit_kb = IntegerField('Memory Limit (KB)', validators=[WtformsOptional(), NumberRange(min=0)])


class QuestionForm(FlaskForm):
    """Form for creating/editing questions. Needs JS for dynamic fields."""
    question_type = SelectField('Question Type', choices=[(t.value, t.name.replace('_', ' ').title()) for t in QuestionType], validators=[DataRequired()])
    question_text = TextAreaField('Question Text', validators=[DataRequired()])
    difficulty = SelectField('Difficulty', choices=[('Easy', 'Easy'), ('Medium', 'Medium'), ('Hard', 'Hard')], validators=[WtformsOptional()])
    points = StringField('Points', default="1.0", validators=[DataRequired()]) # Use StringField to accept float easily initially
    explanation = TextAreaField('Explanation (Optional)')
    is_public = BooleanField('Make Publicly Available? (Careful: allows use outside your org)')
    # Add tags field if needed (e.g., SelectMultipleField or StringField with parsing)
    # tags = StringField('Tags (comma-separated)')

    # Placeholder fields - these need to be dynamically handled/populated via route/JS
    # Normally, you might structure the route to handle different forms or use FieldList
    correct_answer_text = StringField('Correct Answer (Fill-in/Short)', validators=[WtformsOptional()]) # For TEXT based answers
    options = FieldList(FormField(QuestionOptionForm), min_entries=1, label="MCQ Options") # For MCQ
    test_cases = FieldList(FormField(TestCaseForm), min_entries=1, label="Test Cases") # For Coding

    submit = SubmitField('Save Question')

    def validate_points(self, points):
        try:
            p_float = float(points.data)
            if p_float <= 0:
                 raise ValidationError('Points must be a positive number.')
        except ValueError:
            raise ValidationError('Points must be a valid number.')


class QuizForm(FlaskForm):
    """Form for creating/editing quizzes."""
    title = StringField('Quiz Title', validators=[DataRequired(), Length(max=150)])
    description = TextAreaField('Description', validators=[WtformsOptional()])
    # Use DateTimeLocalField if available and preferred for picker
    # Example if using WTForms 3+ and browser picker:
    # start_time = DateTimeLocalField('Start Time (Optional)', format='%Y-%m-%dT%H:%M', validators=[WtformsOptional()])
    # end_time = DateTimeLocalField('End Time (Optional)', format='%Y-%m-%dT%H:%M', validators=[WtformsOptional()])
    # Using basic StringFields requires parsing in the route
    start_time_str = StringField('Start Time (Optional - YYYY-MM-DD HH:MM)', validators=[WtformsOptional()])
    end_time_str = StringField('End Time (Optional - YYYY-MM-DD HH:MM)', validators=[WtformsOptional()])

    duration_minutes = IntegerField('Duration (Minutes)', default=60, validators=[DataRequired(), NumberRange(min=1)])
    status = SelectField('Status', choices=[(s.value, s.value) for s in QuizStatus if s != QuizStatus.ACTIVE], default=QuizStatus.DRAFT.value, validators=[DataRequired()]) # Exclude ACTIVE? Or handle in logic
    max_attempts = IntegerField('Max Attempts (0 for unlimited)', default=1, validators=[DataRequired(), NumberRange(min=0)])
    selection_strategy = SelectField('Question Selection', choices=[(s.value, s.value) for s in QuestionSelectionStrategy], default=QuestionSelectionStrategy.FIXED.value, validators=[DataRequired()])
    num_questions_to_pool = IntegerField('Number of Questions to Pool (if Random)', validators=[WtformsOptional(), NumberRange(min=1)])
    shuffle_questions = BooleanField('Shuffle Question Order')
    shuffle_options = BooleanField('Shuffle MCQ Option Order')
    show_results_immediately = BooleanField('Show Results Immediately After Submission', default=True)
    # TODO: Add fields for results_visibility_config JSON (maybe multiple checkboxes?)
    allow_navigation = BooleanField('Allow Navigation Between Questions', default=True)
    proctoring_enabled = BooleanField('Enable Proctoring Features (Requires User Consent)')
    # TODO: Add fields for proctoring_config JSON (checkboxes for cam/mic/screen?)

    # Field for selecting questions - MultiCheckboxField is suitable for smaller lists
    questions = MultiCheckboxField('Select Questions', coerce=int, validators=[InputRequired(message="Please select at least one question.")])

    submit = SubmitField('Save Quiz')

    # Example validation dependant on strategy
    def validate_num_questions_to_pool(self, field):
        if self.selection_strategy.data == QuestionSelectionStrategy.RANDOM.value:
            if not field.data or field.data < 1:
                raise ValidationError('Number of questions to pool is required for Random strategy.')
        elif field.data:
             # Clear the field if strategy is not Random? Or just ignore it.
             # field.data = None # Option 1: Clear it
             pass # Option 2: Ignore it (route logic should handle)


class AssignQuizForm(FlaskForm):
    """Form for assigning a quiz to students."""
    # Use MultiCheckboxField for selecting students
    students = MultiCheckboxField('Select Students', coerce=int, validators=[DataRequired(message="Please select at least one student.")])
    # Use DateTimeLocalField if available
    # due_date = DateTimeLocalField('Due Date (Optional)', format='%Y-%m-%dT%H:%M', validators=[WtformsOptional()])
    due_date_str = StringField('Due Date (Optional - YYYY-MM-DD HH:MM)', validators=[WtformsOptional()])
    submit = SubmitField('Assign Quiz')