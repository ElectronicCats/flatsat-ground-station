"""Flask application factory with WebSocket support."""

import os
import threading
import time

from flask import Flask, g, redirect, render_template, request, url_for
from flask_socketio import SocketIO

from core.constants import RADIO_LABELS
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


def _local_mode_from_shell(mode_raw: str | None, status_raw: str | None = None) -> str:
    mode = parse_mode(mode_raw)
    if mode == "satellite":
        return "satellite"
    if status_raw and "Radio0: LoRa  mode=command" in status_raw:
        return "ground_station"
    if mode == "raw":
        if status_raw and "mode=stream" in status_raw:
            return "raw"
        return "ground_station"
    return mode


def _local_role_from_mode(mode: str) -> str:
    from flask import current_app
    try:
        gs = current_app.config.get("GS_STATE")
        if gs and getattr(gs, "forced_device_role", "auto") != "auto":
            return gs.forced_device_role
        # In Dual radio mode the local board is always a Ground Station,
        # unless the board is explicitly configured in satellite/mission mode.
        if gs and getattr(gs, "active_radio", 0) == 2 and mode not in ("satellite", "mission"):
            return "ground_station"
    except Exception:
        pass
    return "satellite" if mode in ("satellite", "mission", "unknown") else "ground_station"


def _normalize_mode(m: str | None) -> str | None:
    if not m:
        return m
    if m in ("sat", "satellite", "mission"):
        return "mission"
    if m in ("gs", "ground_station"):
        return "ground_station"
    return m


