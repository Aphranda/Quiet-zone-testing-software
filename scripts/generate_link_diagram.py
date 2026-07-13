from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape


OUT_PATH = Path("resource/链路图.svg")


@dataclass(frozen=True)
class Pt:
    x: float
    y: float


@dataclass(frozen=True)
class Terminal:
    name: str
    point: Pt
    orientation: str = "h"
    hot: bool = False
    label: str | None = None
    label_dx: float = 0.0
    label_dy: float = 0.0
    side: str | None = None


class Svg:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def add(self, line: str) -> None:
        self.lines.append(line)

    def text(self, x: float, y: float, text: str, cls: str, anchor: str = "middle") -> None:
        self.add(f'<text class="{cls}" x="{x:g}" y="{y:g}" text-anchor="{anchor}">{escape(text)}</text>')

    def rect(self, x: float, y: float, w: float, h: float, cls: str) -> None:
        self.add(f'<rect class="{cls}" x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}"/>')

    def path(self, d: str, cls: str) -> None:
        self.add(f'<path class="{cls}" d="{d}"/>')

    def line(self, p1: Pt, p2: Pt, cls: str) -> None:
        self.add(
            f'<line class="{cls}" x1="{p1.x:g}" y1="{p1.y:g}" x2="{p2.x:g}" y2="{p2.y:g}"/>'
        )

    def circle(self, p: Pt, r: float, cls: str) -> None:
        self.add(f'<circle class="{cls}" cx="{p.x:g}" cy="{p.y:g}" r="{r:g}"/>')

    def polygon(self, points: list[Pt], cls: str) -> None:
        joined = " ".join(f"{point.x:g},{point.y:g}" for point in points)
        self.add(f'<polygon class="{cls}" points="{joined}"/>')

    def switch(
        self,
        *,
        name: str,
        x: float,
        y: float,
        w: float,
        h: float,
        terminals: list[Terminal],
        throws: list[tuple[str, str, str]],
        hot: bool = False,
        label: Pt | None = None,
    ) -> dict[str, Pt]:
        terminal_by_name = {terminal.name: terminal.point for terminal in terminals}
        self.rect(x, y, w, h, "switchHot" if hot else "switch")

        # Draw switch blades before terminals so the small protruding contacts stay crisp.
        for start, end, cls in throws:
            self.line(terminal_by_name[start], terminal_by_name[end], cls)

        for terminal in terminals:
            self.terminal(terminal)
            if terminal.label:
                self.text(
                    terminal.point.x + terminal.label_dx,
                    terminal.point.y + terminal.label_dy,
                    terminal.label,
                    "tiny",
                )

        label = label or Pt(x + w / 2, y + h + 26)
        self.text(label.x, label.y, name, "small")
        return terminal_by_name

    def terminal(self, terminal: Terminal) -> None:
        p = terminal.point
        cls = "terminalHot" if terminal.hot else "terminal"
        if terminal.orientation == "v":
            if terminal.side == "top":
                y = p.y
            elif terminal.side == "bottom":
                y = p.y - 26
            else:
                y = p.y - 13
            self.rect(p.x - 5, y, 10, 26, cls)
        else:
            if terminal.side == "left":
                x = p.x
            elif terminal.side == "right":
                x = p.x - 24
            else:
                x = p.x - 12
            self.rect(x, p.y - 4.5, 24, 9, cls)


