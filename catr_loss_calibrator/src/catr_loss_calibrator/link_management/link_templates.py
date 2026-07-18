from __future__ import annotations

from catr_loss_calibrator.link_management.models import LinkPort, LinkRoute


def link_command(*ports: str | LinkPort) -> str:
    return link_route(*ports).to_command().command


def link_route(*ports: str | LinkPort, description: str = "") -> LinkRoute:
    parsed = tuple(_parse_port(port) for port in ports if str(port).strip())
    if not parsed:
        raise ValueError("At least one link port is required.")
    return LinkRoute(ports=parsed, description=description)


def _parse_port(port: str | LinkPort) -> LinkPort:
    if isinstance(port, LinkPort):
        return port
    try:
        return LinkPort(port.strip().upper())
    except ValueError as exc:
        raise ValueError(f"Unsupported link port: {port}") from exc
