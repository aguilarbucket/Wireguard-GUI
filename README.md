# WireGuard GUI 0.2.0

Interfaz web ligera y autocontenida para administrar un servidor WireGuard sobre la imagen de LinuxServer. La imagen final contiene WireGuard, Flask/Gunicorn y la UI; no usa el socket de Docker ni un servicio de base de datos externo.

> Estado: candidata técnica. La construcción, el arranque, la interfaz `wg0` y una conexión externa desde un cliente iOS sobre red móvil fueron verificados en Docker Desktop/WSL2. Valide igualmente el comportamiento en su propio router, proveedor de Internet y sistema operativo antes de usarlo en producción.

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

## Ejecución con Docker Compose
Mi forma favorita es: 

1) Crear una carpeta
2) Copiar el compose.yaml de ejemplo del GIT.
3) Copiar el .env y modificar los valores según corresponda a su caso. 
4) Abrir CMD dentro de la carpeta con los archivos.
5) ejecutar: docker compose -f compose.yaml up -d
6) Resultado: 
[+] up 2/2
 ✔ Network wireguard-gui_default Created                                                                            0.0s
 ✔ Container wireguard-gui       Started

 Ir a la interfaz grafica,http://127.0.0.1:51821
Iniciar sesion con la contraseña establecida en el .env según su criterio.

Generar un cliente nuevo via QR, lo escanea con su cliente wireguard desde su movil IOS o Android. 
o si es PC (Windows requiere cliente Wireguard)(Linux, al menos Distro Ubuntu viene incluido el perfil VPN para importar el archivo .conf) - Baja el archivo #nombrecliente.conf

Y estas listo para conectarte a tu VPN, bien sea que estes en una cafeteria, o un aeropuerto, o algun lugar donde tus datos sensibles no se sientan muy seguro que digamos. 

### 1. Obtener el proyecto

```bash
git clone https://github.com/aguilarbucket/Wireguard-GUI.git
cd Wireguard-GUI
```

Se requiere Docker Engine con Compose v2 en Linux, o Docker Desktop con backend WSL2 en Windows. Compruebe la instalación con `docker version` y `docker compose version`.

### 2. Crear la configuración local

Linux/macOS:

```bash
cp .env.example .env
```

PowerShell:

```powershell
Copy-Item .env.example .env
```

Edite `.env` antes del primer arranque. El archivo real está excluido de Git porque contiene información propia del despliegue.

| Variable | Valor recomendado | Descripción |
| --- | --- | --- |
| `IMAGE_TAG` | `alpha` | Canal público de pruebas. Fije una versión numerada cuando exista una versión estable. |
| `ADMIN_PASSWORD` | frase única de 16+ caracteres | Contraseña inicial de la GUI. Sólo se utiliza para inicializar un volumen nuevo. |
| `SERVER_ENDPOINT` | `vpn.example.com` | IP pública o nombre DNS público del servidor, sin `http://`, `https://`, ruta ni puerto. |
| `SERVER_PORT` | `51820` | Puerto UDP publicado por Docker, abierto en el firewall y reenviado por el router. |
| `VPN_SUBNET` | `10.13.13.0/24` | Red privada exclusiva de la VPN. No debe coincidir con la LAN, otras VPN ni redes Docker. |
| `PEER_DNS` | `1.1.1.1` o DNS propio | DNS entregado por defecto a los clientes. |
| `CLIENT_ALLOWED_IPS` | `0.0.0.0/0` | Rutas del cliente. El valor predeterminado habilita full tunnel IPv4. |
| `WG_MTU` | vacío | Permite detección automática. Pruebe `1280`–`1420` sólo ante fragmentación o cortes. |
| `WEB_PORT` | `51821` | Puerto local de administración, publicado únicamente en `127.0.0.1`. |
| `PUID` / `PGID` | `1000` | Usuario y grupo propietarios del volumen `./config` en el host. |
| `TZ` | `America/Santiago` | Zona horaria del contenedor. |
| `SESSION_COOKIE_SECURE` | `false` local; `true` con HTTPS | Evita enviar la cookie por HTTP cuando la GUI está detrás de TLS. |
| `TRUSTED_PROXY_COUNT` | `0` local; normalmente `1` con proxy | Número exacto de proxies inversos confiables. |

