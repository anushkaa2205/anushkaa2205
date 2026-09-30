#!/usr/bin/env python3
"""Draws the README's custom SVGs.

  assets/banner-{dark,light}.svg          two-panel terminal: VISUAL.MAP portrait + SYSTEM.INFO
  assets/radar-{dark,light}.svg           skills radar
  assets/radar-languages-{dark,light}.svg languages radar

Usage (from the repo root):  python scripts/build_assets.py
Everything is read from assets/profile.json.

Portrait: put a photo at assets/photo.png (background removed = best) or assets/photo.jpg.
It is cropped to your head and shoulders, shrunk to a small grid and turned into 1-bit dots
with Floyd-Steinberg dithering in serpentine order (the "FS/SERPENTINE" label).
Photos need Pillow (pip install pillow). Without a photo a placeholder silhouette is drawn.
"""
import json
import math
import pathlib
from xml.sax.saxutils import escape

ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
CFG = json.loads((ASSETS / "profile.json").read_text(encoding="utf-8"))

FONT = "'JetBrains Mono','Fira Code',Consolas,Menlo,'DejaVu Sans Mono',monospace"
CHAR_W = 0.6  # monospace glyph width as a fraction of font size, used to place dotted leaders

THEMES = {
    "dark": dict(bg="#0d1117", win="#0f1520", bar="#131b27", panel="#111a27", phead="#152033",
                 border="#233047", text="#c9d1d9", dim="#7d8590", key="#B565FF", accent="#FF2E97",
                 value="#ffffff", grid="#30363d", ok="#3fb950", lead="#3a4659",
                 dot_a="#B565FF", dot_b="#FF2E97", pill="#1d1633", fill="0.28"),
    "light": dict(bg="#ffffff", win="#ffffff", bar="#f6f8fa", panel="#fbfcfe", phead="#f1f3f7",
                  border="#d0d7de", text="#24292f", dim="#57606a", key="#8E2DE2", accent="#D6146F",
                  value="#1f2328", grid="#d0d7de", ok="#1a7f37", lead="#c3cad3",
                  dot_a="#8E2DE2", dot_b="#D6146F", pill="#f3eaff", fill="0.20"),
}


# ---------------------------------------------------------------- portrait -> dots

def _placeholder(gw: int, gh: int):
    """Soft head-and-shoulders silhouette as a grayscale grid (0..1), no Pillow needed."""
    img = []
    for y in range(gh):
        row = []
        for x in range(gw):
            u, v = x / gw, y / gh
            head = ((u - 0.5) / 0.19) ** 2 + ((v - 0.34) / 0.22) ** 2
            body = ((u - 0.5) / 0.44) ** 2 + ((v - 1.05) / 0.42) ** 2
            val = 0.0
            if head < 1:
                val = 0.75 - 0.35 * head + 0.15 * (0.5 - v)
            elif body < 1 and v > 0.58:
                val = 0.55 - 0.25 * body
            row.append(max(0.0, min(1.0, val)))
        img.append(row)
    return img


def _photo(path: pathlib.Path, gw: int, gh: int, p: dict):
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps  # only needed for photos

    im = Image.open(path)
    im = ImageOps.exif_transpose(im).convert("RGBA")
    alpha = im.getchannel("A")
    box = alpha.point(lambda a: 255 if a > 40 else 0).getbbox() or (0, 0, im.width, im.height)

    # crop: subject width + margin, panel aspect ratio, anchored just above the head
    l, t, r, b = box
    w = (r - l) * 1.06
    h = w * gh / gw
    cx = (l + r) / 2
    top = max(0, t - 0.04 * h)
    crop = (int(cx - w / 2), int(top), int(cx + w / 2), int(top + h))

    base = Image.new("RGBA", im.size, (0, 0, 0, 255))
    base.alpha_composite(im)  # transparent background becomes black = no dots
    gray = base.convert("L").crop(crop).resize((gw, gh), Image.LANCZOS)
    mask = alpha.crop(crop).resize((gw, gh), Image.LANCZOS)

    gray = ImageOps.autocontrast(gray, cutoff=1, mask=mask.point(lambda a: 255 if a > 128 else 0))
    gray = ImageEnhance.Contrast(gray).enhance(p.get("contrast", 1.3))
    gray = ImageEnhance.Brightness(gray).enhance(p.get("brightness", 1.0))
    gamma = p.get("gamma", 1.0)  # < 1 lifts midtones (faces), > 1 darkens them
    gray = gray.point(lambda v: int(255 * (v / 255) ** gamma))
    if p.get("sharpen", 0):
        gray = gray.filter(ImageFilter.UnsharpMask(radius=1.2, percent=int(p["sharpen"]), threshold=2))
    if p.get("invert"):
        gray = ImageOps.invert(gray)

    g, m = gray.load(), mask.load()
    return [[(g[x, y] / 255.0) * (m[x, y] / 255.0) for x in range(gw)] for y in range(gh)]


