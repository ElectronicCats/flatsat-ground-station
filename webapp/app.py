"""Flask application factory."""

from flask import Flask, render_template, request, redirect, url_for, make_response, g

from webapp.config import Config
from webapp.db import close_db, init_db
from webapp.auth import authenticate, create_session_token, login_required, get_current_user


def create_app(config_class=Config, db_path=None):
    app = Flask(__name__)
    app.config.from_object(config_class)

    if db_path:
        app.config["DATABASE"] = db_path

    app.teardown_appcontext(close_db)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            user, role = authenticate(username, password)
            if user:
                token = create_session_token(user, role)
                resp = redirect(url_for("dashboard"))
                resp.set_cookie("session_token", token)
                return resp
            return render_template("login.html", error="Invalid credentials")
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        resp = redirect(url_for("login"))
        resp.delete_cookie("session_token")
        return resp

    @app.route("/")
    def index():
        return redirect(url_for("login"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        return render_template("dashboard.html")

    return app
