from flask import Flask, render_template
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
    from .insights import bp as insights_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(shop_bp)
    app.register_blueprint(insights_bp)

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("error.html", code=403, message="You don't have permission to open this page."), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", code=404, message="We couldn't find that page."), 404

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        return render_template("error.html", code=500, message="Something went wrong on our side."), 500

    with app.app_context():
        db.create_all()

    return app
