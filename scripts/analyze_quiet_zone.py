from __future__ import annotations

import argparse
import csv
import shutil
from dataclasses import dataclass
from html import escape
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


@dataclass(frozen=True)
class TracePoint:
    x_mm: float
    y_mm: float
    point_index: int
    source_file: str


@dataclass(frozen=True)
class QuietZoneData:
    points: list[TracePoint]
    frequency_hz: np.ndarray
    magnitude_db: np.ndarray
    phase_deg: np.ndarray

    @property
    def positions_mm(self) -> np.ndarray:
        return np.array([(point.x_mm, point.y_mm) for point in self.points], dtype=float)


@dataclass(frozen=True)
class PointMetrics:
    mean_magnitude_db: np.ndarray
    band_ripple_db: np.ndarray
    max_deviation_from_spatial_mean_db: np.ndarray


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze quiet-zone VNA CSV data.")
    parser.add_argument("--input", default="test_results", help="Input directory containing saved CSV files.")
    parser.add_argument("--output", default=None, help="Output directory. Defaults to the input directory.")
    parser.add_argument("--pattern", default="*_step_*.csv", help="CSV glob pattern to analyze.")
    parser.add_argument("--center-x-min", type=float, default=50.0)
    parser.add_argument("--center-x-max", type=float, default=250.0)
    parser.add_argument("--center-y-min", type=float, default=100.0)
    parser.add_argument("--center-y-max", type=float, default=200.0)
    parser.add_argument("--center-point-x", type=float, default=200.0, help="X coordinate for center envelope plot.")
    parser.add_argument("--center-point-y", type=float, default=200.0, help="Y coordinate for center envelope plot.")
    parser.add_argument("--edge-point-x", type=float, default=0.0, help="X coordinate for edge envelope plot.")
    parser.add_argument("--edge-point-y", type=float, default=0.0, help="Y coordinate for edge envelope plot.")
    parser.add_argument(
        "--template-dir",
        default=r"E:\OneDrive\4.Code\STM32\PinProbeA1\STM32F103RCT6_PinprobeA1\Doc\model",
        help="Directory containing the GTS report template assets.",
    )
    return parser.parse_args()


def load_quiet_zone_data(input_dir: Path, pattern: str) -> QuietZoneData:
    files = sorted(input_dir.glob(pattern))
    if not files:
        raise SystemExit(f"No CSV files matched: {input_dir / pattern}")

    points: list[TracePoint] = []
    frequency_hz: np.ndarray | None = None
    magnitude_rows: list[np.ndarray] = []
    phase_rows: list[np.ndarray] = []

    for path in files:
        rows = _read_csv_rows(path)
        if not rows:
            continue

        first = rows[0]
        x_mm = float(first["x_mm"])
        y_mm = float(first["y_mm"])
        point_index = int(first["point_index"]) if first.get("point_index") else len(points) + 1
        current_frequency = np.array([float(row["frequency_hz"]) for row in rows], dtype=float)
        magnitude_db = np.array([float(row["magnitude_db"]) for row in rows], dtype=float)
        phase_deg = np.array([float(row["phase_deg"]) for row in rows], dtype=float)

        if frequency_hz is None:
            frequency_hz = current_frequency
        elif frequency_hz.shape != current_frequency.shape or not np.allclose(frequency_hz, current_frequency):
            raise SystemExit(f"Frequency axis mismatch: {path}")

        points.append(TracePoint(x_mm=x_mm, y_mm=y_mm, point_index=point_index, source_file=path.name))
        magnitude_rows.append(magnitude_db)
        phase_rows.append(phase_deg)

    if frequency_hz is None or not points:
        raise SystemExit("No valid trace rows found.")

    return QuietZoneData(
        points=points,
        frequency_hz=frequency_hz,
        magnitude_db=np.vstack(magnitude_rows),
        phase_deg=np.vstack(phase_rows),
    )


def resolve_input_dir(input_dir: Path, pattern: str) -> Path:
    if not input_dir.exists():
        return input_dir
    if list(input_dir.glob(pattern)):
        return input_dir

    candidates = [
        path
        for path in input_dir.iterdir()
        if path.is_dir() and list(path.glob(pattern))
    ]
    if not candidates:
        return input_dir
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def circular_phase_spread_deg(values_deg: np.ndarray) -> float:
    values = np.mod(values_deg, 360.0)
    values.sort()
    gaps = np.diff(np.r_[values, values[0] + 360.0])
    return float(360.0 - gaps.max())


