from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager


db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'routes.login'

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'rahasia'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///posts.db'
    app.config['UPLOAD_FOLDER'] = 'app/static/uploads'

    db.init_app(app)
    login_manager.init_app(app)

    from .routes import bp as routes_bp
    app.register_blueprint(routes_bp)

    return app

