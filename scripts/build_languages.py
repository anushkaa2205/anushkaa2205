#!/usr/bin/env python3
"""Draws the "most used languages" card into assets/languages-{dark,light}.svg.

Usage (from the repo root):  python scripts/build_languages.py
- Adds up the bytes of code per language across your public, non-fork repos (GitHub API).
- Saves the totals to assets/languages.json, so the card can be redrawn offline:
      python scripts/build_languages.py --offline
- Optional: set GITHUB_TOKEN to avoid the 60-requests/hour anonymous limit.

This replaces the github-readme-stats "top-langs" widget, a shared public server that
often gets rate-limited and shows a broken image.
"""
import json
import os
import pathlib
import sys
import urllib.request
from xml.sax.saxutils import escape

ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
DATA = ASSETS / "languages.json"

USER = "anushkaa2205"
SKIP_REPOS = {USER}                       # the profile repo itself (only holds these scripts)
SKIP_LANGS = {"PowerShell", "Batchfile", "Dockerfile", "Procfile", "Makefile"}  # tooling, not "languages I code in"
TOP_N = 6

# GitHub's own language colours, so the card matches the rest of GitHub
LANG_COLORS = {
    "JavaScript": "#f1e05a", "TypeScript": "#3178c6", "HTML": "#e34c26", "CSS": "#663399",
    "Python": "#3572A5", "Java": "#b07219", "C++": "#f34b7d", "C": "#555555",
    "Shell": "#89e051", "SCSS": "#c6538c", "Jupyter Notebook": "#DA5B0B", "EJS": "#a91e50",
    "Go": "#00ADD8", "Rust": "#dea584", "PHP": "#4F5D95", "Kotlin": "#A97BFF",
}
OTHER_COLOR = "#8b949e"

FONT = "'JetBrains Mono','Fira Code',Consolas,Menlo,'DejaVu Sans Mono',monospace"
THEMES = {
    "dark": dict(bg="#0d1117", border="#30363d", title="#FF2E97", text="#c9d1d9", dim="#8b949e", track="#21262d"),
    "light": dict(bg="#ffffff", border="#d0d7de", title="#D6146F", text="#24292f", dim="#57606a", track="#eaeef2"),
}


def api(url: str):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": USER})
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch() -> dict:
    repos = api(f"https://api.github.com/users/{USER}/repos?per_page=100&type=owner")
    totals, used = {}, []
    for repo in repos:
        if repo["fork"] or repo["name"] in SKIP_REPOS:
            continue
        langs = api(repo["languages_url"])
        if langs:
            used.append(repo["name"])
        for lang, size in langs.items():
            if lang not in SKIP_LANGS:
                totals[lang] = totals.get(lang, 0) + size
    return {"user": USER, "repos": sorted(used), "bytes": dict(sorted(totals.items(), key=lambda kv: -kv[1]))}


def card(t: dict, data: dict) -> str:
    items = list(data["bytes"].items())
    total = sum(v for _, v in items) or 1
    top = items[:TOP_N]
    rest = sum(v for _, v in items[TOP_N:])
    rows = [(k, v, LANG_COLORS.get(k, OTHER_COLOR)) for k, v in top]
    if rest:
        rows.append(("Other", rest, OTHER_COLOR))

    W, PAD = 480, 26
    bar_y, bar_h = 64, 10
    leg_y0, leg_row = bar_y + bar_h + 34, 28
    n_rows = (len(rows) + 1) // 2
    H = leg_y0 + (n_rows - 1) * leg_row + 30

    o = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="most used languages">',
        f"<defs><style>text{{font-family:{FONT}}}</style>",
        f'<clipPath id="bar"><rect x="{PAD}" y="{bar_y}" width="{W - 2*PAD}" height="{bar_h}" rx="5"/></clipPath></defs>',
        f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="12" fill="{t["bg"]}" stroke="{t["border"]}" stroke-width="2"/>',
        f'<text x="{PAD}" y="40" fill="{t["title"]}" style="font-size:17px;font-weight:600">most used languages</text>',
        f'<rect x="{PAD}" y="{bar_y}" width="{W - 2*PAD}" height="{bar_h}" rx="5" fill="{t["track"]}"/>',
        '<g clip-path="url(#bar)">',
    ]
    x, span = float(PAD), W - 2 * PAD
    for _, v, c in rows:
        w = span * v / total
        o.append(f'<rect x="{x:.2f}" y="{bar_y}" width="{w + 0.5:.2f}" height="{bar_h}" fill="{c}"/>')
        x += w
    o.append("</g>")

    col_x = (PAD, W / 2 + 6)
    for i, (name, v, c) in enumerate(rows):
        cx = col_x[i % 2]
        y = leg_y0 + (i // 2) * leg_row
        pct = 100 * v / total
        o.append(f'<circle cx="{cx + 6}" cy="{y - 5}" r="6" fill="{c}"/>')
        o.append(f'<text x="{cx + 20}" y="{y}" fill="{t["text"]}" style="font-size:14px">{escape(name)}</text>')
        o.append(f'<text x="{cx + 200}" y="{y}" text-anchor="end" fill="{t["dim"]}" style="font-size:14px">{pct:.1f}%</text>')
    o.append("</svg>")
    return "\n".join(o)


def main() -> None:
    if "--offline" in sys.argv:
        data = json.loads(DATA.read_text(encoding="utf-8"))
    else:
        try:
            data = fetch()
            DATA.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        except Exception as e:  # network down / rate limited: keep the last good data
            if not DATA.exists() or os.environ.get("CI"):  # in Actions: fail loudly
                raise
            print(f"! GitHub API failed ({e}); redrawing from saved {DATA.name}")
            data = json.loads(DATA.read_text(encoding="utf-8"))
    for name, t in THEMES.items():
        path = ASSETS / f"languages-{name}.svg"
        path.write_text(card(t, data), encoding="utf-8")
        print("wrote", path.relative_to(ROOT))
    total = sum(data["bytes"].values()) or 1
    print("repos:", ", ".join(data["repos"]))
    print("top:", ", ".join(f"{k} {100*v/total:.1f}%" for k, v in list(data["bytes"].items())[:TOP_N]))


if __name__ == "__main__":
    main()
