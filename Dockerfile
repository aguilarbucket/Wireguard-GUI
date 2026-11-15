ARG BASE_IMAGE=lscr.io/linuxserver/wireguard:latest
FROM ${BASE_IMAGE}

ARG BUILD_DATE
ARG VERSION=0.2.0
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

RUN apk add --no-cache curl python3 py3-pip py3-virtualenv sudo \
    && python3 -m venv /opt/wireguard-gui/venv

COPY requirements.txt /opt/wireguard-gui/requirements.txt
RUN /opt/wireguard-gui/venv/bin/pip install --no-cache-dir -r /opt/wireguard-gui/requirements.txt

COPY wggui /opt/wireguard-gui/wggui
COPY docker/root /
RUN chmod +x \
      /etc/s6-overlay/s6-rc.d/init-wggui/run \
      /etc/s6-overlay/s6-rc.d/svc-wggui/run \
    && chmod 0440 /etc/sudoers.d/wggui

EXPOSE 51820/udp 51821/tcp
