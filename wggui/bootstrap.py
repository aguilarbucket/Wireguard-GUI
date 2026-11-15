"""Idempotent clean-install bootstrap, run by s6 before WireGuard starts."""

from __future__ import annotations

import os
from pathlib import Path

from werkzeug.security import generate_password_hash

from .db import Database
from .validation import dns, endpoint, ip_list, mtu, port, subnet
from .wireguard import WireGuardManager


def bootstrap() -> None:
    data_dir = Path(os.environ.get("WGGUI_DATA_DIR", "/config/wggui"))
    config_path = Path(os.environ.get("WG_CONFIG", "/config/wg_confs/wg0.conf"))
    db = Database(data_dir / "state.db")
    db.initialize()
    manager = WireGuardManager(config_path, db)

    if db.setting() is None:
        password = os.environ.get("ADMIN_PASSWORD", "")
        if len(password) < 12:
            raise SystemExit("ADMIN_PASSWORD debe tener al menos 12 caracteres en la primera ejecución.")
        server_endpoint = endpoint(os.environ.get("SERVER_ENDPOINT"))
        listen_port = port(os.environ.get("SERVER_PORT", "51820"))
        vpn_subnet = str(subnet(os.environ.get("VPN_SUBNET", "10.13.13.0/24")))
        peer_dns = dns(os.environ.get("PEER_DNS", "1.1.1.1"))
        allowed = ip_list(os.environ.get("CLIENT_ALLOWED_IPS", "0.0.0.0/0"))
        configured_mtu = mtu(os.environ.get("WG_MTU"))
        private, public = manager.generate_keypair()
        with db.transaction() as conn:
            conn.execute(
                """INSERT INTO settings
                (id,endpoint,listen_port,subnet,dns,client_allowed_ips,mtu,
                 server_private_key,server_public_key,admin_password_hash)
                VALUES (1,?,?,?,?,?,?,?,?,?)""",
                (server_endpoint, listen_port, vpn_subnet, peer_dns, allowed, configured_mtu,
                 private, public, generate_password_hash(password, method="scrypt")),
            )
        print("[wggui] Instalación limpia inicializada; cero clientes.", flush=True)
    else:
        print("[wggui] Estado persistente encontrado; no se regeneran claves ni credenciales.", flush=True)

    manager.write_config(manager.render())


if __name__ == "__main__":
    bootstrap()
