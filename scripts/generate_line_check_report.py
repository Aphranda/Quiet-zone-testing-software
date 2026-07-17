from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from html import escape
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

BAD = "\u5efa\u8bae\u91cd\u6d4b"
WARN = "\u5173\u6ce8/\u590d\u6838"
OK = "\u6b63\u5e38"
TEST_TIME = "\u6d4b\u8bd5\u65f6\u95f4"


@dataclass
class ScanData:
    folder: str
    flag: str
    probe: str
    xy_mm: np.ndarray
    freqs_ghz: np.ndarray
    magnitude_db: np.ndarray
    phase_deg: np.ndarray
    index_points: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate line-scan quiet-zone diagnostic report.")
    script_dir = Path(__file__).resolve().parent
    project_dir = script_dir.parent
    parser.add_argument("--input", default=str(project_dir / "test_results"), help="Directory containing *_step_S21 folders.")
    parser.add_argument("--output", default=None, help="Output directory. Defaults to input/analysis_line_check_0714.")
    parser.add_argument("--report", default="line_check_report_0714.html", help="HTML report filename under input directory.")
    parser.add_argument("--expected-points", type=int, default=161)
    parser.add_argument("--phase-limit-mm", type=float, default=510.0, help="Ignore phase positions above this absolute coordinate.")
    parser.add_argument("--taper-limit-db", type=float, default=1.5)
    parser.add_argument("--ripple-limit-db", type=float, default=1.0, help="Centered +/- ripple limit.")
    parser.add_argument("--phase-limit-deg", type=float, default=10.0)
    parser.add_argument("--include-incomplete", action="store_true", default=True, help="Include incomplete/live scans in report.")
    return parser.parse_args()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def parse_offset(folder_name: str) -> tuple[float, float]:
    match = re.search(r"_X([+-]\d+(?:\.\d+)?)_Y([+-]\d+(?:\.\d+)?)_step_", folder_name)
    if not match:
        return 0.0, 0.0
    return float(match.group(1)), float(match.group(2))


def parse_probe(folder_name: str) -> str:
    match = re.search(r"_probe_([^_]+)_X", folder_name)
    return match.group(1) if match else ""


def parse_test_time(folder_name: str) -> str:
    match = re.match(r"^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})_", folder_name)
    if not match:
        return ""
    year, month, day, hour, minute, second = match.groups()
    return f"{year}-{month}-{day} {hour}:{minute}:{second}"


def safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_")[:150]


def load_scan_folder(folder: Path) -> ScanData | None:
    index_path = folder / "trace_index.csv"
    if not index_path.exists():
        return None
    index_rows = read_csv_rows(index_path)
    if not index_rows:
        return None

    offset_x, offset_y = parse_offset(folder.name)
    points: list[tuple[float, float]] = []
    magnitudes: list[np.ndarray] = []
    phases: list[np.ndarray] = []
    freqs_ghz: np.ndarray | None = None

    for row in index_rows:
        trace_path = folder / row.get("filename", "")
        if not trace_path.exists():
            continue
        trace_rows = read_csv_rows(trace_path)
        if not trace_rows:
            continue

        current_freqs = np.array([float(item["frequency_hz"]) / 1e9 for item in trace_rows], dtype=float)
        if freqs_ghz is None:
            freqs_ghz = current_freqs
        elif len(freqs_ghz) != len(current_freqs) or not np.allclose(freqs_ghz, current_freqs):
            continue

        x_abs = float(row["x_mm"]) + offset_x + 61.5
        y_abs = float(row["y_mm"]) + offset_y + 61.5
        points.append((x_abs, y_abs))
        magnitudes.append(np.array([float(item["magnitude_db"]) for item in trace_rows], dtype=float))
        phases.append(np.array([float(item["phase_deg"]) for item in trace_rows], dtype=float))

    if freqs_ghz is None or not points:
        return None

    return ScanData(
        folder=folder.name,
        flag=index_rows[0].get("flag", ""),
        probe=parse_probe(folder.name),
        xy_mm=np.array(points, dtype=float),
        freqs_ghz=freqs_ghz,
        magnitude_db=np.vstack(magnitudes),
        phase_deg=np.vstack(phases),
        index_points=len(index_rows),
    )


