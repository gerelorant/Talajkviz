from app import app
from model import setup


if __name__ == '__main__':
    with app.app_context():
        setup()
