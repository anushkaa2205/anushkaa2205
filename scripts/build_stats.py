#!/usr/bin/env python3
"""Draws the "GitHub stats" and "streak" cards into assets/ from live GitHub data.

  assets/stats-{dark,light}.svg    stars, commits, merged PRs, issues
  assets/streak-{dark,light}.svg   total contributions, current streak, longest streak
  assets/stats.json                the numbers behind both cards (last good fetch)

Usage (from the repo root):
    GITHUB_TOKEN=<token> python scripts/build_stats.py      fetch fresh numbers + redraw
    python scripts/build_stats.py --offline                 redraw from assets/stats.json

A GitHub Action (.github/workflows/refresh-stats.yml) runs this every few hours and
commits the result, so the README never depends on the shared public widget servers
(github-readme-stats / streak-stats), which cache for hours and get rate-limited.

Needs a token because the contribution calendar is only exposed through GraphQL.
In Actions the built-in GITHUB_TOKEN is enough; a personal token (secret STATS_TOKEN)
additionally counts private contributions.
"""
import datetime as dt
import json
import os
import pathlib
import sys
import urllib.request
from xml.sax.saxutils import escape

ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
DATA = ASSETS / "stats.json"

USER = "anushkaa2205"

FONT = "'Segoe UI',Ubuntu,'Helvetica Neue',Arial,sans-serif"
THEMES = {
    "dark": dict(bg="#0d1117", border="#30363d", title="#FF2E97", text="#c9d1d9", value="#ffffff",
                 icon="#B565FF", dim="#8b949e", ring="#FF2E97", ring_a="#8E2DE2", track="#3b1530",
                 divider="#8E2DE2", streak_label="#B565FF", logo="#c9d1d9", logo_bg="#161b22"),
    "light": dict(bg="#ffffff", border="#d0d7de", title="#D6146F", text="#24292f", value="#1f2328",
                  icon="#8E2DE2", dim="#57606a", ring="#D6146F", ring_a="#8E2DE2", track="#f6d5e6",
                  divider="#8E2DE2", streak_label="#8E2DE2", logo="#24292f", logo_bg="#f6f8fa"),
}

# Primer Octicons (MIT), 16x16
ICON = {
    "star": "M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Zm0 2.445L6.615 5.5a.75.75 0 0 1-.564.41l-3.097.45 2.24 2.184a.75.75 0 0 1 .216.664l-.528 3.084 2.769-1.456a.75.75 0 0 1 .698 0l2.77 1.456-.53-3.084a.75.75 0 0 1 .216-.664l2.24-2.183-3.096-.45a.75.75 0 0 1-.564-.41L8 2.694Z",
    "history": "m.427 1.927 1.215 1.215a8.002 8.002 0 1 1-1.6 5.685.75.75 0 1 1 1.493-.154 6.5 6.5 0 1 0 1.18-4.458l1.358 1.358A.25.25 0 0 1 3.896 6H.25A.25.25 0 0 1 0 5.75V2.104a.25.25 0 0 1 .427-.177ZM7.75 4a.75.75 0 0 1 .75.75v2.992l2.028.812a.75.75 0 0 1-.557 1.392l-2.5-1A.751.751 0 0 1 7 8.25v-3.5A.75.75 0 0 1 7.75 4Z",
    "merge": "M5.45 5.154A4.25 4.25 0 0 0 9.25 7.5h1.378a2.251 2.251 0 1 1 0 1.5H9.25A5.734 5.734 0 0 1 5 7.123v3.505a2.25 2.25 0 1 1-1.5 0V5.372a2.25 2.25 0 1 1 1.95-.218ZM4.25 13.5a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm8.5-4.5a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5ZM5 3.25a.75.75 0 1 0 0 .005V3.25Z",
    "issue": "M8 9.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Z",
    "flame": "M9.533.753V.752c.217 2.385 1.463 3.626 2.653 4.81C13.37 6.74 14.498 7.863 14.498 10c0 3.5-3 6-6.5 6S1.5 13.512 1.5 10c0-1.298.536-2.56 1.425-3.286.376-.308.862 0 1.035.454C4.46 8.487 5.581 8.419 6 8c.282-.282.341-.811-.003-1.5C4.34 3.187 7.035.75 8.77.146c.39-.137.726.194.763.607ZM7.998 14.5c2.832 0 5-1.98 5-4.5 0-1.463-.68-2.19-1.879-3.383l-.036-.037c-1.013-1.008-2.3-2.29-2.834-4.434-.322.256-.63.579-.864.953-.432.696-.621 1.58-.046 2.73.473.947.67 2.284-.278 3.232-.61.61-1.545.84-2.403.633a2.79 2.79 0 0 1-1.436-.874A3.198 3.198 0 0 0 3 10c0 2.53 2.164 4.5 4.998 4.5Z",
    "github": "M6.766 11.328c-2.063-.25-3.516-1.734-3.516-3.656 0-.781.281-1.625.75-2.188-.203-.515-.172-1.609.063-2.062.625-.078 1.468.25 1.968.703.594-.187 1.219-.281 1.985-.281.765 0 1.39.094 1.953.265.484-.437 1.344-.765 1.969-.687.218.422.25 1.515.046 2.047.5.593.766 1.39.766 2.203 0 1.922-1.453 3.375-3.547 3.64.531.344.89 1.094.89 1.954v1.625c0 .468.391.734.86.547C13.781 14.359 16 11.53 16 8.030 16 3.61 12.406 0 7.984 0 3.563 0 0 3.61 0 8.031a7.88 7.880 0 0 0 5.172 7.422c.422.156.828-.125.828-.547v-1.25c-.219.094-.5.156-.75.156-1.031 0-1.64-.562-2.078-1.609-.172-.422-.36-.672-.719-.719-.187-.015-.25-.093-.25-.187 0-.188.313-.328.625-.328.453 0 .844.281 1.25.86.313.452.64.655 1.031.655s.641-.14 1-.5c.266-.265.47-.5.657-.656",
}

