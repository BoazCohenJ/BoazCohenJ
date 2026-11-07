"""Generates the profile README as ONE continuous PCB.

The README is a stack of full-width SVG slices that share the same flat board
colour, dot grid and edge rails, so on GitHub they read as a single board:
corner mounting holes at the very top and bottom, power rails down both
sides, and traces that run from section to section.

Public content: keep self-hosting generic (no service names, hardware, hosts or IPs).

The two featured chips (section 4) are filled from GitHub on every run: repo name, about text,
stars and commit count. A scheduled GitHub Action (.github/workflows/update-profile.yml) re-runs this
script and commits the result when something changed.

Run:  python build.py          (needs the GitHub CLI, `gh`, signed in or with GH_TOKEN set)
Writes assets/*.svg, README.md and preview.html next to this script.

Slice rules (so the seams stay invisible):
  - every slice is 900 units wide, or 450 / 300 for side-by-side slices
  - every slice height is a multiple of 20 (the dot grid period)
  - rails sit at x=10 and x=890 and are drawn by svg()
"""
import json
import math
import os
import shutil
import subprocess
import sys
import textwrap
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "assets")
os.makedirs(OUT, exist_ok=True)

BOARD = "#0d3328"
COPPER, SILK, CYAN, PULSE, DIM = "#d9a441", "#e9f1ec", "#5eead4", "#fff1a8", "#8fb5a6"
AMBER = "#ffb547"
CHIP, CHIP_EDGE = "#12171b", "#2a363e"
MONO = "Consolas, 'SF Mono', Menlo, 'DejaVu Sans Mono', monospace"
SANS = "'Segoe UI', Helvetica, Arial, sans-serif"
OWNER = "BoazCohenJ"
GH = f"https://github.com/{OWNER}/"
W = 900


def esc(s):
    return escape(s, {'"': "&quot;"})


DEFS = f"""<defs>
<pattern id="dots" width="20" height="20" patternUnits="userSpaceOnUse"><circle cx="10" cy="10" r="1.1" fill="#2a7a62" opacity=".45"/></pattern>
<filter id="glow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="2.2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
</defs>"""


# --------------------------------------------------------------------------- primitives
def trace(d, w=3, op=".9"):
    return (f'<path d="{d}" fill="none" stroke="{COPPER}" stroke-width="{w}" '
            f'stroke-linecap="round" stroke-linejoin="round" opacity="{op}"/>')


def pad(x, y, r=5):
    return (f'<circle cx="{x}" cy="{y}" r="{r}" fill="{COPPER}"/>'
            f'<circle cx="{x}" cy="{y}" r="{r * 0.45:.1f}" fill="#06160f"/>')


def pulse(d, dur, begin, r=3):
    return (f'<circle r="{r}" fill="{PULSE}" filter="url(#glow)" opacity="0">'
            f'<animateMotion dur="{dur}s" begin="{begin:.2f}s" repeatCount="indefinite" path="{d}"/>'
            f'<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;.1;.9;1" '
            f'dur="{dur}s" begin="{begin:.2f}s" repeatCount="indefinite"/></circle>')


def led(x, y, color, begin=0.0, dur=1.6, r=4):
    """Flashing status LEDs were removed on request; the moving pulses on the traces stay.
    Kept as a no-op so the call sites don't need to change."""
    return ""


def hole(x, y):
    """Mounting hole."""
    return (f'<circle cx="{x}" cy="{y}" r="11" fill="none" stroke="{COPPER}" stroke-width="3"/>'
            f'<circle cx="{x}" cy="{y}" r="6" fill="#020a07"/>')


def svg(w, h, body, label, corners="none", rails=True):
    """One slice of the board. corners: none | top | bottom."""
    r = 18
    if corners == "top":
        d = f"M0,{h} V{r} Q0,0 {r},0 H{w - r} Q{w},0 {w},{r} V{h} Z"
    elif corners == "bottom":
        d = f"M0,0 H{w} V{h - r} Q{w},{h} {w - r},{h} H{r} Q0,{h} 0,{h - r} Z"
    else:
        d = f"M0,0 H{w} V{h} H0 Z"
    base = (f'<rect width="{w}" height="{h}" fill="{BOARD}"/>'
            f'<rect width="{w}" height="{h}" fill="url(#dots)"/>')
    if rails:
        y0 = 48 if corners == "top" else 0
        y1 = h - 48 if corners == "bottom" else h
        base += trace(f"M10,{y0} V{y1}") + trace(f"M{w - 10},{y0} V{y1}")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{esc(label)}">{DEFS}'
            f'<clipPath id="clip"><path d="{d}"/></clipPath>'
            f'<g clip-path="url(#clip)">{base}{body}</g></svg>')


def save(name, content):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(content)


