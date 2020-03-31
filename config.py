class Config:
    SQLALCHEMY_DATABASE_URI = "sqlite:///data/test.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    PER_PAGE = 20

    SECRET_KEY = "secret"
    ENV = "development"

    BABEL_TRANSLATIONS = ["data/translations"]
    BABEL_DEFAULT_LOCALE = "hu"
    BABEL_DEFAULT_TIMEZONE = "Europe/Budapest"
    LANGUAGES = ["hu", "en"]

    SECURITY_PASSWORD_HASH = "sha512_crypt"
    SECURITY_PASSWORD_SALT = "fhasdgihwntlgy8f"
    SECURITY_USER_IDENTITY_ATTRIBUTES = ["username", "email"]