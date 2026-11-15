"""Administrative authentication routes."""

from __future__ import annotations

import secrets

from flask import Blueprint, current_app, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from .security import clear_login_failures, login_allowed, record_login_failure, login_required

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("authenticated"):
        return redirect(url_for("main.index"))
    error = None
    if request.method == "POST":
        client_ip = request.remote_addr or "unknown"
        if not login_allowed(client_ip):
            return render_template("login.html", error="Demasiados intentos. Intente nuevamente en 15 minutos."), 429
        settings = current_app.extensions["wggui_db"].setting()
        supplied = request.form.get("password", "")
        if settings and check_password_hash(settings["admin_password_hash"], supplied):
            clear_login_failures(client_ip)
            session.clear()
            session["authenticated"] = True
            session["csrf_token"] = secrets.token_urlsafe(32)
            session.permanent = True
            return redirect(url_for("main.index"))
        record_login_failure(client_ip)
        error = "Credenciales incorrectas."
    return render_template("login.html", error=error)


@auth_bp.post("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