# --------------------------------------------------------------------------- header (top of the board)
def header_body():
    """Centred chip ("HI, I'M BOAZ") with channels fanning out to both sides.
    Chip and nets are drawn in the old chip-local coordinates inside a translated group."""
    b = []
    for x, y in [(30, 30), (870, 30)]:
        b.append(hole(x, y))

    # --- chip + nets, in chip-local coordinates; global = local + (-260, +20)
    nets = []  # (path, end_x, end_y)
    for i in range(4):                       # left, upper channels (global y 20..56, ending at x=72)
        y0, ty = 84 + 16 * i, 12 * i
        dy = y0 - ty
        nets.append((f"M628,{y0} H616 l{-dy},{-dy} H332", 332, ty))
    for i in range(4):                       # left, lower channels (global y 264..300)
        y0, ty = 148 + 16 * i, 244 + 12 * i
        dy = ty - y0
        nets.append((f"M628,{y0} H616 l{-dy},{dy} H332", 332, ty))
    for i in range(4):                       # right, upper channels, mirrored (ending at x=828)
        y0, ty = 84 + 16 * i, 12 * i
        dy = y0 - ty
        nets.append((f"M792,{y0} H804 l{dy},{-dy} H1088", 1088, ty))
    for i in range(4):                       # right, lower channels
        y0, ty = 148 + 16 * i, 244 + 12 * i
        dy = ty - y0
        nets.append((f"M792,{y0} H804 l{dy},{dy} H1088", 1088, ty))
    for i in range(8):                       # top and bottom pins fan outwards
        x = 654 + 16 * i
        d = (i - 3.5) * 8
        ad = abs(d)
        nets.append((f"M{x},58 V50 l{d:g},{-ad:g}", x + d, 50 - ad))
        nets.append((f"M{x},222 V230 l{d:g},{ad:g}", x + d, 230 + ad))

    g = []
    for d, ex, ey in nets:
        g.append(trace(d))
    for d, ex, ey in nets:
        g.append(pad(round(ex, 1), round(ey, 1), 4.5))
    for n, (d, ex, ey) in enumerate(nets):
        g.append(pulse(d, 3 + (n % 5) * 0.6, (n * 0.37) % 3.2))

    g.append(f'<rect x="620" y="50" width="180" height="180" rx="4" fill="none" stroke="{SILK}" '
             f'stroke-opacity=".35" stroke-width="1.5"/>')
    for i in range(8):
        c = 654 + 16 * i
        g.append(f'<rect x="{c - 3}" y="58" width="6" height="12" fill="{COPPER}"/>'
                 f'<rect x="{c - 3}" y="210" width="6" height="12" fill="{COPPER}"/>')
        c2 = 84 + 16 * i
        g.append(f'<rect x="628" y="{c2 - 3}" width="12" height="6" fill="{COPPER}"/>'
                 f'<rect x="780" y="{c2 - 3}" width="12" height="6" fill="{COPPER}"/>')
    g.append('<rect x="640" y="70" width="140" height="140" rx="7" fill="#0f1317" stroke="#2c363d" stroke-width="2"/>')
    g.append('<circle cx="654" cy="84" r="3.5" fill="#3a444c"/>')
    g.append(f'<text x="710" y="116" text-anchor="middle" font-family="{MONO}" font-size="13" letter-spacing="3" fill="{SILK}" opacity=".85">HI, I\'M</text>')
    g.append(f'<text x="710" y="148" text-anchor="middle" font-family="{SANS}" font-size="32" font-weight="700" fill="{SILK}">BOAZ</text>')
    g.append(f'<text x="710" y="170" text-anchor="middle" font-family="{MONO}" font-size="10" fill="{DIM}">ELEC · PHYS</text>')
    g.append(f'<text x="710" y="186" text-anchor="middle" font-family="{MONO}" font-size="10" fill="{DIM}">REV.2026</text>')
    g.append(led(764, 86, CYAN, 0.2, 1.2, 3))
    g.append(f'<text x="800" y="246" font-family="{MONO}" font-size="10" fill="{SILK}" opacity=".7">U1</text>')
    b.append(f'<g transform="translate(-260 20)">{"".join(g)}</g>')

    # --- left: typed subtitle (two lines) + R1 / D1 / C1 on one net
    for k, (line, t0) in enumerate([("high school student", 0.9), ("electronics & physics", 2.0)]):
        y = 124 + 26 * k
        b.append(f'<clipPath id="type{k}"><rect x="70" y="{y - 20}" width="0" height="28">'
                 f'<animate attributeName="width" from="0" to="230" dur="1.0s" begin="{t0}s" fill="freeze"/></rect></clipPath>')
        b.append(f'<g clip-path="url(#type{k})"><text x="72" y="{y}" font-family="{MONO}" font-size="17" fill="{CYAN}">{esc(line)}</text></g>')
    b.append(f'<rect x="276" y="{150 - 14}" width="2.5" height="20" fill="{CYAN}" opacity="0">'
             f'<animate attributeName="opacity" values="1;0;1" dur="1s" begin="3.0s" repeatCount="indefinite"/></rect>')

    sy = 204
    b.append(trace(f"M72,{sy} H280"))
    b.append(pad(72, sy))
    b.append(pad(280, sy))
    b.append(pulse(f"M72,{sy} H280", 3.0, 0.5))
    b.append(f'<rect x="100" y="{sy - 9}" width="56" height="18" rx="8" fill="#d8c3a0"/>')
    for col, x in [("#7a3e12", 112), ("#111111", 120), ("#c0392b", 128), ("#d4af37", 142)]:
        b.append(f'<rect x="{x}" y="{sy - 9}" width="5" height="18" fill="{col}"/>')
    b.append(f'<circle cx="196" cy="{sy}" r="12" fill="#ff4d4d" filter="url(#glow)" opacity=".85"/>'
             f'<circle cx="192" cy="{sy - 4}" r="3.5" fill="#fff" opacity=".6"/>')
    b.append(f'<rect x="232" y="{sy - 11}" width="26" height="22" rx="6" fill="#c9a24b"/>'
             f'<text x="245" y="{sy + 3}" text-anchor="middle" font-family="{MONO}" font-size="9" fill="#5a4313">104</text>')
    for lab, x in [("R1 1k", 128), ("D1", 196), ("C1 100nF", 245)]:
        b.append(f'<text x="{x}" y="{sy + 26}" text-anchor="middle" font-family="{MONO}" font-size="10" fill="{SILK}" opacity=".75">{lab}</text>')

    # --- right: Y1 crystal + the V=I·R label on one net
    b.append(trace(f"M620,{sy} H828"))
    b.append(pad(620, sy))
    b.append(pad(828, sy))
    b.append(pulse(f"M828,{sy} H620", 3.4, 1.1))
    b.append(f'<rect x="672" y="{sy - 10}" width="50" height="20" rx="10" fill="#cfd6db" stroke="#8d979d"/>'
             f'<text x="697" y="{sy + 3.5}" text-anchor="middle" font-family="{MONO}" font-size="9" fill="#444">16M</text>')
    b.append(f'<text x="697" y="{sy + 26}" text-anchor="middle" font-family="{MONO}" font-size="10" fill="{SILK}" opacity=".75">Y1 16MHz</text>')
    b.append(f'<text x="764" y="{sy + 5}" font-family="{MONO}" font-size="14" fill="{SILK}" opacity=".8">V=I·R</text>')

    b.append(f'<text x="72" y="314" font-family="{MONO}" font-size="10" fill="{SILK}" opacity=".55">'
             f'DATASHEET BC-2026 · BOAZ COHEN · REV 2026 · 2-LAYER · HAND-ROUTED</text>')
    return "".join(b)


