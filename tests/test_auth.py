from tests.conftest import csrf_from


def test_api_requires_authentication(client):
    response = client.get("/api/status")
    assert response.status_code == 401
    assert response.get_json()["error"] == "Autenticación requerida."


def test_login_rejects_wrong_password(client):
    token = csrf_from(client.get("/auth/login"))
    response = client.post("/auth/login", data={"password": "wrong-password", "csrf_token": token})
    assert response.status_code == 200
    assert "Credenciales incorrectas" in response.get_data(as_text=True)


def test_login_rotates_session_and_allows_access(client):
    token = csrf_from(client.get("/auth/login"))
    response = client.post("/auth/login", data={"password": "very-secure-password", "csrf_token": token})
    assert response.status_code == 302
    assert client.get("/api/status").status_code == 200


def test_csrf_is_required(authenticated):
    client, _token = authenticated
    response = client.post("/api/peers", json={"name": "Phone"})
    assert response.status_code == 403


def test_security_headers(client):
    response = client.get("/auth/login")
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_password_change_rotates_credentials(authenticated):
    client, token = authenticated
    response = client.put(
        "/api/password",
        json={"current_password": "very-secure-password", "new_password": "a-new-secure-password"},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 200
    client.post("/auth/logout", data={"csrf_token": token})
    login_token = csrf_from(client.get("/auth/login"))
    assert client.post(
        "/auth/login", data={"password": "a-new-secure-password", "csrf_token": login_token}
    ).status_code == 302
