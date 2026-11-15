from wggui import bootstrap as bootstrap_module
from wggui.db import Database


def test_clean_bootstrap_is_idempotent_and_has_zero_peers(tmp_path, monkeypatch):
    data = tmp_path / "data"
    config = tmp_path / "wg_confs" / "wg0.conf"
    monkeypatch.setenv("WGGUI_DATA_DIR", str(data))
    monkeypatch.setenv("WG_CONFIG", str(config))
    monkeypatch.setenv("ADMIN_PASSWORD", "a-long-bootstrap-password")
    monkeypatch.setenv("SERVER_ENDPOINT", "vpn.example.com")
    monkeypatch.setattr(bootstrap_module.WireGuardManager, "generate_keypair", lambda self: ("private", "public"))

    bootstrap_module.bootstrap()
    first = Database(data / "state.db").setting()
    bootstrap_module.bootstrap()
    db = Database(data / "state.db")
    second = db.setting()

    assert first["server_private_key"] == second["server_private_key"] == "private"
    assert db.peers() == []
    assert config.stat().st_size > 0


def test_clean_bootstrap_requires_strong_password(tmp_path, monkeypatch):
    monkeypatch.setenv("WGGUI_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("WG_CONFIG", str(tmp_path / "wg0.conf"))
    monkeypatch.setenv("ADMIN_PASSWORD", "short")
    monkeypatch.setenv("SERVER_ENDPOINT", "vpn.example.com")
    try:
        bootstrap_module.bootstrap()
    except SystemExit as error:
        assert "12 caracteres" in str(error)
    else:
        raise AssertionError("bootstrap should fail")