# --------------------------------------------------------------------------- intro note + portfolio connector
INTRO = ("I study electronics and physics. I build small, useful tools for Windows and Android, "
         "run my own tools at home, and tinker with microcontrollers on the side.")


def intro_body():
    b = []
    for k, line in enumerate(textwrap.wrap(INTRO, 84)):
        b.append(f'<text x="44" y="{44 + k * 26}" font-family="{SANS}" font-size="16.5" fill="{SILK}">{esc(line)}</text>')
    b.append(f'<text x="44" y="22" font-family="{MONO}" font-size="10" letter-spacing="1.5" fill="{COPPER}">NOTE 1</text>')
    b.append(trace("M10,16 H30", 3))
    b.append(pad(30, 16, 3.5))
    return "".join(b)


def connector():
    b = []
    b.append(trace("M10,40 H40"))
    b.append(f'<rect x="40" y="16" width="150" height="48" rx="4" fill="#0f1317" stroke="#2c363d" stroke-width="2"/>')
    for i in range(6):
        b.append(pad(58 + i * 24, 40, 6))
    b.append(f'<text x="40" y="11" font-family="{MONO}" font-size="10" fill="{COPPER}">J1</text>')
    b.append(f'<text x="214" y="34" font-family="{MONO}" font-size="11" letter-spacing="2" fill="{DIM}">PORTFOLIO</text>')
    b.append(f'<text x="214" y="62" font-family="{SANS}" font-size="27" font-weight="700" fill="{SILK}">boazcohen.dev ↗</text>')
    d = "M520,40 H850 l14,14 H890"
    b.append(trace(d))
    b.append(pad(890, 54, 4.5))
    b.append(pulse(d, 3.2, 0.3))
    b.append(led(500, 40, CYAN, 0, 1.3, 4))
    return svg(W, 80, "".join(b), "Portfolio: boazcohen.dev")


