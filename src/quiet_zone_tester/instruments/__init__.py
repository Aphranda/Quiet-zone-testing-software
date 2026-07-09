"""Deprecated compatibility re-exports.

New code should import real hardware adapters from `quiet_zone_tester.hardware`.
"""

from quiet_zone_tester.hardware.positioner import Axis, IclPositionerConfig, IclPositionerController
from quiet_zone_tester.hardware.switch_box import (
    Lcd74000fSwitchBoxConfig,
    Lcd74000fSwitchBoxController,
    Lcd74000fSwitchBoxError,
    Tc500SwitchBoxConfig,
    Tc500SwitchBoxController,
    Tc500SwitchBoxError,
)
from quiet_zone_tester.hardware.transport import (
    ModbusRtuConfig,
    ModbusRtuError,
    ModbusRtuSession,
    ScpiCommunicationError,
    ScpiConnectionConfig,
    VisaScpiSession,
)
from quiet_zone_tester.hardware.vna import ScpiVnaController, VnaScpiConfig

__all__ = [
    "Axis",
    "IclPositionerConfig",
    "IclPositionerController",
    "Lcd74000fSwitchBoxConfig",
    "Lcd74000fSwitchBoxController",
    "Lcd74000fSwitchBoxError",
    "ModbusRtuConfig",
    "ModbusRtuError",
    "ModbusRtuSession",
    "ScpiCommunicationError",
    "ScpiConnectionConfig",
    "ScpiVnaController",
    "Tc500SwitchBoxConfig",
    "Tc500SwitchBoxController",
    "Tc500SwitchBoxError",
    "VisaScpiSession",
    "VnaScpiConfig",
]
