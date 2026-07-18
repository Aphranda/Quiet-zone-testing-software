from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LinkPort(str, Enum):
    DUT = "DUT"
    H = "H"
    V = "V"
    VNA1 = "VNA1"
    VNA2 = "VNA2"
    SA = "SA"
    SG = "SG"
    AMP1 = "AMP1"
    AMP2 = "AMP2"


@dataclass(frozen=True)
class LinkCommand:
    command: str
    description: str = ""


@dataclass(frozen=True)
class LinkRoute:
    ports: tuple[LinkPort, ...]
    description: str = ""

    def to_command(self) -> LinkCommand:
        return LinkCommand(command="CONFigure:LINK " + ", ".join(port.value for port in self.ports), description=self.description)
