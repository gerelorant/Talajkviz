import typing

import wtforms as wtf
from flask import request
from flask_security import current_user
from flask_admin.contrib.sqla.fields import QuerySelectField, \
    QuerySelectMultipleField
from flask_admin.form.fields import DateTimeField
from flask_babelex import lazy_gettext as _l
from flask_wtf import FlaskForm

import model


def choices(question):
    def choices():
        return model.Choice.query\
            .filter(model.Choice.question_id == question.id)

    return choices


class QuestionForm(FlaskForm):
    question: model.Question = None
    fill: model.FilledQuiz = None

    @classmethod
    def from_model(
            cls,
            question: model.Question,
            fill: model.FilledQuiz,
            *args,
            **kwargs):
        class Form(QuestionForm):
            pass

        if question.show_choices:
            if question.multiple:
                Form.answer = QuerySelectMultipleField(
                    '',
                    query_factory=choices(question),
                    get_pk=lambda x: x.id,
                    get_label=lambda x: x.value
                )
                Form.submit = wtf.SubmitField(_l('Save'))
            else:
                Form.answer = wtf.RadioField(
                    '',
                    choices = [(x.id, x.value) for x in choices(question)()],
                    coerce=int
                )
                Form.submit = wtf.SubmitField(_l('Save'))
        else:
            Form.answer = wtf.StringField(
                '',
                validators=[wtf.validators.Length(max=255)]
            )
            Form.submit = wtf.SubmitField(_l('Save'))

        form = Form(fill, question, *args, **kwargs)
        return form

    def __init__(
            self,
            fill: model.FilledQuiz,
            question: model.Question,
            *args,
            **kwargs):
        super().__init__(*args, **kwargs)
        self.fill = fill
        self.question = question

        answers = model.Answer.query\
            .filter(model.Answer.quiz == self.fill)\
            .filter(model.Answer.question == self.question)
        first = answers.first()
        all = answers.all()

        if request.method == 'GET':
            if isinstance(self.answer, wtf.StringField):
                self.answer.data = first.text if first else None
            elif isinstance(self.answer, wtf.SelectField):
                self.answer.data = first.choice_id if first else None
            elif isinstance(self.answer, QuerySelectField):
                self.answer.data = first
            elif isinstance(self.answer, QuerySelectMultipleField):
                self.answer.data = all
            return

        if isinstance(self.answer, wtf.StringField):
            ans = answers.first()
            if ans is None:
                ans = model.Answer(
                    text=self.answer.data,
                    quiz_id=fill.id,
                    question_id=self.question.id
                )
                model.db.session.add(ans)
            else:
                ans.text = self.answer.data
        elif isinstance(self.answer, (wtf.RadioField, wtf.SelectField)):
            ans = answers.first()
            if ans is None:
                ans = model.Answer(
                    choice_id=self.answer.data,
                    quiz_id=fill.id,
                    question_id=self.question.id
                )
                model.db.session.add(ans)
            else:
                ans.choice_id = self.answer.data
        elif isinstance(self.answer, QuerySelectField):
            ans = answers.first()
            if ans is None:
                print(self.answer.data)
                ans = model.Answer(
                    choice=self.answer.data,
                    quiz_id=fill.id,
                    question_id=self.question.id
                )
                model.db.session.add(ans)
            else:
                ans.choice = self.answer.data
        elif isinstance(self.answer, QuerySelectMultipleField):
            for ans in answers:
                model.db.session.remove(ans)
            for selected in self.answer.data:
                ans = model.Answer(
                    choice_id=selected.id,
                    quiz_id=fill.id,
                    question_id=self.question.id
                )
                model.db.session.add(ans)

        model.db.session.commit()