Ejemplo mínimo para full tunnel:

```dotenv
IMAGE_TAG=alpha
ADMIN_PASSWORD=reemplace-por-una-frase-larga-y-unica
SERVER_ENDPOINT=vpn.example.com
SERVER_PORT=51820
VPN_SUBNET=10.13.13.0/24
PEER_DNS=1.1.1.1
CLIENT_ALLOWED_IPS=0.0.0.0/0
WG_MTU=
WEB_PORT=51821
TZ=America/Santiago
PUID=1000
PGID=1000
SESSION_COOKIE_SECURE=false
TRUSTED_PROXY_COUNT=0
```

No agregue `::/0` hasta haber configurado y validado IPv6 de extremo a extremo; el despliegue predeterminado está preparado para IPv4.

### 3. Preparar IP pública, DNS y router

Para aceptar clientes desde Internet deben cumplirse todas estas condiciones:

1. El router debe tener una IP pública accesible. Si el ISP usa CGNAT, solicite una IP pública, use un VPS como punto de entrada o una solución que transporte UDP; el reenvío de puertos doméstico no funcionará por sí solo.
2. Reserve una IP fija o una concesión DHCP para el equipo que ejecuta Docker.
3. Cree en el router una regla **UDP** desde `SERVER_PORT` hacia la IP LAN del host y el mismo puerto. No abra TCP para WireGuard.
4. Permita únicamente ese puerto UDP en el firewall del host. La interfaz web `51821/tcp` debe permanecer local o detrás de HTTPS y autenticación adicional.
5. Configure `SERVER_ENDPOINT` con la IP pública o, preferiblemente, un nombre DNS estable. Si la IP cambia, use DDNS.
6. Pruebe desde una red externa, por ejemplo datos móviles; una prueba TCP o desde la misma LAN puede producir un resultado engañoso.

Este Compose no incluye un actualizador DDNS. Si la IP pública cambia, configure el servicio DDNS en el router o mediante una herramienta externa. WireGuard necesita que el nombre público resuelva a la IP vigente, además del reenvío UDP y ausencia de CGNAT.

### 4. Iniciar con la imagen de Docker Hub

La opción recomendada para una instalación normal descarga la imagen publicada y evita construirla localmente:

```bash
docker compose pull wireguard-gui
docker compose up -d --no-build
docker compose ps
docker compose logs --no-log-prefix wireguard-gui
docker exec wireguard-gui wg show
```