def dither(img):
    """Floyd-Steinberg, serpentine scan. Returns list of (x, y) 'on' cells."""
    h, w = len(img), len(img[0])
    buf = [row[:] for row in img]
    on = []
    for y in range(h):
        ltr = y % 2 == 0
        xs = range(w) if ltr else range(w - 1, -1, -1)
        d = 1 if ltr else -1
        for x in xs:
            old = buf[y][x]
            new = 1.0 if old >= 0.5 else 0.0
            if new:
                on.append((x, y))
            err = old - new
            if 0 <= x + d < w:
                buf[y][x + d] += err * 7 / 16
            if y + 1 < h:
                if 0 <= x - d < w:
                    buf[y + 1][x - d] += err * 3 / 16
                buf[y + 1][x] += err * 5 / 16
                if 0 <= x + d < w:
                    buf[y + 1][x + d] += err * 1 / 16
    return on


def portrait_points():
    p = CFG.get("portrait", {})
    gw, gh = p.get("grid", [150, 170])
    for rel in p.get("files", []):
        path = ROOT / rel
        if path.exists():
            try:
                return dither(_photo(path, gw, gh, p)), gw, gh, f"photo: {rel}"
            except ImportError:
                print("! Pillow not installed (pip install pillow): using placeholder portrait")
                break
    return dither(_placeholder(gw, gh)), gw, gh, "placeholder silhouette"


# ---------------------------------------------------------------- banner

