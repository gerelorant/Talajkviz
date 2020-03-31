import datetime as dt
import pytz
import typing

import sqlalchemy as sa
from sqlalchemy.ext.hybrid import hybrid_property
from flask_babelex import get_timezone
from flask_migrate import init, migrate, upgrade
from flask_security import UserMixin, RoleMixin, current_user
from flask_security.utils import verify_password, hash_password
from flask_sqlalchemy import SQLAlchemy, Model
from Levenshtein import distance as str_distance


def int_or_float(num: float) -> typing.Union[int, float]:
    if num is None:
        return 0
    return num if num % 1 else int(num)


class BaseModel(Model):
    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)

    @classmethod
    def load_csv(
            cls,
            path: str,
            separator: str = ';',
            newline: str = '\n',
            encoding: str = 'cp1252') -> typing.Generator[dict, None, None]:
        with open(path, encoding=encoding) as f:
            data = f.read()

        lines = [x.strip() for x in data.split(newline)]
        headers = [x.strip() for x in lines[0].split(separator)]
        for line in lines[1:]:
            if not line:
                continue

            values = [x.strip() for x in line.split(separator)]

            kwargs = {}
            for i, name in enumerate(headers):
                kwargs[name] = values[i]

            yield kwargs

    def update(self, **kwargs):
        for (k, v) in kwargs.items():
            if isinstance(v, str) and not v:
                continue
            setattr(self, k, v)

    @classmethod
    def update_or_create(cls, **kwargs):
        pk_name = list(kwargs.keys())[0]
        pk = kwargs[pk_name]

        model = cls.query.filter_by(**{pk_name: pk}).first()
        if model is None:
            model = cls()
            model.update(**kwargs)
            db.session.add(model)
        else:
            model.update(**kwargs)

    @classmethod
    def from_csv(
            cls,
            path: str = None,
            separator: str = ';',
            newline: str = '\n',
            encoding: str = 'cp1252'):
        """Load settings from CSV file.

        :param path: Path to csv file.
        :param separator: Cell separator character.
        :param newline: Line separator character.
        :param encoding: Encoding of CSV file.
        """
        if path is None:
            path = f'data/import/{getattr(cls, "__tablename__")}.csv'

        file_data = cls.load_csv(path, separator, newline, encoding)
        for model_data in file_data:
            cls.update_or_create(**model_data)
        db.session.commit()


db = SQLAlchemy(
    model_class=BaseModel,
    metadata=sa.MetaData(
        naming_convention={
            "ix": 'ix_%(column_0_label)s',
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(column_0_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s"
        }
    )
)


def name_column(
        length: int = 80,
        nullable: bool = False,
        unique: bool = True,
        index: bool = True):
    return db.Column(
        db.String(length),
        nullable=nullable,
        unique=unique,
        index=index)


class Role(db.Model, RoleMixin):
    name = name_column(length=16)
    description = db.Column(db.Text)

    def __repr__(self) -> str:
        """String representation of role."""
        return f'{self.name}'


class User(db.Model, UserMixin):
    username = db.Column(db.String(16), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, index=True)
    password = db.Column(db.String(255))
    language = db.Column(db.String(8), default='hu')

    roles = db.relationship(
        "Role",
        secondary=db.Table(
            'user_role',
            db.Column('user_id', db.Integer,
                      db.ForeignKey('user.id'), primary_key=True),
            db.Column('role_id', db.Integer,
                      db.ForeignKey('role.id'), primary_key=True)
        ),
        backref=db.backref("users", lazy="dynamic")
    )

    def __repr__(self) -> str:
        """String representation of user."""
        return f'{self.username}'

    def update(self, **kwargs):
        for (k, v) in kwargs.items():
            if isinstance(v, str) and not v:
                continue
            if k == 'password':
                self.password = hash_password(v)
            elif not hasattr(self, k) and Role.query.filter_by(name=k).first():
                self.add_roles(k)
            else:
                setattr(self, k, v)

    @property
    def password_str(self):
        return None

    @password_str.setter
    def password_str(self, value: str):
        if value:
            self.password = hash_password(value)


    @property
    def is_active(self) -> bool:
        return True

    def has_role(self, role: typing.Union[str, Role]) -> bool:
        """Returns `True` if the user identifies with the specified role.

        :param role: A role name or `Role` instance"""
        if super().has_role('admin'):
            return True
        else:
            return super().has_role(role)

    def has_any_role(self, *roles: typing.Union[str, Role]) -> bool:
        """Returns if user has any of the given roles.

        Returns True if user has the `admin` role."""
        if self.has_role('admin'):
            return True

        for role in roles:
            if self.has_role(role):
                return True

        return False

    def has_all_roles(self, *roles: typing.Union[str, Role]) -> bool:
        """Returns if user has all of the given roles.

        Returns True if user has the `admin` role."""
        if self.has_role('admin'):
            return True

        for role in roles:
            if not self.has_role(role):
                return False

        return True

    def add_roles(self, *roles: typing.Union[str, Role]):
        """Adds role to user."""
        for role in roles:
            if self.has_role(role):
                continue

            if isinstance(role, str):
                role_obj = Role.query.filter_by(name=role).first()
                if role_obj is None:
                    raise ValueError(f'Undefined role: {role}')
            else:
                role_obj = role

            self.roles.append(role_obj)

    def verify_password(self, password: str) -> bool:
        """Checks if given password is the same as the stored one.

        :param password: Password to check.
        :return: True if the stored password was provided.

        :raise ValueError: If password is not set.
        """
        if self.password is None:
            raise ValueError('Password is not set.')

        return verify_password(password, self.password)

    def set_password(self, password: str) -> None:
        """Stores new password in database."""
        self.password = hash_password(password)


class Quiz(db.Model):
    name = name_column()
    start_time_utc = db.Column(db.DateTime, index=True)
    public = db.Column(db.Boolean, default=False)

    host_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
        index=True,
        default=lambda: current_user.id
    )
    host = db.relationship(
        "User",
        backref=db.backref("hosted", lazy="dynamic", cascade="delete, delete-orphan")
    )

    def __repr__(self) -> str:
        return self.name

    @property
    def start_time(self) -> dt.datetime:
        if self.start_time_utc is not None:
            tz = get_timezone()
            utc = pytz.utc.localize(self.start_time_utc)
            return utc.astimezone(tz).replace(tzinfo=None)

    @start_time.setter
    def start_time(self, value):
        if value is None:
            self.start_time_utc = None
        else:
            tz = get_timezone()
            utc = tz.localize(value).astimezone(pytz.utc)
            self.start_time_utc = utc.replace(tzinfo=None)