def svg_header() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="760" viewBox="0 0 1100 760" role="img" aria-labelledby="title desc">
  <title id="title">LCD74000F 开关切换箱链路图</title>
  <desc id="desc">在接近原始链路图器件位置的基础上重绘。SW1 到 SW5 是一出二开关，SW6 是一出四开关；绿色三角和黄色三角分别表示放大器 AMP1 与 AMP2。</desc>
  <defs>
    <marker id="arrowBlue" viewBox="0 0 10 10" refX="8.4" refY="5" markerWidth="7" markerHeight="7" orient="auto">
      <path d="M0 0 10 5 0 10z" fill="#1d4ed8"/>
    </marker>
    <marker id="arrowGreen" viewBox="0 0 10 10" refX="8.4" refY="5" markerWidth="7" markerHeight="7" orient="auto">
      <path d="M0 0 10 5 0 10z" fill="#059669"/>
    </marker>
    <marker id="arrowGray" viewBox="0 0 10 10" refX="8.4" refY="5" markerWidth="7" markerHeight="7" orient="auto">
      <path d="M0 0 10 5 0 10z" fill="#64748b"/>
    </marker>
    <style>
      .bg { fill: #ffffff; }
      .title { font: 700 28px "Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans CJK SC", Arial, sans-serif; fill: #111827; }
      .label { font: 700 20px "Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans CJK SC", Arial, sans-serif; fill: #111827; }
      .small { font: 700 15px "Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans CJK SC", Arial, sans-serif; fill: #111827; }
      .tiny { font: 700 12px "Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans CJK SC", Arial, sans-serif; fill: #334155; }
      .hint { font: 600 12px "Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans CJK SC", Arial, sans-serif; fill: #64748b; }
      .panel { fill: none; stroke: #111827; stroke-width: 3; stroke-dasharray: 28 18; }
      .switch { fill: #ffffff; stroke: #1f2937; stroke-width: 3; rx: 3; }
      .switchHot { fill: #ff1f1f; stroke: #111827; stroke-width: 3; rx: 3; }
      .terminal { fill: #111827; stroke: #111827; stroke-width: 1; rx: 1; }
      .terminalHot { fill: #e11d25; stroke: #111827; stroke-width: 1; rx: 1; }
      .bladeActive { stroke: #1d4ed8; stroke-width: 3.4; stroke-linecap: square; }
      .bladeInactive { stroke: #64748b; stroke-width: 2.4; stroke-dasharray: 9 7; stroke-linecap: square; }
      .bladeGreen { stroke: #059669; stroke-width: 3.6; stroke-linecap: square; }
      .wireBlue { fill: none; stroke: #1d4ed8; stroke-width: 3.4; stroke-linecap: square; stroke-linejoin: round; marker-end: url(#arrowBlue); }
      .wireBlueNoArrow { fill: none; stroke: #1d4ed8; stroke-width: 3.4; stroke-linecap: square; stroke-linejoin: round; }
      .wireGreen { fill: none; stroke: #059669; stroke-width: 3.6; stroke-linecap: square; stroke-linejoin: round; marker-end: url(#arrowGreen); }
      .wireGreenNoArrow { fill: none; stroke: #059669; stroke-width: 3.6; stroke-linecap: square; stroke-linejoin: round; }
      .wireGray { fill: none; stroke: #64748b; stroke-width: 2.4; stroke-linecap: square; stroke-linejoin: round; stroke-dasharray: 9 7; marker-end: url(#arrowGray); }
      .wireGrayNoArrow { fill: none; stroke: #64748b; stroke-width: 2.4; stroke-linecap: square; stroke-linejoin: round; stroke-dasharray: 9 7; }
      .junctionBlue { fill: #1d4ed8; stroke: #ffffff; stroke-width: 2; }
      .junctionGreen { fill: #059669; stroke: #ffffff; stroke-width: 2; }
      .portIn { fill: #22c7ee; stroke: #111827; stroke-width: 3; rx: 2; }
      .portOut { fill: #ff1f1f; stroke: #e11d25; stroke-width: 3; rx: 2; }
      .ampBox { fill: #ffffff; stroke: #1f2937; stroke-width: 3; rx: 3; }
      .amp1 { fill: #22c55e; stroke: #1f2937; stroke-width: 3; }
      .amp2 { fill: #f7a15a; stroke: #1f2937; stroke-width: 3; }
      .legend { fill: #f8fafc; stroke: #cbd5e1; stroke-width: 1.4; rx: 6; }
    </style>
  </defs>"""


def draw_amp(svg: Svg, *, name: str, x: float, y: float, cls: str) -> None:
    svg.rect(x, y, 78, 86, "ampBox")
    svg.polygon([Pt(x + 18, y + 20), Pt(x + 60, y + 20), Pt(x + 39, y + 70)], cls)
    svg.text(x + 39, y + 108, name, "small")


def draw() -> str:
    svg = Svg()
    svg.add(svg_header())
    svg.rect(0, 0, 1100, 760, "bg")
    svg.text(550, 42, "开关切换箱", "title")
    svg.add('<rect class="panel" x="80" y="86" width="966" height="584"/>')

    svg.add('<g id="legend">')
    svg.add('<rect class="legend" x="640" y="18" width="392" height="58"/>')
    svg.path("M662 38 H728", "wireGreen")
    svg.text(740, 43, "DUT → AMP1 → SA / VNA2", "tiny", "start")
    svg.path("M662 62 H728", "wireBlue")
    svg.text(740, 67, "H/V → 直通或 AMP2 → VNA1 / SG / SA", "tiny", "start")
    svg.add("</g>")

    svg.text(28, 156, "H", "label")
    svg.rect(58, 145, 42, 12, "portIn")
    svg.text(28, 214, "V", "label")
    svg.rect(58, 203, 42, 12, "portIn")
    svg.text(910, 72, "DUT", "label")
    svg.rect(904, 94, 12, 42, "portIn")

    sw1 = svg.switch(
        name="SW1",
        x=184,
        y=118,
        w=64,
        h=78,
        hot=True,
        terminals=[
            Terminal("2", Pt(184, 150.5), hot=True, label="2", label_dx=-22, label_dy=-12, side="left"),
            Terminal("1", Pt(184, 208.5), hot=True, label="1", label_dx=-22, label_dy=20, side="left"),
            Terminal("C", Pt(248, 179.5), hot=True, side="right"),
        ],
        throws=[("2", "C", "bladeActive"), ("1", "C", "bladeInactive")],
        label=Pt(216, 228),
    )
    svg.path(f"M100 151 H{sw1['2'].x:g}", "wireBlue")
    svg.path(f"M100 209 H{sw1['1'].x:g}", "wireGray")
    svg.path(f"M{sw1['C'].x:g} 180 H344", "wireBlue")

    sw2 = svg.switch(
        name="SW2",
        x=344,
        y=120,
        w=64,
        h=78,
        terminals=[
            Terminal("C", Pt(344, 180.5), side="left"),
            Terminal("2", Pt(408, 149.5), label="2", label_dx=18, label_dy=-12, side="right"),
            Terminal("1", Pt(408, 206.5), label="1", label_dx=18, label_dy=18, side="right"),
        ],
        throws=[("C", "2", "bladeActive"), ("C", "1", "bladeInactive")],
        label=Pt(376, 222),
    )
    svg.path(f"M{sw2['2'].x:g} 150 H574 V226", "wireBlue")
    svg.path(f"M{sw2['1'].x:g} 207 V356", "wireBlueNoArrow")

    draw_amp(svg, name="AMP2", x=535, y=226, cls="amp2")
    svg.path("M574 312 V416 H420", "wireBlue")

    sw3 = svg.switch(
        name="SW3",
        x=344,
        y=344,
        w=64,
        h=78,
        terminals=[
            Terminal("C", Pt(344, 388.5), side="left"),
            Terminal("1", Pt(408, 360.5), label="1", label_dx=-10, label_dy=-25, side="right"),
            Terminal("2", Pt(408, 416.5), label="2", label_dx=18, label_dy=25, side="right"),
        ],
        throws=[("C", "2", "bladeActive"), ("C", "1", "bladeInactive")],
        label=Pt(318, 366),
    )
    svg.path(f"M{sw3['C'].x:g} 389 H304 V480", "wireBlue")

    # SW6 one-to-four selector.
    svg.rect(220, 480, 168, 74, "switch")
    svg.text(248, 516, "SW6", "small")
    svg.text(220, 568, "1", "tiny")
    svg.text(267, 568, "2", "tiny")
    svg.text(314, 568, "3", "tiny")
    svg.text(361, 568, "4", "tiny")
    sw6_terms = [
        Terminal("C", Pt(305, 480), "v", side="top"),
        Terminal("1", Pt(243, 554), "v", side="bottom"),
        Terminal("2", Pt(289, 554), "v", side="bottom"),
        Terminal("3", Pt(335, 554), "v", side="bottom"),
        Terminal("4", Pt(381, 554), "v", side="bottom"),
    ]
    svg.line(Pt(305, 493), Pt(335, 554), "bladeActive")
    for term in sw6_terms:
        svg.terminal(term)
    svg.path("M244 567 V646", "wireBlue")
    svg.path("M290 567 V646", "wireGray")
    svg.path("M336 567 V646", "wireBlue")
    svg.path("M386 548 H592 V450 H896 V540", "wireBlue")

    svg.rect(238, 646, 12, 48, "portOut")
    svg.rect(284, 646, 12, 48, "portOut")
    svg.rect(330, 646, 12, 48, "portOut")
    svg.text(244, 728, "VNA1", "label")
    svg.text(290, 728, "VNA2", "label")
    svg.text(336, 728, "SG", "label")

    svg.path("M910 136 V184", "wireGreen")
    draw_amp(svg, name="AMP1", x=872, y=184, cls="amp1")
    svg.path("M910 266 V334", "wireGreen")

    sw4 = svg.switch(
        name="SW4",
        x=872,
        y=334,
        w=72,
        h=76,
        terminals=[
            Terminal("C", Pt(910, 334), "v", side="top"),
            Terminal("1", Pt(884, 400), "v", label="1", label_dx=-26, label_dy=18),
            Terminal("2", Pt(944, 400), "v", label="2", label_dx=20, label_dy=18),
        ],
        throws=[("C", "1", "bladeGreen"), ("C", "2", "bladeInactive")],
        label=Pt(928, 382),
    )
    svg.path("M890 412 V500 H592 V600 H290", "wireGreen")
    svg.path("M944 412 V540", "wireGreen")

    sw5 = svg.switch(
        name="SW5",
        x=896,
        y=540,
        w=76,
        h=78,
        terminals=[
            Terminal("1", Pt(916, 540), "v", label="1", label_dx=-39, label_dy=20, side="top"),
            Terminal("2", Pt(960, 540), "v", label="2", label_dx=22, label_dy=20, side="top"),
            Terminal("C", Pt(934, 618), "v", side="bottom"),
        ],
        throws=[("1", "C", "bladeActive"), ("2", "C", "bladeGreen")],
        label=Pt(909, 582),
    )
    svg.path("M934 636 V646", "wireGreen")
    svg.rect(928, 646, 12, 48, "portOut")
    svg.text(934, 728, "SA", "label")

    svg.circle(Pt(592, 500), 4.5, "junctionGreen")
    svg.circle(Pt(592, 600), 4.5, "junctionGreen")
    svg.circle(Pt(592, 548), 4.5, "junctionBlue")
    svg.circle(Pt(896, 540), 4.5, "junctionBlue")
    svg.text(
        92,
        710,
        "说明：器件位置尽量贴近原始图；SW1-SW5 为一出二开关，SW6 为一出四开关；开关边缘的小突起是端子。",
        "hint",
        "start",
    )

    return "\n".join(svg.lines) + "\n</svg>\n"


def main() -> int:
    OUT_PATH.write_text(draw(), encoding="utf-8", newline="\n")
    print(f"wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
