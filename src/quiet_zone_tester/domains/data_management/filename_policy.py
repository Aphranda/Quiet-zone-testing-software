from __future__ import annotations

from datetime import datetime


class FilenamePolicy:
    """Build filesystem-safe names for scan folders and trace CSV files."""

    INVALID_FILENAME_CHARS = '<>:"/\\|?*'

    def safe_part(self, value: object) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        cleaned = "".join("_" if char in self.INVALID_FILENAME_CHARS or char.isspace() else char for char in text)
        cleaned = cleaned.strip("._")
        return cleaned[:80]

    def position_parts(self, position_mm: tuple[float, float] | None) -> tuple[str, str]:
        if position_mm is None:
            return "Xunknown", "Yunknown"
        return f"X{position_mm[0]:.3f}", f"Y{position_mm[1]:.3f}"

    def probe_offset_tag_from_settings(self, settings: dict) -> str:
        if "probe_x_offset_mm" not in settings and "probe_y_offset_mm" not in settings:
            return ""

        preset = str(settings.get("probe_offset_preset", "")).strip() or "custom"
        x_offset_mm = float(settings.get("probe_x_offset_mm", 0.0))
        y_offset_mm = float(settings.get("probe_y_offset_mm", 0.0))
        return f"probe_{preset}_X{x_offset_mm:+.3f}_Y{y_offset_mm:+.3f}"

    def trace_filename(
        self,
        *,
        parameter: str,
        position_mm: tuple[float, float] | None,
        scan_mode: str,
        file_flag: str = "",
        filename_tag: str = "",
        point_index: int | None = None,
        timestamp: datetime | None = None,
    ) -> str:
        timestamp = timestamp or datetime.now()
        timestamp_text = timestamp.strftime("%Y%m%d_%H%M%S_%f")
        x_text, y_text = self.position_parts(position_mm)
        flag_text = self.safe_part(file_flag) or "NOFLAG"
        tag_text = self.safe_part(filename_tag)
        mode_text = self.safe_part(scan_mode) or "test"
        parameter_text = self.safe_part(parameter) or "S"
        point_text = f"_P{point_index:04d}" if point_index is not None else ""
        tag_part = f"_{tag_text}" if tag_text else ""
        return f"{flag_text}{tag_part}_{x_text}_{y_text}_{timestamp_text}_{mode_text}_{parameter_text}{point_text}.csv"

    def scan_folder_name(self, *, settings: dict, scan_mode: str, timestamp: datetime | None = None) -> str:
        timestamp = timestamp or datetime.now()
        timestamp_text = timestamp.strftime("%Y%m%d_%H%M%S")
        flag_text = self.safe_part(str(settings.get("file_flag", ""))) or "NOFLAG"
        probe_text = self.safe_part(self.probe_offset_tag_from_settings(settings))
        mode_text = self.safe_part(scan_mode) or "scan"
        parameter_text = self.safe_part(str(settings.get("parameter", ""))) or "S"
        probe_part = f"_{probe_text}" if probe_text else ""
        return f"{timestamp_text}_{flag_text}{probe_part}_{mode_text}_{parameter_text}"
