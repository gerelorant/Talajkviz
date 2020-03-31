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


class QuizForm(FlaskForm):
    quiz: model.Quiz = None
    name = wtf.StringField(
        _l('Name'),
        validators=[wtf.validators.DataRequired()]
    )
    start_time = DateTimeField(
        _l('Start Time'),
    )

    @classmethod
    def from_model(
            cls,
            quiz: model.Quiz,
            *args,
            **kwargs):
        class Form(cls):
            pass

        def block_fields(form, block=None):
            block_id = block.id if block else 'new'
            name = block.name if block else None
            order_number = block.order_number if block else None
            check_time = block.check_time if block else None

            setattr(form, f'block_{block_id}_block_order', wtf.IntegerField(
                _l('Block Number'),
                default=order_number,
                render_kw={"columns": ('md', 2, 1)}
            ))

            setattr(form, f'block_{block_id}_name', wtf.StringField(
                _l('Block Name'),
                default=name,
                render_kw={"columns": ('md', 2, 2)}
            ))

            setattr(form, f'block_{block_id}_check_time', wtf.IntegerField(
                _l('Block Check Time'),
                default=check_time,
                render_kw={"columns": ('md', 2, 1)}
            ))

            if block is None:
                setattr(Form, f'block_{block_id}_add',
                        wtf.SubmitField('plus'))
            else:
                setattr(Form, f'block_{block_id}_save',
                        wtf.SubmitField('floppy-disk'))
                setattr(Form, f'block_{block_id}_delete',
                        wtf.SubmitField('trash'))

        def question_fields(form, question=None, block=None):
            question_id = question.id if question else 'new'
            block_id = block.id if block else \
                question.block.id if question else 'new'
            setattr(
                form,
                f'question_{block_id}_{question_id}_order_number',
                wtf.IntegerField(
                    _l('Question Number'),
                    default=question.order_number if question else None,
                    render_kw={"columns": ('md', 2, 1)}
                )
            )
            setattr(
                Form,
                f'question_{block_id}_{question_id}_time',
                wtf.IntegerField(
                    _l('Time'),
                    default=question.time if question else None,
                    render_kw={"columns": ('md', 1, 1)}
                )
            )
            setattr(
                form,
                f'question_{block_id}_{question_id}_show_choices',
                wtf.BooleanField(
                    _l('Show Choices'),
                    default=question.show_choices if question else None,
                                        render_kw={"columns": ('md', 5, 1)}
                )
            )

            if question is None:
                setattr(
                    Form,
                    f'question_{block_id}_{question_id}_add',
                    wtf.SubmitField('plus')
                )
            else:
                setattr(
                    Form,
                    f'question_{block_id}_{question_id}_save',
                    wtf.SubmitField('floppy-disk')
                )
                setattr(
                    Form,
                    f'question_{block_id}_{question_id}_delete',
                    wtf.SubmitField('trash')
                )

            setattr(
                form,
                f'question_{block_id}_{question_id}_content',
                wtf.TextAreaField(
                    _l('Content'),
                    default=question.content if question else None,
                    render_kw={"columns": ('md', ' d-none ', 12)}
                )
            )

        def choice_fields(form, choice=None, question=None, block=None):
            choice_id = choice.id if choice else 'new'
            question_id = question.id if question else \
                choice.question_id if choice else 'new'
            block_id = block.id if block else \
                question.block.id if question else  \
                choice.question.block.id if choice else 'new'
            
            setattr(
                form,
                f'choice_{block_id}_{question_id}_{choice_id}_value',
                wtf.StringField(
                    _l('Value'),
                    default=choice.value if choice else None,
                    render_kw={"columns": ('md', 1, 3)}
                )
            )
            setattr(
                form,
                f'choice_{block_id}_{question_id}_{choice_id}_points',
                wtf.FloatField(
                    _l('Points'),
                    default=choice.points if choice else None,
                    render_kw={"columns": ('md', 2, 1)}
                )
            ),
            setattr(
                form,
                f'choice_{block_id}_{question_id}_{choice_id}_flexibility',
                wtf.IntegerField(
                    _l('Flexibility'),
                    default=choice.max_levenshtein_distance if choice else None,
                    render_kw={"columns": ('md', 2, 1)}
                )
            )

            if choice is None:
                setattr(
                    Form,
                    f'choice_{block_id}_{question_id}_{choice_id}_add',
                    wtf.SubmitField('plus')
                )
            else:
                setattr(
                    Form,
                    f'choice_{block_id}_{question_id}_{choice_id}_save',
                    wtf.SubmitField('floppy-disk')
                )
                setattr(
                    Form,
                    f'choice_{block_id}_{question_id}_{choice_id}_delete',
                    wtf.SubmitField('trash')
                )

        blocks = quiz.blocks if quiz is not None else []
        for block in blocks:
            block_fields(Form, block)
            for question in block.questions:
                question_fields(Form, question)
                for choice in question.choices:
                    choice_fields(Form, choice)
                choice_fields(Form, question=question)
            question_fields(Form, block=block)
        block_fields(Form)

        return Form(quiz, *args, **kwargs)

    def __init__(self, quiz: model.Quiz, *args, **kwargs):
        self.quiz = quiz
        super().__init__(*args, **kwargs)
        self.name.data = quiz.name if quiz else None
        self.start_time.data = quiz.start_time if quiz else None


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
