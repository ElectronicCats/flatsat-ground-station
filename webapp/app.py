"""Flask application factory with WebSocket support."""

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
        # VULNERABLE: no ownership check (GS-06 IDOR)
        config = db.execute("SELECT * FROM radio_config WHERE id = ?", (config_id,)).fetchone()
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

        # VULNERABLE: f-string in shell commands (GS-07 — all 4 fields)
        try:
            output = subprocess.check_output(
                f"echo 'Setting frequency to {frequency}, SF={spreading_factor}, BW={bandwidth}, power={tx_power}'",
                shell=True,
                stderr=subprocess.STDOUT,
            )
            shell_output = output.decode(errors="replace")
        except subprocess.CalledProcessError as e:
            shell_output = e.output.decode(errors="replace")

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

        extra_bytes = bytes.fromhex(extra_hex) if extra_hex else b""
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
            # Bootstrap: R1 command mode + sync difficulty (retry once on failure)
            r1_resp = device.send_shell_command_full("lora_mode R1 command")
            if r1_resp is None:
                time.sleep(0.5)
                r1_resp = device.send_shell_command_full("lora_mode R1 command")
            diff_raw = device.send_shell_command_full("difficulty")
            if diff_raw is None:
                time.sleep(0.5)
                diff_raw = device.send_shell_command_full("difficulty")
            gs.difficulty = parse_difficulty(diff_raw)
            warnings = []
            if r1_resp is None or "error" in (r1_resp or "").lower() or "unknown" in (r1_resp or "").lower():
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

    def _sync_radio_config_to_db(dev):
        """Read LoRa config from hardware and upsert into radio_config for current user."""
        try:
            from webapp.db import get_db

            db = get_db()
            for radio, radio_label in zip(("R0", "R1"), RADIO_LABELS, strict=False):
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

    def _local_mode_from_shell(mode_raw: str | None, status_raw: str | None = None) -> str:
        mode = parse_mode(mode_raw)
        if status_raw and "mode=command" in status_raw and mode == "raw":
            return "ground_station"
        return mode

    def _local_role_from_mode(mode: str) -> str:
        return "ground_station" if mode == "ground_station" else "satellite"

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
        flight = parse_flight(flight_raw)
        mode = _local_mode_from_shell(mode_raw, status_raw)
        role = _local_role_from_mode(mode)
        return {
            **fw,
            "mode": mode,
            "flight": flight["flight"],
            "battery_mv": flight["battery_mv"],
            "tm_rate": flight["tm_rate"],
            "difficulty": parse_difficulty(diff_raw),
            "sc_id": parse_sc_id(scid_raw) if scid_raw is not _SENTINEL else None,
            "role": role,
            "role_label": "Ground Station" if role == "ground_station" else "Satellite",
        }

    def _build_satellite_snapshot(local: dict, remote: dict) -> dict:
        if local["role"] == "ground_station":
            return {
                "available": remote.get("available", False),
                "source": "remote",
                "source_label": "Relayed Telemetry" if remote.get("available") else "Waiting for Telemetry",
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
        status_raw = dev.send_shell_command_full("status")
        local = _build_local_snapshot(
            fw_raw=fw_raw,
            mode_raw=mode_raw,
            flight_raw=flight_raw,
            diff_raw=diff_raw,
            scid_raw=scid_raw,
            status_raw=status_raw,
        )
        remote = app.config["GS_STATE"].get_remote_satellite_snapshot()
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
        flight_raw = dev.send_shell_command_full("flight")
        mode_raw = dev.send_shell_command_full("mode")
        status_raw = dev.send_shell_command_full("status")
        diff_raw = dev.send_shell_command_full("difficulty")
        local = _build_local_snapshot(
            mode_raw=mode_raw,
            flight_raw=flight_raw,
            diff_raw=diff_raw,
            status_raw=status_raw,
        )
        remote = app.config["GS_STATE"].get_remote_satellite_snapshot()
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
        mode_raw = dev.send_shell_command_full("mode")
        status_raw = dev.send_shell_command_full("status")
        local_mode = _local_mode_from_shell(mode_raw, status_raw)
        if _local_role_from_mode(local_mode) == "ground_station":
            remote = app.config["GS_STATE"].get_remote_satellite_snapshot()
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
        if request.method == "GET":
            radio = request.args.get("radio", "R0")
            raw = dev.send_shell_command_full(f"lora_config {radio}")
            return parse_lora_config(raw)
        data = request.get_json(silent=True) or {}
        radio = data.get("radio", "R0")
        freq = data.get("frequency")
        sf = data.get("sf")
        bw = data.get("bw")
        power = data.get("power")
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
        _sync_radio_config_to_db(dev)
        log_activity("INFO", "satellite", f"{radio} LoRa config updated: freq={freq} sf={sf} bw={bw} power={power}")
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
            # Ground Station: firmware in raw + radios in command mode
            dev.send_shell_command_full("mode raw")
            dev.send_shell_command_full("lora_apply ALL")
            dev.send_shell_command_full("lora_mode ALL command")
            log_activity("INFO", "satellite", "Mode changed to Ground Station (R0+R1 command mode)")
            return {"status": "ok", "mode": "ground_station"}

        if mode == "raw":
            dev.send_shell_command_full("mode raw")
            resp = dev.send_shell_command_full("lora_mode ALL stream")
        elif mode == "mission":
            dev.send_shell_command_full("mode mission")
            resp = dev.send_shell_command_full("lora_mode ALL stream")
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
        gs = app.config["GS_STATE"]
        gs.difficulty = int(level)
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
            dev.send_shell_command_full("lora_mode ALL stream")
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
        # Firmware reset_defaults sets both radios to 915 MHz — restore R1 uplink offset
        dev.send_shell_command_full("lora_freq R1 916000000")
        dev.send_shell_command_full("lora_apply R1")
        log_activity("WARN", "satellite", "Factory defaults restored (R1 freq corrected)")
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

    from core.ccsds import parse_frame, sdls_unprotect_frame
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
                    print(f"[RADIO0 RAW] {line!r}")
                    try:
                        parsed = parse_lora_rx(line)
                        if parsed:
                            raw_bytes = bytes.fromhex(parsed["data"])
                            # SDLS: decrypt TM payload based on difficulty
                            difficulty = getattr(gs, "difficulty", 0)
                            if difficulty >= 2:
                                raw_bytes = sdls_unprotect_frame(raw_bytes, difficulty)
                            pkt = parse_frame(raw_bytes)
                            if pkt and not pkt.crc_valid:
                                print("[RADIO0 CRC] bad CRC, dropping frame")
                                pkt = None
                            if pkt:
                                # Valid CCSDS frame with good CRC
                                decoded = decode_tm_payload(pkt.apid, pkt.payload)
                                gs.update_remote_satellite(
                                    pkt.apid,
                                    decoded,
                                    rssi=parsed.get("rssi"),
                                    snr=parsed.get("snr"),
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
