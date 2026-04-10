"""Flask application factory with WebSocket support."""

import threading
import time

from flask import Flask, g, redirect, render_template, request, url_for
from flask_socketio import SocketIO

from core.device import FlatSatDevice
from core.serial_manager import discover_devices
from core.shell_parser import (
    parse_difficulty,
    parse_flight,
    parse_fw_version,
    parse_lora_config,
    parse_mode,
    parse_sc_id,
    parse_sensors,
)
from core.state import GroundStationState
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

    # Initialize DB and seed on first request (or immediately if context available)
    with app.app_context():
        init_db()
        from webapp.seed import seed_db

        seed_db()

    socketio.init_app(app, cors_allowed_origins="*")

    # Shared ground station state
    gs_state = GroundStationState()
    app.config["GS_STATE"] = gs_state
    app.config["SCANNED_DEVICES"] = {}

    def log_activity(level, source, message):
        """Insert a log entry into the logs table."""
        try:
            from datetime import datetime

            from webapp.db import get_db

            db = get_db()
            db.execute(
                "INSERT INTO logs (timestamp, level, source, message) VALUES (?, ?, ?, ?)",
                (datetime.now().isoformat(), level, source, message),
            )
            db.commit()
        except Exception:
            pass

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
                log_activity("INFO", "auth", f"User '{user}' logged in (role={role})")
                return resp
            log_activity("WARN", "auth", f"Failed login attempt for '{username}'")
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
        bridge = RadioBridge(app.config["GS_STATE"])
        result = bridge.send_raw(raw_bytes)
        log_activity("INFO", "telecommand", f"TC sent ({len(raw_bytes)} bytes): {raw_hex[:32]}")
        return result

    @app.route("/commands")
    @login_required
    def commands_page():
        return render_template("commands.html")

    @app.route("/api/hardware/status")
    @login_required
    def api_hardware_status():
        gs = app.config["GS_STATE"]
        if gs.is_hardware:
            return {
                "mode": "hardware",
                "serial_number": gs.device.serial_number if gs.device else None,
            }
        if gs.is_simulated:
            return {"mode": "simulated", "mock_running": gs.mock_running}
        return {"mode": "idle"}

    @app.route("/api/hardware/simulate", methods=["POST"])
    @login_required
    def api_hardware_simulate():
        """Start simulated telemetry mode."""
        gs = app.config["GS_STATE"]
        if gs.is_hardware and gs.device:
            gs.device.disconnect()
        gs.set_simulated()
        gs.start_mock()
        return {"mode": "simulated", "mock_running": True}

    @app.route("/api/hardware/scan", methods=["POST"])
    @login_required
    def api_hardware_scan():
        devices = discover_devices()
        scanned = {}
        result = []
        for d in devices:
            sn = d.identity.serial_number
            scanned[sn] = d
            result.append(
                {
                    "serial_number": sn,
                    "is_complete": d.is_complete,
                    "health": d.health.name,
                    "radio0": d.radio0_port,
                    "radio1": d.radio1_port,
                    "shell": d.shell_port,
                }
            )
        app.config["SCANNED_DEVICES"] = scanned
        return {"devices": result}

    @app.route("/api/hardware/connect", methods=["POST"])
    @login_required
    def api_hardware_connect():
        data = request.get_json(silent=True) or {}
        serial_number = data.get("serial_number", "")

        # Re-scan to get fresh port info
        scanned = app.config.get("SCANNED_DEVICES", {})
        discovered = scanned.get(serial_number)
        if not discovered:
            return {"error": f"Device {serial_number} not found. Run scan first."}, 404

        gs = app.config["GS_STATE"]
        if gs.device:
            gs.device.disconnect()
            time.sleep(0.5)  # Let OS release serial ports

        device = FlatSatDevice(discovered)
        connect_result = device.connect()

        if device.is_connected:
            gs.set_hardware(device)
            log_activity("INFO", "hardware", f"Connected to FlatSat ...{serial_number[-4:]}")
            return {
                "mode": "hardware",
                "serial_number": serial_number,
                "endpoints": connect_result,
            }
        log_activity("ERROR", "hardware", f"Failed to connect to ...{serial_number[-4:]}: {connect_result}")
        return {"error": "Failed to connect", "endpoints": connect_result}, 500

    @app.route("/api/hardware/disconnect", methods=["POST"])
    @login_required
    def api_hardware_disconnect():
        gs = app.config["GS_STATE"]
        if gs.device:
            gs.device.disconnect()
            time.sleep(0.3)  # Let OS release serial ports
        log_activity("INFO", "hardware", "Disconnected from FlatSat")
        gs.set_idle()
        app.config["SCANNED_DEVICES"] = {}  # Force re-scan
        return {"mode": "idle"}

    @app.route("/api/hardware/stop", methods=["POST"])
    @login_required
    def api_hardware_stop():
        """Stop simulation and go back to idle."""
        gs = app.config["GS_STATE"]
        gs.stop_mock()
        gs.set_idle()
        return {"mode": "idle"}

    @app.route("/satellite")
    @login_required
    def satellite_page():
        return render_template("satellite.html")

    def _require_hardware():
        gs = app.config["GS_STATE"]
        if not gs.is_hardware or not gs.device:
            return None, ({"error": "Satellite not connected"}, 400)
        return gs.device, None

    @app.route("/api/satellite/info")
    @login_required
    def api_satellite_info():
        """Full info — call once on page load."""
        dev, err = _require_hardware()
        if err:
            return err
        fw_raw = dev.send_shell_command_full("fw_version")
        mode_raw = dev.send_shell_command_full("mode")
        flight_raw = dev.send_shell_command_full("flight")
        diff_raw = dev.send_shell_command_full("difficulty")
        scid_raw = dev.send_shell_command_full("sc_id")
        fw = parse_fw_version(fw_raw)
        flight = parse_flight(flight_raw)
        return {
            **fw,
            "mode": parse_mode(mode_raw),
            "flight": flight["flight"],
            "battery_mv": flight["battery_mv"],
            "tm_rate": flight["tm_rate"],
            "difficulty": parse_difficulty(diff_raw),
            "sc_id": parse_sc_id(scid_raw),
        }

    @app.route("/api/satellite/status")
    @login_required
    def api_satellite_status():
        """Lightweight status — only flight/battery/mode. For polling."""
        dev, err = _require_hardware()
        if err:
            return err
        flight_raw = dev.send_shell_command_full("flight")
        mode_raw = dev.send_shell_command_full("mode")
        status_raw = dev.send_shell_command_full("status")
        flight = parse_flight(flight_raw)

        mode = parse_mode(mode_raw)
        # Detect ground station: lora_mode=command means receiving
        if status_raw and "mode=command" in status_raw and mode == "raw":
            mode = "ground_station"

        return {
            "mode": mode,
            "flight": flight["flight"],
            "battery_mv": flight["battery_mv"],
            "tm_rate": flight["tm_rate"],
        }

    @app.route("/api/satellite/sensors")
    @login_required
    def api_satellite_sensors():
        dev, err = _require_hardware()
        if err:
            return err
        raw = dev.send_shell_command_full("sensors")
        return parse_sensors(raw)

    @app.route("/api/satellite/lora_config", methods=["GET", "POST"])
    @login_required
    def api_satellite_lora_config():
        dev, err = _require_hardware()
        if err:
            return err
        if request.method == "GET":
            raw = dev.send_shell_command_full("lora_config R0")
            return parse_lora_config(raw)
        data = request.get_json(silent=True) or {}
        freq = data.get("frequency")
        sf = data.get("sf")
        bw = data.get("bw")
        power = data.get("power")
        results = []
        if freq:
            results.append(dev.send_shell_command_full(f"lora_freq R0 {freq}"))
        if sf:
            results.append(dev.send_shell_command_full(f"lora_sf R0 {sf}"))
        if bw:
            results.append(dev.send_shell_command_full(f"lora_bw R0 {bw}"))
        if power:
            results.append(dev.send_shell_command_full(f"lora_power R0 {power}"))
        results.append(dev.send_shell_command_full("lora_apply R0"))
        log_activity("INFO", "satellite", f"LoRa config updated: freq={freq} sf={sf} bw={bw} power={power}")
        return {"status": "ok", "responses": results}

    @app.route("/api/satellite/mode", methods=["POST"])
    @login_required
    def api_satellite_mode():
        dev, err = _require_hardware()
        if err:
            return err
        data = request.get_json(silent=True) or {}
        mode = data.get("mode", "raw")

        if mode == "ground_station":
            # Ground Station: R0 command (receive RX lines), R1 command (TX telecommands)
            # Copy R0 LoRa config to R1 so TX goes on same frequency
            dev.send_shell_command_full("lora_mode ALL command")
            dev.send_shell_command_full("lora_apply ALL")
            log_activity("INFO", "satellite", "Mode changed to Ground Station (R0+R1 command mode)")
            return {"status": "ok", "mode": "ground_station"}

        if mode == "raw":
            dev.send_shell_command_full("mode raw")
            resp = dev.send_shell_command_full("lora_mode stream")
        elif mode == "mission":
            dev.send_shell_command_full("mode mission")
            resp = dev.send_shell_command_full("lora_mode stream")
        else:
            resp = dev.send_shell_command_full(f"mode {mode}")

        log_activity("INFO", "satellite", f"Mode changed to {mode}")
        return {"status": "ok", "response": resp}

    @app.route("/api/satellite/flight", methods=["POST"])
    @login_required
    def api_satellite_flight():
        dev, err = _require_hardware()
        if err:
            return err
        data = request.get_json(silent=True) or {}
        flight = data.get("flight", "idle")
        resp = dev.send_shell_command_full(f"flight {flight}")
        log_activity("INFO", "satellite", f"Flight state changed to {flight}")
        return {"status": "ok", "response": resp}

    @app.route("/api/satellite/difficulty", methods=["POST"])
    @login_required
    def api_satellite_difficulty():
        dev, err = _require_hardware()
        if err:
            return err
        data = request.get_json(silent=True) or {}
        level = data.get("level", 0)
        resp = dev.send_shell_command_full(f"difficulty {level}")
        log_activity("INFO", "satellite", f"Difficulty set to {level}")
        return {"status": "ok", "response": resp}

    @app.route("/api/satellite/tinygs", methods=["POST"])
    @login_required
    def api_satellite_tinygs():
        dev, err = _require_hardware()
        if err:
            return err
        data = request.get_json(silent=True) or {}
        action = data.get("action", "status")
        if action == "spoof":
            profile = data.get("profile", "norbi")
            resp = dev.send_shell_command_full(f"tinygs spoof {profile}")
            log_activity("INFO", "satellite", f"TinyGS spoofing {profile}")
        elif action == "stop":
            resp = dev.send_shell_command_full("tinygs stop")
            log_activity("INFO", "satellite", "TinyGS stopped")
        else:
            resp = dev.send_shell_command_full("tinygs status")
        return {"status": "ok", "response": resp}

    @app.route("/api/satellite/reset", methods=["POST"])
    @login_required
    def api_satellite_reset():
        dev, err = _require_hardware()
        if err:
            return err
        resp = dev.send_shell_command_full("reset_defaults")
        log_activity("WARN", "satellite", "Factory defaults restored")
        return {"status": "ok", "response": resp}

    @socketio.on("connect")
    def handle_connect():
        pass

    # Start telemetry background thread
    start_telemetry_thread(app)

    return app