W, H = 495, 195


# ---------------------------------------------------------------- fetching

def _request(url: str, body: dict | None = None):
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is not set (GitHub's GraphQL API needs a token). "
                         "Use --offline to redraw from assets/stats.json.")
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Accept": "application/vnd.github+json", "User-Agent": USER,
                 "Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def gql(query: str, **variables):
    res = _request("https://api.github.com/graphql", {"query": query, "variables": variables})
    if res.get("errors"):
        raise RuntimeError(f"GraphQL error: {res['errors']}")
    return res["data"]


PROFILE_Q = """
query($login: String!, $after: String) {
  user(login: $login) {
    name
    createdAt
    pullRequests(states: MERGED) { totalCount }
    issues { totalCount }
    repositories(ownerAffiliations: OWNER, first: 100, after: $after) {
      nodes { stargazerCount }
      pageInfo { hasNextPage endCursor }
    }
  }
}"""

CALENDAR_Q = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      contributionCalendar { weeks { contributionDays { date contributionCount } } }
    }
  }
}"""


def iso(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch() -> dict:
    stars, after = 0, None
    while True:
        u = gql(PROFILE_Q, login=USER, after=after)["user"]
        stars += sum(n["stargazerCount"] for n in u["repositories"]["nodes"])
        page = u["repositories"]["pageInfo"]
        if not page["hasNextPage"]:
            break
        after = page["endCursor"]

    # contribution calendar, one year at a time (GraphQL caps each window at 1 year)
    now = dt.datetime.now(dt.timezone.utc)
    start = dt.datetime.fromisoformat(u["createdAt"].replace("Z", "+00:00"))
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    days, commit_contribs = {}, 0
    while start <= now:
        end = min(start + dt.timedelta(days=365) - dt.timedelta(seconds=1), now)
        cc = gql(CALENDAR_Q, login=USER, **{"from": iso(start), "to": iso(end)})["user"]["contributionsCollection"]
        commit_contribs += cc["totalCommitContributions"]
        for week in cc["contributionCalendar"]["weeks"]:
            for d in week["contributionDays"]:
                days[d["date"]] = max(days.get(d["date"], 0), d["contributionCount"])
        start += dt.timedelta(days=365)

    # all-time commits the same way github-readme-stats' include_all_commits does (commit search);
    # fall back to the calendar's commit count if search is unavailable
    try:
        commits = _request(f"https://api.github.com/search/commits?q=author:{USER}&per_page=1")["total_count"]
    except Exception as e:
        print(f"! commit search failed ({e}); using calendar commit count")
        commits = commit_contribs

    data = {
        "user": USER,
        "name": u["name"] or USER,
        "stars": stars,
        "commits": commits,
        "prs_merged": u["pullRequests"]["totalCount"],
        "issues": u["issues"]["totalCount"],
        "created": u["createdAt"][:10],
    }
    data.update(summarize(days, now.date()))
    return data


def summarize(days: dict, today: dt.date) -> dict:
    """Total contributions + current/longest streak from {"YYYY-MM-DD": count}."""
    series = sorted((dt.date.fromisoformat(k), v) for k, v in days.items()
                    if dt.date.fromisoformat(k) <= today)
    total = sum(v for _, v in series)
    first = next((d for d, v in series if v > 0), None)

    longest, run_start, prev = None, None, None
    for d, v in series:
        if v > 0:
            if run_start is None or prev is None or (d - prev).days != 1:
                run_start = d
            prev = d
            length = (d - run_start).days + 1
            if longest is None or length > longest[0]:
                longest = (length, run_start, d)
        else:
            run_start, prev = None, None

    # current streak: ends today, or yesterday if today has nothing yet (today is still in play)
    counts = dict(series)
    end = today if counts.get(today, 0) > 0 else today - dt.timedelta(days=1)
    s = end
    while counts.get(s, 0) > 0:
        s -= dt.timedelta(days=1)
    cur_len = (end - s).days
    current = (cur_len, s + dt.timedelta(days=1), end) if cur_len else (0, today, today)

    def pack(t):
        return {"length": t[0], "start": t[1].isoformat(), "end": t[2].isoformat()} if t else \
               {"length": 0, "start": today.isoformat(), "end": today.isoformat()}

    return {
        "total_contributions": total,
        "first_contribution": (first or today).isoformat(),
        "today": today.isoformat(),
        "current": pack(current),
        "longest": pack(longest),
    }


# ---------------------------------------------------------------- drawing

def fmt_day(d: str, this_year: int, with_year: bool = False) -> str:
    x = dt.date.fromisoformat(d)
    s = f"{x.strftime('%b')} {x.day}"
    return f"{s}, {x.year}" if with_year or x.year != this_year else s


def fmt_range(r: dict, this_year: int) -> str:
    if r["length"] == 0:
        return fmt_day(r["end"], this_year)
    if r["start"] == r["end"]:
        return fmt_day(r["start"], this_year)
    yr = dt.date.fromisoformat(r["start"]).year != this_year or dt.date.fromisoformat(r["end"]).year != this_year
    return f"{fmt_day(r['start'], this_year, yr)} - {fmt_day(r['end'], this_year, yr)}"


def head(t: dict, label: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{escape(label)}">',
        f"<defs><style>text{{font-family:{FONT}}}</style>"
        f'<linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{t["ring_a"]}"/>'
        f'<stop offset="1" stop-color="{t["ring"]}"/></linearGradient></defs>',
        f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="6" fill="{t["bg"]}" stroke="{t["border"]}"/>',
    ]


def icon(name: str, x: float, y: float, size: float, color: str) -> str:
    k = size / 16
    return f'<path transform="translate({x:g} {y:g}) scale({k:g})" fill="{color}" fill-rule="evenodd" d="{ICON[name]}"/>'


def stats_card(t: dict, d: dict) -> str:
    o = head(t, f"{d['name']}'s GitHub stats")
    o.append(f'<text x="25" y="38" fill="{t["title"]}" style="font-size:18px;font-weight:600">{escape(d["name"])}\'s GitHub Stats</text>')
    rows = [("star", "Total Stars Earned:", d["stars"]),
            ("history", "Total Commits:", d["commits"]),
            ("merge", "Total PRs Merged:", d["prs_merged"]),
            ("issue", "Total Issues:", d["issues"])]
    for i, (ic, label, val) in enumerate(rows):
        y = 75 + i * 27
        o.append(icon(ic, 25, y - 13, 16, t["icon"]))
        o.append(f'<text x="50" y="{y}" fill="{t["text"]}" style="font-size:14px;font-weight:600">{label}</text>')
        o.append(f'<text x="215" y="{y}" fill="{t["value"]}" style="font-size:14px;font-weight:700">{val:,}</text>')
    cx, cy, r = 400, 100, 44
    o.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{t["track"]}" stroke-width="7"/>')
    o.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="url(#g)" stroke-width="7" stroke-linecap="round"/>')
    o.append(f'<circle cx="{cx}" cy="{cy}" r="{r-9}" fill="{t["logo_bg"]}"/>')
    o.append(icon("github", cx - 26, cy - 26, 52, t["logo"]))
    o.append("</svg>")
    return "\n".join(o)


def streak_card(t: dict, d: dict) -> str:
    this_year = dt.date.fromisoformat(d["today"]).year
    o = head(t, "GitHub contribution streak")
    cols = (W / 6, W / 2, 5 * W / 6)
    for x in (W / 3, 2 * W / 3):
        o.append(f'<line x1="{x:.1f}" y1="28" x2="{x:.1f}" y2="167" stroke="{t["divider"]}" stroke-width="1.5"/>')

    def side(cx, num, label, sub):
        o.append(f'<text x="{cx:.1f}" y="88" text-anchor="middle" fill="{t["value"]}" style="font-size:28px;font-weight:700">{num:,}</text>')
        o.append(f'<text x="{cx:.1f}" y="122" text-anchor="middle" fill="{t["text"]}" style="font-size:14px">{label}</text>')
        o.append(f'<text x="{cx:.1f}" y="148" text-anchor="middle" fill="{t["dim"]}" style="font-size:12px">{escape(sub)}</text>')

    first = fmt_day(d["first_contribution"], this_year, with_year=True)
    side(cols[0], d["total_contributions"], "Total Contributions", f"{first} - Present")
    side(cols[2], d["longest"]["length"], "Longest Streak", fmt_range(d["longest"], this_year))

    cx, cy, r = cols[1], 72, 40
    circ = 2 * 3.14159265 * r
    gap = 34
    o.append(f'<circle cx="{cx:.1f}" cy="{cy}" r="{r}" fill="none" stroke="{t["ring"]}" stroke-width="5" '
             f'stroke-dasharray="{circ - gap:.2f} {gap}" stroke-dashoffset="{-gap / 2:.2f}" '
             f'transform="rotate(-90 {cx:.1f} {cy})"/>')
    o.append(icon("flame", cx - 11, cy - r - 13, 22, t["ring"]))
    o.append(f'<text x="{cx:.1f}" y="{cy + 10}" text-anchor="middle" fill="{t["value"]}" style="font-size:28px;font-weight:700">{d["current"]["length"]:,}</text>')
    o.append(f'<text x="{cx:.1f}" y="140" text-anchor="middle" fill="{t["streak_label"]}" style="font-size:14px;font-weight:700">Current Streak</text>')
    o.append(f'<text x="{cx:.1f}" y="163" text-anchor="middle" fill="{t["dim"]}" style="font-size:12px">{escape(fmt_range(d["current"], this_year))}</text>')
    o.append("</svg>")
    return "\n".join(o)


def draw(data: dict) -> None:
    for name, t in THEMES.items():
        for kind, fn in (("stats", stats_card), ("streak", streak_card)):
            path = ASSETS / f"{kind}-{name}.svg"
            path.write_text(fn(t, data) + "\n", encoding="utf-8")
            print("wrote", path.relative_to(ROOT))


def main() -> None:
    if "--offline" in sys.argv:
        data = json.loads(DATA.read_text(encoding="utf-8"))
    else:
        data = fetch()  # fails loudly: a red Actions run beats silently stale numbers
        DATA.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    draw(data)
    print(f"stars {data['stars']} | commits {data['commits']} | PRs merged {data['prs_merged']} | "
          f"issues {data['issues']} | contributions {data['total_contributions']} | "
          f"current streak {data['current']['length']} | longest {data['longest']['length']}")


if __name__ == "__main__":
    main()
