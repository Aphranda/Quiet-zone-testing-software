import unittest

import numpy as np

from quiet_zone_tester.domains.acquisition import AcquisitionService, AcquisitionServiceError
from quiet_zone_tester.domains.scan_management import ScanSettings
from quiet_zone_tester.models import SParameterTrace


def _trace(parameter: str = "S21") -> SParameterTrace:
    return SParameterTrace(
        frequency_hz=np.array([1.0e9, 2.0e9], dtype=float),
        complex_values=np.array([1.0 + 0.0j, 0.0 + 1.0j], dtype=complex),
        parameter=parameter,
    )


class _Vna:
    def __init__(self, connected: bool = True) -> None:
        self._connected = connected
        self.calls: list[tuple] = []
        self.trace = _trace()

    @property
    def is_connected(self) -> bool:
        return self._connected

    def configure_power(self, power_dbm: float) -> None:
        self.calls.append(("power", power_dbm))

    def configure_if_bandwidth(self, bandwidth_hz: float) -> None:
        self.calls.append(("if_bandwidth", bandwidth_hz))

    def configure_sweep(self, start_hz: float, stop_hz: float, points: int) -> None:
        self.calls.append(("sweep", start_hz, stop_hz, points))

    def configure_measurement_parameter(self, parameter: str) -> None:
        self.calls.append(("parameter", parameter))

    def configure_continuous_sweep(self, enabled: bool) -> None:
        self.calls.append(("continuous", enabled))

    def trigger_sweep(self, parameter: str = "S21") -> None:
        self.calls.append(("trigger", parameter))

    def read_s_parameter(self, parameter: str = "S21") -> SParameterTrace:
        self.calls.append(("read", parameter))
        return SParameterTrace(self.trace.frequency_hz, self.trace.complex_values, parameter)

    def measure_s_parameter(self, parameter: str = "S21") -> SParameterTrace:
        self.calls.append(("measure", parameter))
        return SParameterTrace(self.trace.frequency_hz, self.trace.complex_values, parameter)

    def query_sweep_time_s(self) -> float:
        self.calls.append(("sweep_time",))
        return 0.123


class AcquisitionServiceTest(unittest.TestCase):
    def test_configure_trace_sets_power_if_sweep_and_parameter(self) -> None:
        vna = _Vna()

        sweep_time = AcquisitionService(vna).configure_trace(
            start_ghz=1.0,
            stop_ghz=2.0,
            points=101,
            parameter="S11",
            power_dbm=-5.0,
            if_bandwidth_hz=300.0,
        )

        self.assertEqual(
            vna.calls,
            [
                ("power", -5.0),
                ("if_bandwidth", 300.0),
                ("sweep", 1.0e9, 2.0e9, 101),
                ("parameter", "S11"),
                ("continuous", False),
                ("sweep_time",),
            ],
        )
        self.assertEqual(sweep_time, 0.123)

    def test_configure_trace_can_enable_continuous_sweep(self) -> None:
        vna = _Vna()

        AcquisitionService(vna).configure_trace(
            start_ghz=1.0,
            stop_ghz=2.0,
            points=101,
            parameter="S21",
            continuous_sweep=True,
        )

        self.assertIn(("continuous", True), vna.calls)
        self.assertEqual(vna.calls[-1], ("sweep_time",))

    def test_configure_for_scan_keeps_original_scan_parameter_behavior(self) -> None:
        vna = _Vna()

        AcquisitionService(vna).configure_for_scan(
            {
                "start_ghz": 3.0,
                "stop_ghz": 4.0,
                "points": 11,
                "parameter": "S21",
                "vna_power_dbm": -12.0,
                "if_bandwidth_hz": 1000.0,
            }
        )

        self.assertEqual(
            vna.calls,
            [
                ("power", -12.0),
                ("if_bandwidth", 1000.0),
                ("sweep", 3.0e9, 4.0e9, 11),
                ("continuous", False),
                ("sweep_time",),
            ],
        )

    def test_configure_for_scan_accepts_scan_settings_dataclass(self) -> None:
        vna = _Vna()
        settings = ScanSettings.from_mapping(
            {
                "start_ghz": 3.0,
                "stop_ghz": 4.0,
                "points": 11,
                "parameter": "S21",
                "vna_power_dbm": -12.0,
                "if_bandwidth_hz": 1000.0,
                "scan_mode": "step",
                "x_start_mm": 0.0,
                "x_stop_mm": 1.0,
                "y_start_mm": 0.0,
                "y_stop_mm": 0.0,
                "step_x_mm": 1.0,
                "step_y_mm": 1.0,
            }
        )

        AcquisitionService(vna).configure_for_scan(settings)

        self.assertIn(("sweep", 3.0e9, 4.0e9, 11), vna.calls)
        self.assertIn(("continuous", False), vna.calls)
        self.assertEqual(vna.calls[-1], ("sweep_time",))

    def test_acquire_trace_configures_then_samples(self) -> None:
        vna = _Vna()

        trace = AcquisitionService(vna).acquire_trace(
            start_ghz=1.0,
            stop_ghz=2.0,
            points=2,
            parameter="S22",
            power_dbm=-10.0,
            if_bandwidth_hz=500.0,
        )

        self.assertEqual(trace.parameter, "S22")
        self.assertEqual(vna.calls[-1], ("measure", "S22"))

    def test_trigger_and_read_trace_are_separate_operations(self) -> None:
        vna = _Vna()
        service = AcquisitionService(vna)

        service.trigger_trace("S11")
        trace = service.read_trace("S11")

        self.assertEqual(trace.parameter, "S11")
        self.assertEqual(vna.calls, [("trigger", "S11"), ("read", "S11")])

    def test_sample_scan_trace_honors_stop_callback(self) -> None:
        vna = _Vna()
        service = AcquisitionService(vna)

        with self.assertRaises(AcquisitionServiceError):
            service.sample_scan_trace("S21", stop_requested=lambda: True)

        self.assertEqual(vna.calls, [])

    def test_sample_scan_trace_triggers_then_reads(self) -> None:
        vna = _Vna()
        service = AcquisitionService(vna)

        trace = service.sample_scan_trace("S22")

        self.assertEqual(trace.parameter, "S22")
        self.assertEqual(vna.calls, [("trigger", "S22"), ("read", "S22")])

    def test_rejects_unconnected_vna(self) -> None:
        service = AcquisitionService(_Vna(connected=False))

        with self.assertRaises(AcquisitionServiceError):
            service.configure_if_bandwidth(1000.0)
        with self.assertRaises(AcquisitionServiceError):
            service.sample_trace("S21")


if __name__ == "__main__":
    unittest.main()