def analyze_scan(
    data: ScanData,
    plots_dir: Path,
    root: Path,
    expected_points: int,
    phase_position_limit_mm: float,
    taper_limit_db: float,
    ripple_limit_db: float,
    phase_limit_deg: float,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    parts = data.flag.split("-")
    pol = parts[0] if len(parts) > 0 else ""
    axis = parts[1] if len(parts) > 1 else ""
    label = parts[2] if len(parts) > 2 else ""

    position = data.xy_mm[:, 0] if axis == "X" else data.xy_mm[:, 1]
    fixed = data.xy_mm[:, 1] if axis == "X" else data.xy_mm[:, 0]
    order = np.argsort(position)
    position = position[order]
    magnitude = data.magnitude_db[order, :]
    phase = data.phase_deg[order, :]

    actual_points = len(position)
    freq_count = phase.shape[1]
    complete_ok = actual_points >= expected_points

    phase_mask = position <= phase_position_limit_mm + 1e-9
    if int(phase_mask.sum()) < 3:
        phase_mask = np.ones_like(position, dtype=bool)
    phase_position = position[phase_mask]
    phase_ref_index = int(np.argmin(np.abs(phase_position - (phase_position.min() + phase_position.max()) / 2.0)))

    taper_values: list[float] = []
    ripple_values: list[float] = []
    phase_values: list[float] = []
    phase_positions: list[float] = []
    mag_profiles: list[np.ndarray] = []
    phase_profiles: list[np.ndarray] = []
    metric_rows: list[dict[str, object]] = []
    taper_fail = 0
    ripple_fail = 0
    phase_fail = 0

    for index, freq in enumerate(data.freqs_ghz):
        mag_line = magnitude[:, index]
        mag_fit = np.polyfit(position, mag_line, 1)
        mag_trend = np.polyval(mag_fit, position)
        mag_ref_index = int(np.argmin(np.abs(position - (position.min() + position.max()) / 2.0)))
        taper = mag_trend - mag_trend[mag_ref_index]
        raw_residual = mag_line - mag_trend
        residual_center = (float(raw_residual.max()) + float(raw_residual.min())) / 2.0
        centered_residual = raw_residual - residual_center

        taper_max = float(np.max(np.abs(taper)))
        ripple_plus_minus = float(np.max(np.abs(centered_residual)))
        ripple_peak_to_peak = float(raw_residual.max() - raw_residual.min())
        taper_values.append(taper_max)
        ripple_values.append(ripple_plus_minus)
        taper_fail += int(taper_max > taper_limit_db)
        ripple_fail += int(ripple_plus_minus > ripple_limit_db)

        phase_unwrapped = np.unwrap(np.deg2rad(phase[:, index])) * 180.0 / np.pi
        phase_eval = phase_unwrapped[phase_mask]
        phase_eval = phase_eval - phase_eval[phase_ref_index]
        phase_fit = np.polyfit(phase_position, phase_eval, 1)
        phase_residual = phase_eval - np.polyval(phase_fit, phase_position)
        worst_index = int(np.argmax(np.abs(phase_residual)))
        phase_worst = float(abs(phase_residual[worst_index]))
        phase_values.append(phase_worst)
        phase_positions.append(float(phase_position[worst_index]))
        phase_profiles.append(phase_residual)
        mag_profiles.append(centered_residual)
        phase_fail += int(phase_worst >= phase_limit_deg)

        metric_rows.append(
            {
                "folder": data.folder,
                "test_time": parse_test_time(data.folder),
                "flag": data.flag,
                "pol": pol,
                "axis": axis,
                "label": label,
                "probe": data.probe,
                "expected_points": expected_points,
                "index_points": data.index_points,
                "actual_points": actual_points,
                "missing_files": max(0, data.index_points - actual_points),
                "freq_count_min": freq_count,
                "freq_count_max": freq_count,
                "fixed_mm": float(np.median(fixed)),
                "position_min_mm": float(position.min()),
                "position_max_mm": float(position.max()),
                "complete_ok": bool(complete_ok),
                "target_frequency_ghz": float(freq),
                "point_count": actual_points,
                "phase_eval_point_count": int(phase_mask.sum()),
                "phase_limit_pos_mm": phase_position_limit_mm,
                "reference_position_mm": float(phase_position[phase_ref_index]),
                "taper_max_abs_db": taper_max,
                "ripple_center_offset_db": residual_center,
                "ripple_plus_minus_db": ripple_plus_minus,
                "ripple_peak_to_peak_db": ripple_peak_to_peak,
                "phase_max_abs_deg": phase_worst,
                "amp_span_db": float(mag_line.max() - mag_line.min()),
                "phase_worst_position_mm": float(phase_position[worst_index]),
                "phase_worst_signed_deg": float(phase_residual[worst_index]),
            }
        )

    worst_phase_index = int(np.argmax(phase_values))
    taper_worst = float(max(taper_values))
    ripple_worst = float(max(ripple_values))
    phase_worst = float(max(phase_values))
    if (not complete_ok) or phase_fail >= 10 or phase_worst >= 12.0:
        recommendation = BAD
    elif phase_fail > 0 or ripple_fail > 0 or taper_fail > 0 or phase_worst >= 7.0:
        recommendation = WARN
    else:
        recommendation = OK

    base_name = safe_name(data.folder)
    phase_tag = f"{phase_position_limit_mm:.0f}phase"
    summary_png = plots_dir / f"{base_name}_summary_{phase_tag}_centered_ripple.png"
    profile_png = plots_dir / f"{base_name}_worst_profile_{phase_tag}_centered_ripple.png"

    fig, axes = plt.subplots(3, 1, figsize=(8.6, 7.0), sharex=True)
    axes[0].plot(data.freqs_ghz, taper_values, color="#1F3864")
    axes[0].axhline(taper_limit_db, color="#c62828", linestyle="--")
    axes[0].set_ylabel("Taper dB")
    axes[0].grid(True, alpha=0.25)
    axes[1].plot(data.freqs_ghz, ripple_values, color="#2e7d32")
    axes[1].axhline(ripple_limit_db, color="#c62828", linestyle="--")
    axes[1].set_ylabel("Ripple +/- dB")
    axes[1].grid(True, alpha=0.25)
    axes[2].plot(data.freqs_ghz, phase_values, color="#6a1b9a")
    axes[2].axhline(phase_limit_deg, color="#c62828", linestyle="--")
    axes[2].set_ylabel("Phase deg")
    axes[2].set_xlabel("Frequency GHz")
    axes[2].grid(True, alpha=0.25)
    fig.suptitle(f"{data.flag} {data.probe} phase <= {phase_position_limit_mm:.0f} mm, centered ripple")
    fig.tight_layout()
    fig.savefig(summary_png, dpi=150)
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(8.6, 5.6))
    axes[0].plot(position, mag_profiles[worst_phase_index], color="#1F3864")
    axes[0].axhline(0, color="#777", linewidth=0.8)
    axes[0].axhline(ripple_limit_db, color="#c62828", linestyle="--")
    axes[0].axhline(-ripple_limit_db, color="#c62828", linestyle="--")
    axes[0].set_ylabel("Centered mag residual dB")
    axes[0].grid(True, alpha=0.25)
    axes[1].plot(phase_position, phase_profiles[worst_phase_index], color="#6a1b9a")
    axes[1].axhline(phase_limit_deg, color="#c62828", linestyle="--")
    axes[1].axhline(-phase_limit_deg, color="#c62828", linestyle="--")
    axes[1].set_xlabel("Position mm")
    axes[1].set_ylabel("Phase residual deg")
    axes[1].grid(True, alpha=0.25)
    fig.suptitle(f"Worst phase freq {data.freqs_ghz[worst_phase_index]:.1f} GHz ({data.flag} {data.probe})")
    fig.tight_layout()
    fig.savefig(profile_png, dpi=150)
    plt.close(fig)

    summary = {
        "folder": data.folder,
        "test_time": parse_test_time(data.folder),
        "flag": data.flag,
        "pol": pol,
        "axis": axis,
        "label": label,
        "probe": data.probe,
        "expected_points": expected_points,
        "index_points": data.index_points,
        "actual_points": actual_points,
        "missing_files": max(0, data.index_points - actual_points),
        "freq_count_min": freq_count,
        "freq_count_max": freq_count,
        "fixed_mm": float(np.median(fixed)),
        "position_min_mm": float(position.min()),
        "position_max_mm": float(position.max()),
        "complete_ok": bool(complete_ok),
        "freq_count": freq_count,
        "taper_worst": taper_worst,
        "ripple_worst": ripple_worst,
        "phase_worst": phase_worst,
        "phase_fail_count": int(phase_fail),
        "ripple_fail_count": int(ripple_fail),
        "taper_fail_count": int(taper_fail),
        "worst_phase_freq": float(data.freqs_ghz[worst_phase_index]),
        "worst_phase_pos": float(phase_positions[worst_phase_index]),
        "phase_limit_pos_mm": phase_position_limit_mm,
        "summary_png": str(summary_png.relative_to(root)).replace("\\", "/"),
        "profile_png": str(profile_png.relative_to(root)).replace("\\", "/"),
        "recommendation": recommendation,
    }
    return summary, metric_rows