Imagen: [`alejandroromeroa/wireguard-gui`](https://hub.docker.com/r/alejandroromeroa/wireguard-gui). Mientras continúe la validación, `IMAGE_TAG=alpha` selecciona el canal de pruebas.

### 5. Construir localmente

Para auditar o modificar el código, construya la imagen desde este repositorio:

```bash
docker build -t alejandroromeroa/wireguard-gui:local .
# Cambie temporalmente IMAGE_TAG=local en .env.
docker compose up -d --no-build
docker compose ps
docker compose logs --no-log-prefix wireguard-gui
docker exec wireguard-gui wg show
```

Cuando el servicio figure como `healthy`, abra `http://127.0.0.1:51821` e ingrese con `ADMIN_PASSWORD`. El primer arranque genera las claves del servidor, la base SQLite y `wg0.conf` dentro de `./config`.

Comandos habituales:

```bash
# Ver logs en tiempo real
docker compose logs -f wireguard-gui

# Reiniciar sin perder datos
docker compose restart wireguard-gui

# Detener o eliminar el contenedor conservando ./config
docker compose stop
docker compose down

# Actualizar el canal configurado en IMAGE_TAG
docker compose pull
docker compose up -d --no-build
```

### Docker Desktop en Windows

El checkout local puede usar un `.env` ignorado por Git con un endpoint dinámico como `vpn.example.com`, UI en `127.0.0.1:51821` y full tunnel IPv4 (`0.0.0.0/0`) como valor predeterminado para nuevos clientes. Un CNAME DNS-only puede apuntar al hostname actualizado por el router, evitando modificar `SERVER_ENDPOINT` cuando cambie la IP pública.

```bash
docker compose up -d
docker compose ps
```

Docker Desktop debe usar contenedores Linux y WSL2. Si no llegan paquetes UDP, verifique primero el reenvío del router, la IP LAN actual del equipo, el firewall de Windows y que Docker publique `0.0.0.0:51820/udp` con `docker compose ps`. Evite mantener reglas amplias o temporales de firewall después de la prueba.

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

### Crear y configurar peers

En WireGuard cada teléfono, notebook o servidor debe tener su propio peer; no reutilice la misma configuración en varios dispositivos.

1. Abra la GUI y seleccione **Crear cliente**.
2. Asigne un nombre descriptivo, por ejemplo `iphone-alejandro` o `notebook-trabajo`.
3. Deje DNS y AllowedIPs vacíos para heredar los valores predeterminados, o defínalos específicamente para ese dispositivo.
4. Mantenga `PersistentKeepalive = 25` para móviles y clientes detrás de NAT. Use `0` sólo cuando comprenda el efecto y el cliente pueda recibir tráfico sin mantener el mapeo NAT.
5. Cree el peer y escanee el QR desde la aplicación oficial de WireGuard, o descargue el `.conf` e impórtelo.
6. Active el túnel desde una red externa y compruebe en la GUI que aparezcan handshake reciente y tráfico RX/TX.

Rutas habituales:

- **Full tunnel IPv4:** `0.0.0.0/0`. Todo el tráfico IPv4 del cliente sale por la VPN.
- **Sólo VPN:** `10.13.13.0/24`. El cliente alcanza únicamente la subred WireGuard.
- **Split tunnel hacia VPN y LAN:** `10.13.13.0/24, 192.168.1.0/24`. Sustituya la LAN y verifique que no se solape con la red desde la que se conecta el cliente.

El servidor asigna automáticamente una dirección `/32` libre dentro de `VPN_SUBNET`. Deshabilitar un peer lo retira de la configuración activa conservando sus datos; eliminarlo revoca y borra definitivamente su configuración. Las claves y códigos QR son credenciales: no los envíe por canales inseguros ni los conserve en repositorios.

Endpoint, DNS y AllowedIPs sólo afectan configuraciones generadas y pueden cambiarse sin bajar `wg0`. MTU y subred requieren recrear la interfaz. Cambiar el puerto también exige actualizar `SERVER_PORT` en `.env` para que la publicación Docker coincida y luego ejecutar:

```bash
docker compose up -d --force-recreate
```

No cambie la subred mientras existan clientes; la API lo impide para evitar reasignaciones silenciosas.

### Recomendaciones básicas de producción

- Mantenga la GUI ligada a `127.0.0.1`; publíquela sólo mediante un proxy HTTPS protegido o acceda a ella a través de la propia VPN.
- Use una contraseña administrativa única, actualizaciones planificadas y copias de seguridad cifradas de `./config`.
- Reserve la IP LAN del host y documente el puerto UDP, el registro DNS y la regla NAT.
- Cree un peer por dispositivo, revoque equipos perdidos y revise periódicamente los handshakes.
- No publique `.env`, `./config`, archivos `.conf`, códigos QR ni claves.
- Fije una etiqueta o digest de imagen validado antes de un despliegue crítico; pruebe las actualizaciones antes de aplicarlas.
- Exponga sólo `NET_ADMIN`; no añada `privileged`, el socket Docker ni capabilities adicionales sin una necesidad comprobada.

### Actualización

1. Realice un backup.
2. Revise las notas de LinuxServer y de WireGuard GUI.
3. Descargue la nueva imagen y revise las notas de la versión.
4. Recree el contenedor conservando `./config`.

```bash
docker compose pull
docker compose up -d --no-build
docker compose ps
docker exec wireguard-gui wg show
```

Evite actualizaciones automáticas sin supervisión. Durante las pruebas, `alpha` es una etiqueta móvil; para despliegues estables use una etiqueta numerada o un digest que haya validado.

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

- **El contenedor no inicia:** ejecute `docker compose config` para detectar variables faltantes y luego `docker compose logs wireguard-gui`. En un volumen nuevo, `ADMIN_PASSWORD` debe tener al menos 12 caracteres.
- **`wg0` no sube:** revise `docker compose logs`, la disponibilidad de WireGuard en el host, `NET_ADMIN` y los permisos de `./config`. En Linux confirme el módulo con `sudo modprobe wireguard`.
- **La UI funciona pero no hay handshake:** confirme que el cliente usa el DNS/IP y puerto correctos, que el registro DNS resuelve a la IP pública actual, que el router reenvía UDP, que no existe CGNAT y que el reloj de ambos equipos es correcto.
- **Funcionó y dejó de funcionar:** compruebe si cambió la IP pública, la IP LAN del host o la concesión DHCP. Revise el DDNS configurado externamente y recree el cliente si su configuración conserva un endpoint anterior.
- **Hay handshake pero no navega:** verifique `CLIENT_ALLOWED_IPS=0.0.0.0/0`, DNS del peer, `net.ipv4.ip_forward`, las reglas FORWARD/NAT y posibles solapamientos entre `VPN_SUBNET`, LAN y red del cliente.
- **Navega por IP pero no por nombre:** cambie temporalmente `PEER_DNS` por un resolvedor accesible como `1.1.1.1` o `9.9.9.9`, genere/actualice el peer y vuelva a importar la configuración.
- **Algunas páginas cargan y otras no:** sospeche de MTU. Pruebe de forma controlada `WG_MTU=1420`, `1380` o `1280`, recree el contenedor y regenere la configuración del cliente.
- **El healthcheck falla:** pruebe `docker exec wireguard-gui curl --fail http://127.0.0.1:51821/health` y revise permisos de `/config/wggui`.
- **El puerto cambió:** actualice el mismo `SERVER_PORT` en `.env`, router y firewall, y ejecute `docker compose up -d --force-recreate`. La GUI no puede modificar el mapeo de puertos de Docker.
- **El cliente móvil muestra bytes enviados pero cero recibidos:** normalmente el servidor no recibió el paquete o la respuesta no volvió. Revise endpoint, UDP/NAT, CGNAT y firewall antes de modificar AllowedIPs.

Diagnóstico mínimo del servidor:

```bash
docker compose ps
docker compose logs --tail=200 wireguard-gui
docker exec wireguard-gui wg show
docker exec wireguard-gui ip address show wg0
docker exec wireguard-gui ip route
```

Consulte [docs/INFORME_TECNICO.md](docs/INFORME_TECNICO.md) para los hallazgos, decisiones y riesgos abiertos.

## Origen, base y agradecimientos

Este proyecto existe gracias al trabajo previo de tres comunidades:

- [WireGuard](https://www.wireguard.com/) proporciona el protocolo, las herramientas `wg`/`wg-quick` y la base técnica de la VPN.
- [LinuxServer.io — docker-wireguard](https://github.com/linuxserver/docker-wireguard) es la imagen Linux original utilizada como base del contenedor. Aporta WireGuard, s6-overlay y las convenciones de operación sobre las que se integra esta GUI.
- [wg-easy](https://github.com/wg-easy/wg-easy) ha sido la referencia funcional y de experiencia de usuario para simplificar la administración, creación de clientes, códigos QR y visualización de estado.

WireGuard GUI desarrolla su propia capa Flask, persistencia y flujo de sincronización sobre la imagen de LinuxServer; no pretende sustituir ni atribuirse el trabajo de esos proyectos. Consulte sus repositorios, documentación y licencias originales. Gracias a sus autores y colaboradores: **LinuxServer/docker-wireguard y wg-easy son la base técnica y conceptual de este trabajo**.
