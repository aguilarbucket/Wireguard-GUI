# Auditoría Docker Scout de WireGuard GUI

**18 de noviembre de 2026 · Fases 0, 1 y 2 · Linux amd64**

El nuevo `latest` reduce de **12 a 11** los CVE que Scout identifica en el sistema de archivos final. Retirar `net-tools` elimina **CVE-2025-46836** del entorno de ejecución. Alpine confirma que dos alertas altas de Scout ya estaban corregidas en ambas versiones. Una tercera alerta alta corresponde al cliente de línea de comandos de SQLite, ausente de ambas imágenes. Quedan ocho hallazgos del inventario de Scout por seguimiento en los componentes de Coreutils y OpenSSL.

## Promoción a latest

El 18 de noviembre se promovió en Docker Hub el mismo artefacto que superó las pruebas, con índice `sha256:ea4a54ef5e61007c51ff44b034ceeed0afdcc9a7c5109c9f0afe78922f8ffc59`. La verificación remota confirmó el manifiesto amd64 y la atestación. Scout leyó el SBOM publicado y devolvió los mismos 11 CVE en cinco paquetes. El digest publicado también superó nuevamente las pruebas de GUI, API, WireGuard y persistencia en un despliegue local desechable. [Manifiesto de la promoción](release-manifest.txt) · [SARIF de Docker Hub](release.sarif.json) · [Regresión del digest publicado](release-regression.txt).

La comprobación de parches previa a la promoción volvió a consultar los repositorios firmados de Alpine v3.24. `apk upgrade --simulate` confirmó que las 98 revisiones APK instaladas estaban al día. Para reversión, `beta` conserva el índice `sha256:588a5bfbbc105612dc320e3f558b5a5145efd56601bb337d9b1d57e9ef0a31d5`.

## Fase 0. Identidad e inventario

| Artefacto | Índice OCI | Manifiesto Linux amd64 |
| --- | --- | --- |
| Docker Hub `alejandroromeroa/wireguard-gui:latest` durante la auditoría, antes de la promoción | `sha256:588a5bfbbc105612dc320e3f558b5a5145efd56601bb337d9b1d57e9ef0a31d5` | `sha256:7c0038b6b36f24ecbf17412d0f1ef3fcb0637e17fd431de36f2940156afb008f` |
| Candidata local `wireguard-gui:scout-remediation-sbom` | `sha256:ea4a54ef5e61007c51ff44b034ceeed0afdcc9a7c5109c9f0afe78922f8ffc59` | `sha256:99b9c881d369a34d196176770ef1ade8dd26f80f6164f9585833fd1fd3e99fcd` |

La primera consulta a Docker Hub y el cierre de la auditoría previa a la promoción devolvieron el mismo índice y manifiesto. La procedencia de la versión anterior apunta al commit `be9f708609188eb9a2af7f802deacd593ce47437` y al índice de LinuxServer/WireGuard `sha256:10db56ad834f94541307d5dfdbe87370e26d155bb341a5bf65789f970f24ab5c`. Ambas imágenes usan esa base y ejecutan Alpine **3.24.4**. [Manifiesto anterior](published-manifest.txt) · [Procedencia anterior](baseline-provenance.json) · [Metadatos de la candidata](candidate-sbom-build-metadata.json).

