from __future__ import annotations

from dataclasses import dataclass

from quiet_zone_tester.domains.scan_management import ScanSettings
from quiet_zone_tester.models import DEFAULT_FREQUENCY_STEP_MHZ, calculate_sweep_points


DEFAULT_START_GHZ = 10.0
DEFAULT_STOP_GHZ = 17.0
DEFAULT_SWEEP_POINTS = calculate_sweep_points(DEFAULT_START_GHZ, DEFAULT_STOP_GHZ, DEFAULT_FREQUENCY_STEP_MHZ)
DEFAULT_IF_BANDWIDTH_HZ = 1000.0
DEFAULT_STEP_MM = 2.5
DEFAULT_DISTANCE_PER_TURN_MM = 24.0
DEFAULT_STEP_SPEED_MM_S = 20.0
DEFAULT_SETTLE_DELAY_S = 0.1
DEFAULT_PROBE_OFFSET_MM = 0.0
DEFAULT_PROBE_POINT_SPACING_MM = 123.0
DEFAULT_PROBE_POINT_HALF_SPACING_MM = DEFAULT_PROBE_POINT_SPACING_MM / 2.0


@dataclass(frozen=True)
class ProbeOffsetPreset:
    label: str
    offset_mm: tuple[float, float] | None


@dataclass(frozen=True)
class ScanSetupFormState:
    start_ghz: float
    stop_ghz: float
    frequency_step_mhz: float
    vna_power_dbm: float
    if_bandwidth_hz: float
    parameter: str
    scan_mode: str
    x_start_mm: float
    x_stop_mm: float
    y_start_mm: float
    y_stop_mm: float
    step_x_mm: float
    step_y_mm: float
    step_x_turns: float
    step_y_turns: float
    x_mm_per_turn: float
    y_mm_per_turn: float
    step_speed_mm_s: float
    settle_delay_s: float
    probe_offset_preset: str
    probe_x_offset_mm: float
    probe_y_offset_mm: float
    continuous_speed_mm_s: float


class ScanSetupViewModel:
    def build_settings(self, state: ScanSetupFormState) -> dict:
        is_step_mode = state.scan_mode == "step"
        step_x_mm = state.step_x_mm if is_step_mode else self.computed_step_distance_mm(state, "X")
        step_y_mm = state.step_y_mm if is_step_mode else self.computed_step_distance_mm(state, "Y")
        settings = ScanSettings.from_mapping(
            {
                "start_ghz": state.start_ghz,
                "stop_ghz": state.stop_ghz,
                "frequency_step_mhz": state.frequency_step_mhz,
                "points": self.sweep_points(state),
                "vna_power_dbm": state.vna_power_dbm,
                "if_bandwidth_hz": state.if_bandwidth_hz,
                "parameter": state.parameter,
                "scan_mode": state.scan_mode,
                "x_start_mm": state.x_start_mm,
                "x_stop_mm": state.x_stop_mm,
                "y_start_mm": state.y_start_mm,
                "y_stop_mm": state.y_stop_mm,
                "step_input_mode": "bidirectional",
                "step_x_mm": step_x_mm,
                "step_y_mm": step_y_mm,
                "step_x_turns": state.step_x_turns,
                "step_y_turns": state.step_y_turns,
                "x_mm_per_turn": state.x_mm_per_turn,
                "y_mm_per_turn": state.y_mm_per_turn,
                "step_speed_mm_s": state.step_speed_mm_s,
                "settle_delay_s": state.settle_delay_s,
                "probe_offset_preset": state.probe_offset_preset,
                "probe_x_offset_mm": state.probe_x_offset_mm,
                "probe_y_offset_mm": state.probe_y_offset_mm,
                "continuous_speed_mm_s": state.continuous_speed_mm_s,
            }
        )
        return settings.to_dict()

    @staticmethod
    def probe_offset_presets() -> tuple[ProbeOffsetPreset, ...]:
        offset = DEFAULT_PROBE_POINT_HALF_SPACING_MM
        return (
            ProbeOffsetPreset("右上", (-offset, -offset)),
            ProbeOffsetPreset("左上", (-offset, offset)),
            ProbeOffsetPreset("右下", (offset, -offset)),
            ProbeOffsetPreset("左下", (offset, offset)),
            ProbeOffsetPreset("自定义", None),
        )

    @staticmethod
    def computed_step_distance_mm(state: ScanSetupFormState, axis: str) -> float:
        if axis.upper() == "Y":
            if state.scan_mode == "continuous":
                return state.y_mm_per_turn
            return state.step_y_turns * state.y_mm_per_turn
        if state.scan_mode == "continuous":
            return state.x_mm_per_turn
        return state.step_x_turns * state.x_mm_per_turn

    @staticmethod
    def turns_from_step_distance(step_mm: float, mm_per_turn: float) -> float:
        return float(step_mm) / float(mm_per_turn)

    @staticmethod
    def sweep_points(state: ScanSetupFormState) -> int:
        return calculate_sweep_points(state.start_ghz, state.stop_ghz, state.frequency_step_mhz)
