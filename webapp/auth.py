"""Authentication with deliberately broken session tokens (GS-05)."""

import base64
import hashlib
import time
from functools import wraps

from flask import request, redirect, url_for, g

from webapp.db import get_db


def _md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def create_session_token(username: str, role: str) -> str:
    """Create a base64 session token. DELIBERATELY INSECURE (GS-05)."""
    timestamp = str(int(time.time()))
    payload = f"{username}:{role}:{timestamp}"
    return base64.b64encode(payload.encode()).decode()


def parse_session_token(token: str) -> tuple[str | None, str | None]:
    """Parse a session token. Returns (username, role) or (None, None)."""
    try:
        decoded = base64.b64decode(token).decode()
        parts = decoded.split(":")
        if len(parts) >= 2:
            return parts[0], parts[1]
    except Exception:
        pass
    return None, None


def get_current_user():
    """Get current user from session token cookie."""
    token = request.cookies.get("session_token")
    if not token:
        return None, None
    return parse_session_token(token)


def login_required(f):
    """Decorator: redirect to login if no valid session."""
    @wraps(f)
    def decorated(*args, **kwargs):
        username, role = get_current_user()
        if username is None:
            return redirect(url_for("login"))
        g.username = username
        g.role = role
        return f(*args, **kwargs)
    return decorated


def authenticate(username: str, password: str) -> tuple[str | None, str | None]:
    """Check credentials against DB. Returns (username, role) or (None, None)."""
    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE username = ? AND password_hash = ?",
        (username, _md5(password)),
    ).fetchone()
    if user:
        return user["username"], user["role"]
    return None, None
