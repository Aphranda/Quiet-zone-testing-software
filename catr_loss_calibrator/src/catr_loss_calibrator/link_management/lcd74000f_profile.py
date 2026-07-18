from __future__ import annotations

from dataclasses import dataclass

from catr_loss_calibrator.link_management.models import LinkPort, LinkRoute

SUPPORTED_PORTS = frozenset(port.value for port in LinkPort)


@dataclass(frozen=True)
class Lcd74000fProfile:
    model: str = "LCD74000F"
    supported_ports: frozenset[str] = SUPPORTED_PORTS

    def validate_route(self, route: LinkRoute) -> None:
        if len(route.ports) < 2:
            raise ValueError("A link route must contain at least two ports.")

        unknown = [port.value for port in route.ports if port.value not in self.supported_ports]
        if unknown:
            raise ValueError(f"Unsupported LCD74000F port(s): {', '.join(unknown)}")

        _validate_amplifier_direction(route)


def _validate_amplifier_direction(route: LinkRoute) -> None:
    ports = route.ports
    if LinkPort.AMP1 in ports:
        _require_order(ports, LinkPort.DUT, LinkPort.AMP1, "AMP1 must be used after DUT.")
    if LinkPort.AMP2 in ports:
        if LinkPort.H in ports:
            _require_order(ports, LinkPort.H, LinkPort.AMP2, "AMP2 must be used after H.")
        if LinkPort.V in ports:
            _require_order(ports, LinkPort.V, LinkPort.AMP2, "AMP2 must be used after V.")


def _require_order(ports: tuple[LinkPort, ...], before: LinkPort, after: LinkPort, message: str) -> None:
    if before in ports and after in ports and ports.index(before) > ports.index(after):
        raise ValueError(message)
