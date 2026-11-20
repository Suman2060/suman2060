#!/usr/bin/env python3
"""Animated mountain-bike contribution graph.

Usage:  python3 generate_bike.py USERNAME OUTPUT.svg [--demo]

Reads your public contribution calendar, draws a mountain ridge whose height
follows your weekly activity, and sends a bike riding along it. Each week of
the calendar lights up as the bike passes.
"""
import math
import random
import re
import sys
import urllib.request
from datetime import date, timedelta

CELL, PITCH = 12, 15
X0, BASE, GRID_Y = 30, 128, 150
DUR = 16
LEVEL_FILL = ["#6C8FB5", "#B7DCA0", "#8BC34A", "#558B2F", "#2E7D32"]
LEVEL_OP = [0.22, 1, 1, 1, 1]


def fetch(user):
    req = urllib.request.Request(
        f"https://github.com/users/{user}/contributions",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    page = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    tips = {}
    for m in re.finditer(r'<tool-tip[^>]*\bfor="([^"]+)"[^>]*>([^<]*)</tool-tip>', page):
        n = re.search(r"(\d+)\s+contribution", m.group(2))
        tips[m.group(1)] = int(n.group(1)) if n else 0
    days = []
    for m in re.finditer(r"<td\b[^>]*>", page):
        tag = m.group(0)
        d = re.search(r'data-date="(\d{4})-(\d{2})-(\d{2})"', tag)
        lv = re.search(r'data-level="(\d)"', tag)
        if not d or not lv:
            continue
        cid = re.search(r'\bid="([^"]+)"', tag)
        level = int(lv.group(1))
        count = tips.get(cid.group(1), level) if cid else level
        days.append((date(*map(int, d.groups())), level, count))
    if len(days) < 50:
        raise SystemExit("Could not read the contribution calendar.")
    return sorted(days)


def demo():
    random.seed(4)
    d = date.today()
    while d.weekday() != 6:
        d -= timedelta(days=1)
    start = d - timedelta(days=52 * 7)
    days, mood = [], 0.4
    for i in range(52 * 7 + 3):
        if i % 7 == 0:
            mood = max(0.05, min(0.9, mood + random.uniform(-0.3, 0.3)))
        c = int(random.random() < mood) * random.randint(1, 9)
        lv = 0 if c == 0 else 1 if c < 3 else 2 if c < 5 else 3 if c < 8 else 4
        days.append((start + timedelta(days=i), lv, c))
    return days


def bez(p0, p1, p2, p3, t):
    u = 1 - t
    return tuple(u**3 * a + 3 * u**2 * t * b + 3 * u * t**2 * c + t**3 * e
                 for a, b, c, e in zip(p0, p1, p2, p3))


def build(days):
    first = days[0][0]
    first_dow = (first.weekday() + 1) % 7
    cells, weekly = [], {}
    for d, lv, c in days:
        idx = d.toordinal() - first.toordinal() + first_dow
        col, row = idx // 7, idx % 7
        cells.append((col, row, lv, c))
        weekly[col] = weekly.get(col, 0) + c
    ncols = max(weekly) + 1
    totals = [weekly.get(i, 0) for i in range(ncols)]
    sm = [(totals[max(i - 1, 0)] + 2 * totals[i] + totals[min(i + 1, ncols - 1)]) / 4
          for i in range(ncols)]
    peak = max(sm) or 1
    xs = [X0 + i * PITCH + CELL / 2 for i in range(ncols)]
    ys = [BASE - (12 + 68 * s / peak) for s in sm]
    xe = X0 + ncols * PITCH - (PITCH - CELL)
    pts = [(X0, ys[0])] + list(zip(xs, ys)) + [(xe, ys[-1])]

    # smooth ridge + arc-length table (to time the lighting of each week)
    d_path = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    samples, acc = [(pts[0][0], 0.0)], 0.0
    for a, b in zip(pts, pts[1:]):
        mx = (a[0] + b[0]) / 2
        c1, c2 = (mx, a[1]), (mx, b[1])
        d_path += f" C{mx:.1f},{a[1]:.1f} {mx:.1f},{b[1]:.1f} {b[0]:.1f},{b[1]:.1f}"
        prev = a
        for k in range(1, 25):
            p = bez(a, c1, c2, b, k / 24)
            acc += math.dist(prev, p)
            samples.append((p[0], acc))
            prev = p
    total_len = acc

    def frac(x):
        for (xa, la), (xb, lb) in zip(samples, samples[1:]):
            if xa <= x <= xb:
                return (la + (lb - la) * ((x - xa) / (xb - xa or 1))) / total_len
        return 1.0

    W = X0 * 2 + ncols * PITCH - (PITCH - CELL)
    H = GRID_Y + 7 * PITCH + 38
    total = sum(c for _, _, _, c in cells)
    ride = 0.9

    cols_svg = []
    for col in range(ncols):
        t0 = ride * frac(xs[col])
        t1 = min(t0 + 0.012, 0.95)
        rects = "".join(
            f'<rect x="{X0 + col * PITCH}" y="{GRID_Y + row * PITCH}" width="{CELL}" height="{CELL}" '
            f'rx="3" fill="{LEVEL_FILL[lv]}" fill-opacity="{LEVEL_OP[lv]}"/>'
            for c_, row, lv, _ in cells if c_ == col)
        cols_svg.append(
            f'<g>{rects}<animate attributeName="opacity" values="0.3;0.3;1;1;0.3" '
            f'keyTimes="0;{t0:.4f};{t1:.4f};0.96;1" dur="{DUR}s" repeatCount="indefinite"/></g>')

    legend_x = W - X0 - 5 * PITCH - 58
    legend = f'<text x="{legend_x}" y="{H - 14}" font-size="11" fill="#6C8FB5">Less</text>'
    for i in range(5):
        legend += (f'<rect x="{legend_x + 30 + i * PITCH}" y="{H - 24}" width="{CELL}" height="{CELL}" rx="3" '
                   f'fill="{LEVEL_FILL[i]}" fill-opacity="{LEVEL_OP[i]}"/>')
    legend += f'<text x="{legend_x + 30 + 5 * PITCH + 4}" y="{H - 14}" font-size="11" fill="#6C8FB5">More</text>'

    wheel = lambda cx, dur: (
        f'<g transform="translate({cx},-9)"><circle r="9" fill="none" stroke="#263238" stroke-width="2.6"/>'
        f'<g><animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="{dur}s" repeatCount="indefinite"/>'
        '<line x1="-8" y1="0" x2="8" y2="0" stroke="#78909C" stroke-width="1"/>'
        '<line x1="0" y1="-8" x2="0" y2="8" stroke="#78909C" stroke-width="1"/>'
        '<line x1="-5.6" y1="-5.6" x2="5.6" y2="5.6" stroke="#78909C" stroke-width="1"/>'
        '<line x1="-5.6" y1="5.6" x2="5.6" y2="-5.6" stroke="#78909C" stroke-width="1"/>'
        '<circle cx="8" cy="0" r="1.4" fill="#FFD54F"/></g>'
        '<circle r="1.8" fill="#263238"/></g>')

    bike = f'''<g>
  <animateMotion dur="{DUR}s" repeatCount="indefinite" rotate="auto" calcMode="linear" keyPoints="0;1;1" keyTimes="0;{ride};1"><mpath href="#ridge"/></animateMotion>
  <animate attributeName="opacity" values="0;1;1;0;0" keyTimes="0;0.03;{ride};0.95;1" dur="{DUR}s" repeatCount="indefinite"/>
  <g transform="scale(0.85)">
    <g><animateTransform attributeName="transform" type="translate" values="0,0;0,-1.2;0,0" dur="0.5s" repeatCount="indefinite"/>
    <g fill="#B0BEC5"><circle cx="-26" cy="-3" r="2"><animate attributeName="opacity" values="0.7;0" dur="0.9s" repeatCount="indefinite"/></circle>
      <circle cx="-33" cy="-6" r="1.5"><animate attributeName="opacity" values="0.6;0" dur="0.9s" begin="0.3s" repeatCount="indefinite"/></circle>
      <circle cx="-39" cy="-2" r="1.2"><animate attributeName="opacity" values="0.5;0" dur="0.9s" begin="0.6s" repeatCount="indefinite"/></circle></g>
    {wheel(-14, 0.55)}{wheel(14, 0.55)}
    <g fill="none" stroke-linecap="round" stroke-linejoin="round">
      <polyline points="-14,-9 -2,-9 9,-21 -6,-22 -14,-9" stroke="#FF7043" stroke-width="2.6"/>
      <line x1="-2" y1="-9" x2="-6" y2="-22" stroke="#FF7043" stroke-width="2.6"/>
      <polyline points="9,-21 14,-9" stroke="#455A64" stroke-width="2.4"/>
      <polyline points="9,-21 8,-26 12,-26" stroke="#263238" stroke-width="2.2"/>
      <line x1="-9" y1="-23.5" x2="-3" y2="-23.5" stroke="#263238" stroke-width="3.2"/>
    </g>
    <polyline points="-5,-25 1,-17 -2,-10" fill="none" stroke="#37474F" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round"/>
    <g transform="translate(-2,-9)"><animateTransform attributeName="transform" type="translate" values="-2,-9" dur="1s" repeatCount="indefinite"/>
      <circle r="2.4" fill="#263238"/></g>
    <line x1="-5" y1="-25" x2="4" y2="-35" stroke="#FFD54F" stroke-width="5.4" stroke-linecap="round"/>
    <line x1="4" y1="-35" x2="10" y2="-26.5" stroke="#FFD54F" stroke-width="3.2" stroke-linecap="round"/>
    <circle cx="7" cy="-39.5" r="4" fill="#FFCC80"/>
    <path d="M2.8,-40.5 Q7,-48 11.4,-40.5 Z" fill="#E53935"/>
    </g>
  </g>
</g>'''

    flag = (f'<line x1="{xe - 4}" y1="{ys[-1]:.1f}" x2="{xe - 4}" y2="{ys[-1] - 34:.1f}" stroke="#5D4037" stroke-width="2.2"/>'
            f'<g transform="translate({xe - 3},{ys[-1] - 34:.1f}) scale(0.7)">'
            '<path d="M0,0 L22,17 L8,17 L24,36 L0,36 Z" fill="#DC143C" stroke="#003893" stroke-width="2.5" stroke-linejoin="round">'
            '<animateTransform attributeName="transform" type="skewY" values="0;6;0;-4;0" dur="1.8s" repeatCount="indefinite"/></path></g>')

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
<defs>
  <linearGradient id="rock" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#7FA3C7"/><stop offset="1" stop-color="#3E6A8F"/></linearGradient>
  <path id="ridge" d="{d_path}"/>
</defs>
<g font-family="'Trebuchet MS','Segoe UI',Verdana,sans-serif">
<path d="{d_path} L{xe:.1f},{BASE + 8} L{X0},{BASE + 8} Z" fill="url(#rock)" opacity="0.9"/>
<use href="#ridge" fill="none" stroke="#F4FAFF" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
{flag}
{''.join(cols_svg)}
<text x="{X0}" y="{H - 14}" font-size="12" font-weight="700" fill="#6C8FB5">{total} contributions in the last year</text>
{legend}
{bike}
</g>
</svg>
'''


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    user, out = args[0], args[1]
    data = demo() if "--demo" in sys.argv else fetch(user)
    open(out, "w", encoding="utf-8").write(build(data))
    print("wrote", out)
