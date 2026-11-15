from __future__ import annotations

import re

import pytest
from werkzeug.security import generate_password_hash

from wggui import create_app


@pytest.fixture()
def app(tmp_path):
    data = tmp_path / "data"
    config = tmp_path / "wg_confs" / "wg0.conf"
    application = create_app({
        "TESTING": True,
        "DATA_DIR": data,
        "DATABASE": data / "state.db",
        "SECRET_FILE": data / "session.key",
        "WG_CONFIG": config,
        "SESSION_COOKIE_SECURE": False,
    })
    db = application.extensions["wggui_db"]
    with db.transaction() as conn:
        conn.execute(
            """INSERT INTO settings
            (id,endpoint,listen_port,subnet,dns,client_allowed_ips,mtu,
             server_private_key,server_public_key,admin_password_hash)
            VALUES (1,?,?,?,?,?,?,?,?,?)""",
            ("vpn.example.com", 51820, "10.13.13.0/29", "1.1.1.1", "0.0.0.0/0", None,
             "server-private", "server-public", generate_password_hash("very-secure-password", method="scrypt")),
        )
    manager = application.extensions["wireguard"]
    manager.write_config(manager.render())
    manager.sync_runtime = lambda: None
    counter = iter(range(1, 100))

    def keys():
        number = next(counter)
        return f"private-{number}", f"public-{number}"

    manager.generate_keypair = keys
    manager.generate_psk = lambda: f"psk-{next(counter)}"
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


def csrf_from(response) -> str:
    match = re.search(rb'name="csrf_token" value="([^"]+)"', response.data)
    assert match
    return match.group(1).decode()


@pytest.fixture()
def authenticated(client):
    page = client.get("/auth/login")
    token = csrf_from(page)
    response = client.post("/auth/login", data={"password": "very-secure-password", "csrf_token": token})
    assert response.status_code == 302
    with client.session_transaction() as session:
        token = session["csrf_token"]
    return client, token
