"""Strict validation shared by bootstrap and HTTP handlers."""

from __future__ import annotations

import ipaddress
import re

NAME_RE = re.compile(r"^[\w .-]{1,48}$", re.UNICODE)
HOST_RE = re.compile(r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


class ValidationError(ValueError):
    pass


def name(value: object) -> str:
    result = str(value or "").strip()
    if not NAME_RE.fullmatch(result):
        raise ValidationError("El nombre debe tener 1–48 caracteres: letras, números, espacio, punto, guion o guion bajo.")
    return result


def endpoint(value: object) -> str:
    result = str(value or "").strip()
    try:
        ipaddress.ip_address(result)
        return result
    except ValueError:
        if not HOST_RE.fullmatch(result):
            raise ValidationError("El endpoint debe ser una IP o un nombre DNS válido.")
        return result.lower()


def port(value: object) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("El puerto debe ser numérico.") from exc
    if not 1 <= result <= 65535:
        raise ValidationError("El puerto debe estar entre 1 y 65535.")
    return result


def subnet(value: object) -> ipaddress.IPv4Network:
    try:
        result = ipaddress.ip_network(str(value), strict=True)
    except ValueError as exc:
        raise ValidationError("La subred VPN debe ser una red IPv4 válida, por ejemplo 10.13.13.0/24.") from exc
    if result.version != 4 or result.prefixlen > 30:
        raise ValidationError("La subred VPN debe ser IPv4 y disponer de al menos dos hosts.")
    return result


def ip_list(value: object, field: str = "AllowedIPs") -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValidationError(f"{field} no puede estar vacío.")
    networks = []
    try:
        for item in raw.split(","):
            networks.append(str(ipaddress.ip_network(item.strip(), strict=False)))
    except ValueError as exc:
        raise ValidationError(f"{field} contiene una red no válida.") from exc
    return ", ".join(networks)


def dns(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValidationError("DNS no puede estar vacío.")
    values = []
    for item in raw.split(","):
        item = item.strip()
        try:
            values.append(str(ipaddress.ip_address(item)))
        except ValueError:
            if not HOST_RE.fullmatch(item):
                raise ValidationError("DNS debe contener IPs o nombres DNS válidos.")
            values.append(item.lower())
    return ", ".join(values)


def keepalive(value: object) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("PersistentKeepalive debe ser numérico.") from exc
    if not 0 <= result <= 65535:
        raise ValidationError("PersistentKeepalive debe estar entre 0 y 65535.")
    return result


def mtu(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("MTU debe ser numérico.") from exc
    if not 576 <= result <= 9000:
        raise ValidationError("MTU debe estar entre 576 y 9000.")
    return result
