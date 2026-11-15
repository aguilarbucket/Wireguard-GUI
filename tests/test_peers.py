from __future__ import annotations


def create(client, token, name="Phone"):
    return client.post("/api/peers", json={"name": name}, headers={"X-CSRF-Token": token})


def test_create_assigns_unique_addresses_and_persists(authenticated, app):
    client, token = authenticated
    first = create(client, token, "Phone")
    second = create(client, token, "Laptop")
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.get_json()["address"] == "10.13.13.2"
    assert second.get_json()["address"] == "10.13.13.3"
    config = app.config["WG_CONFIG"].read_text()
    assert "PublicKey = public-1" in config
    assert "AllowedIPs = 10.13.13.2/32" in config


def test_duplicate_name_is_rejected(authenticated):
    client, token = authenticated
    assert create(client, token, "Phone").status_code == 201
    response = create(client, token, "phone")
    assert response.status_code == 400
    assert "Ya existe" in response.get_json()["error"]


def test_private_keys_are_not_in_status(authenticated):
    client, token = authenticated
    create(client, token)
    response = client.get("/api/status")
    text = response.get_data(as_text=True)
    assert "private-1" not in text
    assert "psk-2" not in text


def test_download_and_qr_are_authenticated_and_no_store(authenticated):
    client, token = authenticated
    peer_id = create(client, token).get_json()["id"]
    config = client.get(f"/api/peers/{peer_id}/config")
    assert config.status_code == 200
    assert "PrivateKey = private-1" in config.get_data(as_text=True)
    assert config.headers["Cache-Control"] == "no-store"
    qr = client.get(f"/api/peers/{peer_id}/qr")
    assert qr.status_code == 200
    assert qr.mimetype == "image/svg+xml"


def test_disable_removes_peer_from_server_config(authenticated, app):
    client, token = authenticated
    peer_id = create(client, token).get_json()["id"]
    response = client.patch(f"/api/peers/{peer_id}", json={"enabled": False}, headers={"X-CSRF-Token": token})
    assert response.status_code == 200
    assert "public-1" not in app.config["WG_CONFIG"].read_text()
    assert app.extensions["wggui_db"].peer(peer_id)["enabled"] == 0


def test_rename_and_edit_peer(authenticated, app):
    client, token = authenticated
    peer_id = create(client, token).get_json()["id"]
    response = client.patch(
        f"/api/peers/{peer_id}",
        json={"name": "Work laptop", "dns": "9.9.9.9", "allowed_ips": "10.0.0.0/8", "persistent_keepalive": 15},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 200
    peer = app.extensions["wggui_db"].peer(peer_id)
    assert peer["name"] == "Work laptop"
    assert peer["dns"] == "9.9.9.9"
    assert "AllowedIPs = 10.0.0.0/8" in app.extensions["wireguard"].client_config(peer_id)


def test_delete_revokes_and_removes_peer(authenticated, app):
    client, token = authenticated
    peer_id = create(client, token).get_json()["id"]
    response = client.delete(f"/api/peers/{peer_id}", headers={"X-CSRF-Token": token})
    assert response.status_code == 204
    assert app.extensions["wggui_db"].peer(peer_id) is None


def test_failed_runtime_sync_rolls_back_database_and_file(authenticated, app):
    client, token = authenticated
    manager = app.extensions["wireguard"]
    before = app.config["WG_CONFIG"].read_text()

    def fail():
        raise RuntimeError("simulated sync failure")

    manager.sync_runtime = fail
    try:
        manager.create_peer({"name": "Phone"})
    except RuntimeError as error:
        assert "simulated" in str(error)
    else:
        raise AssertionError("sync failure should propagate")
    assert app.extensions["wggui_db"].peers() == []
    assert app.config["WG_CONFIG"].read_text() == before


def test_invalid_name_is_rejected(authenticated):
    client, token = authenticated
    response = create(client, token, "bad/name")
    assert response.status_code == 400
