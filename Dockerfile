ARG BASE_IMAGE=lscr.io/linuxserver/wireguard@sha256:10db56ad834f94541307d5dfdbe87370e26d155bb341a5bf65789f970f24ab5c
FROM ${BASE_IMAGE} AS alpine-stable

RUN test "$(cut -d. -f1,2 /etc/alpine-release)" = 3.24 \
    && printf '%s\n' \
       'https://dl-cdn.alpinelinux.org/alpine/v3.24/main' \
       'https://dl-cdn.alpinelinux.org/alpine/v3.24/community' > /etc/apk/repositories

FROM alpine-stable AS python-builder

RUN apk add --no-cache python3 py3-pip py3-virtualenv \
    && python3 -m venv /opt/wireguard-gui/venv

COPY requirements.txt /opt/wireguard-gui/requirements.txt
RUN /opt/wireguard-gui/venv/bin/pip install --no-cache-dir -r /opt/wireguard-gui/requirements.txt \
    && /opt/wireguard-gui/venv/bin/pip uninstall --yes pip setuptools

FROM alpine-stable

ARG BUILD_DATE
ARG VERSION=0.2.0-beta
ARG VCS_REF
LABEL org.opencontainers.image.title="WireGuard GUI" \
      org.opencontainers.image.description="Interfaz web ligera para administrar WireGuard sobre la imagen de LinuxServer.io" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.source="https://github.com/aguilarbucket/Wireguard-GUI" \
      org.opencontainers.image.url="https://github.com/aguilarbucket/Wireguard-GUI" \
      org.opencontainers.image.documentation="https://github.com/aguilarbucket/Wireguard-GUI#readme" \
      org.opencontainers.image.licenses="GPL-3.0-only"

# Esta aplicación entrega un DNS externo a cada peer y no usa el CoreDNS
# opcional de LinuxServer. Retirarlo elimina superficie de ataque no utilizada.
ENV USE_COREDNS=false

# LinuxServer conserva la comprobación netstat de CoreDNS. BusyBox la provee.
RUN apk del --no-cache coredns net-tools \
    && apk add --no-cache python3 sudo \
    && apk upgrade --no-cache \
    && command -v netstat

COPY --from=python-builder /opt/wireguard-gui/venv /opt/wireguard-gui/venv
COPY wggui /opt/wireguard-gui/wggui
COPY docker/root /
RUN chmod +x \
      /etc/s6-overlay/s6-rc.d/init-wggui/run \
      /etc/s6-overlay/s6-rc.d/svc-wggui/run \
    && chmod 0440 /etc/sudoers.d/wggui

EXPOSE 51820/udp 51821/tcp
