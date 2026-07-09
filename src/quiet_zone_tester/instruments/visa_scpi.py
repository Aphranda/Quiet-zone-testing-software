"""Deprecated compatibility re-export for `quiet_zone_tester.hardware.transport.visa_scpi`."""

from quiet_zone_tester.hardware.transport.visa_scpi import (
    ScpiCommunicationError,
    ScpiConnectionConfig,
    VisaScpiSession,
)

__all__ = ["ScpiCommunicationError", "ScpiConnectionConfig", "VisaScpiSession"]