Docker Scout **1.28.0** escaneó el índice publicado por digest y obtuvo 110 paquetes y 12 CVE en seis paquetes. Las cinco alertas de OpenSSL tienen severidad asignada en esta ejecución. La comparación repitió el análisis con los SPDX de la etapa final generados por el mismo escáner Syft (`1.51.0`). Se verificó que el sujeto de la atestación de la candidata coincide con su manifiesto amd64. Los resultados incluyen todas las severidades y el contenido heredado del que informa cada SBOM. [SARIF publicado](baseline.sarif.json) · [Identidad de los SBOM](sbom-evidence.json) · [Documentación de Scout](https://docs.docker.com/scout/how-tos/view-create-sboms/).

## Fase 1. Contraste de los 12 hallazgos

Se consultaron las 12 fichas del Tracker, el SecDB por repositorio y las versiones que ofrecían los índices firmados de Alpine v3.24 para x86_64. La simulación de `apk upgrade` sobre la imagen publicada no encontró revisiones instaladas que actualizar. [Fichas de Alpine](alpine-tracker.json) · [SecDB main](alpine-secdb-main.json) · [SecDB community](alpine-secdb-community.json) · [Política e inventario APK](baseline-apk.txt).

| CVE | Paquete instalado en la referencia | Scout | Evaluación y tratamiento |
| --- | --- | --- | --- |
| [CVE-2025-46836](https://security.alpinelinux.org/vuln/CVE-2025-46836) | `net-tools 2.10-r3` | Media | **Mitigada en la candidata.** Alpine marca v3.24 como posiblemente vulnerable. Se retiraron `net-tools` y su subpaquete `mii-tool`. BusyBox proporciona el `netstat` que usa LinuxServer. |
| [CVE-2026-107891](https://security.alpinelinux.org/vuln/CVE-2026-107891) | `musl 1.2.6-r3` | Alta | **Ya corregida en ambas imágenes.** Tracker y SecDB confirman el backport en `1.2.6-r3` de v3.24. Scout sigue usando `1.2.6-r6`, que corresponde a Edge. Falso positivo de revisión para v3.24. |
| [CVE-2026-96512](https://security.alpinelinux.org/vuln/CVE-2026-96512) | `sudo 1.9.17_p2-r2` | Alta | **Ya corregida en ambas imágenes.** Tracker y SecDB confirman el backport en `1.9.17_p2-r2` de v3.24. Scout sigue usando `1.9.17_p2-r4`, que corresponde a Edge. La política de la aplicación también carece de restricciones temporales `NOTBEFORE` y `NOTAFTER`. |
| [CVE-2026-119586](https://security.alpinelinux.org/vuln/CVE-2026-119586) | `sqlite-libs 3.53.4-r0` | Alta | **No aplicable al binario presente.** Alpine registra el paquete fuente `sqlite` como posiblemente vulnerable. El [aviso de SQLite](https://www.sqlite.org/cves.html#status_of_recent_sqlite_cves) limita el hallazgo al comando `.recover` de la CLI. El APK y la comprobación de binarios confirman que ambas imágenes sólo incluyen la biblioteca; la API usa `sqlite3` de Python. |
| [CVE-2026-56391](https://security.alpinelinux.org/vuln/CVE-2026-56391) | `coreutils 9.11-r0` | Media | **Pendiente en Alpine estable.** `uniq` está presente. Los flujos auditados no ejecutan `uniq` con argumentos ni entradas de la GUI. [Aviso de CERT Polska](https://cert.pl/en/posts/2026/07/CVE-2026-56391/). |
| [CVE-2026-56392](https://security.alpinelinux.org/vuln/CVE-2026-56392) | `coreutils 9.11-r0` | Baja | **Pendiente en Alpine estable.** `unexpand` está presente. Los flujos auditados no lo invocan con datos del usuario. [Aviso de CERT Polska](https://cert.pl/en/posts/2026/07/CVE-2026-56391/). |
| [CVE-2016-2781](https://security.alpinelinux.org/vuln/CVE-2016-2781) | `coreutils 9.11-r0` | Media | **Pendiente en Alpine estable.** `chroot` está presente. La precondición es una sesión local con terminal y el uso de `chroot --userspec`. La aplicación no usa esa vía ni expone terminales. |
| [CVE-2026-88822](https://security.alpinelinux.org/vuln/CVE-2026-88822) | `libssl3 3.5.9-r0` | Media | **Pendiente en Alpine estable.** El aviso se refiere a la detección automática de pares QUIC. El servidor web auditado usa HTTP/TCP. |
| [CVE-2026-95691](https://security.alpinelinux.org/vuln/CVE-2026-95691) | `libssl3 3.5.9-r0` | Alta | **Pendiente en Alpine estable.** Afecta clientes QUIC. Los flujos de WireGuard y de la GUI auditados carecen de esa ruta. |
| [CVE-2026-88823](https://security.alpinelinux.org/vuln/CVE-2026-88823) | `libssl3 3.5.9-r0` | Alta | **Pendiente en Alpine estable.** Afecta un uso incremental de AES-GCM-SIV. El código auditado carece de llamadas a ese cifrado. |
| [CVE-2026-95692](https://security.alpinelinux.org/vuln/CVE-2026-95692) | `libssl3 3.5.9-r0` | Alta | **Pendiente en Alpine estable.** Afecta validación del IV de AES-GCM-SIV. El código auditado carece de llamadas a ese cifrado. |
| [CVE-2026-107496](https://security.alpinelinux.org/vuln/CVE-2026-107496) | `libssl3 3.5.9-r0` | Alta | **Pendiente en Alpine estable.** Afecta cifrado CMS con certificados de destinatario no confiables. La GUI no cifra CMS. |

Para los cinco avisos de OpenSSL, el Tracker registra `3.5.9-r1` como corregida en Edge y carece de filas para v3.24. `libssl3` y `libcrypto3` siguen en `3.5.9-r0` y se deben actualizar conjuntamente desde v3.24 cuando haya una revisión que incluya los parches. OpenSSL clasifica los cinco como bajos y señaló `3.5.10` para su publicación del 1 de diciembre. La evaluación de alcance corresponde a WireGuard GUI y al arranque probado de LinuxServer. Otros servicios, modificaciones o proxies podrían usar las rutas afectadas. [Aviso de OpenSSL del 10 de noviembre](https://openssl-library.org/news/secadv/20261110.txt).

OpenSSL también publicó **CVE-2026-35190**, **CVE-2026-107493** y **CVE-2026-124709** el 17 de noviembre para la rama 3.5. Estos tres avisos son seguimiento adicional fuera del conteo Scout. Sus precondiciones son, respectivamente, un servidor TLS configurado con Suite B, una llamada de lectura PEM que reutiliza una pila suministrada por la aplicación y un servidor QUIC. No se identificaron esos flujos en la aplicación auditada. [Aviso de OpenSSL del 17 de noviembre](https://openssl-library.org/news/secadv/20261117.txt).

## Fase 2. Candidata y diferencias

La rama local `security/scout-remediation` fija por digest la base LinuxServer usada por la publicación, exige Alpine v3.24 y usa sus repositorios oficiales `main` y `community` por HTTPS en ambas etapas. Durante la construcción, `apk upgrade --no-cache` evaluó la disponibilidad de parches en esa rama y conservó las revisiones vigentes. Se desinstalaron `net-tools` y `mii-tool` en la etapa final, junto con la retirada preexistente de CoreDNS. Se verificaron `/bin/netstat → /bin/busybox`, la ejecución de `netstat -apn`, WireGuard e iptables, y la sintaxis de `sudoers`. [Dockerfile](../../Dockerfile) · [Inventario de la candidata](candidate-apk.txt) · [Metadatos de construcción](candidate-sbom-build-metadata.json).

| Resultado sobre el SBOM de ejecución | Publicada | Candidata |
| --- | ---: | ---: |
| Paquetes | 110 | 108 |
| Paquetes con alertas | 6 | 5 |
| Críticas | 0 | 0 |
| Altas | 7 | 7 |
| Medias | 4 | 3 |
| Bajas | 1 | 1 |
| Sin severidad | 0 | 0 |
| **CVE totales** | **12** | **11** |

El único CVE eliminado es **CVE-2025-46836**. Scout no registró CVE nuevos ni cambios de versión entre los 108 paquetes restantes. Se conservaron los dos falsos positivos de backport y el hallazgo de SQLite en los SARIF. [Comparación de Scout](scout-runtime-comparison.md) · [SARIF de referencia](baseline-runtime.sarif.json) · [SARIF de la candidata](candidate-runtime.sarif.json).

Con `local://`, Scout indexó **307 → 305 paquetes** y **67 → 66 CVE distintos**. Los 55 CVE adicionales en cada imagen corresponden a dependencias Go que el índice local ubica en `/usr/bin/coredns` dentro de una capa heredada. El proceso de construcción retira ese binario del sistema de archivos visible en ambas imágenes. Los datos de la capa siguen formando parte del artefacto distribuible y pueden disparar políticas que auditan todas las capas. El SARIF local tiene una entrada adicional en cada imagen porque un mismo CVE figura para dos componentes. [SARIF local de referencia](baseline-local-layer-scan.sarif.json) · [SARIF local de la candidata](candidate-attested-local.sarif.json) · [Ubicación de los módulos Go](local-go-layer-locations.json).

## Regresión y límites

Docker Desktop **4.99.0** ejecutó las dos imágenes en Linux amd64 con el kernel **6.18.58.1-microsoft-standard-WSL2**. Cada prueba usó una red Docker dedicada, un volumen exclusivo para `/config`, dos contenedores con `NET_ADMIN` y un puerto web aleatorio en `127.0.0.1`. La prueba de UDP se hizo entre contenedores. Las claves y los peers se generaron para la prueba y los recursos se eliminaron tras cada ejecución.

| Prueba | Publicada | Candidata |
| --- | --- | --- |
| Arranque s6, `/health` e interfaz `wg0` en UDP 51820 | Pasa | Pasa |
| Microsoft Edge headless 157, autenticación, JS, CSS, panel y alta de un peer desde la GUI | Pasa | Pasa |
| API autenticada, 401 sin sesión, 403 sin CSRF, perfil y QR con `no-store` | Pasa | Pasa |
| Handshake real de WireGuard, contadores RX/TX e ICMP inicial 3/3 | Pasa | Pasa |
| Deshabilitar y habilitar el peer en el kernel, reiniciar preservando la clave y el estado, reconectar el cliente y eliminar el peer | Pasa | Pasa |

La reconexión se verificó levantando nuevamente la interfaz del cliente de prueba con el mismo perfil. La reanudación automática del túnel tras el reinicio no se acreditó. Las pruebas cubren Linux amd64 en Docker Desktop y el flujo por la red Docker, sin prueba de acceso por un puerto UDP publicado ni tráfico de salida enrutado por la VPN. La suite existente pasó **20 pruebas** con **86 %** de cobertura total en Windows. [Registro de regresión](regression.txt) · [Script de regresión](regression.py) · [Salida de pytest](pytest.txt).

## Reproducción

Las referencias `registry://` y `sbom://` fijan el origen del inventario. La ruta del tar corresponde a un artefacto local de la auditoría. Para repetir la compilación con los índices disponibles en otra fecha se generará un digest nuevo.

```powershell
$published = 'docker.io/alejandroromeroa/wireguard-gui@sha256:588a5bfbbc105612dc320e3f558b5a5145efd56601bb337d9b1d57e9ef0a31d5'
docker scout cves --platform linux/amd64 --format sarif "registry://$published"
docker buildx imagetools inspect $published --format '{{json .SBOM.SPDX}}' |
    Set-Content -Encoding utf8 .pytest_cache/baseline-sbom.spdx.json

$archive = '.pytest_cache/scout-candidate-oci.tar'
$blob = 'blobs/sha256/48984d3ceec7f077b0c403ba909f95fb6cbca94c7ddd27bb2d5834f768df0f22'
$statement = tar -xOf $archive $blob | ConvertFrom-Json
if ($statement.subject[0].digest.sha256 -ne '99b9c881d369a34d196176770ef1ade8dd26f80f6164f9585833fd1fd3e99fcd') {
    throw 'El SBOM no corresponde al manifiesto de la candidata'
}
$statement.predicate | ConvertTo-Json -Depth 20 -Compress |
    Set-Content -Encoding utf8NoBOM .pytest_cache/candidate-sbom.spdx.json
docker scout compare --platform linux/amd64 --hide-policies `
    --to sbom://.pytest_cache/baseline-sbom.spdx.json sbom://.pytest_cache/candidate-sbom.spdx.json
```

Para crear otra candidata local con atestación y exportar su OCI, se puede usar el mismo generador que la referencia. La nueva atestación debe identificarse en el índice del nuevo OCI antes de extraer su SPDX.

```powershell
$archive = Join-Path (Get-Location) '.pytest_cache/scout-candidate-oci.tar'
docker buildx build --platform linux/amd64 --pull --no-cache `
    --sbom 'generator=docker/buildkit-syft-scanner@sha256:873a7458c3c8ac8e32c7b796c10e1600b07b963d2aa000a72a2d97aaaa2d6315' `
    --output "type=oci,dest=$archive" --load `
    --build-arg VERSION=0.2.0-scout-remediation -t wireguard-gui:scout-remediation-sbom .
```
