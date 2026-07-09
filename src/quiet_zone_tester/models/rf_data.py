from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SParameterTrace:
    frequency_hz: np.ndarray
    complex_values: np.ndarray
    parameter: str = "S21"

    def __post_init__(self) -> None:
        if self.frequency_hz.ndim != 1 or self.complex_values.ndim != 1:
            raise ValueError("S-parameter trace arrays must be one-dimensional.")
        if self.frequency_hz.shape != self.complex_values.shape:
            raise ValueError("Frequency and S-parameter arrays must have identical shape.")
        if self.frequency_hz.size == 0:
            raise ValueError("S-parameter trace cannot be empty.")

    @property
    def magnitude_db(self) -> np.ndarray:
        return 20.0 * np.log10(np.maximum(np.abs(self.complex_values), 1e-15))

    @property
    def phase_deg(self) -> np.ndarray:
        return np.rad2deg(np.unwrap(np.angle(self.complex_values)))

    @property
    def frequency_ghz(self) -> np.ndarray:
        return self.frequency_hz / 1e9