def write_heatmap(summaries: list[dict[str, object]], metrics: list[dict[str, object]], plots_dir: Path) -> None:
    heat_rows: list[list[float]] = []
    labels: list[str] = []
    for summary in summaries:
        rows = [row for row in metrics if row["folder"] == summary["folder"]]
        rows.sort(key=lambda row: float(row["target_frequency_ghz"]))
        if rows:
            heat_rows.append([float(row["phase_max_abs_deg"]) for row in rows])
            labels.append(f"{summary['flag']} {summary['probe']}")
    if not heat_rows:
        return
    heat = np.array(heat_rows, dtype=float)
    first_rows = [row for row in metrics if row["folder"] == summaries[0]["folder"]]
    first_rows.sort(key=lambda row: float(row["target_frequency_ghz"]))
    freqs = np.array([float(row["target_frequency_ghz"]) for row in first_rows])

    fig, ax = plt.subplots(figsize=(10.5, max(4.2, 0.34 * len(labels) + 1.8)))
    image = ax.imshow(heat, aspect="auto", cmap="magma", vmin=0, vmax=max(10.0, float(np.nanmax(heat))))
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    xticks = np.linspace(0, len(freqs) - 1, min(11, len(freqs)), dtype=int)
    ax.set_xticks(xticks)
    ax.set_xticklabels([f"{freqs[index]:.1f}" for index in xticks], fontsize=8)
    ax.set_xlabel("Frequency GHz")
    ax.set_title("Phase residual heatmap")
    colorbar = fig.colorbar(image, ax=ax, shrink=0.92)
    colorbar.set_label("deg")
    fig.tight_layout()
    fig.savefig(plots_dir / "phase_heatmap_by_line.png", dpi=160)
    plt.close(fig)


