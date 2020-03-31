import datetime as dt

from flask import current_app, has_app_context, abort, request, redirect, flash
from flask_admin import Admin, expose, AdminIndexView
from flask_admin.contrib.sqla import ModelView as SQLAlchemyModelView
from flask_admin.contrib.sqla.filters import EnumEqualFilter
from flask_admin.contrib.sqla.form import get_form
from flask_admin.model.form import create_editable_list_form
from flask_babelex import gettext as _, lazy_gettext as _l
from flask_security import current_user, login_required
import sqlalchemy as sa
import wtforms as wtf

import model
from form import QuestionForm, \
    QuizEditorForm, BlockEditorForm, QuestionEditorForm, ChoiceEditorForm


class IndexView(AdminIndexView):

    @expose('/')
    def index(self, page: int = 1):
        per_page = current_app.config.get('PER_PAGE', 20)
        quizzes = model.Quiz.query\
            .order_by(model.Quiz.start_time_utc.desc())\
            .paginate(page, per_page, error_out=False)

        return self.render('index.html', quizzes=quizzes)

    @expose('/form', methods=['GET', 'POST', 'DELETE'])
    @login_required
    def form(self):
        form_type = request.args.get('form_type')
        quiz_id = request.args.get('quiz_id', 0)
        block_id = request.args.get('block_id', 0)
        question_id = request.args.get('question_id', 0)
        choice_id = request.args.get('choice_id', 0)

        if form_type == 'quiz':
            form = QuizEditorForm(
                quiz=model.Quiz.query.get(quiz_id))

        elif form_type == 'block':
            form = BlockEditorForm(
                block=model.Block.query.get(block_id),
                quiz=model.Quiz.query.get(quiz_id))

        elif form_type == 'question':
            form = QuestionEditorForm(
                question=model.Question.query.get(question_id),
                block=model.Block.query.get(block_id))

        elif form_type == 'choice':
            form = ChoiceEditorForm(
                choice=model.Choice.query.get(choice_id),
                question=model.Question.query.get(question_id))

        else:
            return abort(400)

        if request.method == 'GET':
            form.load_model()
            return self.render('_editor_form.html', form=form)
        elif form.validate_on_submit():
            if form.delete.data:
                model.db.session.delete(form.model)
                model.db.session.commit()
                flash(_('Successful delete!'))
            else:
                form.save_model()
                if form.model.id is None:
                    model.db.session.add(form.model)
                model.db.session.commit()
                flash(_('Successful edit!'))
        else:
            flash(_('Validation error!'))

        return redirect(request.referrer)


    @expose('/<int:quiz_id>/pager')
    def pager(self, quiz_id: int):
        active = request.args.get('active', 1, type=int)
        quiz = model.Quiz.query.get(quiz_id)
        if quiz is None:
            return abort(404)

        fill = model.FilledQuiz.query\
            .filter_by(user_id=current_user.id)\
            .filter_by(quiz_id=quiz_id).first()

        block = fill.current_block
        if block is None:
            return abort(404)

        questions = fill.available_questions
        finish = True
        for question in questions:
            if question.answers.filter_by(quiz_id=fill.id).first() is None:
                finish = False
                break

        return self.render("pager.html", questions=questions,
                           finish=finish, active=active)

    @expose('/<int:quiz_id>/',
            methods=['GET', 'POST'])
    @expose('/<int:quiz_id>/<int:block>/',
            methods=['GET', 'POST'])
    @expose('/<int:quiz_id>/<int:block>/<int:question>',
            methods=['GET', 'POST'])
    @login_required
    def quiz(self, quiz_id: int, block: int = None, question: int = None):
        quiz = model.Quiz.query.get(quiz_id)
        if quiz is None:
            return abort(404)

        fill = model.FilledQuiz.query\
            .filter_by(user_id=current_user.id)\
            .filter_by(quiz_id=quiz_id).first()

        if fill is None:
            fill = model.FilledQuiz(
                user_id=current_user.id,
                quiz_id=quiz_id)
            model.db.session.add(fill)
            model.db.session.commit()

        if block is None:
            block = fill.current_block
        else:
            finish = request.args.get('finish', False)
            block = quiz.blocks.filter_by(order_number=block).first()
            if finish:
                fill.finished_blocks.append(block)
                model.db.session.commit()

        if block is None:
            block = quiz.blocks.order_by(model.Block.order_number).first()

        if block in fill.finished_blocks:
            answers = fill.answers\
                .join(model.Question)\
                .filter(model.Question.block_id == block.id)\
                .order_by(model.Question.order_number)

            block_points = model.int_or_float(
                sum([ans.points for ans in answers])
            )
            return self.render('answers.html', block=block,
                               answers=answers,
                               block_points=block_points,
                               total=fill.points)

        question = question or 1
        question = block.questions\
            .filter_by(order_number = question)\
            .first()

        if question not in fill.available_questions:
            return abort(403)

        if block == fill.current_block:
            form = QuestionForm.from_model(question, fill)
            return self.render('quiz.html', form=form)
        else:
            answer = fill.answers\
                .filter(model.Answer.question_id == question.id)\
                .first()
            return self. render('answer.html', answer=answer)


