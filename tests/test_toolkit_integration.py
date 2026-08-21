import os
import subprocess
import sys
import tempfile
import time
import pytest
from werkzeug.serving import make_server
import threading

from modules.webapp.config import Config
from modules.webapp.db import init_db
from modules.webapp.seed import seed_db
from modules.webapp.app import create_app


class ServerThread(threading.Thread):
    def __init__(self, app, port):
        super().__init__()
        self.server = make_server("127.0.0.1", port, app)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self):
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()


def _run_server_and_script(level: int, script_name: str, args=None):
    class DynamicConfig(Config):
        CTF_LEVEL = level
        TESTING = False
        SECRET_KEY = "pwnsat_ground_station_2026"

    db_fd, db_path = tempfile.mkstemp(suffix=f"_srv_lvl{level}.db")
    app_instance = create_app(DynamicConfig, db_path=db_path)
    with app_instance.app_context():
        init_db()
        seed_db()

    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()

    server = ServerThread(app_instance, port)
    server.daemon = True
    server.start()
    time.sleep(0.3)

    base_url = f"http://127.0.0.1:{port}"
    script_path = os.path.join(os.path.dirname(__file__), "..", "toolkit", script_name)

    cmd = [sys.executable, script_path, base_url]
    if args:
        cmd.extend(args)

    res = subprocess.run(cmd, capture_output=True, text=True)

    server.shutdown()
    os.close(db_fd)
    if os.path.exists(db_path):
        os.unlink(db_path)

    return res


def test_exploit_lvl1_script():
    res = _run_server_and_script(level=1, script_name="exploit_lvl1.py")
    assert res.returncode == 0
    assert "LEVEL 1: EASY MODE" in res.stdout
    assert "FAIL" not in res.stdout


def test_exploit_lvl2_script():
    res = _run_server_and_script(level=2, script_name="exploit_lvl2.py")
    assert res.returncode == 0
    assert "LEVEL 2: MEDIUM MODE" in res.stdout
    assert "FAIL" not in res.stdout


def test_exploit_lvl3_script():
    res = _run_server_and_script(level=3, script_name="exploit_lvl3.py")
    assert res.returncode == 0
    assert "LEVEL 3: HARD MODE" in res.stdout
    assert "FAIL" not in res.stdout


def test_exploit_demo_script():
    res = _run_server_and_script(level=1, script_name="exploit_demo.py")
    assert res.returncode == 0
    assert "EXPLOITATION COMPLETE" in res.stdout
    assert "FAIL" not in res.stdout
