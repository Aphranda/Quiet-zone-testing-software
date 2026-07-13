from __future__ import annotations

from dataclasses import dataclass


DEFAULT_VNA_IP_ADDRESS = "192.168.1.10"
DEFAULT_VNA_PORT = 5025
DEFAULT_VNA_TIMEOUT_MS = 5000
DEFAULT_VNA_MODEL = "E5080B"
SUPPORTED_VNA_MODELS = ("E5080B", "N5245B")

DEFAULT_POSITIONER_BAUDRATE = 115200
DEFAULT_POSITIONER_BYTESIZE = 8
DEFAULT_POSITIONER_PARITY = "N"
DEFAULT_POSITIONER_STOPBITS = 1
DEFAULT_POSITIONER_TIMEOUT_MS = 1000
DEFAULT_POSITIONER_RETRIES = 2
DEFAULT_POSITIONER_RETRY_DELAY_S = 0.05
DEFAULT_POSITIONER_X_AXIS = 2
DEFAULT_POSITIONER_Y_AXIS = 3
DEFAULT_POSITIONER_PULSES_PER_MM = 400.0
DEFAULT_POSITIONER_SPEED_MM_S = 20.0

DEFAULT_SWITCH_BOX_MODEL = "LCD74000F"
SUPPORTED_SWITCH_BOX_MODELS = ("LCD74000F", "TC500")
DEFAULT_SWITCH_BOX_CONNECTION_TYPE = "TCP/IP"
DEFAULT_SWITCH_BOX_SERIAL_PORT = "COM3"
DEFAULT_SWITCH_BOX_BAUDRATE = 115200


@dataclass(frozen=True)
class SwitchBoxModelDefaults:
    connection_type: str
    ip_address: str
    tcp_port: int
    timeout_ms: int


LCD74000F_SWITCH_BOX_DEFAULTS = SwitchBoxModelDefaults(
    connection_type="TCP/IP",
    ip_address="192.168.1.113",
    tcp_port=7,
    timeout_ms=2000,
)
TC500_SWITCH_BOX_DEFAULTS = SwitchBoxModelDefaults(
    connection_type="Serial",
    ip_address="192.168.1.120",
    tcp_port=35,
    timeout_ms=1500,
)


def switch_box_model_defaults(model: str) -> SwitchBoxModelDefaults:
    if str(model).strip().upper() == "TC500":
        return TC500_SWITCH_BOX_DEFAULTS
    return LCD74000F_SWITCH_BOX_DEFAULTS