admin = Admin(
    name='Talajkvíz',
    template_mode='bootstrap3',
    index_view=IndexView(
        url='/'
    )
)


def add_view(name = None, category = None, model_class = None):
    def wrap(cls):
        if model_class is None:
            view = cls(
                name=name,
                category=category)
        else:
            view = cls(
                model_class,
                model.db.session,
                name=name,
                category=category
            )
        admin.add_view(view)

        return cls

    return wrap


def query_filter(model_class, label: str = None, flt = None):
    if label is None:
        label = _l(model_class.__name__)

    if flt:
        qry = model_class.query.filter(flt)
    else:
        qry = model_class.query
    return EnumEqualFilter(model_class.id, label,
                           options=[(x.id, str(x)) for x in qry.all()])


class ModelView(SQLAlchemyModelView):
    can_set_page_size = True
    page_size = 20

    columns = {}
    roles = []
    create_roles = []
    edit_roles = []
    delete_roles = []
    action_roles = []

    can_export = True
    export_types = ['xlsx', 'csv', 'json', 'dbf']

    column_extra_fields = {}

    def is_accessible(self) -> bool:
        """Returns if page can be accessed by user."""
        self._refresh_filters_cache()
        self._refresh_forms_cache()
        if current_user.is_authenticated:
            return current_user.has_any_role(*self.roles)
        else:
            return False

    @property
    def can_create(self) -> bool:
        if current_user.is_anonymous:
            return False

        return current_user.has_any_role(*self.create_roles)

    @property
    def can_edit(self) -> bool:
        if current_user.is_anonymous:
            return False

        return current_user.has_any_role(*self.edit_roles)

    @property
    def can_delete(self) -> bool:
        if current_user.is_anonymous:
            return False

        return current_user.has_any_role(*self.delete_roles)

    @property
    def column_display_actions(self) -> bool:
        if current_user.is_anonymous:
            return False

        return current_user.has_any_role(*self.action_roles, *self.delete_roles)

    @property
    def column_list(self) -> tuple:
        return tuple(self.columns.keys()) or []

    @property
    def column_labels(self) -> dict:
        return self.columns or {}

    def scaffold_list_form(self, widget=None, validators=None):
        """
            Create form for the `index_view` using only the columns from
            `self.column_editable_list`.

            :param widget:
                WTForms widget class. Defaults to `XEditableWidget`.
            :param validators:
                `form_args` dict with only validators
                {'name': {'validators': [required()]}}
        """
        converter = self.model_form_converter(self.session, self)
        form_class = get_form(self.model, converter,
                              base_class=self.form_base_class,
                              only=self.column_editable_list,
                              field_args=validators,
                              extra_fields=self.column_extra_fields)

        # if widget is None:
        #    widget = XEditableWidgetWithDateTime()

        return create_editable_list_form(self.form_base_class, form_class,
                                         widget)

    @classmethod
    def add_view(cls):
        admin.add_view(cls(
            cls.model_class,
            model.db.session,
            name=cls.name,
            category=cls.category
        ))

    @property
    def _column_filters(self):
        return []

    @property
    def column_filters(self):
        if has_app_context():
            return self._column_filters
        else:
            return []

    @property
    def column_type_formatters(self) -> dict:
        data = super().column_type_formatters
        data.update({
            dt.datetime:
                lambda view, value: value.strftime('%Y.%m.%d %H:%M:%S'),
            float:
                lambda view, value: value if value % 1 else int(value)
        })
        return data

    def get_empty_list_message(self):
        """Returns the message shown if there are no records to show."""
        return _l('There are no items in the table.')


@add_view(_l('Quizzes'), None, model.Quiz)
class QuizView(ModelView):
    create_template = "create.html"
    edit_template = "edit.html"

    def get_query(self):
        if current_user.has_role('admin'):
            return super().get_query()

        return model.db.session.query(model.Quiz)\
            .filter_by(host_id=current_user.id)

    def get_count_query(self):
        if current_user.has_role('admin'):
            return super().get_count_query()

        return model.db.session.query(sa.func.count(model.Quiz.id))\
            .filter_by(host_id=current_user.id)

    def create_form(self, obj=None):
        return QuizEditorForm(obj)

    def edit_form(self, obj=None):
        form = QuizEditorForm(obj)
        if request.method == 'GET':
            form.load_model()
        return form


@add_view(_l('Filled Quizzes'), _l('Check'), model.FilledQuiz)
class FilledQuizView(ModelView):
    can_create = False
    can_edit = False
    can_delete = False

    columns = {
        'user': _l('User'),
        'quiz': _l('Quiz'),
        'points': _l('Points')
    }

    @property
    def _column_filters(self):
        # noinspection PyTypeChecker
        return [query_filter(model.User)]


@add_view(_l('Answers'), _l('Check'), model.Answer)
class AnswerView(ModelView):
    can_create = False
    can_edit = False
    can_delete = False

    columns = {
        'question': _l('Question'),
        'quiz.user': _l('User'),
        'value': _l('Answer'),
        'points': _l('Points')
    }
    @property
    def _column_filters(self):
        # noinspection PyTypeChecker
        return [query_filter(model.FilledQuiz)]