# --------------------------------------------------------------------------- section heads (silkscreen label + trace to the rails)
def head(ref, title, sub):
    b = []
    tx = 80
    ex = tx + len(title) * 16.4 + 12
    b.append(f'<rect x="26" y="10" width="{ex - 26:.0f}" height="44" rx="4" fill="none" stroke="{SILK}" stroke-opacity=".45" stroke-width="1.5"/>')
    b.append(f'<rect x="34" y="16" width="32" height="32" rx="4" fill="{COPPER}"/>')
    b.append(f'<text x="50" y="37" text-anchor="middle" font-family="{MONO}" font-size="14" font-weight="700" fill="#06160f">{ref}</text>')
    b.append(f'<text x="{tx}" y="41" font-family="{MONO}" font-size="24" font-weight="700" letter-spacing="2" fill="{SILK}">{esc(title)}</text>')
    sx0 = ex + 14
    b.append(f'<text x="{sx0:.0f}" y="40" font-family="{MONO}" font-size="14" fill="{DIM}">{esc(sub)}</text>')
    sx = min(sx0 + len(sub) * 8.4 + 14, 770)
    d1 = f"M{sx:.0f},32 H850 l14,14 H890"
    d0 = "M10,32 H34"
    b.append(trace(d0))
    b.append(trace(d1))
    b.append(pad(10, 32, 4))
    b.append(pad(890, 46, 4.5))
    b.append(pulse(d1, 3.4, 0.2))
    return "".join(b)


def section_body(ref, title, sub, body):
    return head(ref, title, sub) + f'<g transform="translate(0 60)">{body}</g>'


# --------------------------------------------------------------------------- 1 features
FEATURES = [
    ("Windows tools", " that stay out of the way: small, no install, one job each"),
    ("Android apps", " that are calm and local-first"),
    ("Firmware", " on ESP32 and other microcontrollers, with OLEDs and an oscilloscope nearby"),
    ("Self-hosting", " in containers: my own tools, running at home"),
    ("Physics and math", " as the debugging tool for everything above"),
]


def features_body():
    b = []
    for i, (bold, rest) in enumerate(FEATURES):
        y = 18 + 36 * i
        d = f"M10,{y} H48"
        b.append(trace(d, 3))
        b.append(pad(10, y, 4))
        b.append(pad(48, y, 5))
        b.append(pulse(d, 2.2, 0.35 * i, 2.5))
        b.append(f'<text x="66" y="{y + 6}" font-family="{SANS}" font-size="16.5">'
                 f'<tspan font-weight="700" fill="{SILK}">{esc(bold)}</tspan>'
                 f'<tspan fill="#b4d4c7">{esc(rest)}</tspan></text>')
    return "".join(b)


# --------------------------------------------------------------------------- 2 block diagram
def box(x, y, w, h, title, sub, ref, n):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{CHIP}" stroke="{CHIP_EDGE}" stroke-width="2"/>'
            f'<text x="{x + 10}" y="{y + 15}" font-family="{MONO}" font-size="9.5" fill="{COPPER}">{ref}</text>'
            f'<text x="{x + 12}" y="{y + 36}" font-family="{SANS}" font-size="15" font-weight="700" fill="{SILK}">{esc(title)}</text>'
            f'<text x="{x + w - 10}" y="{y + 15}" text-anchor="end" font-family="{MONO}" font-size="10" fill="{DIM}">{esc(sub)}</text>'
            + led(x + w - 12, y + h - 12, CYAN if n % 2 else "#fbbf24", (n * 0.37) % 1.5, 1.2 + (n % 3) * 0.3, 3))


def block_body():
    b = []
    ins = [("PHYSICS", "F = m·a"), ("MATH", "∫ f(x) dx"), ("ELECTRONICS", "V = I·R")]
    outs = [("WINDOWS TOOLS", "C# · .NET"), ("ANDROID APPS", "React Native"),
            ("FIRMWARE", "ESP32 · Arduino"), ("SELF-HOSTING", "Docker")]
    in_y = [60, 150, 240]
    out_y = [48, 114, 180, 246]
    cx0, cx1 = 330, 570
    for i, y in enumerate(in_y):
        d = f"M200,{y} H{cx0 - 6}"
        b.append(trace(d, 3))
        b.append(pulse(d, 2.4, 0.4 * i))
        b.append(pad(200, y, 4.5))
    for i, y in enumerate(out_y):
        d = f"M{cx1 + 6},{y} H690"
        b.append(trace(d, 3))
        b.append(pulse(d, 2.4, 0.3 * i + 0.6))
        b.append(pad(690, y, 4.5))
    for y in in_y:
        b.append(f'<rect x="{cx0 - 12}" y="{y - 3}" width="12" height="6" fill="{COPPER}"/>')
    for y in out_y:
        b.append(f'<rect x="{cx1}" y="{y - 3}" width="12" height="6" fill="{COPPER}"/>')
    b.append(f'<rect x="{cx0}" y="24" width="{cx1 - cx0}" height="252" rx="8" fill="#0f1317" stroke="#2c363d" stroke-width="2"/>')
    b.append(f'<circle cx="{cx0 + 16}" cy="40" r="3.5" fill="#3a444c"/>')
    mid = (cx0 + cx1) // 2
    b.append(f'<text x="{mid}" y="146" text-anchor="middle" font-family="{SANS}" font-size="44" font-weight="700" fill="{SILK}">BOAZ</text>')
    b.append(f'<text x="{mid}" y="172" text-anchor="middle" font-family="{MONO}" font-size="13" fill="{DIM}">BC-2026 · CORE</text>')
    b.append(f'<text x="{mid}" y="192" text-anchor="middle" font-family="{MONO}" font-size="10" fill="{DIM}">curiosity in, working things out</text>')
    b.append(led(cx1 - 18, 40, CYAN, 0.2, 1.1, 4))
    for i, (t, sub) in enumerate(ins):
        b.append(box(34, in_y[i] - 28, 166, 56, t, sub, f"IN{i + 1}", i))
    for i, (t, sub) in enumerate(outs):
        b.append(box(690, out_y[i] - 26, 176, 52, t, sub, f"OUT{i + 1}", i + 3))
    b.append(f'<text x="34" y="294" font-family="{MONO}" font-size="10" fill="{SILK}" opacity=".55">FIG. 1 · SIGNAL FLOW</text>')
    return "".join(b)


