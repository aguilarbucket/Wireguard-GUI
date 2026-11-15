"""HTML shell and JSON API."""

from __future__ import annotations

import io
import ipaddress
import os
import secrets

import segno
from flask import Blueprint, Response, current_app, jsonify, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from .security import login_required
from .validation import ValidationError, dns, endpoint, ip_list, mtu, port, subnet
from .wireguard import WireGuardError

main_bp = Blueprint("main", __name__)


def _manager():
    return current_app.extensions["wireguard"]


def _json_body() -> dict:
    if not request.is_json:
        raise ValidationError("Se requiere Content-Type application/json.")
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ValidationError("El cuerpo JSON debe ser un objeto.")
    return body


@main_bp.get("/health")
def health():
    db_ok = current_app.extensions["wggui_db"].setting() is not None
    return jsonify(status="ok" if db_ok else "initializing"), 200 if db_ok else 503


@main_bp.get("/")
@login_required
def index():
    return render_template("index.html")


@main_bp.get("/api/status")
@login_required
def status():
    return jsonify(_manager().runtime_status())


@main_bp.post("/api/peers")
@login_required
def create_peer():
    peer = _manager().create_peer(_json_body())
    return jsonify(id=peer["id"], name=peer["name"], address=peer["address"]), 201


@main_bp.patch("/api/peers/<uuid:peer_id>")
@login_required
def update_peer(peer_id):
    peer = _manager().update_peer(str(peer_id), _json_body())
    return jsonify(id=peer["id"], name=peer["name"], enabled=bool(peer["enabled"]))


@main_bp.delete("/api/peers/<uuid:peer_id>")
@login_required
def delete_peer(peer_id):
    _manager().delete_peer(str(peer_id))
    return "", 204


@main_bp.get("/api/peers/<uuid:peer_id>/config")
@login_required
def download_config(peer_id):
    peer = current_app.extensions["wggui_db"].peer(str(peer_id))
    if not peer:
        return jsonify(error="Cliente no encontrado."), 404
    content = _manager().client_config(str(peer_id))
    safe_name = "".join(character if character.isalnum() or character in "-_" else "_" for character in peer["name"])
    return Response(
        content,
        mimetype="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.conf"', "Cache-Control": "no-store"},
    )


@main_bp.get("/api/peers/<uuid:peer_id>/qr")
@login_required
def peer_qr(peer_id):
    try:
        content = _manager().client_config(str(peer_id))
    except KeyError:
        return jsonify(error="Cliente no encontrado."), 404
    output = io.BytesIO()
    segno.make(content, error="m").save(output, kind="svg", scale=4, xmldecl=False, svgns=True)
    return Response(output.getvalue(), mimetype="image/svg+xml", headers={"Cache-Control": "no-store"})


@main_bp.get("/api/settings")
@login_required
def get_settings():
    value = current_app.extensions["wggui_db"].setting()
    return jsonify(
        endpoint=value["endpoint"], listen_port=value["listen_port"], subnet=value["subnet"],
        dns=value["dns"], allowed_ips=value["client_allowed_ips"], mtu=value["mtu"],
    )


@main_bp.put("/api/settings")
@login_required
def update_settings():
    payload = _json_body()
    allowed = {"endpoint", "listen_port", "subnet", "dns", "allowed_ips", "mtu"}
    if set(payload) != allowed:
        raise ValidationError("Debe enviar todos los campos de configuración y ningún campo adicional.")
    values = {
        "endpoint": endpoint(payload["endpoint"]),
        "listen_port": port(payload["listen_port"]),
        "subnet": str(subnet(payload["subnet"])),
        "dns": dns(payload["dns"]),
        "client_allowed_ips": ip_list(payload["allowed_ips"]),
        "mtu": mtu(payload["mtu"]),
    }
    db = current_app.extensions["wggui_db"]
    old = db.setting()
    assert old is not None
    if values["subnet"] != old["subnet"] and db.peers():
        raise ValidationError("No se puede cambiar la subred mientras existan clientes; elimínelos primero.")
    cold_change = (
        values["subnet"] != old["subnet"]
        or values["mtu"] != old["mtu"]
        or values["listen_port"] != old["listen_port"]
    )

    def mutate(conn):
        conn.execute(
            """UPDATE settings SET endpoint=:endpoint,listen_port=:listen_port,subnet=:subnet,
            dns=:dns,client_allowed_ips=:client_allowed_ips,mtu=:mtu,updated_at=CURRENT_TIMESTAMP WHERE id=1""",
            values,
        )

    _manager()._persist_and_sync(mutate)
    return jsonify(ok=True, restart_required=cold_change)


@main_bp.put("/api/password")
@login_required
def update_password():
    payload = _json_body()
    if set(payload) != {"current_password", "new_password"}:
        raise ValidationError("Se requieren la contraseña actual y la nueva.")
    new_password = str(payload["new_password"])
    if len(new_password) < 12:
        raise ValidationError("La nueva contraseña debe tener al menos 12 caracteres.")
    db = current_app.extensions["wggui_db"]
    settings = db.setting()
    if not settings or not check_password_hash(settings["admin_password_hash"], str(payload["current_password"])):
        return jsonify(error="La contraseña actual es incorrecta."), 403
    with db.transaction() as conn:
        conn.execute(
            "UPDATE settings SET admin_password_hash=?,updated_at=CURRENT_TIMESTAMP WHERE id=1",
            (generate_password_hash(new_password, method="scrypt"),),
        )

    # Rotar la clave invalida de inmediato todas las demás sesiones administrativas.
    secret = secrets.token_bytes(32)
    secret_path = current_app.config["SECRET_FILE"]
    temp = secret_path.with_suffix(".tmp")
    temp.write_bytes(secret)
    os.chmod(temp, 0o600)
    os.replace(temp, secret_path)
    current_app.secret_key = secret
    session.modified = True  # vuelve a firmar esta sesión con la clave nueva
    return jsonify(ok=True)


@main_bp.errorhandler(ValidationError)
def validation_error(error):
    return jsonify(error=str(error)), 400


@main_bp.errorhandler(WireGuardError)
def wireguard_error(error):
    current_app.logger.error("Operación WireGuard fallida: %s", error)
    return jsonify(error="No fue posible sincronizar WireGuard; no se guardaron los cambios."), 503


@main_bp.errorhandler(KeyError)
def not_found(_error):
    return jsonify(error="Cliente no encontrado."), 404
