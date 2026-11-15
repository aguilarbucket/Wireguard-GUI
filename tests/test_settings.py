def test_subnet_change_blocked_while_peers_exist(authenticated):
    client, token = authenticated
    client.post("/api/peers", json={"name": "Phone"}, headers={"X-CSRF-Token": token})
    payload = client.get("/api/settings").get_json()
    payload["subnet"] = "10.99.0.0/24"
    response = client.put("/api/settings", json=payload, headers={"X-CSRF-Token": token})
    assert response.status_code == 400
    assert "mientras existan clientes" in response.get_json()["error"]


def test_hot_setting_change_does_not_request_restart(authenticated):
    client, token = authenticated
    payload = client.get("/api/settings").get_json()
    payload["endpoint"] = "new.example.com"
    response = client.put("/api/settings", json=payload, headers={"X-CSRF-Token": token})
    assert response.status_code == 200
    assert response.get_json()["restart_required"] is False


def test_mtu_change_requests_restart(authenticated):
    client, token = authenticated
    payload = client.get("/api/settings").get_json()
    payload["mtu"] = 1380
    response = client.put("/api/settings", json=payload, headers={"X-CSRF-Token": token})
    assert response.status_code == 200
    assert response.get_json()["restart_required"] is True