def region_metrics(data: QuietZoneData, mask: np.ndarray) -> dict[str, np.ndarray]:
    magnitude = data.magnitude_db[mask]
    phase = data.phase_deg[mask]
    amplitude_p2p = magnitude.max(axis=0) - magnitude.min(axis=0)
    amplitude_std = magnitude.std(axis=0)
    relative_phase = (phase - phase[0:1] + 180.0) % 360.0 - 180.0
    phase_spread = np.array(
        [circular_phase_spread_deg(relative_phase[:, index]) for index in range(relative_phase.shape[1])],
        dtype=float,
    )
    return {
        "amplitude_p2p_db": amplitude_p2p,
        "amplitude_std_db": amplitude_std,
        "phase_spread_deg": phase_spread,
    }


def point_metrics(data: QuietZoneData) -> PointMetrics:
    spatial_mean = data.magnitude_db.mean(axis=0)
    return PointMetrics(
        mean_magnitude_db=data.magnitude_db.mean(axis=1),
        band_ripple_db=data.magnitude_db.max(axis=1) - data.magnitude_db.min(axis=1),
        max_deviation_from_spatial_mean_db=np.max(np.abs(data.magnitude_db - spatial_mean), axis=1),
    )


def write_frequency_metrics(
    output_dir: Path,
    data: QuietZoneData,
    full_metrics: dict[str, np.ndarray],
    center_metrics: dict[str, np.ndarray],
) -> Path:
    path = output_dir / "quiet_zone_frequency_metrics.csv"
    frequency_ghz = data.frequency_hz / 1e9
    with path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            [
                "frequency_ghz",
                "full_amp_p2p_db",
                "full_amp_std_db",
                "full_phase_spread_deg",
                "center_amp_p2p_db",
                "center_amp_std_db",
                "center_phase_spread_deg",
            ]
        )
        for index, freq_ghz in enumerate(frequency_ghz):
            writer.writerow(
                [
                    f"{freq_ghz:.6f}",
                    f"{full_metrics['amplitude_p2p_db'][index]:.6f}",
                    f"{full_metrics['amplitude_std_db'][index]:.6f}",
                    f"{full_metrics['phase_spread_deg'][index]:.6f}",
                    f"{center_metrics['amplitude_p2p_db'][index]:.6f}",
                    f"{center_metrics['amplitude_std_db'][index]:.6f}",
                    f"{center_metrics['phase_spread_deg'][index]:.6f}",
                ]
            )
    return path


