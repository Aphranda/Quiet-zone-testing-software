from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


DEFAULT_FEED_HORN_BANDS: dict[tuple[str, str], str] = {
    ("F10_17G", "H10_15G"): "10_15G",
    ("F10_17G", "H14P5_22G"): "14P5_17G",
    ("F17_31G", "H14P5_22G"): "17_22G",
    ("F17_31G", "H21P7_33G"): "21P7_31G",
}
FEED_HORN_BANDS = DEFAULT_FEED_HORN_BANDS


@dataclass(frozen=True)
class LossFilePolicy:
    extension: str = ".csv"
    feed_horn_bands: Mapping[tuple[str, str], str] = field(default_factory=lambda: dict(DEFAULT_FEED_HORN_BANDS))

    @classmethod
    def from_band_config(cls, band_config: Mapping[str, Any] | None) -> "LossFilePolicy":
        return cls(feed_horn_bands=feed_horn_bands_from_config(band_config))

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
            return self.feed_horn_bands[(feed, horn)]
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


def feed_horn_bands_from_config(band_config: Mapping[str, Any] | None) -> dict[tuple[str, str], str]:
    entries = band_entries_from_config(band_config)
    return {(entry["feed"], entry["horn"]): entry["band"] for entry in entries}


def band_entries_from_config(band_config: Mapping[str, Any] | None) -> tuple[dict[str, Any], ...]:
    entries = (band_config or {}).get("feed_horn_bands", ()) if isinstance(band_config, Mapping) else ()
    if not entries:
        return tuple(
            {"feed": feed, "horn": horn, "band": band}
            for (feed, horn), band in sorted(DEFAULT_FEED_HORN_BANDS.items())
        )

    result: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        feed = str(entry.get("feed", "")).strip().upper()
        horn = str(entry.get("horn", "")).strip().upper()
        band = str(entry.get("band", "")).strip().upper()
        if not feed or not horn or not band:
            continue
        normalized: dict[str, Any] = {"feed": feed, "horn": horn, "band": band}
        for key in ("start_ghz", "stop_ghz"):
            if key in entry:
                normalized[key] = float(entry[key])
        if entry.get("horn_gain_file"):
            normalized["horn_gain_file"] = str(entry["horn_gain_file"]).strip()
        result.append(normalized)
    return tuple(result) or band_entries_from_config(None)


def default_feed_horn_from_config(band_config: Mapping[str, Any] | None) -> tuple[str, str]:
    entries = band_entries_from_config(band_config)
    default_feed = str((band_config or {}).get("default_feed", "")).strip().upper() if isinstance(band_config, Mapping) else ""
    default_horn = str((band_config or {}).get("default_horn", "")).strip().upper() if isinstance(band_config, Mapping) else ""
    if default_feed and default_horn and any(
        entry["feed"] == default_feed and entry["horn"] == default_horn for entry in entries
    ):
        return default_feed, default_horn
    first = entries[0]
    return str(first["feed"]), str(first["horn"])