BLOCK_ALT = "Block diagram: physics, math and electronics go into Boaz, and come out as Windows tools, Android apps, firmware and self-hosting."


# --------------------------------------------------------------------------- 3 pin configuration
def pinout_body():
    b = []
    left = [("C#", ".NET desktop"), ("TypeScript", "apps & web"), ("JavaScript", "web"),
            ("Python", "scripts"), ("React Native", "Expo · mobile"), ("Arduino C++", "firmware")]
    right = [("WINDOWS", "tray tools"), ("ANDROID", "phone apps"), ("WEB", "static sites"),
             ("ESP32", "microcontroller"), ("LINUX", "self-hosting"), ("DOCKER", "containers")]
    ys = [52 + 44 * i for i in range(6)]
    bx0, bx1 = 370, 530
    b.append(f'<rect x="{bx0}" y="24" width="{bx1 - bx0}" height="276" rx="8" fill="#0f1317" stroke="#2c363d" stroke-width="2"/>')
    b.append(f'<path d="M{(bx0 + bx1) // 2 - 14},24 a14,14 0 0 0 28,0" fill="{BOARD}" stroke="#2c363d" stroke-width="2"/>')
    b.append(f'<circle cx="{bx0 + 16}" cy="{ys[0] - 14}" r="3.5" fill="#3a444c"/>')
    b.append(f'<text x="438" y="162" text-anchor="middle" transform="rotate(-90 438 162)" font-family="{SANS}" font-size="30" font-weight="700" fill="{SILK}">BC-2026</text>')
    b.append(f'<text x="466" y="162" text-anchor="middle" transform="rotate(-90 466 162)" font-family="{MONO}" font-size="11" fill="{DIM}">BOAZ COHEN · TOP VIEW</text>')
    for i, y in enumerate(ys):
        b.append(trace(f"M336,{y} H{bx0 - 20}", 3))
        b.append(trace(f"M{bx1 + 20},{y} H564", 3))
        b.append(f'<rect x="{bx0 - 20}" y="{y - 5}" width="20" height="10" fill="{COPPER}"/>'
                 f'<rect x="{bx1}" y="{y - 5}" width="20" height="10" fill="{COPPER}"/>')
        b.append(f'<text x="{bx0 + 8}" y="{y + 4}" font-family="{MONO}" font-size="11" fill="{DIM}">{i + 1}</text>')
        b.append(f'<text x="{bx1 - 8}" y="{y + 4}" text-anchor="end" font-family="{MONO}" font-size="11" fill="{DIM}">{12 - i}</text>')
        b.append(pulse(f"M336,{y} H{bx0}", 1.6, 0.35 * i, 2.5))
        b.append(pulse(f"M{bx1},{y} H564", 1.6, 0.35 * i + 0.9, 2.5))
        n, sub = left[i]
        b.append(f'<rect x="106" y="{y - 15}" width="230" height="30" rx="6" fill="{CHIP}" stroke="{CHIP_EDGE}" stroke-width="2"/>'
                 f'<text x="120" y="{y + 5}" font-family="{SANS}" font-size="14" font-weight="700" fill="{SILK}">{esc(n)}</text>'
                 f'<text x="324" y="{y + 4}" text-anchor="end" font-family="{MONO}" font-size="10" fill="{DIM}">{esc(sub)}</text>')
        n, sub = right[i]
        b.append(f'<rect x="564" y="{y - 15}" width="230" height="30" rx="6" fill="{CHIP}" stroke="{CHIP_EDGE}" stroke-width="2"/>'
                 f'<text x="578" y="{y + 5}" font-family="{SANS}" font-size="14" font-weight="700" fill="{SILK}">{esc(n)}</text>'
                 f'<text x="782" y="{y + 4}" text-anchor="end" font-family="{MONO}" font-size="10" fill="{DIM}">{esc(sub)}</text>')
    b.append(f'<text x="106" y="324" font-family="{MONO}" font-size="10" fill="{SILK}" opacity=".55">FIG. 2 · PIN CONFIGURATION · LEFT: LANGUAGES (IN) · RIGHT: TARGETS (OUT)</text>')
    return "".join(b)


PINOUT_ALT = ("Pin configuration: languages C#, TypeScript, JavaScript, Python, React Native and Arduino C++ on the left, "
              "targets Windows, Android, web, ESP32, Linux and Docker on the right.")


