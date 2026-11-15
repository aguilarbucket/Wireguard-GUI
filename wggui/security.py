"""Session, CSRF, headers and lightweight login throttling."""

from __future__ import annotations

import hmac
import secrets
import time
from collections import defaultdict, deque
from functools import wraps

from flask import Flask, abort, jsonify, redirect, request, session, url_for


_attempts: dict[str, deque[float]] = defaultdict(deque)
LOGIN_WINDOW = 15 * 60
LOGIN_LIMIT = 5


def install_security(app: Flask) -> None:
    @app.before_request
    def csrf_protect():
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            expected = session.get("csrf_token", "")
            supplied = request.headers.get("X-CSRF-Token", "") or request.form.get("csrf_token", "")
            if not expected or not supplied or not hmac.compare_digest(expected, supplied):
                abort(403, description="Token CSRF inválido o ausente.")

    @app.after_request
    def harden(response):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self'; "
            "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.path.startswith("/api/") or request.path.startswith("/auth/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.context_processor
    def inject_csrf():
        return {"csrf_token": csrf_token}

    @app.errorhandler(403)
    def forbidden(error):
        if request.path.startswith("/api/"):
            return jsonify(error=str(error.description)), 403
        return str(error.description), 403


def csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("authenticated"):
            if request.path.startswith("/api/"):
                return jsonify(error="Autenticación requerida."), 401
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def login_allowed(ip: str) -> bool:
    now = time.monotonic()
    bucket = _attempts[ip]
    while bucket and bucket[0] < now - LOGIN_WINDOW:
        bucket.popleft()
    return len(bucket) < LOGIN_LIMIT


def record_login_failure(ip: str) -> None:
    _attempts[ip].append(time.monotonic())


def clear_login_failures(ip: str) -> None:
    _attempts.pop(ip, None)
