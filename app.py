import os

from flask import Flask, request
from flask_babelex import Babel, Domain, lazy_gettext as _l
from flask_bootstrap import Bootstrap
from flask_migrate import Migrate, migrate, upgrade
from flask_security import Security, SQLAlchemyUserDatastore, \
    LoginForm, current_user
import wtforms as wtf

from config import Config
import model
import admin


app = Flask(__name__)
app.config.from_object(Config)

# Database ---------------------------------------------------------------------

model.db.init_app(app)
migrations_dir = app.config.get('MIGRATE_DIRECTORY', 'data/migrations')
Migrate(app, model.db, migrations_dir, render_as_batch=True)

# Security ---------------------------------------------------------------------

LoginForm.email.label = wtf.Label('email', _l('Username or e-mail'))
LoginForm.password.label = wtf.Label('password', _l('Password'))
LoginForm.submit.label = wtf.Label('submit', _l('Log in'))

Security(
    app,
    SQLAlchemyUserDatastore(model.db, model.User, model.Role)
)

# Frontend ---------------------------------------------------------------------

admin.admin.init_app(app)
Bootstrap(app)

# Translations -----------------------------------------------------------------

domain = Domain(app.config.get("BABEL_TRANSLATIONS")[0], "messages")
babel = Babel(app, default_domain=domain)
babel.domain = "messages"
babel.translation_directories = app.config.get("BABEL_TRANSLATIONS")


@babel.localeselector
def get_locale():
    if current_user.is_authenticated:
        return current_user.language or 'hu'
    return request.accept_languages.best_match(app.config.get('LANGUAGES'))


@babel.timezoneselector
def get_timezone():
    if current_user.is_authenticated:
        return


if __name__ == '__main__':
    with app.app_context():
        if not os.path.exists(migrations_dir):
            model.setup()
        else:
            migrate()
            upgrade()
    app.run(debug=True)