class Block(db.Model):
    name = name_column(unique=False, index=False)
    order_number = db.Column(db.Integer, nullable=False, index=True)
    check_time = db.Column(db.Integer, nullable=False, default=120)
    quiz_id = db.Column(
        db.Integer,
        db.ForeignKey("quiz.id"),
        nullable=False,
        index=True
    )
    quiz = db.relationship(
        "Quiz",
        backref=db.backref("blocks", lazy="dynamic", cascade="delete, delete-orphan")
    )

    def __repr__(self) -> str:
        return f'{self.quiz} / {self.name}'

    @property
    def question_time(self) -> int:
        return sum([x.time or 0 for x in self.questions])

    @property
    def has_next(self) -> bool:
        last = self.quiz.blocks.order_by(Block.order_number.desc()).first()
        return self != last

    @property
    def has_prev(self) -> bool:
        first = self.quiz.blocks.order_by(Block.order_number).first()
        return self != first


class Question(db.Model):
    order_number = db.Column(db.Integer, nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    show_choices = db.Column(db.Boolean, default=False)
    multiple = db.Column(db.Boolean, default=False)
    time = db.Column(db.Integer, default=120, nullable=False)
    base_points = db.Column(db.Float, default=0)

    block_id = db.Column(
        db.Integer,
        db.ForeignKey("block.id"),
        nullable=False,
        index=True
    )
    block = db.relationship(
        "Block",
        backref=db.backref("questions", lazy="dynamic", cascade="delete, delete-orphan")
    )

    def __repr__(self) -> str:
        return f'{self.block} / {self.order_number}'

    def available(self, quiz_start_time: dt.datetime=None):
        if quiz_start_time is None:
            quiz_start_time = self.block.quiz.start_time_utc

        t = quiz_start_time
        now = dt.datetime.utcnow()

        for block in self.block.quiz.blocks\
                .filter(Block.order_number < self.block.order_number):
            block_time = block.question_time + block.check_time
            t += dt.timedelta(seconds=block_time)

        for question in self.block.questions\
                .filter(Question.order_number < self.order_number):
            t += dt.timedelta(seconds=question.time)

        if t < now:
            return True
        else:
            return False


class Choice(db.Model):
    value = db.Column(db.String(255))
    content = db.Column(db.Text)
    points = db.Column(db.Float, default=1)
    max_levenshtein_distance = db.Column(db.Integer, default=3)

    question_id = db.Column(
        db.Integer,
        db.ForeignKey("question.id"),
        nullable=False,
        index=True
    )
    question = db.relationship(
        "Question",
        backref=db.backref("choices", lazy="dynamic", cascade="delete, delete-orphan")
    )

    def __repr__(self) -> str:
        return f'{self.value}'


class FilledQuiz(db.Model):
    __tablenme__ = 'filled_quiz'
    started_utc = db.Column(db.DateTime(), default=dt.datetime.utcnow())
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
        index=True
    )
    user = db.relationship(
        "User",
        backref=db.backref("quizzes", lazy="dynamic", cascade="delete, delete-orphan")
    )

    quiz_id = db.Column(
        db.Integer,
        db.ForeignKey("quiz.id"),
        nullable=False,
        index=True
    )
    quiz = db.relationship(
        "Quiz",
        backref=db.backref("fills", lazy="dynamic", cascade="delete, delete-orphan")
    )

    finished_blocks = db.relationship(
        "Block",
        secondary=db.Table(
            'done_blocks',
            db.Column('quiz_id', db.Integer(), db.ForeignKey('filled_quiz.id'), primary_key=True),
            db.Column('block_id', db.Integer(), db.ForeignKey('block.id'), primary_key=True)
        ),
        lazy="dynamic",
        backref=db.backref("finished_quizzes", lazy="dynamic")
    )

    def __repr__(self) -> str:
        return f'{self.quiz} / {self.user}'

    @property
    def started(self) -> dt.datetime:
        if self.started_utc is not None:
            tz = get_timezone()
            utc = pytz.utc.localize(self.started_utc)
            return utc.astimezone(tz).replace(tzinfo=None)

    @started.setter
    def started(self, value):
        if value is None:
            self.started_utc = None
        else:
            tz = get_timezone()
            utc = tz.localize(value).astimezone(pytz.utc)
            self.started_utc = utc.replace(tzinfo=None)

    @hybrid_property
    def start_time_utc(self):
        return self.quiz.start_time_utc or self. started_utc

    @property
    def points(self) -> float:
        return sum([ans.points for ans in self.answers]) or 0

    @property
    def current_block(self) -> Block:
        for block in self.quiz.blocks.order_by(Block.order_number):
            if block not in self.finished_blocks:
                return block

    @property
    def finished(self):
        return bool(self.current_block)

    @property
    def available_questions(self):
        block = self.current_block
        if block is None:
            return []
        return [q for q
                in block.questions.order_by(Question.order_number)
                if q.available]

    @property
    def current_question(self):
        questions = self.available_questions
        return questions[-1:][0] if questions else None