class EditorForm(FlaskForm):
    def __init__(self, m: model.db.Model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = m

    def load_model(self):
        # noinspection PyTypeChecker
        for field in self:
            if isinstance(field, (wtf.SubmitField, wtf.HiddenField)):
                continue
            field.data = getattr(self.model, field.name)

    def save_model(self):
        # noinspection PyTypeChecker
        for field in self:
            if isinstance(field, (wtf.SubmitField, wtf.HiddenField)):
                continue
            setattr(self.model, field.name, field.data)


class QuizEditorForm(EditorForm):
    name = wtf.StringField(
        _l('Name'),
        validators=[wtf.validators.DataRequired()])
    start_time = DateTimeField(
        _l('Start Time'),
        validators=[wtf.validators.Optional()])
    public = wtf.BooleanField(
        _l('Public'),
        validators=[wtf.validators.Optional()])
    submit = wtf.SubmitField(_l('Save'), render_kw={'class_':'btn btn-success'})

    def __init__(self, quiz: model.Quiz = None, *args, **kwargs):
        if quiz is None:
            quiz = model.Quiz()
        super().__init__(quiz, *args, **kwargs)


class BlockEditorForm(EditorForm):
    order_number = wtf.IntegerField(
        _l('Order Number'),
        validators=[wtf.validators.DataRequired()])
    name = wtf.StringField(
        _l('Name'),
        validators=[wtf.validators.DataRequired()])
    check_time = wtf.IntegerField(
        _l('Check Time'),
        default=120,
        validators=[wtf.validators.DataRequired()])
    submit = wtf.SubmitField(_l('Save'), render_kw={'class_':'btn btn-success'})
    delete = wtf.SubmitField(_l('Remove'), render_kw={'class_':'btn btn-danger'})

    def __init__(
            self,
            block: model.Block = None,
            quiz: model.Quiz = None,
            *args,
            **kwargs):
        if block is None:
            if quiz is None or quiz.id is None:
                raise ValueError('Quiz must be provided for new block!')
            else:
                latest = quiz.blocks\
                    .order_by(model.Block.order_number.desc())\
                    .first()

                if latest is None:
                    order_number = 1
                else:
                    order_number = latest.order_number + 1
                block = model.Block(quiz_id=quiz.id, order_number=order_number)

        super().__init__(block, *args, **kwargs)


class QuestionEditorForm(EditorForm):
    order_number = wtf.IntegerField(
        _l('Order Number'),
        validators=[wtf.validators.DataRequired()])
    time = wtf.IntegerField(
        _l('Time'),
        validators=[wtf.validators.DataRequired()])
    show_choices = wtf.BooleanField(
        _l('Show Choices'),
        validators=[wtf.validators.Optional()])
    content = wtf.TextAreaField()

    submit = wtf.SubmitField(_l('Save'), render_kw={'class_':'btn btn-success'})
    delete = wtf.SubmitField(_l('Remove'), render_kw={'class_':'btn btn-danger'})

    def __init__(
            self,
            question: model.Question = None,
            block: model.Block = None,
            *args,
            **kwargs):
        if question is None:
            if block is None or block.id is None:
                raise ValueError('Block must be provided for new question!')
            else:
                latest = block.questions\
                    .order_by(model.Question.order_number.desc())\
                    .first()

                if latest is None:
                    order_number = 1
                else:
                    order_number = latest.order_number + 1
                question = model.Question(
                    block_id=block.id,
                    order_number=order_number)
        super().__init__(question, *args, **kwargs)


class ChoiceEditorForm(EditorForm):
    value = wtf.StringField(
        _l('Value'),
        validators=[wtf.validators.DataRequired()])
    points = wtf.FloatField(
        _l('Points'),
        default=0,
        validators=[wtf.validators.Optional()])
    max_levenshtein_distance = wtf.IntegerField(
        _l('Flexibility (1-5)'),
        default=3,
        validators=[wtf.validators.NumberRange(min=1, max=5)])

    submit = wtf.SubmitField(_l('Save'), render_kw={'class_':'btn btn-success'})
    delete = wtf.SubmitField(_l('Remove'), render_kw={'class_':'btn btn-danger'})

    def __init__(
            self,
            choice: model.Choice = None,
            question: model.Question = None,
            *args,
            **kwargs):
        if choice is None:
            if question is None or question.id is None:
                raise ValueError('Question must be provided for new choice!')
            else:
                choice = model.Choice(question_id=question.id)
        super().__init__(choice, *args, **kwargs)