def banner(t: dict, pts, gw: int, gh: int, uid: str) -> str:
    W, H = 1200, 620
    PAD = 24
    TOP = 56                       # below the window bar
    PY, PH = TOP + 22, 520         # panels
    LX, LW = PAD, 440
    RX = LX + LW + 20
    RW = W - PAD - RX
    HEAD = 38

    o = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
        f'role="img" aria-label="{escape(CFG.get("window_title", "profile.sh"))}">',
        "<defs>",
        f'<linearGradient id="d{uid}" x1="0" y1="0" x2="0.35" y2="1">'
        f'<stop offset="0" stop-color="{t["dot_a"]}"/><stop offset="1" stop-color="{t["dot_b"]}"/></linearGradient>',
        "<style>",
        f"text{{font-family:{FONT}}}",
        ".r{opacity:0;animation:in .45s ease-out forwards}",
        ".pic{opacity:0;animation:in 1.6s ease-out .2s forwards}",
        "@keyframes in{to{opacity:1}}",
        ".blink{animation:bl 1.4s steps(1) infinite}",
        "@keyframes bl{50%{opacity:.15}}",
        "@media (prefers-reduced-motion:reduce){.r,.pic{opacity:1;animation:none}.blink{animation:none}}",
        "</style>",
        "</defs>",
        # window
        f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="14" fill="{t["win"]}" stroke="{t["border"]}" stroke-width="1.5"/>',
        f'<path d="M1 {TOP} V15 a14 14 0 0 1 14 -14 H{W-15} a14 14 0 0 1 14 14 V{TOP} Z" fill="{t["bar"]}"/>',
        f'<line x1="1" y1="{TOP}" x2="{W-1}" y2="{TOP}" stroke="{t["border"]}"/>',
        '<circle cx="30" cy="28" r="7" fill="#ff5f56"/><circle cx="54" cy="28" r="7" fill="#ffbd2e"/>'
        '<circle cx="78" cy="28" r="7" fill="#27c93f"/>',
        f'<text x="{W/2}" y="33" text-anchor="middle" fill="{t["dim"]}" style="font-size:14px">'
        f'{escape(CFG.get("window_title", "profile.sh --live"))}</text>',
    ]

    def panel(x, w, title, right_svg=""):
        o.append(f'<rect x="{x}" y="{PY}" width="{w}" height="{PH}" rx="8" fill="{t["panel"]}" stroke="{t["border"]}"/>')
        o.append(f'<path d="M{x} {PY+HEAD} V{PY+8} a8 8 0 0 1 8 -8 H{x+w-8} a8 8 0 0 1 8 8 V{PY+HEAD} Z" fill="{t["phead"]}"/>')
        o.append(f'<line x1="{x}" y1="{PY+HEAD}" x2="{x+w}" y2="{PY+HEAD}" stroke="{t["border"]}"/>')
        o.append(f'<text x="{x+16}" y="{PY+24}" fill="{t["key"]}" style="font-size:13px;font-weight:700;letter-spacing:1px">{title}</text>')
        o.append(right_svg)

    # ---- left: VISUAL.MAP
    panel(LX, LW, "VISUAL.MAP",
          f'<text x="{LX+LW-16}" y="{PY+24}" text-anchor="end" fill="{t["dim"]}" style="font-size:11px">'
          f'{gw*2}×{gh*2} / 1-BIT</text>')
    area_top, area_bot = PY + HEAD + 14, PY + PH - 40
    cell = min((LW - 60) / gw, (area_bot - area_top) / gh)
    iw, ih = gw * cell, gh * cell
    ix, iy = LX + (LW - iw) / 2, area_top + (area_bot - area_top - ih) / 2
    s = cell * 0.78
    path = "".join(f"M{ix + x*cell:.1f} {iy + y*cell:.1f}h{s:.1f}v{s:.1f}h-{s:.1f}z" for x, y in pts)
    o.append(f'<path class="pic" d="{path}" fill="url(#d{uid})"/>')
    # corner brackets
    bx0, by0, bx1, by1, k = LX + 14, area_top - 4, LX + LW - 14, area_bot + 4, 12
    for d in (f"M{bx0} {by0+k}V{by0}H{bx0+k}", f"M{bx1-k} {by0}H{bx1}V{by0+k}",
              f"M{bx0} {by1-k}V{by1}H{bx0+k}", f"M{bx1-k} {by1}H{bx1}V{by1-k}"):
        o.append(f'<path d="{d}" fill="none" stroke="{t["dim"]}" stroke-width="1.2"/>')
    o.append(f'<text x="{LX+22}" y="{PY+PH-14}" fill="{t["dim"]}" style="font-size:11px">'
             f'PTS {len(pts)} · FS/SERPENTINE</text>')

    # ---- right: SYSTEM.INFO
    handle = escape(CFG.get("handle", ""))
    pill_w = len(CFG.get("handle", "")) * 13 * CHAR_W + 34
    px = RX + RW - 14 - pill_w
    right = (
        f'<circle class="blink" cx="{px-66}" cy="{PY+19}" r="4" fill="{t["accent"]}"/>'
        f'<text x="{px-56}" y="{PY+24}" fill="{t["accent"]}" style="font-size:12px;font-weight:700">LIVE</text>'
        f'<rect x="{px}" y="{PY+7}" width="{pill_w:.0f}" height="24" rx="12" fill="{t["pill"]}"/>'
        f'<text x="{px + pill_w/2:.0f}" y="{PY+24}" text-anchor="middle" fill="{t["key"]}" '
        f'style="font-size:13px;font-weight:700">{handle}</text>'
    )
    panel(RX, RW, "SYSTEM.INFO", right)

    rows = CFG["info"]
    FS, ROW = 15, 26
    y0 = PY + HEAD + 36
    lx, rx = RX + 20, RX + RW - 20
    for i, (label, value) in enumerate(rows):
        y = y0 + ROW * i
        lead_x1 = lx + len(label) * FS * CHAR_W + 12
        lead_x2 = rx - len(value) * FS * CHAR_W - 12
        lead = (f'<line x1="{lead_x1:.0f}" y1="{y-4}" x2="{lead_x2:.0f}" y2="{y-4}" stroke="{t["lead"]}" '
                f'stroke-width="1.2" stroke-dasharray="1.5 5"/>' if lead_x2 > lead_x1 + 10 else "")
        o.append(
            f'<g class="r" style="animation-delay:{0.35 + i*0.09:.2f}s">'
            f'<text x="{lx}" y="{y}" fill="{t["dim"]}" style="font-size:{FS}px">{escape(label)}</text>{lead}'
            f'<text x="{rx}" y="{y}" text-anchor="end" fill="{t["value"]}" style="font-size:{FS}px">{escape(value)}</text></g>'
        )
    fy = PY + PH - 34
    o.append(f'<line x1="{RX+16}" y1="{fy}" x2="{RX+RW-16}" y2="{fy}" stroke="{t["border"]}"/>')
    o.append(f'<circle cx="{RX+22}" cy="{fy+19}" r="3" fill="{t["ok"]}"/>')
    o.append(f'<text x="{RX+32}" y="{fy+23}" fill="{t["ok"]}" style="font-size:11px">'
             f'{escape(CFG.get("footer_left", ""))}</text>')
    o.append(f'<text x="{RX+RW-16}" y="{fy+23}" text-anchor="end" fill="{t["dim"]}" style="font-size:11px">'
             f'{escape(CFG.get("footer_right", ""))}</text>')
    o.append("</svg>")
    return "\n".join(o)


