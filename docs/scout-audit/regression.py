"""Playwright, HTTP and WireGuard regression checks against local test images."""

import argparse
import os
import secrets
import subprocess
from contextlib import ExitStack
from time import monotonic, sleep

from playwright.sync_api import Error, expect, sync_playwright


def docker(*args, stdin=None, env=None, check=True):
    result = subprocess.run(
        ["docker", *args], input=stdin, env=env, text=True,
        encoding="utf-8", errors="replace", capture_output=True, timeout=90,
    )
    if result.returncode and check:
        raise RuntimeError(f"docker {args[0]} failed ({result.returncode}): {result.stderr.strip()}")
    return result.stdout.strip()


def peer_state(page, peer_id, enabled):
    status = page.request.get("/api/status")
    assert status.ok
    state = status.json()
    assert state["interface_up"] and state["listen_port"] == 51820
    peers = [peer for peer in state["peers"] if peer["id"] == peer_id]
    assert len(peers) == 1 and peers[0]["enabled"] is enabled
    return peers[0]


def exercise(page, browser, cleanup, server, client, password):
    assert page.request.get("/health").json() == {"status": "ok"}
    assert page.request.get("/api/status").status == 401
    page.goto("/")
    expect(page).to_have_url("/auth/login")
    page.locator("#password").fill(password)
    page.get_by_role("button", name="Ingresar").click()
    expect(page.locator("#metric-interface")).to_have_text("wg0:51820")
    expect(page.locator("#metric-total")).to_have_text("0")
    expect(page.get_by_text("Aún no hay clientes.")).to_be_visible()
    assert page.request.get("/static/app.css").ok and page.request.get("/static/app.js").ok
    assert page.request.get("/api/settings").ok
    assert page.request.post("/api/peers", data={"name": "audit-peer"}).status == 403
    print("PASS health, login, GUI assets and JavaScript, authenticated API, CSRF", flush=True)

    page.get_by_role("button", name="+ Nuevo cliente", exact=True).click()
    page.locator("#peer-name").fill("audit-peer")
    with page.expect_response(lambda res: res.url.endswith("/api/peers") and res.request.method == "POST") as create:
        page.get_by_role("button", name="Crear cliente", exact=True).click()
    assert create.value.status == 201
    peer_id = create.value.json()["id"]
    expect(page.locator("#peers-body")).to_contain_text("audit-peer")
    csrf = page.locator('meta[name="csrf-token"]').get_attribute("content")
    headers = {"X-CSRF-Token": csrf}
    api_peer = f"/api/peers/{peer_id}"
    peer_state(page, peer_id, True)

    config = page.request.get(f"{api_peer}/config")
    qr = page.request.get(f"{api_peer}/qr")
    assert config.ok and config.headers["cache-control"] == "no-store"
    assert qr.ok and qr.headers["content-type"].startswith("image/svg+xml")
    assert qr.headers["cache-control"] == "no-store" and qr.body().startswith(b"<svg")
    client_config = "\n".join(line for line in config.text().splitlines() if not line.startswith("DNS ="))
    docker("exec", "-i", client, "sh", "-ec",
           "umask 077; cat >/tmp/wgprobe.conf; wg-quick up /tmp/wgprobe.conf",
           stdin=client_config + "\n")
    ping = docker("exec", client, "ping", "-c", "3", "-W", "3", "10.231.91.1")
    assert "3 packets transmitted, 3 received" in ping or "3 packets transmitted, 3 packets received" in ping
    peer = peer_state(page, peer_id, True)
    assert peer["recent_handshake"] and peer["rx_bytes"] > 0 and peer["tx_bytes"] > 0
    print("PASS create from GUI, config and QR, WireGuard handshake, ICMP 3/3 and traffic counters", flush=True)

    assert page.request.patch(api_peer, data={"enabled": False}, headers=headers).ok
    peer_state(page, peer_id, False)
    assert not docker("exec", server, "wg", "show", "wg0", "peers")
    assert page.request.patch(api_peer, data={"enabled": True}, headers=headers).ok
    peer_state(page, peer_id, True)
    assert len(docker("exec", server, "wg", "show", "wg0", "peers").splitlines()) == 1
    public_key = docker("exec", server, "wg", "show", "wg0", "public-key")
    docker("restart", "--time", "10", server)
    # Docker Desktop can assign a new host port after restarting a container.
    page = open_page(browser, cleanup, server, storage_state=page.context.storage_state())
    wait_for_health(page)
    peer_state(page, peer_id, True)
    assert docker("exec", server, "wg", "show", "wg0", "public-key") == public_key
    docker("exec", client, "sh", "-ec",
           "wg-quick down /tmp/wgprobe.conf; wg-quick up /tmp/wgprobe.conf")
    docker("exec", client, "ping", "-c", "2", "-W", "3", "10.231.91.1")
    assert peer_state(page, peer_id, True)["recent_handshake"]
    assert page.request.delete(api_peer, headers=headers).status == 204
    assert page.request.get("/api/status").json()["peers"] == []
    assert not docker("exec", server, "wg", "show", "wg0", "peers")
    print("PASS enable and disable in kernel, restart with preserved state and key, client reconnection and peer deletion", flush=True)


