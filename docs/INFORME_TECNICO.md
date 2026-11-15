# Informe técnico — WireGuard GUI v0.2.0

Fecha de revisión: 15 de noviembre de 2026.

## Alcance y limitación de la auditoría

La carpeta de trabajo entregada estaba vacía y el único adjunto disponible era el enunciado; `WireGuard-GUI-v0.1.0.zip` no estaba presente. Por ello no fue posible verificar los seis tests informados, inspeccionar sus 23 entradas ni atribuir defectos concretos a v0.1.0. Esta entrega es una implementación limpia v0.2.0 basada en los requisitos. Si aparece el ZIP original, debe realizarse una comparación separada antes de conservar historial o migrar código.

## Referencias vigentes revisadas

- LinuxServer/WireGuard mantiene el modo servidor controlado por `PEERS`. Cambios en `SERVERURL`, `SERVERPORT`, `INTERNAL_SUBNET`, `PEERDNS`, `INTERFACE`, `ALLOWEDIPS` o `PERSISTENTKEEPALIVE_PEERS` pueden regenerar las configuraciones. Desde 2023 los túneles viven en `/config/wg_confs`; un `.conf` inválido puede detener todos los túneles.
- `NET_ADMIN` es necesario. `SYS_MODULE` y `/lib/modules` sólo se requieren cuando el host no cargó el módulo, por lo que no se conceden por defecto.
- wg-easy actual ofrece una experiencia all-in-one y usa sincronización en caliente; sirve como referencia funcional, no como dependencia ni fuente copiada. Su licencia AGPL exige cuidado si en el futuro se incorpora código.

## Riesgos evitados y controles aplicados

| Prioridad | Riesgo | Control v0.2.0 |
|---|---|---|
| Crítica | LinuxServer sobrescribe clientes | `PEERS` prohibido; un init propio es dueño de `wg0.conf` |
| Crítica | Inyección de comandos | `subprocess` con lista de argumentos, `shell=False`; validación estricta |
| Crítica | Estado SQLite, archivo y kernel divergentes | bloqueo en proceso, `BEGIN IMMEDIATE`, reemplazo atómico, `wg syncconf` y rollback |
| Alta | Claves en API/logs | listados sin secretos; `.conf`/QR sólo autenticados y `no-store`; errores saneados |
| Alta | Administración expuesta | bind Compose a loopback, contraseña sin valor predeterminado, scrypt, CSRF, SameSite, CSP y rate limit |
| Alta | Permisos excesivos | sólo `NET_ADMIN`; Gunicorn sin root y sudo limitado a tres comandos exactos; sin Docker socket ni modo privilegiado |
| Media | IPs duplicadas | asignación dentro de transacción y restricción `UNIQUE` |
| Media | Confundir handshake con conexión | indicador explícito “actividad reciente” con ventana de 180 s |
| Media | Pérdida en reinicio | SQLite, claves y configuración bajo `/config` |

## Decisiones de arquitectura

Se mantiene una sola imagen derivada de LinuxServer. SQLite reduce consumo y evita coordinación distribuida. Gunicorn usa un worker para que el bloqueo de configuración sea efectivo dentro del proceso; cuatro hilos atienden las solicitudes breves. Cada cliente tiene UUID independiente de nombre e IP.

El archivo persistente es la fuente operativa para el arranque; SQLite es la fuente de verdad para regenerarlo. Las mutaciones generan el archivo completo y usan `wg-quick strip` seguido de `wg syncconf`, evitando bajar la interfaz y preservando handshakes cuando WireGuard lo permite.

## Seguridad y secretos

Las contraseñas usan scrypt de Werkzeug. La clave de sesión se genera aleatoriamente en el volumen. Las cookies son HttpOnly y SameSite Strict; `Secure` se activa por entorno cuando existe HTTPS. El límite de login es local al proceso y en memoria, adecuado al único worker pero no sustituto de un control perimetral.

Las claves privadas quedan cifradas sólo por los controles del filesystem, no criptográficamente dentro de SQLite, porque el mismo contenedor necesita una clave disponible para leerlas y `wg0.conf` ya contiene la clave del servidor. Para amenazas de robo de disco se requiere cifrado del volumen/host y backups cifrados.

## Riesgos restantes

1. Se verificó Docker Desktop/WSL2 y una interfaz `wg0` real, pero todavía no un handshake desde un cliente WireGuard externo.
2. La regla NAT usa el wrapper `iptables` y salida `eth+`; debe validarse en hosts nftables y topologías con otra interfaz de salida.
3. La imagen base predeterminada usa `latest`. Producción estrictamente reproducible debe fijar un digest validado y adoptar un ciclo de actualización de seguridad.
4. El rate limit se reinicia con el proceso y no coordina múltiples workers; el despliegue soportado usa uno.
5. No hay cifrado de claves por aplicación en esta versión; se depende del cifrado y los permisos del host.
6. Cambiar el puerto requiere coordinar la publicación de Docker en `.env`; la aplicación no tiene ni debe tener acceso al socket Docker.
7. IPv6 de túnel, rutas site-to-site, firewall por cliente, alta disponibilidad y migraciones desde versiones previas quedan fuera de v0.2.0.

## Criterio de versión

La versión puede publicarse como `0.2.0` candidata después de pasar build y tests locales. Sólo debe marcarse estable tras completar la matriz real de integración del README y registrar host, kernel, Docker, arquitectura, comandos y resultados.

## Resultados verificados en esta entrega

- `pytest`: **20 pruebas aprobadas**, 86 % de cobertura de sentencias.
- `pip-audit`: **sin vulnerabilidades conocidas** después de actualizar Flask a 3.1.3 y pytest a 9.0.3.
- `node --check`: JavaScript válido.
- `docker compose config --quiet`: modelo Compose válido con las variables obligatorias definidas.
- `docker compose build`: imagen `wireguard-gui:0.2.0` construida sobre LinuxServer/WireGuard `1.0.20260223-r0-ls130`.
- `docker compose up`: contenedor **healthy**, persistencia confirmada después de recrearlo, `wg0` activo en `10.13.13.1/24`, UDP 51820 y healthcheck HTTP correcto.
- Handshake y tráfico con un cliente WireGuard externo: **pendientes**; no se sustituyen por mocks ni por la mera existencia de `wg0`.
