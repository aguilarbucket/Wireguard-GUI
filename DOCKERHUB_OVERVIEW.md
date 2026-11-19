# WireGuard GUI

Interfaz web ligera para administrar un servidor WireGuard sobre la imagen de [LinuxServer.io](https://github.com/linuxserver/docker-wireguard), con una experiencia inspirada en [wg-easy](https://github.com/wg-easy/wg-easy).

> **`latest` contiene la versión auditada para Linux amd64.** `beta` conserva la compilación anterior. `alpha` es una referencia histórica.

### Estado de seguridad verificado el 2026-11-18

- Scout registró **0 críticas, 7 altas, 3 medias y 1 baja** en 108 paquetes de `latest`. La retirada de `net-tools` mitigó CVE-2025-46836.
- El índice publicado es `sha256:ea4a54ef5e61007c51ff44b034ceeed0afdcc9a7c5109c9f0afe78922f8ffc59` e incluye SBOM y procedencia.
- La imagen publicada superó las pruebas de GUI, API, túnel WireGuard y persistencia tras reinicio en Docker Desktop con Linux amd64.
- `alpha` contiene **11 críticas, 51 altas, 45 medias y 11 bajas** según su inventario histórico.

Alpine confirma dos backports ya instalados, en `musl` y `sudo`. Una alerta corresponde a la CLI SQLite, ausente de la imagen. Los ocho hallazgos de Coreutils y OpenSSL siguen pendientes de revisiones en Alpine v3.24 estable. [Informe de auditoría y evidencias](https://github.com/aguilarbucket/Wireguard-GUI/blob/main/docs/scout-audit/INFORME.md).

## Inicio rápido

1. Cree una carpeta vacía.
2. Guarde en ella los archivos `compose.yaml` y `.env` mostrados abajo.
3. Cambie todos los valores indicados en `.env`.
4. Configure el reenvío UDP del router antes de probar desde Internet.
5. Inicie el servicio con Docker Compose.

### `compose.yaml`

```yaml
name: wireguard-gui

services:
  wireguard-gui:
    image: alejandroromeroa/wireguard-gui:${IMAGE_TAG:-latest}
    container_name: wireguard-gui
    restart: unless-stopped
    cap_add:
      - NET_ADMIN
    environment:
      PUID: ${PUID:-1000}
      PGID: ${PGID:-1000}
      TZ: ${TZ:-Etc/UTC}
      ADMIN_PASSWORD: ${ADMIN_PASSWORD:?Defina ADMIN_PASSWORD en .env}
      SERVER_ENDPOINT: ${SERVER_ENDPOINT:?Defina SERVER_ENDPOINT en .env}
      SERVER_PORT: ${SERVER_PORT:-51820}
      VPN_SUBNET: ${VPN_SUBNET:-10.13.13.0/24}
      PEER_DNS: ${PEER_DNS:-1.1.1.1}
      CLIENT_ALLOWED_IPS: ${CLIENT_ALLOWED_IPS:-0.0.0.0/0}
      WG_MTU: ${WG_MTU:-}
      SESSION_COOKIE_SECURE: ${SESSION_COOKIE_SECURE:-false}
      TRUSTED_PROXY_COUNT: ${TRUSTED_PROXY_COUNT:-0}
    volumes:
      - ./config:/config
    ports:
      - "${SERVER_PORT:-51820}:${SERVER_PORT:-51820}/udp"
      - "127.0.0.1:${WEB_PORT:-51821}:51821/tcp"
    sysctls:
      net.ipv4.conf.all.src_valid_mark: "1"
      net.ipv4.ip_forward: "1"
    healthcheck:
      test: ["CMD", "curl", "--fail", "--silent", "http://127.0.0.1:51821/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 20s
```

### `.env`

```dotenv
# Canal recomendado. beta conserva la versión anterior.
IMAGE_TAG=latest

# Obligatorio: use una frase única de al menos 12 caracteres; se recomiendan 16 o más.
ADMIN_PASSWORD=CAMBIAR-por-una-frase-larga-y-unica

# Obligatorio: IP pública o DNS público, sin http://, https://, puerto ni ruta.
SERVER_ENDPOINT=vpn.example.com

# Puerto UDP publicado por Docker y reenviado por el router.
SERVER_PORT=51820

# Red exclusiva para la VPN. No debe coincidir con la LAN, otra VPN o una red Docker.
VPN_SUBNET=10.13.13.0/24

# DNS entregado a los clientes.
PEER_DNS=1.1.1.1

# Full tunnel IPv4: todo el tráfico IPv4 del cliente pasa por la VPN.
CLIENT_ALLOWED_IPS=0.0.0.0/0

# Déjelo vacío para detección automática. Cambie sólo al diagnosticar problemas de MTU.
WG_MTU=

# Puerto local de la interfaz web. Compose lo publica únicamente en 127.0.0.1.
WEB_PORT=51821

# Usuario/grupo propietarios de ./config y zona horaria del contenedor.
PUID=1000
PGID=1000
TZ=America/Santiago

# false para acceso local por HTTP. Use true sólo detrás de un proxy HTTPS.
SESSION_COOKIE_SECURE=false

# 0 sin proxy. Use 1 únicamente si existe exactamente un proxy inverso confiable.
TRUSTED_PROXY_COUNT=0
```

## Cómo llenar `.env`

| Variable | Qué debe colocar | Errores frecuentes |
| --- | --- | --- |
| `IMAGE_TAG` | `latest` normalmente; `beta` para volver a la versión anterior. | Usar `alpha`, que se conserva sólo como referencia histórica. |
| `ADMIN_PASSWORD` | Contraseña única de 12+ caracteres. | Dejar el placeholder. Cambiarla en `.env` después del primer arranque no reemplaza la almacenada en `./config`. |
| `SERVER_ENDPOINT` | IP pública o DNS como `vpn.example.com`. | Agregar `https://`, una ruta o `:51820`. El puerto se configura aparte. |
| `SERVER_PORT` | Puerto UDP externo e interno, normalmente `51820`. | Abrir sólo TCP o usar un puerto diferente en el router y el cliente. |
| `VPN_SUBNET` | Subred privada no utilizada, por ejemplo `10.13.13.0/24`. | Reutilizar la LAN `192.168.1.0/24` o una red presente en el cliente. |
| `PEER_DNS` | DNS público o DNS interno accesible por la VPN. | Usar un DNS que sólo responde desde otra red. |
| `CLIENT_ALLOWED_IPS` | `0.0.0.0/0` para full tunnel IPv4. | Agregar `::/0` sin haber preparado IPv6 en el servidor. |
| `WG_MTU` | Vacío normalmente; `1420`, `1380` o `1280` sólo para pruebas. | Cambiarlo sin regenerar/reimportar la configuración del peer. |
| `PUID` / `PGID` | UID/GID con acceso a `./config`; normalmente `1000`. | Usar IDs que no pueden escribir en el volumen. |
| `SESSION_COOKIE_SECURE` | `false` en `127.0.0.1`; `true` con HTTPS. | Activarlo mientras se accede por HTTP y perder la sesión. |
| `TRUSTED_PROXY_COUNT` | `0` directo; normalmente `1` detrás de un proxy. | Confiar en proxies inexistentes o en clientes directos. |

## Primera ejecución

Desde la carpeta que contiene ambos archivos:

```bash
docker compose config --quiet
docker compose pull
docker compose up -d
docker compose ps
docker compose logs --tail=100 wireguard-gui
```

Espere a que el contenedor figure como `healthy` y abra:

```text
http://127.0.0.1:51821
```

Inicie sesión con `ADMIN_PASSWORD`. En el primer arranque se generan automáticamente las claves del servidor, la base de datos y `wg0.conf` dentro de `./config`. Esa carpeta es persistente y contiene secretos: no la publique ni la envíe a Git.

Verificación desde el host:

```bash
docker exec wireguard-gui wg show
docker exec wireguard-gui curl --fail http://127.0.0.1:51821/health
```

## Configuración de Internet y router

Para conectarse desde un móvil o equipo externo:

1. Reserve una IP LAN para el host Docker.
2. Reenvíe `51820/UDP` —o el valor de `SERVER_PORT`— desde el router hacia ese host y el mismo puerto.
3. Permita ese puerto UDP en el firewall del host.
4. Haga que `SERVER_ENDPOINT` resuelva a la IP pública actual. Para IP dinámica use DDNS.
5. Si la IP pública es dinámica, configure DDNS en el router o mediante una herramienta externa.
6. Pruebe desde datos móviles u otra red externa.

Si el proveedor usa CGNAT, el reenvío de puertos doméstico no será suficiente. Solicite una IP pública o utilice una arquitectura que proporcione entrada UDP.

## Crear el primer peer

1. Entre a la GUI y seleccione **Crear cliente**.
2. Use un nombre distinto para cada dispositivo.
3. Mantenga DNS y AllowedIPs predeterminados para full tunnel.
4. Conserve `PersistentKeepalive = 25` para móviles o clientes detrás de NAT.
5. Escanee el QR desde la aplicación oficial de WireGuard o descargue el `.conf`.
6. Active el túnel desde una red externa y confirme handshake y tráfico RX/TX.

No reutilice un peer en varios dispositivos. Deshabilite o elimine inmediatamente el peer de un equipo perdido.

## Solución rápida de problemas

- **La GUI abre, pero no hay handshake:** revise DNS/IP pública, UDP, NAT del router, firewall, CGNAT y reloj de ambos equipos.
- **El móvil envía bytes y no recibe:** el paquete no llega al servidor o la respuesta no vuelve; revise primero endpoint, port-forwarding y firewall.
- **Hay handshake, pero no navega:** confirme `CLIENT_ALLOWED_IPS=0.0.0.0/0`, DNS, reenvío IPv4 y reglas NAT/FORWARD.
- **Navega por IP, pero no por nombre:** pruebe temporalmente `PEER_DNS=1.1.1.1` o `9.9.9.9` y vuelva a importar el peer.
- **Algunas páginas no cargan:** pruebe de forma controlada un MTU menor y regenere la configuración del cliente.
- **El contenedor no inicia:** ejecute `docker compose config --quiet` y revise `docker compose logs wireguard-gui`.

## Actualizar y respaldar

Fije una etiqueta validada en producción. Antes de actualizar, respalde `./config` de forma cifrada:

```bash
docker compose stop wireguard-gui
# Copie o archive ./config en una ubicación segura.
docker compose start wireguard-gui
```

Para actualizar el canal configurado:

```bash
docker compose pull
docker compose up -d --no-build
```

## Seguridad y código fuente

- La administración se publica sólo en `127.0.0.1` por defecto.
- El contenedor utiliza `NET_ADMIN`, pero no requiere `privileged`, `SYS_ADMIN` ni el socket Docker.
- `.env`, `./config`, claves y perfiles de clientes no forman parte de la imagen.
- [Auditoría, mitigaciones y evidencia](https://github.com/aguilarbucket/Wireguard-GUI/blob/main/docs/scout-audit/INFORME.md).
- Código, documentación completa y reporte técnico: [github.com/aguilarbucket/Wireguard-GUI](https://github.com/aguilarbucket/Wireguard-GUI).
- Base técnica: [LinuxServer/docker-wireguard](https://github.com/linuxserver/docker-wireguard).
- Referencia funcional y de experiencia: [wg-easy](https://github.com/wg-easy/wg-easy).

Licencia: GPL-3.0-only.
