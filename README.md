# WireGuard GUI 0.2.0

Interfaz web ligera y autocontenida para administrar un servidor WireGuard sobre la imagen de LinuxServer. La imagen final contiene WireGuard, Flask/Gunicorn y la UI; no usa el socket de Docker ni un servicio de base de datos externo.

> Estado: candidata técnica. La construcción, el arranque y la interfaz `wg0` fueron verificados en Docker Desktop/WSL2. Antes de considerarla estable todavía debe superar una conexión con un cliente WireGuard externo.

## Arquitectura

- `lscr.io/linuxserver/wireguard` proporciona WireGuard, `wg-quick`, iptables y s6-overlay.
- Un servicio s6 idempotente crea la instalación inicial antes de que `svc-wireguard` levante `wg0`.
- Flask/Gunicorn ejecuta un solo proceso con cuatro hilos. SQLite conserva configuración, clientes y credenciales en `/config/wggui/state.db`.
- `/config/wg_confs/wg0.conf` se genera de forma atómica. Cada mutación abre una transacción SQLite, reemplaza la configuración y ejecuta `wg syncconf`; si la sincronización falla, revierte la base y el archivo.
- La GUI nunca define `PEERS`. Esto evita que el generador automático de LinuxServer sobrescriba clientes gestionados por la aplicación.

Las claves privadas deben existir en el volumen para regenerar configuraciones de cliente. El archivo SQLite y `wg0.conf` se crean con modo `0600`; proteja igualmente el host, sus backups y el acceso al volumen.

## Requisitos

- Host Linux con Docker Engine y Compose v2.
- Kernel con WireGuard disponible. Si el host no lo carga automáticamente, ejecute `modprobe wireguard` en el host. La configuración no concede `SYS_MODULE` por defecto.
- Reenvío IPv4 y reglas de firewall/NAT compatibles con iptables.
- Puerto UDP elegido redirigido desde el router hacia el host.
- Proxy inverso con HTTPS para cualquier acceso que no sea estrictamente local.

`NET_ADMIN` es la única capability concedida al contenedor: permite crear `wg0`, configurar rutas y NAT. Gunicorn corre como `abc`; una regla sudo limitada permite únicamente leer `wg0`, ejecutar `wg-quick strip` sobre `wg0.conf` y sincronizar un archivo runtime fijo. No se usa `privileged`, `SYS_ADMIN`, `SYS_MODULE` ni el socket Docker.

## Instalación limpia

```bash
cp .env.example .env
# Edite .env: contraseña larga, endpoint público y red VPN.
docker compose build
docker compose up -d
docker compose ps
docker compose logs --no-log-prefix wireguard-gui
docker exec wireguard-gui wg show
```

### Entorno local preparado en Docker Desktop

El checkout local puede usar un `.env` ignorado por Git con un endpoint dinámico como `vpn.example.com`, UI en `127.0.0.1:51821` y full tunnel IPv4 (`0.0.0.0/0`) como valor predeterminado para nuevos clientes. La contraseña generada se conserva únicamente en `ADMIN_PASSWORD` dentro de ese archivo. Un CNAME DNS-only puede apuntar al hostname actualizado por el router, evitando modificar `SERVER_ENDPOINT` cuando cambie la IP pública.

```bash
docker compose up -d
docker compose ps
```

Abra `http://127.0.0.1:51821`. Para detenerlo sin perder configuración use `docker compose stop`; para eliminar el contenedor conservando `./config`, use `docker compose down`.

### Cloudflare DDNS para una IP pública dinámica

El perfil opcional `ddns` mantiene un registro `A` DNS-only actualizado mediante `favonia/cloudflare-ddns`. Cree en Cloudflare un token basado en **Edit Zone DNS**, restringido únicamente a la zona requerida, copie `secrets/cloudflare_api_token.example` como `secrets/cloudflare_api_token` y reemplace el placeholder por el token (sin espacios ni salto de línea adicional). Nunca use la Global API Key.

```powershell
New-Item -ItemType Directory -Force secrets
Set-Content -NoNewline secrets/cloudflare_api_token 'PEGUE-AQUI-EL-TOKEN-LIMITADO'
docker compose --profile ddns up -d
docker compose logs cloudflare-ddns
```

`DDNS_DOMAIN` debe contener el hostname real, por ejemplo `vpn.example.com`, y el registro debe permanecer sin proxy (nube gris), porque WireGuard usa UDP. Cuando el log confirme la actualización, configure el mismo hostname como endpoint de la GUI; el router todavía debe redirigir UDP 51820 hacia el host.

