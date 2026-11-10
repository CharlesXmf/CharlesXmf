#!/usr/bin/env python3
"""Generate a dark, Cursor-profile-style year heatmap SVG for a GitHub profile README.

Data is read from the public Cursor profile (via the unofficial
cursor-profile.stredan.sk JSON API, which parses cursor.com/@handle).
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

DEFAULT_HANDLE = "charlesxu"
DEFAULT_API = "https://cursor-profile.stredan.sk/v1/{handle}"
USER_AGENT = "CharlesXmf-github-profile-heatmap/1.0"

# Colors sampled from the official cursor.com public-profile heatmap.
BG = "#141414"
LEVELS = ["#242424", "#6d2a0c", "#963508", "#bf4005", "#f44d00"]
LABEL = "#909090"
MONTH_LABEL = "#a0a0a0"

DOT = 11
GAP = 5
STEP = DOT + GAP
PAD_L = 28
PAD_T = 22
PAD_R = 10
PAD_B = 10
FONT = "ui-sans-serif, -apple-system, Helvetica, Arial, sans-serif"


def fetch_profile(handle: str, api_template: str) -> dict:
    url = api_template.format(handle=handle)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Failed to fetch {url}: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Failed to fetch {url}: {exc.reason}") from exc


def level_for(count: int, thresholds: list[int]) -> int:
    if count <= 0:
        return 0
    for index, threshold in enumerate(thresholds, start=1):
        if count <= threshold:
            return index
    return 4


def compute_thresholds(counts: list[int]) -> list[int]:
    positive = sorted(value for value in counts if value > 0)
    if not positive:
        return [1, 2, 3]
    def percentile(p: float) -> int:
        index = min(len(positive) - 1, max(0, int(round((len(positive) - 1) * p))))
        return max(1, positive[index])
    cuts, last = [], 0
    for value in (percentile(0.25), percentile(0.5), percentile(0.75)):
        last = max(last + 1, value)
        cuts.append(last)
    return cuts


def weeks_for_year(year: int) -> list[list[date | None]]:
    start = date(year, 1, 1)
    end = date(year, 12, 31)
    cursor = start - timedelta(days=(start.weekday() + 1) % 7)  # Sunday-start
    weeks: list[list[date | None]] = []
    while True:
        week: list[date | None] = []
        for _ in range(7):
            week.append(cursor if start <= cursor <= end else None)
            cursor += timedelta(days=1)
        weeks.append(week)
        if cursor > end:
            break
    return weeks


def render_svg(handle: str, counts: dict[str, int], year: int) -> str:
    today = date.today()
    year_counts = [value for key, value in counts.items() if key.startswith(str(year))]
    thresholds = compute_thresholds(year_counts)
    weeks = weeks_for_year(year)
    radius = DOT / 2
    width = PAD_L + len(weeks) * STEP - GAP + PAD_R
    height = PAD_T + 7 * STEP - GAP + PAD_B

    cells: list[str] = []
    month_marks: list[tuple[float, str]] = []
    last_month: int | None = None
    last_month_x = -999.0
    for week_index, week in enumerate(weeks):
        for day_index, day in enumerate(week):
            if day is None:
                continue
            x = PAD_L + week_index * STEP + radius
            y = PAD_T + day_index * STEP + radius
            count = counts.get(day.isoformat(), 0)
            level = 0 if day > today else level_for(count, thresholds)
            cells.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{LEVELS[level]}"/>'
            )
            if day.day <= 7 and day.month != last_month and (x - last_month_x) >= 20:
                month_marks.append((PAD_L + week_index * STEP, day.strftime("%b")[0]))
                last_month = day.month
                last_month_x = x

    day_labels = "".join(
        f'<text x="18" y="{(PAD_T + day_index * STEP + radius + 3.5):.1f}" text-anchor="end" '
        f'font-family="{FONT}" font-size="9" fill="{LABEL}">{label}</text>'
        for day_index, label in ((1, "M"), (3, "W"), (5, "F"))
    )
    month_labels = "".join(
        f'<text x="{x:.1f}" y="14" font-family="{FONT}" font-size="10" fill="{MONTH_LABEL}">{text}</text>'
        for x, text in month_marks
    )
    title = f"Cursor activity heatmap for @{handle} in {year}"
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{title}">\n'
        f'  <rect width="{width}" height="{height}" fill="{BG}"/>\n'
        f"  {month_labels}\n"
        f"  {day_labels}\n"
        f"  {''.join(cells)}\n"
        "</svg>\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a Cursor activity heatmap SVG.")
    parser.add_argument("--handle", default=DEFAULT_HANDLE)
    parser.add_argument("--year", type=int, default=date.today().year)
    parser.add_argument("--api", default=DEFAULT_API, help="API URL template with {handle}")
    parser.add_argument("--output", default="profile/cursor-heatmap.svg")
    args = parser.parse_args()

    profile = fetch_profile(args.handle, args.api)
    counts = {item["date"]: int(item["count"]) for item in profile.get("activityCounts") or []}
    if not counts:
        raise SystemExit(f"No activityCounts in profile for @{args.handle}")

    svg = render_svg(args.handle, counts, args.year)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(svg, encoding="utf-8")
    print(f"Wrote {output} ({output.stat().st_size} bytes)", file=sys.stderr)


if __name__ == "__main__":
    main()