def create_app(config_class=Config, db_path=None):
    app = Flask(__name__)
    app.config.from_object(config_class)

    if db_path:
        app.config["DATABASE"] = db_path

    # Ensure the database directory exists (fresh clone won't have it)
    db_dir = os.path.dirname(app.config["DATABASE"])
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

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

    # --- Error Handlers ---

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template("500.html"), 500

    # --- Vulnerability Routes ---

    @app.route("/api/telemetry")
    def api_telemetry():
        from webapp.db import get_db

        search = request.args.get("search", "")
        limit = request.args.get("limit", "50")
        db = get_db()
        
        if app.config["CTF_LEVEL"] == 1:
            # VULNERABLE: string concatenation (GS-01) - Easy mode
            query = f"SELECT * FROM telemetry WHERE raw_hex LIKE '%{search}%' LIMIT {limit}"
            try:
                rows = db.execute(query).fetchall()
                return [dict(row) for row in rows]
            except Exception as e:
                return {"error": str(e)}, 500
        else:
            # SECURE: parameterized query - Medium/Hard mode
            query = "SELECT * FROM telemetry WHERE raw_hex LIKE ? LIMIT ?"
            rows = db.execute(query, (f"%{search}%", limit)).fetchall()
            return [dict(row) for row in rows]

    @app.route("/logs")
    @login_required
    def logs_page():
        from webapp.db import get_db

        db = get_db()
        # Filter out DEBUG entries (GS-11: hidden flag only reachable via injection/SQLi)
        logs = db.execute("SELECT * FROM logs WHERE level != 'DEBUG' ORDER BY id DESC").fetchall()
        return render_template("logs.html", logs=logs)

    @app.route("/api/diagnostics", methods=["POST"])
    @login_required
    def api_diagnostics():
        import subprocess

        data = request.get_json(silent=True) or {}
        cmd = data.get("cmd")
        if not cmd:
            return {"error": "Missing 'cmd' parameter"}, 400
            
        if app.config["CTF_LEVEL"] <= 2:
            # VULNERABLE: shell=True with user input (GS-03) - Easy/Medium mode
            try:
                output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, timeout=10)
                return {"output": output.decode(errors="replace")}
            except subprocess.CalledProcessError as e:
                return {"output": e.output.decode(errors="replace"), "returncode": e.returncode}
            except subprocess.TimeoutExpired:
                return {"error": "Command timed out"}, 408
        else:
            # SECURE: Restricted commands - Hard mode
            import sys
            if sys.platform == "win32":
                allowed_cmds = ["systeminfo", "whoami", "ipconfig"]
            else:
                allowed_cmds = ["uptime", "id", "whoami"]
            if cmd not in allowed_cmds:
                return {"error": "Command not allowed in high-security mode"}, 403
            try:
                output = subprocess.check_output([cmd], stderr=subprocess.STDOUT, timeout=5)
                return {"output": output.decode(errors="replace")}
            except Exception as e:
                return {"error": str(e)}, 500

    @app.route("/api/logs", methods=["GET", "POST"])
    @login_required
    def api_logs():
        from webapp.db import get_db

        if request.method == "POST":
            # GS-11: Log injection (no newline sanitization in Easy/Medium)
            data = request.get_json(silent=True) or {}
            message = data.get("message", "")
            if app.config["CTF_LEVEL"] == 3:
                message = message.replace("\n", " ").replace("\r", " ")
                
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
        
        if app.config["CTF_LEVEL"] <= 2:
            # VULNERABLE: No path validation - Easy/Medium mode
            filepath = os.path.join(logs_dir, filename)
        else:
            # SECURE: Path validation - Hard mode
            filename = os.path.basename(filename)
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
        if g.role != "admin":
            from flask import flash, redirect, url_for
            flash("El apartado de Configuración está reservado para Administradores.")
            return redirect(url_for("dashboard"))

        from webapp.db import get_db

        db = get_db()
        configs = db.execute("SELECT * FROM radio_config WHERE owner = ? ORDER BY id", (g.username,)).fetchall()
        config_map = {}
        for c in configs:
            config_map[c["description"]] = dict(c)
        return render_template("config.html", configs=config_map, radio_labels=RADIO_LABELS)

    @app.route("/api/config/radio/<int:config_id>")
    @login_required
    def api_config_get(config_id):
        from webapp.db import get_db

        db = get_db()
        if app.config["CTF_LEVEL"] <= 2:
            # VULNERABLE: no ownership check (GS-06 IDOR) - Easy/Medium mode
            config = db.execute("SELECT * FROM radio_config WHERE id = ?", (config_id,)).fetchone()
        else:
            # SECURE: ownership check - Hard mode
            config = db.execute("SELECT * FROM radio_config WHERE id = ? AND owner = ?", (config_id, g.username)).fetchone()
            
        if config is None:
            return {"error": "Config not found"}, 404
        return dict(config)

    @app.route("/api/config/radio", methods=["POST"])
    @login_required
    def api_config_update():
        import subprocess

        from webapp.db import get_db

        data = request.get_json(silent=True) or {}
        radio = data.get("radio", RADIO_LABELS[0])
        frequency = data.get("frequency", "915000000")
        spreading_factor = data.get("spreading_factor", "7")
        bandwidth = data.get("bandwidth", "125000")
        tx_power = data.get("tx_power", "14")

        # VULNERABLE: f-string in shell commands (GS-07) - Easy/Medium mode
        if app.config["CTF_LEVEL"] <= 2:
            try:
                output = subprocess.check_output(
                    f"echo 'Setting frequency to {frequency}, SF={spreading_factor}, BW={bandwidth}, power={tx_power}'",
                    shell=True,
                    stderr=subprocess.STDOUT,
                )
                shell_output = output.decode(errors="replace")
            except subprocess.CalledProcessError as e:
                shell_output = e.output.decode(errors="replace")
        else:
            # SECURE: No shell echo - Hard mode
            shell_output = f"Frequency set to {frequency} (secure mode)"

        # Upsert into radio_config for current user
        db = get_db()
        existing = db.execute(
            "SELECT id FROM radio_config WHERE owner = ? AND description = ?",
            (g.username, radio),
        ).fetchone()

        def safe_int(val, default):
            try:
                return int(str(val).split(";")[0].split("&")[0].strip() or default)
            except (ValueError, TypeError):
                return default

        freq_int = safe_int(frequency, 915000000)
        sf_int = safe_int(spreading_factor, 7)
        bw_int = safe_int(bandwidth, 125000)
        power_int = safe_int(tx_power, 14)

        if existing:
            db.execute(
                "UPDATE radio_config SET frequency=?, spreading_factor=?, bandwidth=?, tx_power=? WHERE id=?",
                (freq_int, sf_int, bw_int, power_int, existing["id"]),
            )
        else:
            db.execute(
                "INSERT INTO radio_config (owner, frequency, spreading_factor, bandwidth, tx_power, description) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (g.username, freq_int, sf_int, bw_int, power_int, radio),
            )
        db.commit()

        config = db.execute(
            "SELECT * FROM radio_config WHERE owner = ? AND description = ?",
            (g.username, radio),
        ).fetchone()

        return {
            "status": "ok",
            "shell_output": shell_output,
            "config": dict(config),
        }

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

    @app.route("/api/users/me")
    @login_required
    def api_users_me():
        """Returns current user's profile. Flag in admin_notes (GS-02 XSS target)."""
        from webapp.db import get_db

        db = get_db()
        user = db.execute(
            "SELECT id, username, role, admin_notes FROM users WHERE username = ?",
            (g.username,),
        ).fetchone()
        if user is None:
            return {"error": "User not found"}, 404
        return dict(user)

    @app.route("/api/admin/panel")
    @login_required
    def api_admin_panel():
        """Admin-only panel. Flag reward for auth bypass (GS-05)."""
        if g.role != "admin":
            return {"error": "Forbidden"}, 403
        level = app.config["CTF_LEVEL"]
        return {
            "message": "Ground Station Admin Panel",
            "flag": f"PWNSAT{{SESSION_TOKEN_FORGED_LVL{level}}}",
            "connected_satellites": [],
            "system_status": "operational",
        }

    @app.route("/api/radio/status")
    @login_required
    def api_radio_status():
        """Radio bridge status. Flag for kill chain discovery (GS-08)."""
        gs_state = app.config.get("GS_STATE")
        connected = gs_state is not None and gs_state.connection_mode.name != "IDLE"
        level = app.config["CTF_LEVEL"]
        return {
            "connected": connected,
            "mode": gs_state.connection_mode.name if gs_state else "IDLE",
            "bridge_key": f"PWNSAT{{WEB_TO_SPACE_LINK_LVL{level}}}",
        }

    @app.route("/api/debug/flags")
    def api_debug_flags():
        """Unprotected debug endpoint. Flag for API enumeration (GS-12)."""
        level = app.config["CTF_LEVEL"]
        return {
            "flag": f"PWNSAT{{API_NO_RATE_LIMIT_LVL{level}}}",
            "hint": "This endpoint should not be public",
        }

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
        log_activity("INFO", "telecommand", f"TC raw sent ({len(raw_bytes)} bytes): {raw_hex[:32]}")
        return result

    @app.route("/api/radio/send_tc", methods=["POST"])
    @login_required
    def api_radio_send_tc():
        from core.ccsds import sdls_protect_frame
        from core.telecommand import build_command_tc
        from webapp.radio_bridge import RadioBridge

        data = request.get_json(silent=True) or {}
        opcode = data.get("opcode")
        extra_hex = data.get("data", "")

        if opcode is None:
            return {"error": "Missing 'opcode'"}, 400

        try:
            opcode_int = int(str(opcode), 16)
        except ValueError:
            return {"error": "Invalid opcode"}, 400

        extra_hex = extra_hex.strip()
        if extra_hex.lower().startswith("0x"):
            extra_hex = extra_hex[2:]

        # Backend role validation: restrict operators to allowed opcodes and block custom hex data
        if g.role != "admin":
            allowed_opcodes = [0x10, 0x20]
            if opcode_int not in allowed_opcodes:
                return {"error": "Forbidden: Operator role is not authorized to send this command"}, 403
            if extra_hex:
                return {"error": "Forbidden: Operator role is not authorized to send custom hex data"}, 403

        try:
            extra_bytes = bytes.fromhex(extra_hex) if extra_hex else b""
        except ValueError:
            return {"error": "Invalid hex string in Data field"}, 400
        frame = build_command_tc(opcode_int, data=extra_bytes)

        # SDLS: encrypt TC payload based on current difficulty
        difficulty = app.config["GS_STATE"].difficulty
        frame = sdls_protect_frame(frame, difficulty)

        bridge = RadioBridge(app.config["GS_STATE"])
        result = bridge.send_raw(frame)
        result["frame_hex"] = frame.hex()
        result["frame_size"] = len(frame)
        log_activity("INFO", "telecommand", f"TC sent: opcode=0x{opcode_int:02X} ({len(frame)} bytes)")
        return result

    @app.route("/api/hardware/status")
    @login_required
    def api_hardware_status():
        gs = app.config["GS_STATE"]
        if gs.is_hardware:
            dev = gs.device
            try:
                disc = dev._discovered if dev else None
                ports = {
                    "radio0": getattr(disc, "radio0_port", None),
                    "radio1": getattr(disc, "radio1_port", None),
                    "shell": getattr(disc, "shell_port", None),
                }
                # Ensure port values are strings (not mock objects in tests)
                ports = {k: str(v) if v else None for k, v in ports.items()}
            except Exception:
                ports = {"radio0": None, "radio1": None, "shell": None}
            return {
                "mode": "hardware",
                "serial_number": dev.serial_number if dev else None,
                "ports": ports,
                "active_radio": gs.active_radio,
            }
        if gs.is_simulated:
            return {"mode": "simulated", "mock_running": gs.mock_running}
        return {"mode": "idle"}

    @app.route("/api/hardware/active_radio", methods=["GET", "POST"])
    @login_required
    def api_hardware_active_radio():
        gs = app.config["GS_STATE"]
        if request.method == "POST":
            err_adm = _require_admin()
            if err_adm:
                return err_adm
            data = request.get_json(silent=True) or {}
            radio_idx = data.get("active_radio")
            if radio_idx is None or radio_idx not in (0, 1, 2, "0", "1", "2"):
                return {"error": "Invalid or missing 'active_radio' (must be 0, 1 or 2)"}, 400
            
            radio_idx = int(radio_idx)
            if gs.active_radio == radio_idx:
                log_activity("INFO", "hardware", f"Active radio change ignored: already set to {radio_idx}")
                return {"status": "ok", "active_radio": gs.active_radio, "no_change": True}
                
            gs.active_radio = radio_idx
            
            if gs.is_hardware and gs.device:
                # Sync physical board antenna switch via CDC-Shell
                if radio_idx == 2:
                    gs.device.send_shell_command_full("radio0")
                    # Clear serial buffers
                    gs.device.reset_radio_input_buffers()
                    log_activity("INFO", "hardware", "Active GS radio switched to Dual Mode (TX on R1, RX on R0)")
                else:
                    cmd = "radio1" if radio_idx == 1 else "radio0"
                    gs.device.send_shell_command_full(cmd)
                    # Clear serial buffers
                    gs.device.reset_radio_input_buffers()
                    log_activity("INFO", "hardware", f"Active GS radio switched to Radio {radio_idx} on physical board")
            else:
                log_activity("INFO", "hardware", f"Active GS radio switched to Radio {radio_idx} (simulated)")
                
            return {"status": "ok", "active_radio": gs.active_radio}
            
        return {"active_radio": gs.active_radio}

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

        device_role = data.get("device_role", "auto")
        role_to_send = device_role

        device = FlatSatDevice(discovered)
        connect_result = device.connect(forced_role=role_to_send)

        if device.is_connected:
            # Store connection overrides
            radio_mode = data.get("radio_mode", "auto")
            device_role = data.get("device_role", "auto")
            gs.forced_radio_mode = radio_mode
            gs.forced_device_role = device_role

            # Determine has_radio1 based on override and status query
            if os.environ.get("FLATSAT_SINGLE_RADIO") == "1" or radio_mode == "single":
                device.has_radio1 = False
            elif radio_mode == "dual":
                device.has_radio1 = True
            else:
                # auto-detect
                if not connect_result.get("radio1"):
                    device.has_radio1 = False
                else:
                    # Query status to see if Radio1 is physically present and initialized
                    status_raw = device.send_shell_command_full("status", timeout=0.4)
                    if status_raw:
                        import re
                        if "Radio1" not in status_raw:
                            device.has_radio1 = False
                        else:
                            r1_match = re.search(r"Radio1:.*lora_init=(\d)", status_raw)
                            if r1_match and int(r1_match.group(1)) == 0:
                                device.has_radio1 = False

            # Bootstrap: R1 command mode + sync difficulty (retry once on failure)
            if device.has_radio1:
                r1_resp = device.send_shell_command_full("lora_mode R1 command", timeout=0.4)
                if r1_resp is None:
                    time.sleep(0.1)
                    r1_resp = device.send_shell_command_full("lora_mode R1 command", timeout=0.4)
                if r1_resp is None or "error" in r1_resp.lower() or "not supported" in r1_resp.lower():
                    if radio_mode != "dual":
                        device.has_radio1 = False
            else:
                r1_resp = "not supported"
            diff_raw = device.send_shell_command_full("difficulty", timeout=0.4)
            if diff_raw is None:
                time.sleep(0.1)
                diff_raw = device.send_shell_command_full("difficulty", timeout=0.4)
            gs.difficulty = parse_difficulty(diff_raw)
            
            # Set default active radio based on presence of radio1
            if device.has_radio1:
                gs.active_radio = 2  # Dual (Auto)
            else:
                gs.active_radio = 0  # Radio 0 (CDC0)

            # Query local board properties and cache them
            fw_raw = device.send_shell_command_full("fw_version", timeout=1.0)
            fw = parse_fw_version(fw_raw)
            
            mode_raw = device.send_shell_command_full("mode", timeout=1.0)
            status_raw = device.send_shell_command_full("status", timeout=1.0)
            local_mode = _local_mode_from_shell(mode_raw, status_raw)
            local_role = _local_role_from_mode(local_mode)
            
            flight_raw = device.send_shell_command_full("flight", timeout=1.0)
            flight = parse_flight(flight_raw)
            
            scid_raw = device.send_shell_command_full("sc_id", timeout=1.0)
            sc_id = parse_sc_id(scid_raw)
            
            r0_raw = device.send_shell_command_full("lora_config R0", timeout=1.0)
            r0_cfg = parse_lora_config(r0_raw)
            
            r1_cfg = {"frequency": 0, "sf": 0, "bw": 0, "power": 0}
            if device.has_radio1:
                r1_raw = device.send_shell_command_full("lora_config R1", timeout=1.0)
                r1_cfg = parse_lora_config(r1_raw)
                
            gs.local_device_info = {
                "fw_version": fw.get("fw_version"),
                "git_sha": fw.get("git_sha"),
                "git_dirty": fw.get("git_dirty"),
                "build_date": fw.get("build_date"),
                "sc_id": sc_id,
                "mode": local_mode,
                "flight": flight.get("flight"),
                "difficulty": gs.difficulty,
                "role": local_role,
                "role_label": "Ground Station" if local_role == "ground_station" else "Satellite",
                "active_radio": gs.active_radio,
                "battery_mv": 0,
                "tm_rate": 0,
                "tinygs_profile": None,
                "radio_configs": {
                    "R0": r0_cfg,
                    "R1": r1_cfg,
                }
            }

            warnings = []
            if device.has_radio1 and (r1_resp is None or "error" in (r1_resp or "").lower() or "unknown" in (r1_resp or "").lower()):
                warnings.append(f"R1 command mode: {r1_resp!r}")
            if diff_raw is None or gs.difficulty == 0 and "difficulty" not in (diff_raw or ""):
                warnings.append(f"difficulty sync: {diff_raw!r}")
            warn_str = f" [WARN: {', '.join(warnings)}]" if warnings else ""
            log_activity(
                "INFO",
                "hardware",
                f"Connected to FlatSat ...{serial_number[-4:]} (difficulty={gs.difficulty}){warn_str}",
            )
            _sync_radio_config_to_db(device)
            gs.set_hardware(device)
            return {
                "mode": "hardware",
                "serial_number": serial_number,
                "endpoints": connect_result,
                "warnings": warnings,
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

    def _require_admin():
        if g.role != "admin":
            return ({"error": "La configuración está deshabilitada para Operadores. Utiliza la herramienta flatsat CLI en la terminal."}, 403)
        return None

    def _sync_radio_config_to_db(dev):
        """Read LoRa config from hardware and upsert into radio_config for current user."""
        try:
            from webapp.db import get_db

            db = get_db()
            radios = ("R0",) if not getattr(dev, "has_radio1", True) else ("R0", "R1")
            for radio, radio_label in zip(radios, RADIO_LABELS, strict=False):
                raw = dev.send_shell_command_full(f"lora_config {radio}")
                cfg = parse_lora_config(raw)
                if cfg["frequency"] == 0:
                    continue
                existing = db.execute(
                    "SELECT id FROM radio_config WHERE owner = ? AND description = ?",
                    (g.username, radio_label),
                ).fetchone()
                if existing:
                    db.execute(
                        "UPDATE radio_config SET frequency=?, spreading_factor=?, bandwidth=?, tx_power=? WHERE id=?",
                        (cfg["frequency"], cfg["sf"], cfg["bw"] * 1000, cfg["power"], existing["id"]),
                    )
                else:
                    db.execute(
                        "INSERT INTO radio_config "
                        "(owner, frequency, spreading_factor, bandwidth, tx_power, description) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (g.username, cfg["frequency"], cfg["sf"], cfg["bw"] * 1000, cfg["power"], radio_label),
                    )
            db.commit()
        except Exception:
            pass

    _SENTINEL = object()  # distinguishes "not fetched" from "fetched but None"

    def _build_local_snapshot(
        *,
        fw_raw: str | None | object = _SENTINEL,
        mode_raw: str | None = None,
        flight_raw: str | None = None,
        diff_raw: str | None = None,
        scid_raw: str | None | object = _SENTINEL,
        status_raw: str | None = None,
    ) -> dict:
        # When fw_raw/_scid_raw are _SENTINEL, the caller didn't fetch them —
        # return None so the frontend knows to keep its cached value.
        if fw_raw is _SENTINEL:
            fw = {"fw_version": None, "git_sha": None, "git_dirty": None, "build_date": None}
        else:
            fw = parse_fw_version(fw_raw)

        gs = app.config["GS_STATE"]

        # Flight state fallback
        if flight_raw is None:
            flight = {
                "flight": gs.local_device_info.get("flight"),
                "battery_mv": gs.local_device_info.get("battery_mv"),
                "tm_rate": gs.local_device_info.get("tm_rate"),
                "uptime": gs.local_device_info.get("uptime"),
                "tc_count": gs.local_device_info.get("tc_count"),
                "error_count": gs.local_device_info.get("error_count"),
            }
        else:
            flight = parse_flight(flight_raw)

        # Mode state fallback
        if mode_raw is None:
            mode = gs.local_device_info.get("mode")
        else:
            mode = _local_mode_from_shell(mode_raw, status_raw)

        if not mode or mode == "unknown":
            mode = gs.local_device_info.get("mode") or "satellite"

        role = _local_role_from_mode(mode)
        return {
            **fw,
            "mode": mode,
            "flight": flight["flight"],
            "battery_mv": flight["battery_mv"],
            "tm_rate": flight["tm_rate"],
            "uptime": flight.get("uptime"),
            "tc_count": flight.get("tc_count"),
            "error_count": flight.get("error_count"),
            "difficulty": gs.difficulty,
            "sc_id": parse_sc_id(scid_raw) if scid_raw is not _SENTINEL else None,
            "role": role,
            "role_label": "Ground Station" if role == "ground_station" else "Satellite",
            "active_radio": gs.active_radio,
        }

    def _build_satellite_snapshot(local: dict, remote: dict) -> dict:
        gs = app.config["GS_STATE"]
        active_radio = getattr(gs, "active_radio", 0)
        # If the local board is connected directly as a Satellite, we read its status via USB.
        # However, if it's a dual-radio board (active_radio == 2) and we have successfully received
        # LoRa telemetry packets over the air, we display the remote LoRa telemetry.
        is_ground_station = (local.get("role") == "ground_station") or (active_radio == 2 and remote.get("available", False))
        if is_ground_station:
            return {
                "available": remote.get("available", False),
                "source": "remote",
                "source_label": "LoRa Telemetry" if remote.get("available") else "Waiting for Telemetry",
                "sc_id": remote.get("sc_id"),
                "flight": remote.get("flight"),
                "difficulty": remote.get("difficulty"),
                "battery_mv": remote.get("battery_mv"),
                "tm_rate": None,
                "uptime": remote.get("uptime"),
                "tc_count": remote.get("tc_count"),
                "error_count": remote.get("error_count"),
                "temperature": remote.get("temperature"),
                "pressure": remote.get("pressure"),
                "humidity": remote.get("humidity"),
                "accel_x": remote.get("accel_x"),
                "accel_y": remote.get("accel_y"),
                "accel_z": remote.get("accel_z"),
                "last_seen_ts": remote.get("last_seen_ts"),
                "age_sec": remote.get("age_sec"),
                "stale": remote.get("stale"),
                "rssi": remote.get("rssi"),
                "snr": remote.get("snr"),
            }

        return {
            "available": True,
            "source": "local",
            "source_label": "Direct USB",
            "sc_id": local.get("sc_id"),
            "flight": local.get("flight"),
            "difficulty": local.get("difficulty"),
            "battery_mv": local.get("battery_mv"),
            "tm_rate": local.get("tm_rate"),
            "uptime": local.get("uptime") if local.get("uptime") is not None else remote.get("uptime"),
            "tc_count": local.get("tc_count") if local.get("tc_count") is not None else remote.get("tc_count"),
            "error_count": local.get("error_count") if local.get("error_count") is not None else remote.get("error_count"),
            "temperature": remote.get("temperature"),
            "pressure": remote.get("pressure"),
            "humidity": remote.get("humidity"),
            "accel_x": remote.get("accel_x"),
            "accel_y": remote.get("accel_y"),
            "accel_z": remote.get("accel_z"),
            "last_seen_ts": remote.get("last_seen_ts"),
            "age_sec": remote.get("age_sec"),
            "stale": remote.get("stale"),
            "rssi": remote.get("rssi"),
            "snr": remote.get("snr"),
        }

    @app.route("/api/satellite/info")
    @login_required
    def api_satellite_info():
        """Full info — call once on page load."""
        dev, err = _require_hardware()
        if err:
            return err
        gs = app.config["GS_STATE"]
        
        # Use cached info if available, otherwise query once and cache it
        local = gs.local_device_info
        if local.get("fw_version") is None:
            fw_raw = dev.send_shell_command_full("fw_version")
            mode_raw = dev.send_shell_command_full("mode")
            flight_raw = dev.send_shell_command_full("flight")
            diff_raw = dev.send_shell_command_full("difficulty")
            if diff_raw:
                gs.difficulty = parse_difficulty(diff_raw)
            scid_raw = dev.send_shell_command_full("sc_id")
            status_raw = dev.send_shell_command_full("status")
            local = _build_local_snapshot(
                fw_raw=fw_raw,
                mode_raw=mode_raw,
                flight_raw=flight_raw,
                diff_raw=diff_raw,
                scid_raw=scid_raw,
                status_raw=status_raw,
            )
            gs.local_device_info.update(local)
            
        local["has_radio1"] = getattr(gs.device, "has_radio1", True) if gs.device else True
        local["active_radio"] = gs.active_radio
        remote = gs.get_remote_satellite_snapshot()
        satellite = _build_satellite_snapshot(local, remote)
        return {
            "fw_version": local["fw_version"],
            "git_sha": local["git_sha"],
            "git_dirty": local["git_dirty"],
            "build_date": local["build_date"],
            "mode": local["mode"],
            "flight": local["flight"],
            "battery_mv": local["battery_mv"],
            "tm_rate": local["tm_rate"],
            "difficulty": local["difficulty"],
            "sc_id": local["sc_id"],
            "connection_role": local["role"],
            "local": local,
            "remote": remote,
            "satellite": satellite,
        }

    @app.route("/api/satellite/status")
    @login_required
    def api_satellite_status():
        """Lightweight status — only flight/battery/mode. For polling."""
        dev, err = _require_hardware()
        if err:
            return err
        gs = app.config["GS_STATE"]

        # FAST PATH: In Dual mode (active_radio==2) and local role is GS, satellite data comes from LoRa telemetry.
        # Skip slow shell queries — return remote snapshot directly.
        if getattr(gs, "active_radio", 0) == 2 and gs.local_device_info.get("role") != "satellite":
            remote = gs.get_remote_satellite_snapshot()
            local = {
                "fw_version": gs.local_device_info.get("fw_version"),
                "git_sha": gs.local_device_info.get("git_sha"),
                "git_dirty": gs.local_device_info.get("git_dirty"),
                "build_date": gs.local_device_info.get("build_date"),
                "sc_id": gs.local_device_info.get("sc_id"),
                "mode": gs.local_device_info.get("mode") or "ground_station",
                "flight": gs.local_device_info.get("flight") or "unknown",
                "difficulty": gs.difficulty,
                "role": gs.local_device_info.get("role") or "ground_station",
                "role_label": gs.local_device_info.get("role_label") or "Ground Station",
                "active_radio": gs.active_radio,
                "has_radio1": getattr(gs.device, "has_radio1", True) if gs.device else True,
                "battery_mv": 0,
                "tm_rate": 0,
            }
            satellite = _build_satellite_snapshot(local, remote)
            return {
                "mode": local["mode"],
                "flight": remote.get("flight"),
                "battery_mv": remote.get("battery_mv"),
                "tm_rate": None,
                "difficulty": gs.difficulty,
                "connection_role": local["role"],
                "local": local,
                "remote": remote,
                "satellite": satellite,
            }

        # STANDARD PATH: single radio / direct USB mode — query shell
        flight_raw = dev.send_shell_command_full("flight")
        mode_raw = dev.send_shell_command_full("mode")
        status_raw = dev.send_shell_command_full("status")
        diff_raw = dev.send_shell_command_full("difficulty")
        if diff_raw:
            gs.difficulty = parse_difficulty(diff_raw)
        local = _build_local_snapshot(
            mode_raw=mode_raw,
            flight_raw=flight_raw,
            diff_raw=diff_raw,
            status_raw=status_raw,
        )
        gs.local_device_info.update(local)
        local["has_radio1"] = getattr(gs.device, "has_radio1", True) if gs.device else True
        local["active_radio"] = gs.active_radio
        remote = gs.get_remote_satellite_snapshot()
        satellite = _build_satellite_snapshot(local, remote)
        return {
            "mode": local["mode"],
            "flight": local["flight"],
            "battery_mv": local["battery_mv"],
            "tm_rate": local["tm_rate"],
            "difficulty": local["difficulty"],
            "connection_role": local["role"],
            "local": local,
            "remote": remote,
            "satellite": satellite,
        }


    @app.route("/api/satellite/sensors")
    @login_required
    def api_satellite_sensors():
        dev, err = _require_hardware()
        if err:
            return err
        gs = app.config["GS_STATE"]
        
        # Check cached local role to avoid slow shell query
        local_role = gs.local_device_info.get("role")
        if local_role is None:
            local_mode = _local_mode_from_shell(dev.send_shell_command_full("mode"))
            local_role = _local_role_from_mode(local_mode)
            gs.local_device_info["mode"] = local_mode
            gs.local_device_info["role"] = local_role
            gs.local_device_info["role_label"] = "Ground Station" if local_role == "ground_station" else "Satellite"

        if local_role == "ground_station":
            # In Ground Station mode, sensor data MUST come from telemetry received over RF.
            remote = gs.get_remote_satellite_snapshot()
            return {
                "source": "remote",
                "available": remote.get("available", False),
                "temperature": remote.get("temperature"),
                "pressure": remote.get("pressure"),
                "humidity": remote.get("humidity"),
                "accel_x": remote.get("accel_x"),
                "accel_y": remote.get("accel_y"),
                "accel_z": remote.get("accel_z"),
            }
        raw = dev.send_shell_command_full("sensors")
        return {"source": "local", "available": True, **parse_sensors(raw)}

    @app.route("/api/satellite/lora_config", methods=["GET", "POST"])
    @login_required
    def api_satellite_lora_config():
        dev, err = _require_hardware()
        if err:
            return err
        gs = app.config["GS_STATE"]
        if request.method == "GET":
            radio = request.args.get("radio", "R0")
            # Return cached config if available
            cached_cfg = gs.local_device_info.get("radio_configs", {}).get(radio)
            if cached_cfg and cached_cfg.get("frequency", 0) > 0:
                return cached_cfg
            
            raw = dev.send_shell_command_full(f"lora_config {radio}")
            cfg = parse_lora_config(raw)
            if "radio_configs" not in gs.local_device_info:
                gs.local_device_info["radio_configs"] = {}
            gs.local_device_info["radio_configs"][radio] = cfg
            return cfg
        err_adm = _require_admin()
        if err_adm:
            return err_adm
        data = request.get_json(silent=True) or {}
        radio = data.get("radio", "R0")
        freq = data.get("frequency")
        sf = data.get("sf")
        bw = data.get("bw")
        power = data.get("power")

        # Check local role using cache
        local_role = gs.local_device_info.get("role")
        if local_role is None:
            local_mode = _local_mode_from_shell(dev.send_shell_command_full("mode"))
            local_role = _local_role_from_mode(local_mode)
            gs.local_device_info["mode"] = local_mode
            gs.local_device_info["role"] = local_role
            gs.local_device_info["role_label"] = "Ground Station" if local_role == "ground_station" else "Satellite"

        if local_role == "ground_station":
            from core.ccsds import sdls_protect_frame
            from core.telecommand import build_frequency_tc, build_power_tc
            from webapp.radio_bridge import RadioBridge

            radio_idx = 0 if radio == "R0" else 1
            bridge = RadioBridge(gs)

            # Send telecommands to remote satellite over RF first
            if freq:
                frame = build_frequency_tc(radio_idx, int(freq))
                frame = sdls_protect_frame(frame, gs.difficulty)
                bridge.send_raw(frame)
            if power:
                frame = build_power_tc(radio_idx, int(power))
                frame = sdls_protect_frame(frame, gs.difficulty)
                bridge.send_raw(frame)

        results = []
        if freq:
            results.append(dev.send_shell_command_full(f"lora_freq {radio} {freq}"))
        if sf:
            results.append(dev.send_shell_command_full(f"lora_sf {radio} {sf}"))
        if bw:
            results.append(dev.send_shell_command_full(f"lora_bw {radio} {bw}"))
        if power:
            results.append(dev.send_shell_command_full(f"lora_power {radio} {power}"))
        results.append(dev.send_shell_command_full(f"lora_apply {radio}"))
        
        # Update cache
        if "radio_configs" not in gs.local_device_info:
            gs.local_device_info["radio_configs"] = {}
        if radio not in gs.local_device_info["radio_configs"]:
            gs.local_device_info["radio_configs"][radio] = {"frequency": 0, "sf": 0, "bw": 0, "power": 0}
        cfg = gs.local_device_info["radio_configs"][radio]
        if freq is not None: cfg["frequency"] = int(freq)
        if sf is not None: cfg["sf"] = int(sf)
        if bw is not None: cfg["bw"] = int(bw)
        if power is not None: cfg["power"] = int(power)
        
        _sync_radio_config_to_db(dev)
        log_activity("INFO", "satellite", f"{radio} LoRa config updated: freq={freq} sf={sf} bw={bw} power={power}")
        return {"status": "ok", "responses": results}

    @app.route("/api/satellite/mode", methods=["POST"])
    @login_required
    def api_satellite_mode():
        err_adm = _require_admin()
        if err_adm:
            return err_adm
        dev, err = _require_hardware()
        if err:
            return err
        data = request.get_json(silent=True) or {}
        mode = data.get("mode", "raw")
        gs = app.config["GS_STATE"]

        # Comprobación de estado actual para evitar doble acción
        if _normalize_mode(gs.local_device_info.get("mode")) == _normalize_mode(mode):
            log_activity("INFO", "satellite", f"Mode change ignored: already in {mode}")
            return {"status": "ok", "response": f"Already in mode: {mode}", "no_change": True}

        if mode == "ground_station":
            # Ground Station: firmware in raw + radios in command mode
            dev.send_shell_command_full("mode gs")
            dev.send_shell_command_full("lora_apply ALL")
            dev.send_shell_command_full("lora_mode ALL command")
            
            # Update cache
            gs.local_device_info["mode"] = "ground_station"
            gs.local_device_info["role"] = "ground_station"
            gs.local_device_info["role_label"] = "Ground Station"
            
            log_activity("INFO", "satellite", "Mode changed to Ground Station (R0+R1 command mode)")
            return {"status": "ok", "mode": "ground_station"}

        if mode == "raw":
            dev.send_shell_command_full("mode gs")
            resp = dev.send_shell_command_full("lora_mode ALL stream")
            
            # Update cache
            gs.local_device_info["mode"] = "raw"
            gs.local_device_info["role"] = "ground_station"
            gs.local_device_info["role_label"] = "Ground Station"
        elif mode == "mission":
            # Satellite: BOTH radios stream. The firmware couples role to
            # lora_mode — a command-mode radio makes the board a ground station —
            # so the satellite must keep R0+R1 in stream to stay a satellite.
            dev.send_shell_command_full("mode sat")
            resp = dev.send_shell_command_full("lora_mode ALL stream")

            # Update cache
            gs.local_device_info["mode"] = "mission"
            gs.local_device_info["role"] = "satellite"
            gs.local_device_info["role_label"] = "Satellite"
        else:
            # Map general mode strings to FW mode arguments
            fw_mode = "gs" if mode in ("gs", "ground_station", "raw") else "sat" if mode in ("sat", "satellite", "mission") else mode
            resp = dev.send_shell_command_full(f"mode {fw_mode}")
            
            # Update cache
            gs.local_device_info["mode"] = mode
            role = _local_role_from_mode(mode)
            gs.local_device_info["role"] = role
            gs.local_device_info["role_label"] = "Ground Station" if role == "ground_station" else "Satellite"

        log_activity("INFO", "satellite", f"Mode changed to {mode}")
        return {"status": "ok", "response": resp}

    @app.route("/api/satellite/flight", methods=["POST"])
    @login_required
    def api_satellite_flight():
        err_adm = _require_admin()
        if err_adm:
            return err_adm
        dev, err = _require_hardware()
        if err:
            return err
        data = request.get_json(silent=True) or {}
        flight = data.get("flight", "idle")

        gs = app.config["GS_STATE"]
        local_role = gs.local_device_info.get("role")
        if local_role is None:
            local_mode = _local_mode_from_shell(dev.send_shell_command_full("mode"))
            local_role = _local_role_from_mode(local_mode)
            gs.local_device_info["mode"] = local_mode
            gs.local_device_info["role"] = local_role
            gs.local_device_info["role_label"] = "Ground Station" if local_role == "ground_station" else "Satellite"

        # Comprobación de estado actual para evitar doble acción
        current_flight = gs.remote_satellite.get("flight") if local_role == "ground_station" else gs.local_device_info.get("flight")
        if current_flight and current_flight.lower() == flight.lower():
            log_activity("INFO", "satellite", f"Flight state change ignored: already in {flight}")
            return {"status": "ok", "response": f"Already in flight state: {flight}", "no_change": True}

        if local_role == "ground_station":
            from core.ccsds import sdls_protect_frame
            from core.telecommand import build_command_tc
            from webapp.radio_bridge import RadioBridge

            opcode_map = {
                "idle": 0x00,
                "nominal": 0x02,
                "safe": 0x01,
                "debug": 0x03
            }
            opcode = opcode_map.get(flight, 0x00)
            frame = build_command_tc(opcode)

            difficulty = gs.difficulty
            frame = sdls_protect_frame(frame, difficulty)

            bridge = RadioBridge(gs)
            result = bridge.send_raw(frame)
            if result.get("status") == "error":
                log_activity("ERROR", "satellite", f"Flight state telecommand (set flight to {flight}) failed: {result.get('error')}")
                return {"error": result.get("error"), "result": result}
                
            dev.send_shell_command_full(f"flight {flight}")
            gs.local_device_info["flight"] = flight
            gs.remote_satellite["flight"] = flight.upper()
            log_activity("INFO", "satellite", f"Flight state telecommand (set flight to {flight}) transmitted over RF and set locally")
            return {"status": "ok", "response": "Telecommand sent", "result": result}

        resp = dev.send_shell_command_full(f"flight {flight}")
        gs.local_device_info["flight"] = flight
        log_activity("INFO", "satellite", f"Flight state changed to {flight}")
        return {"status": "ok", "response": resp}

    @app.route("/api/satellite/difficulty", methods=["POST"])
    @login_required
    def api_satellite_difficulty():
        err_adm = _require_admin()
        if err_adm:
            return err_adm
        dev, err = _require_hardware()
        if err:
            return err
        data = request.get_json(silent=True) or {}
        level = data.get("level", 0)

        gs = app.config["GS_STATE"]

        # Comprobación de estado actual para evitar doble acción
        try:
            level_int = int(level)
        except (ValueError, TypeError):
            level_int = 0
        if gs.difficulty == level_int:
            log_activity("INFO", "satellite", f"Difficulty change ignored: already at level {level_int}")
            return {"status": "ok", "response": f"Already at difficulty level: {level_int}", "no_change": True}

        local_role = gs.local_device_info.get("role")
        if local_role is None:
            local_mode = _local_mode_from_shell(dev.send_shell_command_full("mode"))
            local_role = _local_role_from_mode(local_mode)
            gs.local_device_info["mode"] = local_mode
            gs.local_device_info["role"] = local_role
            gs.local_device_info["role_label"] = "Ground Station" if local_role == "ground_station" else "Satellite"

        if local_role == "ground_station":
            from core.ccsds import sdls_protect_frame
            from core.telecommand import build_difficulty_tc
            from webapp.radio_bridge import RadioBridge

            frame = build_difficulty_tc(int(level))

            difficulty = gs.difficulty
            frame = sdls_protect_frame(frame, difficulty)

            bridge = RadioBridge(gs)
            result = bridge.send_raw(frame)
            gs.difficulty = int(level)
            gs.local_device_info["difficulty"] = int(level)
            gs.remote_satellite["difficulty"] = int(level)
            log_activity("INFO", "satellite", f"Difficulty telecommand (set difficulty to {level}) transmitted over RF")
            return {"status": "ok", "response": "Telecommand sent", "result": result}

        resp = dev.send_shell_command_full(f"difficulty {level}")
        gs.difficulty = int(level)
        gs.local_device_info["difficulty"] = int(level)
        log_activity("INFO", "satellite", f"Difficulty set to {level}")
        return {"status": "ok", "response": resp}

    @app.route("/api/satellite/tinygs", methods=["POST"])
    @login_required
    def api_satellite_tinygs():
        err_adm = _require_admin()
        if err_adm:
            return err_adm
        dev, err = _require_hardware()
        if err:
            return err
        data = request.get_json(silent=True) or {}
        action = data.get("action", "status")
        gs = app.config["GS_STATE"]
        if action == "spoof":
            profile = data.get("profile", "norbi")
            
            # Comprobación de estado actual para evitar doble acción
            if _normalize_mode(gs.local_device_info.get("mode")) == "tinygs" and gs.local_device_info.get("tinygs_profile") == profile:
                log_activity("INFO", "satellite", f"TinyGS spoof ignored: already spoofing {profile}")
                return {"status": "ok", "response": f"Already spoofing profile: {profile}", "no_change": True}
                
            dev.send_shell_command_full("lora_mode ALL stream")
            resp = dev.send_shell_command_full(f"tinygs spoof {profile}")
            gs.local_device_info["mode"] = "tinygs"
            gs.local_device_info["tinygs_profile"] = profile
            log_activity("INFO", "satellite", f"TinyGS spoofing {profile}")
        elif action == "stop":
            # Comprobación de estado actual para evitar doble acción
            if _normalize_mode(gs.local_device_info.get("mode")) in ("mission", "ground_station", "raw"):
                log_activity("INFO", "satellite", "TinyGS stop ignored: TinyGS is not active")
                return {"status": "ok", "response": "TinyGS is not active", "no_change": True}
                
            resp = dev.send_shell_command_full("tinygs stop")
            gs.local_device_info["mode"] = "mission" # revert to satellite/mission
            gs.local_device_info["tinygs_profile"] = None
            log_activity("INFO", "satellite", "TinyGS stopped")
        else:
            resp = dev.send_shell_command_full("tinygs status")
        return {"status": "ok", "response": resp}

    @app.route("/api/satellite/reset", methods=["POST"])
    @login_required
    def api_satellite_reset():
        err_adm = _require_admin()
        if err_adm:
            return err_adm
        dev, err = _require_hardware()
        if err:
            return err

        gs = app.config["GS_STATE"]
        local_mode = _local_mode_from_shell(dev.send_shell_command_full("mode"))
        if _local_role_from_mode(local_mode) == "ground_station":
            resp = dev.send_shell_command_full("reset_defaults")
            gs.active_radio = 0
            dev.send_shell_command_full("radio0")
            gs.difficulty = 0
            log_activity("WARN", "satellite", "Local Ground Station defaults restored (Active radio set to 0, difficulty set to 0)")
            return {"status": "ok", "response": resp}

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

    from core.ccsds import detect_tm_difficulty, parse_frame, sdls_unprotect_frame
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
                # HARDWARE MODE: read from the active radio
                # Pause RX while a telecommand is transmitting: the TX path may flip
                # the physical radio and reset serial buffers, so reading now would
                # grab the wrong radio or fight the TX for the port lock.
                if getattr(gs, "tx_in_progress", False):
                    time.sleep(0.05)
                    continue
                # Step 1: Read line (connection-level — fallback on failure)
                try:
                    if not gs.device.is_connected:
                        raise OSError("Device disconnected")
                    # In Dual mode (2) or Radio 0 (0) mode, receive on Radio 0. Otherwise, on Radio 1 (1).
                    rx_radio = 0 if gs.active_radio in (0, 2) else 1
                    line = gs.device.read_line_from_radio(rx_radio, timeout=1.0)
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
                    print(f"[RADIO{rx_radio} RAW] {line!r}")
                    try:
                        parsed = parse_lora_rx(line)
                        if parsed:
                            hex_data = parsed["data"]
                            print(
                                f"[RADIO{rx_radio} PARSED] hex={hex_data}"
                                f" ({len(hex_data) // 2} bytes)"
                                f" rssi={parsed.get('rssi')} snr={parsed.get('snr')}"
                            )
                            raw_bytes = bytes.fromhex(parsed["data"])
                            # Heartbeats carry the satellite's own SDLS level and can be
                            # trial-decrypted against known invariants, so let them drive
                            # the RX difficulty. Encrypt-then-CRC means a wrong level still
                            # passes the CRC check, so we cannot rely on the local board's
                            # setting matching the sender's.
                            detected = detect_tm_difficulty(raw_bytes)
                            if detected is not None and detected != getattr(gs, "remote_difficulty", None):
                                print(
                                    f"[RADIO{rx_radio} SDLS] satellite difficulty={detected}"
                                    f" (local board={getattr(gs, 'difficulty', 0)})"
                                )
                                gs.remote_difficulty = detected
                            difficulty = getattr(gs, "remote_difficulty", None)
                            if difficulty is None:
                                difficulty = getattr(gs, "difficulty", 0)
                            # Parse the frame as received. Firmware computes the CRC *after*
                            # encrypting the payload (encrypt-then-CRC), so the CRC must be
                            # validated over the ciphertext — before decryption.
                            pkt = parse_frame(raw_bytes)
                            # SDLS: recover the plaintext payload for decoding, and stay
                            # robust to firmware that instead does CRC-over-plaintext.
                            if pkt is not None and difficulty >= 2:
                                dec_frame = sdls_unprotect_frame(raw_bytes, difficulty)
                                pkt_dec = parse_frame(dec_frame)
                                if pkt.crc_valid:
                                    # encrypt-then-CRC: CRC authenticated the ciphertext;
                                    # swap in the decrypted payload for decoding.
                                    if pkt_dec is not None:
                                        pkt.payload = pkt_dec.payload
                                elif pkt_dec is not None and pkt_dec.crc_valid:
                                    # CRC-over-plaintext: the decrypted frame authenticates.
                                    pkt = pkt_dec
                            if pkt is None:
                                print(f"[RADIO{rx_radio} CCSDS] parse_frame returned None for {len(raw_bytes)} bytes")
                            elif not pkt.crc_valid and raw_bytes[-2:] != b"\x00\x00":
                                print(f"[RADIO{rx_radio} CRC] bad CRC, dropping frame (apid={pkt.apid})")
                                pkt = None
                            else:
                                print(
                                    f"[RADIO{rx_radio} CCSDS] valid frame: apid=0x{pkt.apid:03X}"
                                    f" seq={pkt.seq_count} payload={len(pkt.payload)} bytes"
                                )
                            if pkt:
                                # Check if we are a satellite and received a telecommand using cached mode
                                local_mode = gs.local_device_info.get("mode") or "ground_station"
                                if _local_role_from_mode(local_mode) == "satellite" and (pkt.pkt_type == 1 or pkt.apid in [0x020, 0x021, 0x022, 0x027]):
                                    import struct
                                    from core.constants import (
                                        APID_TC_COMMAND,
                                        APID_TC_SET_DIFFICULTY,
                                        APID_TC_SET_FREQ,
                                        APID_TC_SET_POWER,
                                        TC_OP_NOP,
                                        TC_OP_SET_SAFE_MODE,
                                        TC_OP_SET_NOMINAL,
                                        TC_OP_SET_DEBUG,
                                    )

                                    if pkt.apid == APID_TC_COMMAND and len(pkt.payload) > 0:
                                        opcode = pkt.payload[0]
                                        flight_modes = {
                                            TC_OP_NOP: "idle",
                                            TC_OP_SET_SAFE_MODE: "safe",
                                            TC_OP_SET_NOMINAL: "nominal",
                                            TC_OP_SET_DEBUG: "debug",
                                        }
                                        flight_mode = flight_modes.get(opcode)
                                        if flight_mode:
                                            gs.device.send_shell_command_full(f"flight {flight_mode}")
                                    elif pkt.apid == APID_TC_SET_DIFFICULTY and len(pkt.payload) > 0:
                                        level = pkt.payload[0]
                                        gs.device.send_shell_command_full(f"difficulty {level}")
                                        gs.difficulty = level
                                    elif pkt.apid == APID_TC_SET_FREQ and len(pkt.payload) >= 5:
                                        radio_idx, freq = struct.unpack("<BI", pkt.payload[:5])
                                        radio = f"R{radio_idx}"
                                        gs.device.send_shell_command_full(f"lora_freq {radio} {freq}")
                                        gs.device.send_shell_command_full(f"lora_apply {radio}")
                                    elif pkt.apid == APID_TC_SET_POWER and len(pkt.payload) >= 2:
                                        radio_idx, power = struct.unpack("<Bb", pkt.payload[:2])
                                        radio = f"R{radio_idx}"
                                        gs.device.send_shell_command_full(f"lora_power {radio} {power}")
                                        gs.device.send_shell_command_full(f"lora_apply {radio}")

                                    with app.app_context():
                                        from webapp.db import get_db
                                        try:
                                            db = get_db()
                                            db.execute(
                                                "INSERT INTO logs (timestamp, level, source, message) VALUES (?, ?, ?, ?)",
                                                (
                                                    datetime.now().isoformat(),
                                                    "INFO",
                                                    "satellite",
                                                    f"Telecommand APID 0x{pkt.apid:03X} processed: payload={pkt.payload.hex()}",
                                                ),
                                            )
                                            db.commit()
                                        except Exception:
                                            pass

                                # Valid CCSDS frame with good CRC
                                decoded = decode_tm_payload(pkt.apid, pkt.payload)
                                gs.update_remote_satellite(
                                    pkt.apid,
                                    decoded,
                                    rssi=parsed.get("rssi"),
                                    snr=parsed.get("snr"),
                                    timestamp=pkt.timestamp,
                                )
                                from datetime import datetime

                                with app.app_context():
                                    from webapp.db import get_db

                                    db = get_db()
                                    db.execute(
                                        "INSERT INTO telemetry "
                                        "(timestamp, apid, spacecraft_id, temperature, "
                                        "pressure, humidity, accel_x, accel_y, accel_z, "
                                        "raw_hex, rssi, snr) "
                                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                                            parsed.get("rssi"),
                                            parsed.get("snr"),
                                        ),
                                    )
                                    db.commit()
                                socketio.emit(
                                    "telemetry_update",
                                    {
                                        "apid": pkt.apid,
                                        "seq_count": pkt.seq_count,
                                        "crc_valid": pkt.crc_valid,
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
                    except Exception as exc:
                        print(f"[RADIO0 ERR] {exc!r} for line: {line!r}")
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
                time.sleep(5)
            else:
                time.sleep(0.5)

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()


if __name__ == "__main__":
    import os
    app = create_app()
    port = int(os.environ.get("FLATSAT_PORT", 5000))
    print(f"PwnSat2 Ground Station running on http://localhost:{port}")
    socketio.run(app, host="0.0.0.0", port=port, debug=True, allow_unsafe_werkzeug=True)