# ---------------------------------------------------------------- radar charts

def radar(t: dict, title: str, axes: list, uid: str) -> str:
    W, H = 520, 440
    cx, cy, R = W / 2, 238, 138
    n = len(axes)

    def pt(i: int, frac: float):
        a = math.radians(-90 + i * 360 / n)
        return cx + R * frac * math.cos(a), cy + R * frac * math.sin(a)

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{escape(title)} radar chart">',
        "<defs>",
        f'<linearGradient id="g{uid}" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#8E2DE2"/><stop offset="1" stop-color="#FF2E97"/></linearGradient>',
        f"<style>text{{font-family:{FONT}}}</style>",
        "</defs>",
        f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="12" fill="{t["bg"]}" stroke="{t["border"]}" stroke-width="2"/>',
        f'<text x="{cx}" y="38" text-anchor="middle" fill="{t["accent"]}" style="font-size:17px;font-weight:600">{escape(title)}</text>',
    ]
    for ring in (0.25, 0.5, 0.75, 1.0):
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, ring) for i in range(n)))
        out.append(f'<polygon points="{pts}" fill="none" stroke="{t["grid"]}" stroke-width="1"/>')
    for i, (label, _) in enumerate(axes):
        x, y = pt(i, 1.0)
        out.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="{t["grid"]}" stroke-width="1"/>')
        a = math.radians(-90 + i * 360 / n)
        lx, ly = cx + (R + 16) * math.cos(a), cy + (R + 16) * math.sin(a)
        cos, sin = math.cos(a), math.sin(a)
        anchor = "start" if cos > 0.3 else "end" if cos < -0.3 else "middle"
        dy = 4 if abs(sin) < 0.5 else (-2 if sin < 0 else 14)
        out.append(f'<text x="{lx:.1f}" y="{ly + dy:.1f}" text-anchor="{anchor}" fill="{t["text"]}" '
                   f'style="font-size:14px">{escape(label)}</text>')
    pts = [pt(i, max(0, min(100, v)) / 100) for i, (_, v) in enumerate(axes)]
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    out.append(f'<polygon points="{poly}" fill="url(#g{uid})" fill-opacity="{t["fill"]}" '
               f'stroke="url(#g{uid})" stroke-width="2.5" stroke-linejoin="round"/>')
    for x, y in pts:
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{t["accent"]}" stroke="{t["bg"]}" stroke-width="1.5"/>')
    out.append("</svg>")
    return "\n".join(out)


def main() -> None:
    pts, gw, gh, source = portrait_points()
    print(f"portrait: {source}, {len(pts)} dots")
    written = []
    for name, t in THEMES.items():
        path = ASSETS / f"banner-{name}.svg"
        path.write_text(banner(t, pts, gw, gh, name), encoding="utf-8")
        written.append(path)
        for key, spec in CFG["radars"].items():
            fname = "radar" if key == "skills" else f"radar-{key}"
            path = ASSETS / f"{fname}-{name}.svg"
            path.write_text(radar(t, spec["title"], spec["axes"], f"{key}{name}"), encoding="utf-8")
            written.append(path)
    for p in written:
        print("wrote", p.relative_to(ROOT), f"({p.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