def open_page(browser, cleanup, server, storage_state=None):
    address = docker("port", server, "51821/tcp")
    assert address.startswith("127.0.0.1:")
    context = browser.new_context(base_url=f"http://{address}", storage_state=storage_state)
    cleanup.callback(context.close)
    return context.new_page()


def run_image(browser, image):
    name = f"wggui-scout-{secrets.token_hex(5)}"
    server, client = f"{name}-server", f"{name}-peer"
    password = secrets.token_urlsafe(24)
    print(f"IMAGE {image}", flush=True)
    with ExitStack() as cleanup:
        docker("network", "create", name)
        cleanup.callback(docker, "network", "rm", name)
        docker("volume", "create", name)
        cleanup.callback(docker, "volume", "rm", name)
        containers = ("run", "--pull", "never", "-d", "--platform", "linux/amd64",
                      "--network", name, "--cap-add", "NET_ADMIN")
        cleanup.callback(docker, "rm", "-fv", server, check=False)
        docker(*containers, "--name", server, "-p", "127.0.0.1::51821",
               "--sysctl", "net.ipv4.conf.all.src_valid_mark=1",
               "--sysctl", "net.ipv4.ip_forward=1",
               "--mount", f"type=volume,src={name},dst=/config",
               "--env", "ADMIN_PASSWORD", "--env", f"SERVER_ENDPOINT={server}",
               "--env", "VPN_SUBNET=10.231.91.0/24", "--env", "CLIENT_ALLOWED_IPS=10.231.91.0/24",
               "--env", "LOG_CONFS=false", image, env={**os.environ, "ADMIN_PASSWORD": password})
        cleanup.callback(docker, "rm", "-fv", client, check=False)
        docker(*containers, "--name", client, "--entrypoint", "/bin/sleep", image, "infinity")
        page = open_page(browser, cleanup, server)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        wait_for_health(page)
        exercise(page, browser, cleanup, server, client, password)
        assert not errors, errors
        print("PASS browser JavaScript without page errors", flush=True)
    print("PASS isolated Docker resources removed", flush=True)


def wait_for_health(page):
    deadline = monotonic() + 45
    while monotonic() < deadline:
        try:
            if page.request.get("/health", timeout=2000).ok:
                return
        except Error:
            pass
        sleep(1)
    raise RuntimeError("Health endpoint did not become ready")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser-channel", default="msedge")
    parser.add_argument("images", nargs="+")
    options = parser.parse_args()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=options.browser_channel)
        print(f"BROWSER {options.browser_channel} {browser.version}", flush=True)
        for image in options.images:
            run_image(browser, image)
