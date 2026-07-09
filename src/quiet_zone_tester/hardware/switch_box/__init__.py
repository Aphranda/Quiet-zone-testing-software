"""Switch-box hardware adapters."""

from quiet_zone_tester.hardware.switch_box.lcd74000f import (
    Lcd74000fSwitchBoxConfig,
    Lcd74000fSwitchBoxController,
    Lcd74000fSwitchBoxError,
)
from quiet_zone_tester.hardware.switch_box.tc500 import (
    Tc500SwitchBoxConfig,
    Tc500SwitchBoxController,
    Tc500SwitchBoxError,
)

__all__ = [
    "Lcd74000fSwitchBoxConfig",
    "Lcd74000fSwitchBoxController",
    "Lcd74000fSwitchBoxError",
    "Tc500SwitchBoxConfig",
    "Tc500SwitchBoxController",
    "Tc500SwitchBoxError",
]