def write_plots(
    output_dir: Path,
    data: QuietZoneData,
    full_metrics: dict[str, np.ndarray],
    center_metrics: dict[str, np.ndarray],
    metrics: PointMetrics,
    center_point_xy: tuple[float, float],
    edge_point_xy: tuple[float, float],
) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    frequency_ghz = data.frequency_hz / 1e9

    paths["frequency_curves"] = output_dir / "quiet_zone_frequency_curves.png"
    fig, axes = plt.subplots(2, 1, figsize=(11.2, 6.3), sharex=True)
    axes[0].plot(frequency_ghz, full_metrics["amplitude_p2p_db"], label="全区域 幅度峰峰值", color="#1F3864")
    axes[0].plot(frequency_ghz, center_metrics["amplitude_p2p_db"], label="中心区域 幅度峰峰值", color="#2e7d32")
    axes[0].axhline(3.0, color="#d32f2f", linestyle="--", linewidth=1.0, label="3 dB 参考线")
    axes[0].set_ylabel("幅度峰峰值 (dB)")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(loc="upper right")
    axes[1].plot(frequency_ghz, full_metrics["phase_spread_deg"], label="全区域 相位展开范围", color="#6a1b9a")
    axes[1].plot(frequency_ghz, center_metrics["phase_spread_deg"], label="中心区域 相位展开范围", color="#f57c00")
    axes[1].set_xlabel("频率 (GHz)")
    axes[1].set_ylabel("相位范围 (deg)")
    axes[1].grid(True, alpha=0.25)
    axes[1].legend(loc="upper right")
    fig.suptitle("静区频率维度一致性")
    fig.tight_layout()
    fig.savefig(paths["frequency_curves"], dpi=160)
    plt.close(fig)

    center_point_index = _nearest_point_index(data, center_point_xy)
    edge_point_index = _nearest_point_index(data, edge_point_xy)
    paths["center_envelope"] = output_dir / "quiet_zone_center_envelope.png"
    _write_point_trace_plot(
        paths["center_envelope"],
        data,
        center_point_index,
        "中心点 S21 幅度曲线",
        "#1F3864",
    )
    paths["edge_envelope"] = output_dir / "quiet_zone_edge_envelope.png"
    _write_point_trace_plot(
        paths["edge_envelope"],
        data,
        edge_point_index,
        "边缘点 S21 幅度曲线",
        "#d32f2f",
    )

    paths["mean_magnitude_map"] = output_dir / "quiet_zone_mean_magnitude_map.png"
    _write_spatial_map(
        paths["mean_magnitude_map"],
        data,
        metrics.mean_magnitude_db,
        "空间平均幅度分布",
        "平均幅度 (dB)",
        cmap="viridis",
    )

    paths["band_ripple_map"] = output_dir / "quiet_zone_band_ripple_map.png"
    _write_spatial_map(
        paths["band_ripple_map"],
        data,
        metrics.band_ripple_db,
        "各点带内起伏分布",
        "带内起伏 (dB)",
        cmap="magma",
    )

    paths["spatial_deviation_map"] = output_dir / "quiet_zone_spatial_deviation_map.png"
    _write_spatial_map(
        paths["spatial_deviation_map"],
        data,
        metrics.max_deviation_from_spatial_mean_db,
        "各点相对空间均值最大偏差",
        "最大偏差 (dB)",
        cmap="inferno",
    )
    return paths


