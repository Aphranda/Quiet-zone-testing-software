from __future__ import annotations

from math import floor


DEFAULT_FREQUENCY_STEP_MHZ = 100.0


def calculate_sweep_points(start_ghz: float, stop_ghz: float, step_mhz: float = DEFAULT_FREQUENCY_STEP_MHZ) -> int:
    span_mhz = abs(float(stop_ghz) - float(start_ghz)) * 1000.0
    step_mhz = max(float(step_mhz), 1e-9)
    return max(2, int(floor(span_mhz / step_mhz)) + 1)
