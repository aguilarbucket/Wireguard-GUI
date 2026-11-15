ARG BASE_IMAGE=lscr.io/linuxserver/wireguard:latest
FROM ${BASE_IMAGE} AS python-builder

RUN apk add --no-cache python3 py3-pip py3-virtualenv \
    && python3 -m venv /opt/wireguard-gui/venv

COPY requirements.txt /opt/wireguard-gui/requirements.txt
RUN /opt/wireguard-gui/venv/bin/pip install --no-cache-dir -r /opt/wireguard-gui/requirements.txt \
    && /opt/wireguard-gui/venv/bin/pip uninstall --yes pip setuptools

FROM ${BASE_IMAGE}

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

RUN apk del coredns \
    && apk add --no-cache python3 sudo

COPY --from=python-builder /opt/wireguard-gui/venv /opt/wireguard-gui/venv
COPY wggui /opt/wireguard-gui/wggui
COPY docker/root /
RUN chmod +x \
      /etc/s6-overlay/s6-rc.d/init-wggui/run \
      /etc/s6-overlay/s6-rc.d/svc-wggui/run \
    && chmod 0440 /etc/sudoers.d/wggui

EXPOSE 51820/udp 51821/tcp