La primera ejecución exige `ADMIN_PASSWORD` de al menos 12 caracteres, genera claves nuevas, crea `wg0` y comienza con cero clientes. En reinicios posteriores no reemplaza claves ni contraseña aunque cambie `ADMIN_PASSWORD` en `.env`.

La UI se publica por defecto sólo en `http://127.0.0.1:51821`. Acceda mediante un túnel SSH o un proxy HTTPS. Al usar HTTPS, configure `SESSION_COOKIE_SECURE=true`. Si hay exactamente un proxy confiable, configure `TRUSTED_PROXY_COUNT=1`; no lo active directamente frente a clientes no confiables.

### Proxy inverso

El proxy debe:

- terminar TLS;
- reenviar a `127.0.0.1:51821`;
- conservar `Host`;
- enviar `X-Forwarded-For` y `X-Forwarded-Proto`;
- no almacenar en caché `/api/`;
- restringir por red/VPN o una segunda capa de acceso cuando sea posible.

## Operación

La UI permite crear, habilitar, deshabilitar y eliminar clientes; descargar `.conf`; mostrar QR; observar handshakes y tráfico; y cambiar parámetros del servidor. “Actividad reciente” significa handshake en los últimos 180 segundos, no una sesión permanentemente conectada.

Endpoint, DNS y AllowedIPs sólo afectan configuraciones generadas y pueden cambiarse sin bajar `wg0`. MTU y subred requieren recrear la interfaz. Cambiar el puerto también exige actualizar `SERVER_PORT` en `.env` para que la publicación Docker coincida y luego ejecutar:

```bash
docker compose up -d --force-recreate
```

No cambie la subred mientras existan clientes; la API lo impide para evitar reasignaciones silenciosas.

### Actualización

1. Realice un backup.
2. Revise las notas de LinuxServer y de WireGuard GUI.
3. Construya la nueva imagen y ejecute las pruebas.
4. Recree el contenedor conservando `./config`.

```bash
docker compose build --pull
docker compose up -d
docker compose ps
docker exec wireguard-gui wg show
```

Evite actualizadores automáticos sin supervisión: la etiqueta base `latest` hace reproducible el código propio, pero no congela el sistema base. Para despliegues regulados, reemplace `BASE_IMAGE` por una etiqueta o digest de LinuxServer que haya validado.

### Backup y restauración

Para obtener una instantánea consistente:

```bash
docker compose stop wireguard-gui
tar -czf wireguard-gui-backup.tgz config
docker compose start wireguard-gui
```

Guarde el archivo cifrado y fuera del host: contiene claves privadas y el hash de administración. Para restaurar, detenga el contenedor, mueva la carpeta `config` actual a una ubicación segura, extraiga el backup en el directorio del proyecto y vuelva a iniciar. Verifique permisos, `docker compose logs` y `wg show`.

## Desarrollo y pruebas

```bash
py -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m pytest --cov=wggui
```

En Linux, use `python3` y `.venv/bin/python`. Las pruebas sustituyen únicamente la llamada al kernel WireGuard; nunca deben presentarse como una conexión VPN real.

### Validación de integración pendiente

En un host Linux dedicado:

1. construir sin caché y arrancar con un volumen vacío;
2. confirmar cero clientes, permisos `0600`, healthcheck y `wg0` activo;
3. crear un cliente y comprobar que aparece en `wg show` sin reiniciar;
4. importar su configuración en un equipo externo y verificar handshake, DNS, Internet/LAN y tráfico bidireccional;
5. reiniciar contenedor y host, confirmando persistencia;
6. deshabilitar y eliminar el cliente, comprobando la revocación real;
7. forzar un error de `wg syncconf` y comprobar rollback;
8. probar backup/restauración y actualización de imagen;
9. validar nftables/iptables en las distribuciones objetivo y arquitecturas `amd64`/`arm64`.

## Solución de problemas

- **`wg0` no sube:** revise `docker compose logs`, `modprobe wireguard`, `NET_ADMIN` y las reglas del host.
- **La UI funciona pero no hay handshake:** confirme endpoint, redirección UDP, firewall, reloj de ambos equipos y que no exista solapamiento de subredes.
- **Hay handshake pero no tráfico:** revise `net.ipv4.ip_forward`, NAT y políticas FORWARD del host.
- **El healthcheck falla:** ejecute `curl http://127.0.0.1:51821/health` dentro del contenedor y revise permisos de `/config/wggui`.
- **El puerto cambió:** actualice el mismo valor en `.env` y recree el contenedor; la UI no puede modificar el mapeo de puertos Docker.

Consulte [docs/INFORME_TECNICO.md](docs/INFORME_TECNICO.md) para los hallazgos, decisiones y riesgos abiertos.
