import unittest
from pathlib import Path

import numpy as np

from quiet_zone_tester.domains.scan_management import ScanRuntimeService, ScanRuntimeServiceError
from quiet_zone_tester.hardware import Position
from quiet_zone_tester.models import SParameterTrace


def _trace(parameter: str = "S21") -> SParameterTrace:
    return SParameterTrace(
        frequency_hz=np.array([1.0e9, 2.0e9], dtype=float),
        complex_values=np.array([1.0 + 0.0j, 0.0 + 1.0j], dtype=complex),
        parameter=parameter,
    )


def _settings(**overrides) -> dict:
    settings = {
        "start_ghz": 1.0,
        "stop_ghz": 2.0,
        "points": 2,
        "parameter": "S21",
        "vna_power_dbm": -10.0,
        "if_bandwidth_hz": 1000.0,
        "scan_mode": "step",
        "x_start_mm": 0.0,
        "x_stop_mm": 1.0,
        "y_start_mm": 0.0,
        "y_stop_mm": 0.0,
        "step_x_mm": 1.0,
        "step_y_mm": 1.0,
        "step_speed_mm_s": 10.0,
        "continuous_speed_mm_s": 10.0,
        "settle_delay_s": 0.0,
        "file_flag": "case",
        "scan_output_dir": "out",
    }
    settings.update(overrides)
    return settings


class _Motion:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.position = Position(10.0, 20.0)

    def query_position(self) -> Position:
        self.calls.append(("query_position",))
        return self.position

    def move_axis_to(self, axis_name: str, position_mm: float, speed_mm_s: float) -> Position:
        self.calls.append(("move_axis_to", axis_name, position_mm, speed_mm_s))
        if axis_name == "Y":
            self.position = Position(self.position.x_mm, position_mm)
        else:
            self.position = Position(position_mm, self.position.y_mm)
        return self.position

    def jog_axis_until(
        self,
        *,
        axis_name: str,
        target_position_mm: float,
        speed_mm_s: float,
        active_axis_name: str | None,
        active_direction: int,
        wait_if_paused,
        raise_if_stopped,
        is_paused,
    ) -> tuple[str | None, int]:
        self.calls.append(("jog_axis_until", axis_name, target_position_mm, speed_mm_s))
        return axis_name, 1

    def stop_axis_by_name_quietly(self, axis_name: str | None) -> None:
        self.calls.append(("stop_axis_by_name_quietly", axis_name))


class ScanRuntimeServiceTest(unittest.TestCase):
    def _service(self, motion: _Motion, state: dict | None = None) -> ScanRuntimeService:
        state = state or {}
        state.setdefault("configured", 0)
        state.setdefault("saved", [])
        state.setdefault("progress", [])
        state.setdefault("stopped", False)

        def save_trace(trace, **kwargs) -> Path:
            state["saved"].append((trace.parameter, kwargs))
            return Path("trace.csv")

        return ScanRuntimeService(
            motion=motion,
            configure_vna_for_scan=lambda settings: state.__setitem__("configured", state["configured"] + 1),
            measure_trace=lambda settings: _trace(str(settings["parameter"])),
            save_trace=save_trace,
            checkpoint=lambda: None,
            sleep_interruptibly=lambda duration_s: state.setdefault("slept", []).append(duration_s),
            wait_if_paused=lambda: None,
            raise_if_stopped=lambda: None,
            is_paused=lambda: False,
            stop_requested=lambda: bool(state["stopped"]),
            stop_positioner_quietly=lambda: state.__setitem__("stopped_quietly", True),
            probe_offset_filename_tag=lambda settings: "probe",
            scan_output_dir=lambda settings: Path(str(settings["scan_output_dir"])),
        )

    def test_step_scan_moves_axes_saves_each_trace_and_reports_progress(self) -> None:
        motion = _Motion()
        state = {"progress": []}
        service = self._service(motion, state)

        traces = service.run_step_scan(
            _settings(),
            on_progress=lambda index, total, trace: state["progress"].append((index, total, trace is None)),
        )

        self.assertEqual(len(traces), 2)
        self.assertEqual(state["configured"], 1)
        self.assertEqual(
            motion.calls,
            [
                ("query_position",),
                ("move_axis_to", "Y", 20.0, 10.0),
                ("move_axis_to", "X", 10.0, 10.0),
                ("move_axis_to", "X", 11.0, 10.0),
            ],
        )
        self.assertEqual([saved[1]["point_index"] for saved in state["saved"]], [1, 2])
        self.assertEqual([saved[1]["position_mm"] for saved in state["saved"]], [(0.0, 0.0), (1.0, 0.0)])
        self.assertEqual(
            state["progress"],
            [(1, 2, True), (1, 2, False), (2, 2, True), (2, 2, False)],
        )

    def test_continuous_scan_rejects_zero_speed(self) -> None:
        service = self._service(_Motion())

        with self.assertRaises(ScanRuntimeServiceError):
            service.run_continuous_scan(_settings(continuous_speed_mm_s=0.0))

    def test_step_scan_returns_partial_results_when_stop_requested_after_failure(self) -> None:
        motion = _Motion()
        state = {"saved": [], "configured": 0, "stopped": False}
        calls = {"measure": 0}
        service = self._service(motion, state)

        def measure(settings):
            calls["measure"] += 1
            if calls["measure"] == 2:
                state["stopped"] = True
                raise RuntimeError("stopped")
            return _trace(str(settings["parameter"]))

        service = ScanRuntimeService(
            motion=service.motion,
            configure_vna_for_scan=service.configure_vna_for_scan,
            measure_trace=measure,
            save_trace=service.save_trace,
            checkpoint=service.checkpoint,
            sleep_interruptibly=service.sleep_interruptibly,
            wait_if_paused=service.wait_if_paused,
            raise_if_stopped=service.raise_if_stopped,
            is_paused=service.is_paused,
            stop_requested=service.stop_requested,
            stop_positioner_quietly=service.stop_positioner_quietly,
            probe_offset_filename_tag=service.probe_offset_filename_tag,
            scan_output_dir=service.scan_output_dir,
        )

        traces = service.run_step_scan(_settings())

        self.assertEqual(len(traces), 1)
        self.assertTrue(state["stopped_quietly"])


if __name__ == "__main__":
    unittest.main()
