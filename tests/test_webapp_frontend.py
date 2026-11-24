"""The webapp must not depend on the internet, nor on duplicated frontends.

Two traps are guarded here:

1. The dashboard used to load the Socket.IO client from a CDN, so the live
   telemetry feed silently died on any machine without internet access.
2. ``webapp/static`` and ``webapp/templates`` were stale copies of
   ``modules/webapp/static`` and ``modules/webapp/templates`` (the real
   ones).  Editing the wrong copy meant the change never reached the
   browser.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEBAPP = ROOT / "modules" / "webapp"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def test_socketio_client_is_bundled_locally():
    client = WEBAPP / "static" / "js" / "socket-client.js"
    assert client.exists(), "falta el cliente Socket.IO local"
    assert "FlatSatSocket" in _read(client)


def test_dashboard_does_not_load_the_socketio_from_a_cdn():
    """A CDN dependency breaks the live feed offline."""
    for template in (WEBAPP / "templates").glob("*.html"):
        content = _read(template)
        assert "cdnjs.cloudflare.com" not in content, f"{template.name} carga socket.io de un CDN"
        assert "cdn.socket.io" not in content, f"{template.name} carga socket.io de un CDN"


def test_no_template_references_a_https_script():
    """The only external resource allowed is the font-free, local bundle."""
    for template in (WEBAPP / "templates").glob("*.html"):
        for line in _read(template).splitlines():
            if "<script" in line and "src=" in line:
                assert "https://" not in line, f"{template.name} usa un script remoto: {line.strip()}"


def test_telemetry_js_uses_the_local_client():
    telemetry = _read(WEBAPP / "static" / "js" / "telemetry.js")
    assert "FlatSatSocket" in telemetry
    assert "socket.connect()" in telemetry


def test_there_is_only_one_frontend():
    """No duplicated static/ or templates/ outside modules/webapp."""
    assert not (ROOT / "webapp" / "static").exists(), "webapp/static es una copia obsoleta: edita modules/webapp/static"
    assert not (ROOT / "webapp" / "templates").exists(), (
        "webapp/templates es una copia obsoleta: edita modules/webapp/templates"
    )


def test_pyinstaller_bundles_the_frontend():
    spec = _read(ROOT / "flatsat_app.spec")
    assert "modules.webapp" in spec
    assert "static/**/*" in spec
    assert "templates/**/*" in spec
