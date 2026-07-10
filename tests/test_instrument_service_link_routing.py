import unittest

import numpy as np

from quiet_zone_tester.hardware import InstrumentInfo, Position
from quiet_zone_tester.models import SParameterTrace
from quiet_zone_tester.services import InstrumentService


class _Vna:
    is_connected = True

    def __init__(self) -> None:
        self.measured_parameters: list[str] = []

    def connect(self) -> InstrumentInfo:
        return InstrumentInfo("VNA", "VNA", "1")

    def disconnect(self) -> None:
        pass

    def configure_sweep(self, start_hz: float, stop_hz: float, points: int) -> None:
        pass

    def configure_power(self, power_dbm: float) -> None:
        pass

    def configure_if_bandwidth(self, bandwidth_hz: float) -> None:
        pass

    def configure_measurement_parameter(self, parameter: str) -> None:
        pass

    def measure_s_parameter(self, parameter: str = "S21") -> SParameterTrace:
        self.measured_parameters.append(parameter)
        return SParameterTrace(
            frequency_hz=np.array([1.0e9, 2.0e9], dtype=float),
            complex_values=np.array([1.0 + 0.0j, 1.0 + 0.0j], dtype=complex),
            parameter=parameter,
        )


class _Positioner:
    is_connected = True
    position = Position(0.0, 0.0)

    def connect(self) -> InstrumentInfo:
        return InstrumentInfo("POS", "POS", "1")

    def disconnect(self) -> None:
        pass

    def move_to(self, x_mm: float, y_mm: float, speed_mm_s: float | None = None) -> Position:
        return Position(x_mm, y_mm)

    def move_axis_to(self, axis: int, position_mm: float, speed_mm_s: float | None = None) -> Position:
        return self.position

    def jog_axis(self, axis: int, speed_mm_s: float) -> None:
        pass

    def stop_axis(self, axis: int) -> None:
        pass

    def stop_all(self) -> None:
        pass


class _SwitchBox:
    is_connected = True

    def __init__(self) -> None:
        self.sent_commands: list[str] = []
        self.selected_parameters: list[str] = []

    def connect(self) -> InstrumentInfo:
        return InstrumentInfo("SW", "SW", "1")

    def disconnect(self) -> None:
        pass

    def select_s_parameter(self, parameter: str) -> str:
        self.selected_parameters.append(parameter)
        return parameter

    def send_command(self, command: str) -> str:
        self.sent_commands.append(command)
        return command


class InstrumentServiceLinkRoutingTest(unittest.TestCase):
    def test_preview_trace_routes_by_polarization_not_s_parameter(self) -> None:
        vna = _Vna()
        switch_box = _SwitchBox()
        service = InstrumentService(vna=vna, positioner=_Positioner(), switch_box=switch_box)

        service.acquire_preview_trace(
            start_ghz=1.0,
            stop_ghz=2.0,
            points=2,
            parameter="S21",
            polarization="V",
        )

        self.assertEqual(switch_box.sent_commands, ["CONFigure:LINK V, VNA1"])
        self.assertEqual(switch_box.selected_parameters, [])
        self.assertEqual(vna.measured_parameters, ["S21"])


if __name__ == "__main__":
    unittest.main()
