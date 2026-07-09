from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from quiet_zone_tester.domains.scan_management import ScanSession


@dataclass(frozen=True)
class ReportExporter:
    def export_markdown(self, session: ScanSession, output_path: Path | None = None) -> Path:
        path = Path(output_path) if output_path is not None else session.output_dir / "scan_report.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.markdown(session), encoding="utf-8")
        return path

    def markdown(self, session: ScanSession) -> str:
        summary = session.metadata_summary()
        lines = [
            "# 扫描报告",
            "",
            "## 概览",
            "",
            f"- 会话：{summary['session_id']}",
            f"- 状态：{summary['final_state'] or 'Running'}",
            f"- 模式：{summary['scan_mode']}",
            f"- 参数：{summary['parameter']}",
            f"- 标记：{summary['file_flag']}",
            f"- 点数：{summary['completed_count']}/{summary['point_count']}",
            f"- 输出目录：{summary['output_dir']}",
            f"- 开始时间：{summary['started_at']}",
            f"- 结束时间：{summary['finished_at'] or '-'}",
            "",
            "## 扫描范围",
            "",
            f"- X：{summary['scan_volume']['x_start_mm']} -> {summary['scan_volume']['x_stop_mm']} mm",
            f"- Y：{summary['scan_volume']['y_start_mm']} -> {summary['scan_volume']['y_stop_mm']} mm",
            f"- 步进：X {summary['scan_volume']['step_x_mm']} mm, Y {summary['scan_volume']['step_y_mm']} mm",
            "",
            "## Trace 记录",
            "",
        ]
        if session.records:
            lines.append("| 点号 | X/mm | Y/mm | 参数 | 文件 |")
            lines.append("|---:|---:|---:|---|---|")
            for record in session.records:
                x_text = "-" if record.position_mm is None else f"{record.position_mm[0]:.6f}"
                y_text = "-" if record.position_mm is None else f"{record.position_mm[1]:.6f}"
                filename = "-" if record.file_path is None else record.file_path.name
                lines.append(f"| {record.point_index} | {x_text} | {y_text} | {record.parameter} | {filename} |")
        else:
            lines.append("暂无 trace 记录。")

        lines.extend(["", "## 事件", ""])
        if session.events:
            lines.append("| 时间 | 等级 | 类型 | 消息 |")
            lines.append("|---|---|---|---|")
            for event in session.events:
                lines.append(
                    f"| {event.timestamp.isoformat()} | {event.level} | {event.event_type} | {event.message} |"
                )
        else:
            lines.append("暂无事件记录。")

        lines.append("")
        return "\n".join(lines)