_telemetry_thread_started = False


def start_telemetry_thread(app):
    """Background thread: emit telemetry (mock or hardware). Safe to call multiple times."""
    global _telemetry_thread_started
    if _telemetry_thread_started:
        return
    _telemetry_thread_started = True

    import serial

    from core.ccsds import parse_frame
    from core.device import parse_lora_rx
    from core.telemetry import decode_tm_payload, generate_mock_telemetry

    def _loop():
        while True:
            gs = app.config.get("GS_STATE")

            if gs and gs.is_idle:
                # IDLE MODE: waiting for user to choose mode
                time.sleep(0.5)
                continue

            if gs and gs.is_hardware and gs.device:
                # HARDWARE MODE: read from Radio 0
                # Step 1: Read line (connection-level — fallback on failure)
                try:
                    if not gs.device.is_connected:
                        raise OSError("Device disconnected")
                    line = gs.device.read_line(timeout=1.0)
                except (OSError, serial.SerialException) as e:
                    # Connection lost — fall back to simulated
                    if gs.device:
                        gs.device.disconnect()
                    gs.set_simulated()
                    gs.start_mock()
                    with app.app_context():
                        from datetime import datetime as _dt

                        from webapp.db import get_db as _get_db

                        try:
                            db = _get_db()
                            db.execute(
                                "INSERT INTO logs (timestamp, level, source, message) VALUES (?, ?, ?, ?)",
                                (
                                    _dt.now().isoformat(),
                                    "ERROR",
                                    "hardware",
                                    f"Connection lost, falling back to simulated: {e}",
                                ),
                            )
                            db.commit()
                        except Exception:
                            pass
                    time.sleep(0.1)
                    continue

                # Step 2: Parse + store (data-level — skip bad frames, don't disconnect)
                if line:
                    try:
                        parsed = parse_lora_rx(line)
                        if parsed:
                            raw_bytes = bytes.fromhex(parsed["data"])
                            pkt = parse_frame(raw_bytes)
                            if pkt:
                                # Valid CCSDS frame
                                decoded = decode_tm_payload(pkt.apid, pkt.payload)
                                from datetime import datetime

                                with app.app_context():
                                    from webapp.db import get_db

                                    db = get_db()
                                    db.execute(
                                        "INSERT INTO telemetry "
                                        "(timestamp, apid, spacecraft_id, temperature, "
                                        "pressure, humidity, accel_x, accel_y, accel_z, "
                                        "raw_hex) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                        (
                                            datetime.now().isoformat(),
                                            pkt.apid,
                                            2,
                                            decoded.get("temperature"),
                                            decoded.get("pressure"),
                                            decoded.get("humidity"),
                                            decoded.get("accel_x"),
                                            decoded.get("accel_y"),
                                            decoded.get("accel_z"),
                                            parsed["data"],
                                        ),
                                    )
                                    db.commit()
                                socketio.emit(
                                    "telemetry_update",
                                    {
                                        "apid": pkt.apid,
                                        "raw_hex": parsed["data"],
                                        "decoded": decoded,
                                        "timestamp": pkt.timestamp,
                                        "rssi": parsed.get("rssi"),
                                        "snr": parsed.get("snr"),
                                    },
                                )
                            else:
                                # Non-CCSDS frame (TinyGS beacons, etc.)
                                socketio.emit(
                                    "telemetry_update",
                                    {
                                        "raw_hex": parsed["data"],
                                        "decoded": {},
                                        "rssi": parsed.get("rssi"),
                                        "snr": parsed.get("snr"),
                                    },
                                )
                    except Exception:
                        pass  # Bad frame — skip, don't disconnect
                time.sleep(0.1)
            elif gs and gs.is_simulated and gs.mock_running:
                # SIMULATED MODE: generate mock
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
            else:
                time.sleep(0.5)

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()


if __name__ == "__main__":
    import os

    os.makedirs("db", exist_ok=True)
    app = create_app()  # DB init + seed + telemetry thread started inside
    print("PwnSat2 Ground Station running on http://localhost:5000")
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, allow_unsafe_werkzeug=True)
