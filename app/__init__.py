from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)

    from . import models  # noqa: F401  (registers the tables)
    from .auth import bp as auth_bp
    from .shop import bp as shop_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(shop_bp)

    with app.app_context():
        db.create_all()

    return app
