"""Flask application factory."""

from flask import Flask

from webapp.config import Config
from webapp.db import close_db, init_db


def create_app(config_class=Config, db_path=None):
    app = Flask(__name__)
    app.config.from_object(config_class)

    if db_path:
        app.config["DATABASE"] = db_path

    app.teardown_appcontext(close_db)

    return app
