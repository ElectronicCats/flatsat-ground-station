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

    # --- Vulnerability Routes ---

    @app.route("/api/telemetry")
    @login_required
    def api_telemetry():
        from webapp.db import get_db
        search = request.args.get("search", "")
        limit = request.args.get("limit", "50")
        db = get_db()
        # VULNERABLE: string concatenation (GS-01)
        query = f"SELECT * FROM telemetry WHERE raw_hex LIKE '%{search}%' LIMIT {limit}"
        try:
            rows = db.execute(query).fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            return {"error": str(e)}, 500

    @app.route("/logs")
    @login_required
    def logs_page():
        from webapp.db import get_db
        db = get_db()
        logs = db.execute("SELECT * FROM logs ORDER BY id DESC").fetchall()
        return render_template("logs.html", logs=logs)

    @app.route("/api/diagnostics", methods=["POST"])
    @login_required
    def api_diagnostics():
        import subprocess
        data = request.get_json(silent=True) or {}
        cmd = data.get("cmd")
        if not cmd:
            return {"error": "Missing 'cmd' parameter"}, 400
        try:
            # VULNERABLE: shell=True with user input (GS-03)
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, timeout=10)
            return {"output": output.decode(errors="replace")}
        except subprocess.CalledProcessError as e:
            return {"output": e.output.decode(errors="replace"), "returncode": e.returncode}
        except subprocess.TimeoutExpired:
            return {"error": "Command timed out"}, 408

    @app.route("/api/logs", methods=["GET", "POST"])
    @login_required
    def api_logs():
        from webapp.db import get_db

        if request.method == "POST":
            # GS-11: Log injection (no newline sanitization)
            data = request.get_json(silent=True) or {}
            message = data.get("message", "")
            level = data.get("level", "INFO")
            source = data.get("source", "user")
            from datetime import datetime
            db = get_db()
            db.execute(
                "INSERT INTO logs (timestamp, level, source, message) VALUES (?, ?, ?, ?)",
                (datetime.now().isoformat(), level, source, message),
            )
            db.commit()
            return {"status": "ok"}

        # GET: file parameter for LFI (GS-04)
        filename = request.args.get("file")
        if not filename:
            return {"error": "Missing 'file' parameter"}, 400
        import os
        logs_dir = os.path.join(os.path.dirname(__file__), "logs")
        filepath = os.path.join(logs_dir, filename)
        try:
            with open(filepath) as f:
                return {"content": f.read()}
        except FileNotFoundError:
            return {"error": "File not found"}, 404
        except Exception as e:
            return {"error": str(e)}, 500

    @app.route("/config")
    @login_required
    def config_page():
        from webapp.db import get_db
        db = get_db()
        config = db.execute(
            "SELECT * FROM radio_config WHERE owner = ?", (g.username,)
        ).fetchone()
        return render_template("config.html", config=config)

    @app.route("/api/config/radio/<int:config_id>")
    @login_required
    def api_config_get(config_id):
        from webapp.db import get_db
        db = get_db()
        # VULNERABLE: no ownership check (GS-06 IDOR)
        config = db.execute(
            "SELECT * FROM radio_config WHERE id = ?", (config_id,)
        ).fetchone()
        if config is None:
            return {"error": "Config not found"}, 404
        return dict(config)

    @app.route("/api/config/radio", methods=["POST"])
    @login_required
    def api_config_update():
        import subprocess
        data = request.get_json(silent=True) or {}
        frequency = data.get("frequency", "915000000")
        # VULNERABLE: f-string in shell command (GS-07)
        try:
            output = subprocess.check_output(
                f"echo 'Setting frequency to {frequency}'",
                shell=True, stderr=subprocess.STDOUT,
            )
            return {"output": output.decode(errors="replace")}
        except subprocess.CalledProcessError as e:
            return {"output": e.output.decode(errors="replace")}, 500

    @app.route("/api/endpoints")
    def api_endpoints():
        """GS-12: lists all routes without authentication or rate limiting."""
        routes = []
        for rule in app.url_map.iter_rules():
            if rule.endpoint == "static":
                continue
            routes.append({
                "rule": rule.rule,
                "methods": sorted(rule.methods - {"OPTIONS", "HEAD"}),
                "endpoint": rule.endpoint,
            })
        return routes

    return app
