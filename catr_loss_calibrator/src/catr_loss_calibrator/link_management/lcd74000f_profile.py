from __future__ import annotations

from dataclasses import dataclass

from catr_loss_calibrator.link_management.models import LinkPort, LinkRoute

SUPPORTED_PORTS = frozenset(port.value for port in LinkPort)

DEFAULT_LINK_ROUTES: dict[str, LinkRoute] = {
    "DUT_SA": LinkRoute((LinkPort.DUT, LinkPort.SA), "DUT 侧直通到 SA"),
    "DUT_AMP1_SA": LinkRoute((LinkPort.DUT, LinkPort.AMP1, LinkPort.SA), "DUT 侧经 AMP1 到 SA"),
    "DUT_VNA2": LinkRoute((LinkPort.DUT, LinkPort.VNA2), "DUT 到 VNA2 直通"),
    "DUT_AMP1_VNA2": LinkRoute((LinkPort.DUT, LinkPort.AMP1, LinkPort.VNA2), "DUT 到 VNA2 经 AMP1"),
    "H_VNA1": LinkRoute((LinkPort.H, LinkPort.VNA1), "H 极化到 VNA1"),
    "V_VNA1": LinkRoute((LinkPort.V, LinkPort.VNA1), "V 极化到 VNA1"),
    "H_SA": LinkRoute((LinkPort.H, LinkPort.SA), "H 极化到 SA"),
    "V_SA": LinkRoute((LinkPort.V, LinkPort.SA), "V 极化到 SA"),
    "H_AMP2_VNA1": LinkRoute((LinkPort.H, LinkPort.AMP2, LinkPort.VNA1), "H 极化经 AMP2 到 VNA1"),
    "V_AMP2_VNA1": LinkRoute((LinkPort.V, LinkPort.AMP2, LinkPort.VNA1), "V 极化经 AMP2 到 VNA1"),
    "H_AMP2_SA": LinkRoute((LinkPort.H, LinkPort.AMP2, LinkPort.SA), "H 极化经 AMP2 到 SA"),
    "V_AMP2_SA": LinkRoute((LinkPort.V, LinkPort.AMP2, LinkPort.SA), "V 极化经 AMP2 到 SA"),
    "H_SG": LinkRoute((LinkPort.H, LinkPort.SG), "H 极化到 SG"),
    "V_SG": LinkRoute((LinkPort.V, LinkPort.SG), "V 极化到 SG"),
    "H_AMP2_SG": LinkRoute((LinkPort.H, LinkPort.AMP2, LinkPort.SG), "H 极化经 AMP2 到 SG"),
    "V_AMP2_SG": LinkRoute((LinkPort.V, LinkPort.AMP2, LinkPort.SG), "V 极化经 AMP2 到 SG"),
}


@dataclass(frozen=True)
class Lcd74000fProfile:
    model: str = "LCD74000F"
    supported_ports: frozenset[str] = SUPPORTED_PORTS
    link_routes: dict[str, LinkRoute] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.link_routes is None:
            object.__setattr__(self, "link_routes", DEFAULT_LINK_ROUTES)

    def validate_route(self, route: LinkRoute) -> None:
        if len(route.ports) < 2:
            raise ValueError("A link route must contain at least two ports.")

        unknown = [port.value for port in route.ports if port.value not in self.supported_ports]
        if unknown:
            raise ValueError(f"Unsupported LCD74000F port(s): {', '.join(unknown)}")

        _validate_amplifier_direction(route)

    def get_route(self, route_id: str) -> LinkRoute:
        try:
            return self.link_routes[route_id.strip().upper()]
        except KeyError as exc:
            raise KeyError(f"Unknown LCD74000F route: {route_id}") from exc


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