def fmt(value: object, digits: int = 1) -> str:
    return f"{float(value):.{digits}f}"


def write_html_report(report_path: Path, root: Path, summaries: list[dict[str, object]], counts: dict[str, int]) -> None:
    cls = {BAD: "bad", WARN: "warn", OK: "ok"}
    phase_limit_label = fmt(summaries[0]["phase_limit_pos_mm"], 0) if summaries else ""
    body_rows: list[str] = []
    cards: list[str] = []
    for row in summaries:
        rec = str(row["recommendation"])
        body_rows.append(
            f'<tr><td><span class="tag {cls[rec]}">{escape(rec)}</span></td>'
            f'<td>{escape(str(row["test_time"]))}</td><td>{escape(str(row["flag"]))}</td><td>{escape(str(row["probe"]))}</td>'
            f'<td>{fmt(row["fixed_mm"], 1)}</td><td>{fmt(row["position_min_mm"], 1)}-{fmt(row["position_max_mm"], 1)}</td>'
            f'<td class="c">{row["actual_points"]}/{row["expected_points"]}</td><td class="c">{row["freq_count"]}</td>'
            f'<td class="c">{fmt(row["taper_worst"], 2)}</td><td class="c">{fmt(row["ripple_worst"], 2)}</td>'
            f'<td class="c">{fmt(row["phase_worst"], 2)}</td><td class="c">{row["phase_fail_count"]}</td>'
            f'<td class="c">{row["ripple_fail_count"]}</td><td>{fmt(row["worst_phase_freq"], 1)} GHz / {fmt(row["worst_phase_pos"], 1)} mm</td></tr>'
        )
        cards.append(
            f'<div class="card"><h2><span class="tag {cls[rec]}">{escape(rec)}</span> {escape(str(row["flag"]))} / {escape(str(row["probe"]))}</h2>'
            f'<p class="meta">Test time {escape(str(row["test_time"]))}; Fixed {fmt(row["fixed_mm"], 1)} mm; '
            f'points {row["actual_points"]}/{row["expected_points"]}; phase evaluated &lt;= {fmt(row["phase_limit_pos_mm"], 0)} mm; '
            f'worst phase {fmt(row["phase_worst"], 2)} deg @ {fmt(row["worst_phase_freq"], 1)} GHz / {fmt(row["worst_phase_pos"], 1)} mm; '
            f'worst ripple +/- {fmt(row["ripple_worst"], 2)} dB.</p><div class="grid">'
            f'<figure><img src="{escape(str(row["summary_png"]))}"><figcaption>Metrics vs frequency.</figcaption></figure>'
            f'<figure><img src="{escape(str(row["profile_png"]))}"><figcaption>Worst-frequency line profile.</figcaption></figure>'
            '</div></div>'
        )

    html = f'''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><title>Line Scan Diagnostic Report</title><style>
body{{font-family:"Microsoft YaHei",Arial,sans-serif;background:#d0d0d0;margin:0;padding:18px;color:#1a1a1a}}
.page{{background:#fff;max-width:1240px;margin:0 auto 18px;padding:26px 34px;box-shadow:0 2px 8px rgba(0,0,0,.15)}}
h1{{font-size:28px;margin:0 0 8px}} h2{{font-size:18px;margin:8px 0 8px}} .sub,.meta{{color:#555;font-size:13px;line-height:1.55}}
table{{width:100%;border-collapse:collapse;font-size:12px;margin:14px 0}} th{{background:#1F3864;color:white;padding:7px;text-align:left}} td{{border:1px solid #bbb;padding:6px 7px;vertical-align:top}} tbody tr:nth-child(even) td{{background:#f4f7fb}}
.c{{text-align:center}} .tag{{display:inline-block;color:white;border-radius:3px;padding:2px 8px;font-size:12px;font-weight:700;white-space:nowrap}} .bad{{background:#c62828}} .warn{{background:#f57c00}} .ok{{background:#2e7d32}}
.summary{{display:flex;gap:12px;margin:14px 0}} .badge{{flex:1;color:white;border-radius:5px;text-align:center;padding:12px 8px;font-weight:700}} .badge span{{display:block;font-size:24px}} .b1{{background:#c62828}} .b2{{background:#f57c00}} .b3{{background:#2e7d32}} .b4{{background:#1565c0}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}} figure{{margin:0;border:1px solid #ddd;background:#fafafa;padding:6px}} img{{max-width:100%;display:block;margin:0 auto}} figcaption{{font-size:11px;color:#555;margin-top:4px;text-align:center}}
.card{{border-top:5px solid #1F3864;margin-top:18px;padding-top:12px}} .note{{border-left:4px solid #1F3864;background:#f5f8fd;padding:10px 12px;font-size:13px;line-height:1.6;margin:12px 0}}
</style></head><body><div class="page"><h1>Line Scan Diagnostic Report</h1>
<div class="sub">Data: {escape(str(root))}. Frequency range 22-32 GHz, 100 MHz step. Each line is evaluated independently for amplitude taper, centered ripple residual, and phase residual after removing linear phase slope.</div>
<div class="summary"><div class="badge b1"><span>{counts[BAD]}</span>{BAD}</div><div class="badge b2"><span>{counts[WARN]}</span>{WARN}</div><div class="badge b3"><span>{counts[OK]}</span>{OK}</div><div class="badge b4"><span>{len(summaries)}</span>Groups</div></div>
<div class="note">Criteria: taper &lt;= +/-1.5 dB, centered ripple &lt;= +/-1 dB, phase residual &lt; +/-10 deg. Ripple is evaluated after removing linear trend and shifting the residual center to (max+min)/2, then taking max absolute deviation. Phase is evaluated up to {phase_limit_label} mm for the Decision column.</div>
<table><thead><tr><th>Decision</th><th>{TEST_TIME}</th><th>Line</th><th>Probe</th><th>Fixed/mm</th><th>Range/mm</th><th class="c">Points</th><th class="c">Freqs</th><th class="c">Taper/dB</th><th class="c">Ripple +/-dB</th><th class="c">Phase/deg<br><span style="font-weight:400">&lt;={phase_limit_label}mm</span></th><th class="c">Phase Fail</th><th class="c">Ripple Fail</th><th>Worst Phase Location<br><span style="font-weight:400">&lt;={phase_limit_label}mm</span></th></tr></thead><tbody>{''.join(body_rows)}</tbody></table>
<h2>Phase Heatmap</h2><figure><img src="analysis_line_check_0714/plots/phase_heatmap_by_line.png"><figcaption>Phase residual heatmap by measured line.</figcaption></figure></div>
<div class="page"><h1>Per-line Details</h1>{''.join(cards)}</div></body></html>'''
    report_path.write_text(html, encoding="utf-8")


