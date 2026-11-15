"""Persistent WireGuard configuration and safe runtime synchronization."""

from __future__ import annotations

import ipaddress
import os
import sqlite3
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Callable

from .db import Database
from .validation import ValidationError, dns, ip_list, keepalive, name


class WireGuardError(RuntimeError):
    pass


class WireGuardManager:
    def __init__(
        self,
        config_path: Path,
        db: Database,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ):
        self.config_path = config_path
        self.db = db
        self.runner = runner
        self._lock = threading.RLock()

    def _run(self, args: list[str], *, input_text: str | None = None) -> str:
        try:
            result = self.runner(
                args,
                input=input_text,
                text=True,
                capture_output=True,
                check=True,
                timeout=10,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            detail = getattr(exc, "stderr", "") or ""
            raise WireGuardError(f"Falló {' '.join(args[:2])}: {detail.strip() or type(exc).__name__}") from exc
        return result.stdout.strip()

    def _run_root(self, args: list[str]) -> str:
        if getattr(os, "geteuid", lambda: 0)() != 0:
            args = ["sudo", "-n", "--", *args]
        return self._run(args)

    def generate_keypair(self) -> tuple[str, str]:
        private = self._run(["wg", "genkey"])
        public = self._run(["wg", "pubkey"], input_text=private + "\n")
        return private, public

    def generate_psk(self) -> str:
        return self._run(["wg", "genpsk"])

    def render(self, conn: sqlite3.Connection | None = None) -> str:
        owns_connection = conn is None
        conn = conn or self.db.connect()
        try:
            settings = conn.execute("SELECT * FROM settings WHERE id=1").fetchone()
            if settings is None:
                raise WireGuardError("El servidor aún no fue inicializado.")
            network = ipaddress.ip_network(settings["subnet"])
            server_address = next(network.hosts())
            lines = [
                "# Generado por WireGuard GUI. No editar manualmente.",
                "[Interface]",
                f"Address = {server_address}/{network.prefixlen}",
                f"ListenPort = {settings['listen_port']}",
                f"PrivateKey = {settings['server_private_key']}",
            ]
            if settings["mtu"]:
                lines.append(f"MTU = {settings['mtu']}")
            lines.extend([
                "PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth+ -j MASQUERADE",
                "PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth+ -j MASQUERADE",
            ])
            peers = conn.execute("SELECT * FROM peers WHERE enabled=1 ORDER BY address").fetchall()
            for peer in peers:
                lines.extend([
                    "",
                    f"# peer-id: {peer['id']} name: {peer['name']}",
                    "[Peer]",
                    f"PublicKey = {peer['public_key']}",
                    f"PresharedKey = {peer['preshared_key']}",
                    f"AllowedIPs = {peer['address']}/32",
                ])
            return "\n".join(lines) + "\n"
        finally:
            if owns_connection:
                conn.close()

    def write_config(self, content: str) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temp_name = tempfile.mkstemp(prefix=".wg0.", dir=self.config_path.parent, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temp_name, 0o600)
            os.replace(temp_name, self.config_path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def sync_runtime(self) -> None:
        stripped = self._run_root(["wg-quick", "strip", str(self.config_path)])
        runtime_path = self.db.path.parent / "runtime.conf"
        fd, temp_name = tempfile.mkstemp(prefix=".runtime-", dir=runtime_path.parent, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(stripped + "\n")
            os.chmod(temp_name, 0o600)
            os.replace(temp_name, runtime_path)
            self._run_root(["wg", "syncconf", "wg0", str(runtime_path)])
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
            runtime_path.unlink(missing_ok=True)

    def _persist_and_sync(self, mutate: Callable[[sqlite3.Connection], None]) -> None:
        with self._lock:
            previous = self.config_path.read_bytes() if self.config_path.exists() else None
            try:
                with self.db.transaction() as conn:
                    mutate(conn)
                    self.write_config(self.render(conn))
                    self.sync_runtime()
            except Exception:
                if previous is None:
                    self.config_path.unlink(missing_ok=True)
                else:
                    self.write_config(previous.decode("utf-8"))
                raise

    def create_peer(self, payload: dict) -> sqlite3.Row:
        peer_name = name(payload.get("name"))
        peer_id = str(uuid.uuid4())
        private, public = self.generate_keypair()
        psk = self.generate_psk()
        created_id: str = peer_id

        def mutate(conn: sqlite3.Connection) -> None:
            nonlocal created_id
            settings = conn.execute("SELECT * FROM settings WHERE id=1").fetchone()
            if not settings:
                raise WireGuardError("Servidor sin inicializar.")
            network = ipaddress.ip_network(settings["subnet"])
            used = {row[0] for row in conn.execute("SELECT address FROM peers")}
            hosts = network.hosts()
            next(hosts)  # la primera IP pertenece al servidor
            address = next((str(candidate) for candidate in hosts if str(candidate) not in used), None)
            if address is None:
                raise ValidationError("La subred VPN no tiene direcciones disponibles.")
            peer_dns = dns(payload.get("dns", settings["dns"]))
            allowed = ip_list(payload.get("allowed_ips", settings["client_allowed_ips"]))
            persistent = keepalive(payload.get("persistent_keepalive", 25))
            try:
                conn.execute(
                    """INSERT INTO peers
                    (id,name,address,private_key,public_key,preshared_key,client_allowed_ips,dns,persistent_keepalive)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (peer_id, peer_name, address, private, public, psk, allowed, peer_dns, persistent),
                )
            except sqlite3.IntegrityError as exc:
                raise ValidationError("Ya existe un cliente con ese nombre.") from exc

        self._persist_and_sync(mutate)
        peer = self.db.peer(created_id)
        assert peer is not None
        return peer

    def update_peer(self, peer_id: str, payload: dict) -> sqlite3.Row:
        allowed_keys = {"name", "dns", "allowed_ips", "persistent_keepalive", "enabled"}
        if not payload or set(payload) - allowed_keys:
            raise ValidationError("La solicitud contiene campos no permitidos.")

        def mutate(conn: sqlite3.Connection) -> None:
            current = conn.execute("SELECT * FROM peers WHERE id=?", (peer_id,)).fetchone()
            if not current:
                raise KeyError(peer_id)
            values = {
                "name": name(payload["name"]) if "name" in payload else current["name"],
                "dns": dns(payload["dns"]) if "dns" in payload else current["dns"],
                "client_allowed_ips": ip_list(payload["allowed_ips"]) if "allowed_ips" in payload else current["client_allowed_ips"],
                "persistent_keepalive": keepalive(payload["persistent_keepalive"]) if "persistent_keepalive" in payload else current["persistent_keepalive"],
                "enabled": int(bool(payload["enabled"])) if "enabled" in payload else current["enabled"],
            }
            try:
                conn.execute(
                    """UPDATE peers SET name=:name,dns=:dns,client_allowed_ips=:client_allowed_ips,
                    persistent_keepalive=:persistent_keepalive,enabled=:enabled,updated_at=CURRENT_TIMESTAMP
                    WHERE id=:id""",
                    values | {"id": peer_id},
                )
            except sqlite3.IntegrityError as exc:
                raise ValidationError("Ya existe un cliente con ese nombre.") from exc

        self._persist_and_sync(mutate)
        result = self.db.peer(peer_id)
        assert result is not None
        return result

    def delete_peer(self, peer_id: str) -> None:
        def mutate(conn: sqlite3.Connection) -> None:
            cursor = conn.execute("DELETE FROM peers WHERE id=?", (peer_id,))
            if cursor.rowcount != 1:
                raise KeyError(peer_id)

        self._persist_and_sync(mutate)

    def client_config(self, peer_id: str) -> str:
        peer = self.db.peer(peer_id)
        settings = self.db.setting()
        if not peer or not settings:
            raise KeyError(peer_id)
        endpoint_value = settings["endpoint"]
        try:
            if ipaddress.ip_address(endpoint_value).version == 6:
                endpoint_value = f"[{endpoint_value}]"
        except ValueError:
            pass
        network = ipaddress.ip_network(settings["subnet"])
        server_address = next(network.hosts())
        lines = [
            "[Interface]",
            f"PrivateKey = {peer['private_key']}",
            f"Address = {peer['address']}/32",
            f"DNS = {peer['dns']}",
        ]
        if settings["mtu"]:
            lines.append(f"MTU = {settings['mtu']}")
        lines.extend([
            "",
            "[Peer]",
            f"PublicKey = {settings['server_public_key']}",
            f"PresharedKey = {peer['preshared_key']}",
            f"Endpoint = {endpoint_value}:{settings['listen_port']}",
            f"AllowedIPs = {peer['client_allowed_ips']}",
            f"PersistentKeepalive = {peer['persistent_keepalive']}",
            f"# ServerAddress = {server_address}",
        ])
        return "\n".join(lines) + "\n"

    def runtime_status(self) -> dict:
        settings = self.db.setting()
        peers = self.db.peers()
        stats: dict[str, dict] = {}
        interface_up = False
        listen_port = settings["listen_port"] if settings else None
        try:
            output = self._run_root(["wg", "show", "wg0", "dump"])
            rows = output.splitlines()
            interface_up = bool(rows)
            if rows and len(rows[0].split("\t")) >= 3:
                listen_port = int(rows[0].split("\t")[2])
            for row in rows[1:]:
                columns = row.split("\t")
                if len(columns) >= 8:
                    stats[columns[0]] = {
                        "endpoint": None if columns[2] == "(none)" else columns[2],
                        "latest_handshake": int(columns[4]),
                        "rx_bytes": int(columns[5]),
                        "tx_bytes": int(columns[6]),
                    }
        except WireGuardError:
            pass

        now = int(time.time())
        result_peers = []
        for peer in peers:
            runtime = stats.get(peer["public_key"], {})
            handshake = runtime.get("latest_handshake", 0)
            result_peers.append({
                "id": peer["id"],
                "name": peer["name"],
                "address": peer["address"],
                "enabled": bool(peer["enabled"]),
                "latest_handshake": handshake or None,
                "recent_handshake": bool(handshake and now - handshake <= 180),
                "rx_bytes": runtime.get("rx_bytes", 0),
                "tx_bytes": runtime.get("tx_bytes", 0),
                "endpoint": runtime.get("endpoint"),
                "dns": peer["dns"],
                "allowed_ips": peer["client_allowed_ips"],
                "persistent_keepalive": peer["persistent_keepalive"],
            })
        return {
            "interface_up": interface_up,
            "interface": "wg0",
            "listen_port": listen_port,
            "endpoint": settings["endpoint"] if settings else None,
            "peers": result_peers,
        }