class Answer(db.Model):
    text = db.Column(db.String(255))
    choice_id = db.Column(
        db.Integer,
        db.ForeignKey("choice.id"),
        nullable=True,
        index=True
    )
    choice = db.relationship(
        "Choice",
        backref=db.backref("answers", lazy="dynamic", cascade="delete, delete-orphan")
    )

    quiz_id = db.Column(
        db.Integer,
        db.ForeignKey("filled_quiz.id"),
        nullable=False,
        index=True
    )
    quiz = db.relationship(
        "FilledQuiz",
        backref=db.backref("answers", lazy="dynamic", cascade="delete, delete-orphan")
    )

    question_id = db.Column(
        db.Integer,
        db.ForeignKey("question.id"),
        nullable=False,
        index=True
    )
    question = db.relationship(
        "Question",
        backref=db.backref("answers", lazy="dynamic", cascade="delete, delete-orphan")
    )

    @property
    def value(self) -> str:
        if self.choice:
            return self.choice.value

        return self.text

    @property
    def points(self) -> float:
        if self.choice:
            return int_or_float(self.choice.points) or 0

        for choice in self.question.choices.filter(Choice.points <= 0):
            d = str_distance(choice.value, self.text)
            d_max = choice.max_levenshtein_distance
            if d < d_max:
                return int_or_float(choice.points) or 0

        for choice in self.question.choices.filter(Choice.points > 0):
            value = choice.value.strip().lower().replace(' ', '')
            text = self.text.strip().lower().replace(' ', '')
            d = str_distance(value, text)
            d_max = choice.max_levenshtein_distance
            if d < d_max:
                return int_or_float(choice.points) or 0

        return int_or_float(self.question.base_points)


def setup():
    init()
    migrate()
    upgrade()

    print("Creating roles...")
    Role.from_csv()
    print("Creating users...")
    User.from_csv()

    print("Committing...")
    db.session.commit()
    print("Done!")