# --------------------------------------------------------------------------- 4 featured: two chips, filled from GitHub
# (slug, repo, role label, stat, unit, display colour).
# Name, about and the numbers are read from GitHub on every build; only the repos are pinned here.
FEATURED = [
    ("passion", "OpenCal", "MY PASSION PROJECT", "commits", "COMMITS", CYAN),
    ("popular", "NoFocusSteal", "MOST POPULAR", "stars", "STARS", AMBER),
]


def fetch_featured():
    """Name, about, stars and commit count of the featured repos, straight from GitHub.
    Runs before anything is written, so an API failure leaves the last good build in place."""
    gh = shutil.which("gh")
    if not gh:
        sys.exit("build.py: the GitHub CLI (gh) is needed to read repo data")
    fields = ("name description isPrivate stargazerCount "
              "defaultBranchRef { target { ... on Commit { history { totalCount } } } }")
    query = "query { " + " ".join(
        f'r{i}: repository(owner: "{OWNER}", name: "{repo}") {{ {fields} }}'
        for i, (_, repo, *_) in enumerate(FEATURED)) + " }"
    try:
        res = subprocess.run([gh, "api", "graphql", "-f", f"query={query}"],
                             capture_output=True, text=True, check=True, timeout=60)
        data = json.loads(res.stdout)["data"]
        feats = []
        for i, (slug, repo, role, stat, unit, color) in enumerate(FEATURED):
            r = data[f"r{i}"]
            if r["isPrivate"]:
                sys.exit(f"build.py: {repo} is private, refusing to publish it")
            value = (r["stargazerCount"] if stat == "stars"
                     else r["defaultBranchRef"]["target"]["history"]["totalCount"])
            feats.append(dict(slug=slug, repo=r["name"], role=role, desc=(r["description"] or "").strip(),
                              value=int(value), unit=unit, color=color, stat=stat))
        return feats
    except subprocess.CalledProcessError as e:
        sys.exit(f"build.py: gh failed: {e.stderr.strip()}")
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, TypeError) as e:
        sys.exit(f"build.py: unexpected GitHub response ({e!r})")


CHIP_W, CHIP_H = 450, 340
BY, BH, BW = 36, 268, 372          # package body: top, height, width
DIG_W, DIG_H, DIG_PITCH = 20, 36, 28
SEGS = {"0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc",
        "5": "afgcd", "6": "afgedc", "7": "abc", "8": "abcdefg", "9": "abcdfg"}


def seven_segment(x, y, t=4.2, w=DIG_W, h=DIG_H):
    """The seven segment polygons of one digit whose top-left corner is (x, y): {letter: 'x,y x,y ...'}."""
    g, c = 1.0, t / 2
    xl, xr, ym = x + c + g, x + w - c - g, y + h / 2

    def hseg(cy):
        return [(xl, cy), (xl + c, cy - c), (xr - c, cy - c), (xr, cy), (xr - c, cy + c), (xl + c, cy + c)]

    def vseg(cx, y0, y1):
        return [(cx, y0), (cx + c, y0 + c), (cx + c, y1 - c), (cx, y1), (cx - c, y1 - c), (cx - c, y0 + c)]

    segs = {"a": hseg(y + c), "g": hseg(ym), "d": hseg(y + h - c),
            "f": vseg(x + c, y + c + g, ym - g), "b": vseg(x + w - c, y + c + g, ym - g),
            "e": vseg(x + c, ym + g, y + h - c - g), "c": vseg(x + w - c, ym + g, y + h - c - g)}
    return {k: " ".join(f"{px:.1f},{py:.1f}" for px, py in v) for k, v in segs.items()}


def star_points(cx, cy, ro=8.0, ri=3.4):
    pts = []
    for k in range(10):
        a = math.pi / 2 + k * math.pi / 5
        r = ro if k % 2 == 0 else ri
        pts.append(f"{cx + r * math.cos(a):.1f},{cy - r * math.sin(a):.1f}")
    return " ".join(pts)


def readout(x, y, w, h, f):
    """Seven-segment display window: lit digits over dim ghost 8s, with an icon and unit on the left."""
    s, col = str(f["value"]), f["color"]
    n = max(4, len(s))
    dw = n * DIG_PITCH - (DIG_PITCH - DIG_W)
    dx, dy = x + w - 16 - dw, y + (h - DIG_H) / 2
    ghost, lit = [], []
    for slot in range(n):
        px = dx + slot * DIG_PITCH
        segs = seven_segment(px, dy)
        ghost += [f'<polygon points="{p}"/>' for p in segs.values()]
        k = slot - (n - len(s))
        if k >= 0:
            lit += [f'<polygon points="{segs[letter]}"/>' for letter in SEGS[s[k]]]
    ix, iy = x + 26, y + h / 2
    if f["stat"] == "stars":
        icon = f'<polygon points="{star_points(ix, iy)}" fill="{col}" filter="url(#glow)"/>'
    else:
        icon = (f'<path d="M{ix - 12},{iy} H{ix + 12}" stroke="{col}" stroke-width="2.5" stroke-linecap="round"/>'
                f'<circle cx="{ix}" cy="{iy}" r="5" fill="#05110c" stroke="{col}" stroke-width="2.5"/>')
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="#05110c" stroke="#1f2c33" stroke-width="2"/>'
            f'<g fill="{col}" opacity=".1">{"".join(ghost)}</g>'
            f'<g fill="{col}" filter="url(#glow)">{"".join(lit)}</g>'
            f'{icon}<text x="{ix + 22}" y="{iy + 4}" font-family="{MONO}" font-size="12" letter-spacing="2" '
            f'fill="{DIM}">{esc(f["unit"])}</text>')


