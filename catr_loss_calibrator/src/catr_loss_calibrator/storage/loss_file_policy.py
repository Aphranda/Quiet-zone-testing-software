from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


FEED_HORN_BANDS: dict[tuple[str, str], str] = {
    ("F10_17G", "H10_15G"): "10_15G",
    ("F10_17G", "H14P5_22G"): "14P5_17G",
    ("F17_31G", "H14P5_22G"): "17_22G",
    ("F17_31G", "H21P7_33G"): "21P7_31G",
}


@dataclass(frozen=True)
class LossFilePolicy:
    extension: str = ".csv"

    def validate_feed_horn(self, feed: str, horn: str, *, nohorn_band: str | None = None) -> tuple[str, str, str]:
        normalized_feed = feed.strip().upper()
        normalized_horn = horn.strip().upper()
        band = self.band_for(normalized_feed, normalized_horn, nohorn_band=nohorn_band)
        return normalized_feed, normalized_horn, band

    def band_for(self, feed: str, horn: str, *, nohorn_band: str | None = None) -> str:
        feed = feed.strip().upper()
        horn = horn.strip().upper()
        if horn == "NOHORN":
            if not nohorn_band:
                raise ValueError("nohorn_band is required when horn is NOHORN.")
            return nohorn_band.strip().upper()
        try:
            return FEED_HORN_BANDS[(feed, horn)]
        except KeyError as exc:
            raise ValueError(f"No valid band intersection for feed={feed}, horn={horn}.") from exc

    def filename(self, *, param: str, band: str, feed: str, horn: str) -> str:
        parts = [param.strip().upper(), band.strip().upper(), feed.strip().upper(), horn.strip().upper()]
        if any(not part for part in parts):
            raise ValueError("param, band, feed, and horn are required.")
        return "_".join(parts) + self.extension

    def filename_for(self, *, param: str, feed: str, horn: str, nohorn_band: str | None = None) -> str:
        normalized_feed, normalized_horn, band = self.validate_feed_horn(feed, horn, nohorn_band=nohorn_band)
        return self.filename(param=param, band=band, feed=normalized_feed, horn=normalized_horn)

    def path_for(self, root: Path, *, param: str, feed: str, horn: str, nohorn_band: str | None = None) -> Path:
        return root / self.filename_for(param=param, feed=feed, horn=horn, nohorn_band=nohorn_band)