def main() -> None:
    args = parse_args()
    root = Path(args.input).resolve()
    output = Path(args.output).resolve() if args.output else root / "analysis_line_check_0714"
    plots_dir = output / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    summaries: list[dict[str, object]] = []
    metrics: list[dict[str, object]] = []
    for folder in sorted(root.glob("*_step_S21")):
        if folder.name.startswith("NO_USE_"):
            continue
        data = load_scan_folder(folder)
        if data is None:
            continue
        summary, metric_rows = analyze_scan(
            data,
            plots_dir,
            root,
            args.expected_points,
            args.phase_limit_mm,
            args.taper_limit_db,
            args.ripple_limit_db,
            args.phase_limit_deg,
        )
        summaries.append(summary)
        metrics.extend(metric_rows)

    if not summaries:
        raise SystemExit(f"No *_step_S21 scans found in {root}")

    rank = {BAD: 0, WARN: 1, OK: 2}
    summaries.sort(key=lambda row: (rank.get(str(row["recommendation"]), 9), -float(row["phase_worst"]), -float(row["ripple_worst"]), str(row["flag"]), str(row["probe"])))

    write_csv(output / "line_summary.csv", summaries, list(summaries[0].keys()))
    write_csv(output / "line_metrics_100MHz.csv", metrics, list(metrics[0].keys()))
    write_heatmap(summaries, metrics, plots_dir)

    counts = {BAD: 0, WARN: 0, OK: 0}
    for row in summaries:
        counts[str(row["recommendation"])] += 1
    write_html_report(root / args.report, root, summaries, counts)

    print(f"Report: {root / args.report}")
    print(f"Summary: {output / 'line_summary.csv'}")
    print(f"Groups: {len(summaries)} | {BAD}: {counts[BAD]} | {WARN}: {counts[WARN]} | {OK}: {counts[OK]}")


if __name__ == "__main__":
    main()

