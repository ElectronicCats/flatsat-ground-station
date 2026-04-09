"""Flask application factory with WebSocket support."""

import threading
import time

from flask import Flask, g, redirect, render_template, request, url_for
from flask_socketio import SocketIO

from webapp.auth import authenticate, create_session_token, login_required
from webapp.config import Config
from webapp.db import close_db, init_db

socketio = SocketIO()


def create_app(config_class=Config, db_path=None):
    app = Flask(__name__)
    app.config.from_object(config_class)

    if db_path:
        app.config["DATABASE"] = db_path

    app.teardown_appcontext(close_db)

    socketio.init_app(app, cors_allowed_origins="*")

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
        config = db.execute("SELECT * FROM radio_config WHERE owner = ?", (g.username,)).fetchone()
        return render_template("config.html", config=config)

    @app.route("/api/config/radio/<int:config_id>")
    @login_required
    def api_config_get(config_id):
        from webapp.db import get_db

        db = get_db()
        # VULNERABLE: no ownership check (GS-06 IDOR)
        config = db.execute("SELECT * FROM radio_config WHERE id = ?", (config_id,)).fetchone()
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
                shell=True,
                stderr=subprocess.STDOUT,
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
            routes.append(
                {
                    "rule": rule.rule,
                    "methods": sorted(rule.methods - {"OPTIONS", "HEAD"}),
                    "endpoint": rule.endpoint,
                }
            )
        return routes

    @app.route("/api/radio/send", methods=["POST"])
    @login_required
    def api_radio_send():
        from webapp.radio_bridge import RadioBridge

        data = request.get_json(silent=True) or {}
        raw_hex = data.get("data", "")
        try:
            raw_bytes = bytes.fromhex(raw_hex)
        except ValueError:
            return {"error": "Invalid hex data"}, 400
        bridge = RadioBridge()
        result = bridge.send_raw(raw_bytes)
        return result

    @app.route("/commands")
    @login_required
    def commands_page():
        return render_template("commands.html")

    @socketio.on("connect")
    def handle_connect():
        pass

    return app


def start_mock_telemetry(app):
    """Background thread: emit mock telemetry every 2 seconds."""
    from core.telemetry import generate_mock_telemetry

    def _loop():
        while True:
            with app.app_context():
                tm = generate_mock_telemetry()
                socketio.emit(
                    "telemetry_update",
                    {
                        "apid": tm["apid"],
                        "raw_hex": tm["raw_hex"],
                        "decoded": tm["decoded"],
                        "timestamp": tm["timestamp"],
                    },
                )
            time.sleep(2)

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()


if __name__ == "__main__":
    import os

    app = create_app()
    os.makedirs("db", exist_ok=True)
    with app.app_context():
        init_db()
        from webapp.seed import seed_db

        seed_db()
    start_mock_telemetry(app)
    print("PwnSat2 Ground Station running on http://localhost:5000")
    print("Mode: SIMULATED (no FlatSat detected)")
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, allow_unsafe_werkzeug=True)