def _write_spatial_map(
    path: Path,
    data: QuietZoneData,
    values: np.ndarray,
    title: str,
    colorbar_label: str,
    cmap: str,
) -> None:
    positions = data.positions_mm
    x_values = np.unique(positions[:, 0])
    y_values = np.unique(positions[:, 1])
    grid = np.full((len(y_values), len(x_values)), np.nan, dtype=float)
    for (x_mm, y_mm), value in zip(positions, values):
        x_index = int(np.where(x_values == x_mm)[0][0])
        y_index = int(np.where(y_values == y_mm)[0][0])
        grid[y_index, x_index] = value

    fig, ax = plt.subplots(figsize=(11.2, 4.6))
    image = ax.imshow(
        grid,
        origin="lower",
        aspect="auto",
        extent=[x_values.min(), x_values.max(), y_values.min(), y_values.max()],
        cmap=cmap,
    )
    ax.set_title(title)
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")
    ax.set_xticks(x_values[:: max(len(x_values) // 10, 1)])
    ax.set_yticks(y_values)
    ax.grid(color="white", alpha=0.35, linewidth=0.6)
    colorbar = fig.colorbar(image, ax=ax)
    colorbar.set_label(colorbar_label)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _write_point_trace_plot(
    path: Path,
    data: QuietZoneData,
    point_index: int,
    title: str,
    color: str,
) -> None:
    frequency_ghz = data.frequency_hz / 1e9
    trace = data.magnitude_db[point_index]
    point = data.points[point_index]

    fig, ax = plt.subplots(figsize=(11.2, 3.2))
    ax.plot(frequency_ghz, trace, color=color, linewidth=1.4, label=f"X={point.x_mm:.0f} mm, Y={point.y_mm:.0f} mm")
    ax.fill_between(frequency_ghz, trace.min(), trace, color=color, alpha=0.08)
    ax.set_title(f"{title}（X={point.x_mm:.0f} mm, Y={point.y_mm:.0f} mm）")
    ax.set_xlabel("频率 (GHz)")
    ax.set_ylabel("幅度 (dB)")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _nearest_point_index(data: QuietZoneData, target_xy: tuple[float, float]) -> int:
    positions = data.positions_mm
    target = np.array(target_xy, dtype=float)
    return int(np.argmin(np.linalg.norm(positions - target, axis=1)))


def write_point_metrics(output_dir: Path, data: QuietZoneData) -> Path:
    path = output_dir / "quiet_zone_point_metrics.csv"
    metrics = point_metrics(data)

    rows = sorted(
        zip(
            data.points,
            metrics.mean_magnitude_db,
            metrics.band_ripple_db,
            metrics.max_deviation_from_spatial_mean_db,
        ),
        key=lambda item: item[0].point_index,
    )
    with path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            [
                "point_index",
                "x_mm",
                "y_mm",
                "mean_magnitude_db",
                "band_ripple_db",
                "max_deviation_from_spatial_mean_db",
                "source_file",
            ]
        )
        for point, mean_db, ripple_db, deviation_db in rows:
            writer.writerow(
                [
                    point.point_index,
                    f"{point.x_mm:.3f}",
                    f"{point.y_mm:.3f}",
                    f"{mean_db:.6f}",
                    f"{ripple_db:.6f}",
                    f"{deviation_db:.6f}",
                    point.source_file,
                ]
            )
    return path


def write_report(
    output_dir: Path,
    data: QuietZoneData,
    full_metrics: dict[str, np.ndarray],
    center_metrics: dict[str, np.ndarray],
    center_mask: np.ndarray,
) -> Path:
    path = output_dir / "quiet_zone_analysis_report.txt"
    positions = data.positions_mm
    frequency_ghz = data.frequency_hz / 1e9
    point_mean = data.magnitude_db.mean(axis=1)
    point_ripple = data.magnitude_db.max(axis=1) - data.magnitude_db.min(axis=1)
    spatial_mean = data.magnitude_db.mean(axis=0)
    point_deviation = np.max(np.abs(data.magnitude_db - spatial_mean), axis=1)

    with path.open("w", encoding="utf-8") as report:
        report.write("Quiet zone analysis summary\n")
        report.write(f"Files: {len(data.points)} trace CSV files\n")
        report.write(
            "Grid: "
            f"X {positions[:, 0].min():.0f}-{positions[:, 0].max():.0f} mm, "
            f"{len(np.unique(positions[:, 0]))} columns; "
            f"Y {positions[:, 1].min():.0f}-{positions[:, 1].max():.0f} mm, "
            f"{len(np.unique(positions[:, 1]))} rows\n"
        )
        report.write(
            f"Frequency: {frequency_ghz[0]:.3f}-{frequency_ghz[-1]:.3f} GHz, "
            f"{len(frequency_ghz)} points\n\n"
        )
        _write_metric_line(report, "Full region amplitude p2p dB", full_metrics["amplitude_p2p_db"])
        _write_metric_line(report, "Full region phase spread deg", full_metrics["phase_spread_deg"])
        report.write(f"Center region point count: {int(center_mask.sum())}\n")
        _write_metric_line(report, "Center region amplitude p2p dB", center_metrics["amplitude_p2p_db"])
        _write_metric_line(report, "Center region phase spread deg", center_metrics["phase_spread_deg"])

        report.write("\nFrequency pass count by full-region amplitude p2p:\n")
        for threshold_db in (1.0, 2.0, 3.0, 6.0):
            ok_count = int((full_metrics["amplitude_p2p_db"] <= threshold_db).sum())
            report.write(f"  <= {threshold_db:.1f} dB: {ok_count}/{len(frequency_ghz)}\n")

        report.write("\nWorst points by band ripple:\n")
        for index in np.argsort(point_ripple)[-10:][::-1]:
            point = data.points[index]
            report.write(
                f"  P{point.point_index:04d} X{point.x_mm:.0f} Y{point.y_mm:.0f}: "
                f"mean {point_mean[index]:.2f} dB, "
                f"ripple {point_ripple[index]:.2f} dB, "
                f"max_dev {point_deviation[index]:.2f} dB\n"
            )
    return path


def write_html_report(
    output_dir: Path,
    template_dir: Path,
    data: QuietZoneData,
    full_metrics: dict[str, np.ndarray],
    center_metrics: dict[str, np.ndarray],
    center_mask: np.ndarray,
    metrics: PointMetrics,
    plot_paths: dict[str, Path],
) -> Path:
    logo_path = _copy_logo_asset(output_dir, template_dir)
    logo_html = f'<img src="{escape(logo_path.name)}" alt="GTS">' if logo_path else ""
    positions = data.positions_mm
    frequency_ghz = data.frequency_hz / 1e9
    worst_indices = np.argsort(metrics.band_ripple_db)[-8:][::-1]
    report_path = output_dir / "quiet_zone_analysis_report.html"

    pages = [
        _html_cover_page(logo_html, data, positions, frequency_ghz),
        _html_summary_page(logo_html, data, positions, frequency_ghz, full_metrics, center_metrics, center_mask),
        _html_plot_page(
            logo_html,
            "频率维度一致性",
            "全区域与中心区域的幅度峰峰值、相位展开范围随频率变化。",
            plot_paths["frequency_curves"],
            "频率曲线可用于判断哪些频段满足幅度平坦度要求；中心区域通常更接近有效静区。",
            3,
        ),
        _html_envelope_page(
            logo_html,
            plot_paths["center_envelope"],
            plot_paths["edge_envelope"],
        ),
        _html_plot_grid_page(
            logo_html,
            plot_paths["mean_magnitude_map"],
            plot_paths["band_ripple_map"],
            plot_paths["spatial_deviation_map"],
        ),
        _html_worst_points_page(logo_html, data, metrics, worst_indices),
    ]
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>静区测试分析报告</title>
<style>
{_report_css()}
</style>
</head>
<body>
{''.join(pages)}
</body>
</html>
"""
    report_path.write_text(html, encoding="utf-8")
    return report_path


def _copy_logo_asset(output_dir: Path, template_dir: Path) -> Path | None:
    for name in ("logo.png", "logo.svg"):
        source = template_dir / name
        if source.exists():
            target = output_dir / name
            if source.resolve() != target.resolve():
                shutil.copy2(source, target)
            return target
    return None


def _html_cover_page(
    logo_html: str,
    data: QuietZoneData,
    positions: np.ndarray,
    frequency_ghz: np.ndarray,
) -> str:
    return f"""
<div class="page cover-page">
  <div class="page-header">{logo_html}</div>
  <div class="main">
    <h1 class="cover-title">微波暗室静区测试<br>分析报告</h1>
    <div class="cover-divider"></div>
    <div class="cover-subtitle">S 参数空间一致性 · 幅度/相位统计 · 自动生成</div>
    <div class="cover-info">
      文件数量：{len(data.points)} &nbsp;|&nbsp;
      频段：{frequency_ghz[0]:.3f}-{frequency_ghz[-1]:.3f} GHz &nbsp;|&nbsp;
      区域：X {positions[:, 0].min():.0f}-{positions[:, 0].max():.0f} mm，Y {positions[:, 1].min():.0f}-{positions[:, 1].max():.0f} mm
    </div>
  </div>
  {_html_footer(1, 6)}
</div>
"""


def _html_summary_page(
    logo_html: str,
    data: QuietZoneData,
    positions: np.ndarray,
    frequency_ghz: np.ndarray,
    full_metrics: dict[str, np.ndarray],
    center_metrics: dict[str, np.ndarray],
    center_mask: np.ndarray,
) -> str:
    return f"""
<div class="page">
  <div class="page-header">{logo_html}</div>
  <div class="main">
    <div class="h1">测试概览与关键结论</div>
    <div class="sub">数据范围、频率范围、全区域/中心区域的核心指标</div>
    <div class="badges">
      <div class="badge bb"><span class="n">{len(data.points)}</span>测试点</div>
      <div class="badge bg"><span class="n">{len(frequency_ghz)}</span>频点</div>
      <div class="badge bo"><span class="n">{int(center_mask.sum())}</span>中心点</div>
      <div class="badge bp"><span class="n">{len(np.unique(positions[:, 0]))}×{len(np.unique(positions[:, 1]))}</span>空间网格</div>
    </div>
    <div class="h2">静区统计</div>
    <table>
      <thead><tr><th>区域</th><th class="c">幅度峰峰值中位数</th><th class="c">幅度峰峰值最大值</th><th class="c">相位范围中位数</th><th class="c">相位范围最大值</th></tr></thead>
      <tbody>
        <tr><td class="b">全区域</td><td class="c">{np.median(full_metrics["amplitude_p2p_db"]):.3f} dB</td><td class="c">{full_metrics["amplitude_p2p_db"].max():.3f} dB</td><td class="c">{np.median(full_metrics["phase_spread_deg"]):.2f} deg</td><td class="c">{full_metrics["phase_spread_deg"].max():.2f} deg</td></tr>
        <tr><td class="b">中心区域</td><td class="c">{np.median(center_metrics["amplitude_p2p_db"]):.3f} dB</td><td class="c">{center_metrics["amplitude_p2p_db"].max():.3f} dB</td><td class="c">{np.median(center_metrics["phase_spread_deg"]):.2f} deg</td><td class="c">{center_metrics["phase_spread_deg"].max():.2f} deg</td></tr>
      </tbody>
    </table>
    <div class="bar">中心区域幅度一致性优于全区域：中位峰峰值 <span>{np.median(center_metrics["amplitude_p2p_db"]):.2f} dB</span></div>
  </div>
  {_html_footer(2, 6)}
</div>
"""


def _html_plot_page(
    logo_html: str,
    title: str,
    subtitle: str,
    image_path: Path,
    conclusion: str,
    page_num: int,
) -> str:
    return f"""
<div class="page">
  <div class="page-header">{logo_html}</div>
  <div class="main">
    <div class="h1">{escape(title)}</div>
    <div class="sub">{escape(subtitle)}</div>
    <div class="img-wrap"><img src="{escape(image_path.name)}" alt="{escape(title)}"></div>
    <div class="conc"><h3>图表说明</h3><p>{escape(conclusion)}</p></div>
  </div>
  {_html_footer(page_num, 6)}
</div>
"""


def _html_envelope_page(
    logo_html: str,
    center_envelope_path: Path,
    edge_envelope_path: Path,
) -> str:
    return f"""
<div class="page">
  <div class="page-header">{logo_html}</div>
  <div class="main">
    <div class="h1">中心点/边缘点曲线对比</div>
    <div class="sub">中心点 X=200 mm, Y=200 mm；边缘点 X=0 mm, Y=0 mm 的 S21 幅度曲线</div>
    <div class="row2">
      <div class="col2"><div class="img-wrap envelope"><img src="{escape(center_envelope_path.name)}" alt="中心点曲线"></div></div>
      <div class="col2"><div class="img-wrap envelope"><img src="{escape(edge_envelope_path.name)}" alt="边缘点曲线"></div></div>
    </div>
    <div class="conc"><h3>判读</h3><p>中心点曲线用于观察目标静区核心位置的频响；边缘点曲线用于对比扫描边界位置的包络起伏和反射影响。</p></div>
  </div>
  {_html_footer(4, 6)}
</div>
"""


def _html_plot_grid_page(
    logo_html: str,
    mean_map_path: Path,
    ripple_map_path: Path,
    deviation_map_path: Path,
) -> str:
    return f"""
<div class="page">
  <div class="page-header">{logo_html}</div>
  <div class="main">
    <div class="h1">空间分布分析</div>
    <div class="sub">平均幅度、带内起伏、相对空间均值最大偏差</div>
    <div class="row2">
      <div class="col2"><div class="img-wrap small"><img src="{escape(mean_map_path.name)}" alt="平均幅度分布"></div></div>
      <div class="col2"><div class="img-wrap small"><img src="{escape(ripple_map_path.name)}" alt="带内起伏分布"></div></div>
    </div>
    <div class="img-wrap small"><img src="{escape(deviation_map_path.name)}" alt="空间偏差分布"></div>
  </div>
  {_html_footer(5, 6)}
</div>
"""


def _html_worst_points_page(
    logo_html: str,
    data: QuietZoneData,
    metrics: PointMetrics,
    worst_indices: np.ndarray,
) -> str:
    rows = []
    for index in worst_indices:
        point = data.points[int(index)]
        rows.append(
            "<tr>"
            f"<td class=\"c\">P{point.point_index:04d}</td>"
            f"<td class=\"c\">{point.x_mm:.0f}</td>"
            f"<td class=\"c\">{point.y_mm:.0f}</td>"
            f"<td class=\"c\">{metrics.mean_magnitude_db[index]:.2f}</td>"
            f"<td class=\"c\">{metrics.band_ripple_db[index]:.2f}</td>"
            f"<td class=\"c\">{metrics.max_deviation_from_spatial_mean_db[index]:.2f}</td>"
            "</tr>"
        )
    return f"""
<div class="page">
  <div class="page-header">{logo_html}</div>
  <div class="main">
    <div class="h1">风险点位列表</div>
    <div class="sub">按带内起伏从高到低排序，用于定位边缘区域或异常点</div>
    <table>
      <thead><tr><th class="c">点位</th><th class="c">X/mm</th><th class="c">Y/mm</th><th class="c">平均幅度/dB</th><th class="c">带内起伏/dB</th><th class="c">空间最大偏差/dB</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    <div class="conc"><h3>建议</h3><p>优先复测带内起伏较大的点位；若集中在边缘区域，建议收缩有效静区范围或检查边缘反射、天线对准和吸波材料状态。</p></div>
  </div>
  {_html_footer(6, 6)}
</div>
"""


def _html_footer(page: int, total: int) -> str:
    return (
        '<div class="page-footer">'
        "<span>Accurate · Simple · Fast · Agile &nbsp;|&nbsp; 静区测试分析</span>"
        f'<span>内部文件 &nbsp;|&nbsp; <span class="page-num">{page} / {total}</span></span>'
        "</div>"
    )


def _report_css() -> str:
    return """
* { margin:0; padding:0; box-sizing:border-box; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
body { font-family:"等线","SimSun","Microsoft YaHei",sans-serif; background:#d0d0d0; display:flex; flex-direction:column; align-items:center; padding:20px; gap:24px; }
@media print { body { background:#fff; padding:0; gap:0; } .page { box-shadow:none; margin:0; break-after:page; page-break-after:always; } }
.page { background:#fff; width:1120px; min-height:630px; box-shadow:0 2px 8px rgba(0,0,0,.15); display:flex; flex-direction:column; }
.page-header { padding:16px 44px 12px; display:flex; justify-content:flex-end; align-items:center; border-bottom:8px solid #d0d6e4; }
.page-header img { height:28px; }
.main { flex:1; display:flex; flex-direction:column; justify-content:center; padding:16px 44px; }
.page-footer { padding:10px 44px 14px; border-top:8px solid #d0d6e4; display:flex; justify-content:space-between; align-items:center; font-size:9px; color:#aaa; }
.page-num { font-size:10px; color:#999; }
.cover-page { justify-content:center; align-items:center; text-align:center; }
.cover-page .page-header { width:100%; padding-top:48px; }
.cover-page .page-header img { height:48px; }
.cover-page .main { width:100%; align-items:center; justify-content:center; padding:24px 80px; }
.cover-page .page-footer { width:100%; }
.cover-title { font-size:32px; font-weight:800; color:#1a1a1a; margin-bottom:12px; text-align:center; }
.cover-divider { width:80px; height:4px; background:#1F3864; margin:30px auto; }
.cover-subtitle { font-size:16px; color:#1F3864; margin-bottom:48px; text-align:center; }
.cover-info { font-size:14px; color:#666; line-height:2; text-align:center; }
.h1 { font-size:24px; font-weight:700; color:#1a1a1a; margin-bottom:4px; }
.sub { font-size:13px; color:#666; margin-bottom:22px; }
.h2 { font-size:16px; font-weight:700; color:#1F3864; margin:18px 0 10px; padding-bottom:6px; border-bottom:2px solid #1F3864; }
table { width:100%; border-collapse:collapse; font-size:13px; border:1.5px solid #333; margin-bottom:14px; }
thead th { background:#1F3864; color:#fff; font-size:13px; font-weight:600; padding:9px 12px; text-align:left; border:1px solid #1a2e52; }
tbody td { padding:8px 12px; border:1px solid #bbb; color:#1a1a1a; vertical-align:top; line-height:1.55; }
tbody tr:nth-child(even) td { background:#f2f6fc; }
td.c, th.c { text-align:center; } td.b { font-weight:700; }
.row2 { display:flex; gap:20px; } .col2 { flex:1; }
.badges { display:flex; gap:12px; margin-top:8px; }
.badge { flex:1; text-align:center; padding:12px 10px; border-radius:5px; font-size:13px; font-weight:700; color:#fff; }
.badge .n { font-size:24px; display:block; }
.bo { background:#e65100; } .bg { background:#2e7d32; } .bb { background:#1565c0; } .bp { background:#6a1b9a; }
.bar { margin-top:14px; padding:13px 20px; background:linear-gradient(90deg,#1F3864,#283593); color:#fff; border-radius:4px; text-align:center; font-size:14px; font-weight:600; }
.bar span { color:#ffcc80; font-size:18px; }
.img-wrap { text-align:center; margin-bottom:14px; border:1px solid #e0e0e0; border-radius:4px; padding:8px; background:#fafafa; }
.img-wrap img { max-width:100%; max-height:390px; object-fit:contain; }
.img-wrap.small img { max-height:210px; }
.img-wrap.envelope img { max-height:300px; }
.conc { background:linear-gradient(90deg,#e8f5e9,#f1f8e9); border-left:4px solid #2e7d32; border-radius:4px; padding:12px 16px; margin-top:8px; }
.conc h3 { font-size:14px; color:#2e7d32; margin-bottom:5px; }
.conc p { font-size:12px; color:#333; line-height:1.55; }
"""
def _write_metric_line(report, label: str, values: np.ndarray) -> None:
    report.write(
        f"{label} median/mean/p90/max: "
        f"{np.median(values):.3f}/{values.mean():.3f}/"
        f"{np.percentile(values, 90):.3f}/{values.max():.3f}\n"
    )


def main() -> None:
    args = parse_args()
    input_dir = resolve_input_dir(Path(args.input), args.pattern)
    output_dir = Path(args.output) if args.output else input_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    data = load_quiet_zone_data(input_dir, args.pattern)
    positions = data.positions_mm
    full_mask = np.ones(len(data.points), dtype=bool)
    center_mask = (
        (positions[:, 0] >= args.center_x_min)
        & (positions[:, 0] <= args.center_x_max)
        & (positions[:, 1] >= args.center_y_min)
        & (positions[:, 1] <= args.center_y_max)
    )
    if not center_mask.any():
        raise SystemExit("Center region contains no points.")

    full_metrics = region_metrics(data, full_mask)
    center_metrics = region_metrics(data, center_mask)
    metrics = point_metrics(data)
    frequency_path = write_frequency_metrics(output_dir, data, full_metrics, center_metrics)
    point_path = write_point_metrics(output_dir, data)
    report_path = write_report(output_dir, data, full_metrics, center_metrics, center_mask)
    plot_paths = write_plots(
        output_dir,
        data,
        full_metrics,
        center_metrics,
        metrics,
        (args.center_point_x, args.center_point_y),
        (args.edge_point_x, args.edge_point_y),
    )
    html_report_path = write_html_report(
        output_dir=output_dir,
        template_dir=Path(args.template_dir),
        data=data,
        full_metrics=full_metrics,
        center_metrics=center_metrics,
        center_mask=center_mask,
        metrics=metrics,
        plot_paths=plot_paths,
    )

    print(f"Analyzed {len(data.points)} files from {input_dir}")
    print(f"Wrote {frequency_path}")
    print(f"Wrote {point_path}")
    print(f"Wrote {report_path}")
    for plot_path in plot_paths.values():
        print(f"Wrote {plot_path}")
    print(f"Wrote {html_report_path}")
    print(
        "Full amplitude p2p median/mean/max: "
        f"{np.median(full_metrics['amplitude_p2p_db']):.3f}/"
        f"{full_metrics['amplitude_p2p_db'].mean():.3f}/"
        f"{full_metrics['amplitude_p2p_db'].max():.3f} dB"
    )
    print(
        "Center amplitude p2p median/mean/max: "
        f"{np.median(center_metrics['amplitude_p2p_db']):.3f}/"
        f"{center_metrics['amplitude_p2p_db'].mean():.3f}/"
        f"{center_metrics['amplitude_p2p_db'].max():.3f} dB"
    )


if __name__ == "__main__":
    main()
