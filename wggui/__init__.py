"""WireGuard GUI application factory."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from .auth import auth_bp
from .db import Database
from .routes import main_bp
from .security import install_security
from .wireguard import WireGuardManager

__version__ = "0.2.0"


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    data_dir = Path(os.environ.get("WGGUI_DATA_DIR", "/config/wggui"))
    app.config.from_mapping(
        DATA_DIR=data_dir,
        DATABASE=data_dir / "state.db",
        WG_CONFIG=Path(os.environ.get("WG_CONFIG", "/config/wg_confs/wg0.conf")),
        SECRET_FILE=data_dir / "session.key",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        SESSION_COOKIE_SECURE=_as_bool(os.environ.get("SESSION_COOKIE_SECURE", "false")),
        PERMANENT_SESSION_LIFETIME=3600,
        MAX_CONTENT_LENGTH=64 * 1024,
        JSON_SORT_KEYS=False,
        TESTING=False,
    )
    if test_config:
        app.config.update(test_config)

    data_dir = Path(app.config["DATA_DIR"])
    data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    secret_file = Path(app.config["SECRET_FILE"])
    app.secret_key = _load_or_create_secret(secret_file)

    trusted_proxies = int(os.environ.get("TRUSTED_PROXY_COUNT", "0"))
    if trusted_proxies:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=trusted_proxies, x_proto=trusted_proxies)

    db = Database(Path(app.config["DATABASE"]))
    db.initialize()
    app.extensions["wggui_db"] = db
    app.extensions["wireguard"] = WireGuardManager(Path(app.config["WG_CONFIG"]), db)

    install_security(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    return app


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _load_or_create_secret(path: Path) -> bytes:
    if path.exists():
        return path.read_bytes()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    secret = os.urandom(32)
    temp = path.with_suffix(".tmp")
    temp.write_bytes(secret)
    os.chmod(temp, 0o600)
    os.replace(temp, path)
    return secret
