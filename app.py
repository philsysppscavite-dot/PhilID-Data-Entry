import os

from flask import Flask

from config import Config
from extensions import db, login_manager
from models import User


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from blueprints.auth import bp as auth_bp
    from blueprints.main import bp as main_bp
    from blueprints.api import bp as api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)

    with app.app_context():
        db.create_all()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
