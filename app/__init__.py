from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'smartcart-secret-key'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///store.db'

    db.init_app(app)
    login_manager.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from app.shop import bp as shop_bp
    app.register_blueprint(shop_bp)

    with app.app_context():
        db.create_all()

    return app