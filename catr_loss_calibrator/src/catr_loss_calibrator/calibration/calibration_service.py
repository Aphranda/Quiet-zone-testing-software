from __future__ import annotations

from catr_loss_calibrator.calibration.definitions import default_calibration_catalog
from catr_loss_calibrator.calibration.models import CalibrationCatalog


class CalibrationService:
    def catalog(self) -> CalibrationCatalog:
        return default_calibration_catalog()