def chip(i, f):
    """Half-width slice with one QFP-style package (pins on all four sides, pin-1 chamfer, a seven-segment
    readout). Chip 0 sits on the left of the board, chip 1 on the right; three short traces cross the seam
    between them and the outer rail lines up with the board rail."""
    left = i == 0
    bx0 = 40 if left else 38
    bx1 = bx0 + BW
    col = f["color"]
    b = [trace(f"M{10 if left else CHIP_W - 10},0 V{CHIP_H}")]

    # stubs from the board rail to two of the outer pins
    for k in (2, 8):
        y = BY + 20 + 20 * k
        d = f"M10,{y} H{bx0 - 12}" if left else f"M{bx1 + 12},{y} H{CHIP_W - 10}"
        b.append(trace(d, 2.5))
        b.append(pad(10 if left else CHIP_W - 10, y, 3.5))
        b.append(pulse(d if left else f"M{CHIP_W - 10},{y} H{bx1 + 12}", 2.2, 0.4 * k, 2.5))

    # traces that cross the seam to the other chip; each pulse is handed over at the seam
    dur = 2.0
    for n, k in enumerate((3, 5, 7)):
        y = BY + 20 + 20 * k
        t0 = 0.3 * n
        right_way = n % 2 == 0                 # True: left chip -> right chip
        if left:
            d = f"M{bx1 + 12},{y} H{CHIP_W}"
            b.append(trace(d, 3))
            p = d if right_way else f"M{CHIP_W},{y} H{bx1 + 12}"
            b.append(pulse(p, dur, t0 if right_way else t0 + dur, 2.5))
        else:
            d = f"M0,{y} H{bx0 - 12}"
            b.append(trace(d, 3))
            p = d if right_way else f"M{bx0 - 12},{y} H0"
            b.append(pulse(p, dur, t0 + dur if right_way else t0, 2.5))

    # pins on all four sides
    for k in range(12):
        y = BY + 20 + 20 * k
        b.append(f'<rect x="{bx0 - 12}" y="{y - 4}" width="12" height="8" fill="{COPPER}"/>'
                 f'<rect x="{bx1}" y="{y - 4}" width="12" height="8" fill="{COPPER}"/>')
    for k in range(15):
        x = bx0 + 30 + 22 * k
        b.append(f'<rect x="{x - 4}" y="{BY - 12}" width="8" height="12" fill="{COPPER}"/>'
                 f'<rect x="{x - 4}" y="{BY + BH}" width="8" height="12" fill="{COPPER}"/>')

    # package body with a chamfered pin-1 corner, and a recessed lid
    b.append(f'<path d="M{bx0 + 20},{BY} H{bx1 - 8} Q{bx1},{BY} {bx1},{BY + 8} V{BY + BH - 8} '
             f'Q{bx1},{BY + BH} {bx1 - 8},{BY + BH} H{bx0 + 8} Q{bx0},{BY + BH} {bx0},{BY + BH - 8} '
             f'V{BY + 20} Z" fill="{CHIP}" stroke="{CHIP_EDGE}" stroke-width="2"/>')
    b.append(f'<rect x="{bx0 + 7}" y="{BY + 7}" width="{BW - 14}" height="{BH - 14}" rx="4" fill="none" '
             f'stroke="#1a2329" stroke-width="1.5"/>')
    b.append(f'<circle cx="{bx0 + 32}" cy="{BY + 26}" r="4" fill="#3b4a53"/>')
    b.append(f'<text x="{bx0 + 46}" y="{BY + 30}" font-family="{MONO}" font-size="11.5" letter-spacing="2.2" '
             f'fill="{col}">{esc(f["role"])}</text>')
    b.append(f'<text x="{bx1 - 16}" y="{BY + 30}" text-anchor="end" font-family="{MONO}" font-size="11" '
             f'fill="{COPPER}">github ↗</text>')
    b.append(f'<line x1="{bx0 + 16}" y1="{BY + 42}" x2="{bx1 - 16}" y2="{BY + 42}" stroke="{CHIP_EDGE}"/>')

    name = f["repo"]
    fs = min(30, int(340 / (len(name) * 0.6)))
    b.append(f'<text x="{bx0 + 16}" y="{BY + 76}" font-family="{SANS}" font-size="{fs}" font-weight="700" '
             f'fill="{SILK}">{esc(name)}</text>')
    lines = textwrap.wrap(f["desc"], 42)
    if len(lines) > 5:
        lines = lines[:5]
        lines[4] = lines[4][:39].rstrip(" ,.;:") + "…"
    for k, line in enumerate(lines):
        b.append(f'<text x="{bx0 + 16}" y="{BY + 104 + k * 18}" font-family="{MONO}" font-size="12.5" '
                 f'fill="#b4d4c7">{esc(line)}</text>')

    b.append(readout(bx0 + 16, BY + BH - 16 - 60, BW - 32, 60, f))
    alt = (f'{f["role"].capitalize()}: {name}. {f["desc"]} '
           f'{f["value"]} {f["unit"].lower()}.')
    return svg(CHIP_W, CHIP_H, "".join(b), alt, rails=False), alt


# --------------------------------------------------------------------------- footer (bottom of the board)
def footer_body():
    b = []
    for x, y in [(30, 50), (870, 50)]:
        b.append(hole(x, y))
    d1, d2 = "M66,40 H220", "M680,40 H834"
    b.append(trace(d1, 2, ".7"))
    b.append(trace(d2, 2, ".7"))
    b.append(pad(66, 40, 4))
    b.append(pad(834, 40, 4))
    b.append(pulse(d1, 3, 0.2, 2.5))
    b.append(pulse("M834,40 H680", 3.4, 1.0, 2.5))
    b.append(f'<text x="450" y="45" text-anchor="middle" font-family="{MONO}" font-size="13" letter-spacing="2" fill="{DIM}">END OF DATASHEET · BC-2026 · PIN 13: NC</text>')
    b.append(f'<text x="450" y="64" text-anchor="middle" font-family="{MONO}" font-size="9" letter-spacing="1.5" fill="{SILK}" opacity=".45">FAB: HAND-ROUTED · FINISH: ENIG · 1.6 MM</text>')
    return "".join(b)


# --------------------------------------------------------------------------- write everything
featured = fetch_featured()      # first, so a GitHub outage can't leave the board half-written

for old in os.listdir(OUT):
    os.remove(os.path.join(OUT, old))

# Non-clickable parts are merged into a few tall slices so there are fewer seams.
TOP_ALT = "Hi, I'm Boaz. High school student, electronics and physics. " + INTRO
MID_ALT = ("1 Features: Windows tools, Android apps, firmware, self-hosting, and physics and math. "
           "2 " + BLOCK_ALT + " 3 " + PINOUT_ALT + " 4 Featured:")
BOTTOM_ALT = "End of datasheet."

save("top.svg", svg(W, 420, header_body() + f'<g transform="translate(0 320)">{intro_body()}</g>', TOP_ALT, "top"))
save("portfolio.svg", connector())
mid = (section_body("1", "FEATURES", "// what it does", features_body())
       + f'<g transform="translate(0 240)">{section_body("2", "BLOCK DIAGRAM", "// signal flow", block_body())}</g>'
       + f'<g transform="translate(0 600)">{section_body("3", "PIN CONFIGURATION", "// what I speak, where it runs", pinout_body())}</g>'
       + f'<g transform="translate(0 1000)">{head("4", "FEATURED", "// live from GitHub")}</g>')
save("mid.svg", svg(W, 1060, mid, MID_ALT))
save("bottom.svg", svg(W, 80, footer_body(), BOTTOM_ALT, "bottom"))
chips = []
for i, feat in enumerate(featured):
    content, alt = chip(i, feat)
    save(f"chip-{feat['slug']}.svg", content)
    chips.append((feat, alt))


def esc_attr(s):
    return esc(s)


def img(src, alt, width="100%"):
    # align=top removes the inline baseline gap so the slices butt together
    return f'<img src="./assets/{src}" alt="{esc_attr(alt)}" width="{width}" align="top">'


def link(href, inner):
    return f'<a href="{href}">{inner}</a>'


lines = [
    img("top.svg", TOP_ALT),
    link("https://boazcohen.dev", img("portfolio.svg", "Portfolio: boazcohen.dev")),
    img("mid.svg", MID_ALT),
]
# no whitespace between the two chips so they share a line
lines.append("".join(link(GH + feat["repo"], img(f"chip-{feat['slug']}.svg", alt, "49.9%")) for feat, alt in chips))
lines.append(img("bottom.svg", BOTTOM_ALT))

readme = "<p>\n" + "\n".join(lines) + "\n</p>\n"
with open(os.path.join(HERE, "README.md"), "w", encoding="utf-8") as f:
    f.write(readme)

preview = f"""<!doctype html><meta charset="utf-8"><title>README preview</title>
<style>body{{background:#0d1117;color:#e6edf3;font-family:system-ui,sans-serif;margin:0;padding:24px}}
.md{{max-width:888px;margin:0 auto}} .md img{{max-width:100%}} a{{color:#58a6ff}}</style>
<div class="md">{readme}</div>"""
with open(os.path.join(HERE, "preview.html"), "w", encoding="utf-8") as f:
    f.write(preview)
print("ok", len(os.listdir(OUT)), "svgs")
