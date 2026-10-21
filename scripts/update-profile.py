"""Render README cards from public GitHub data. Python standard library only."""

import argparse
from collections import Counter
from datetime import datetime, timezone
from html import escape
import json
import os
from pathlib import Path
import re
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PALETTES = {
    "light": ("#f6f8fa", "#d8e2e9", "#142335", "#576b7e", "#087f70"),
    "dark": ("#0d1726", "#24384a", "#e6edf3", "#97a9bf", "#57d9c0"),
}
COLORS = ["#368eac", "#51b9a5", "#9a8ccc", "#d8a456", "#c57891", "#7c91a6"]


def fetch(path):
    # Only public REST endpoints: never enumerate authenticated/private repos.
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-cards"}
    if os.environ.get("GH_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    req = urllib.request.Request("https://api.github.com/" + path, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def text(x, y, value, size, color, weight=400):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}">{escape(str(value))}</text>'


def card(title, subtitle, body, theme, date):
    bg, border, fg, muted, accent = PALETTES[theme]
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="440" height="286" viewBox="0 0 440 286" role="img" aria-labelledby="title">'
        f'<title id="title">{escape(title)} — {escape(subtitle)} — updated {date}</title>'
        f'<rect x=".5" y=".5" width="439" height="285" rx="14" fill="{bg}" stroke="{border}"/>'
        '<g font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif">'
        + text(26, 37, title, 19, fg, 650)
        + text(26, 60, subtitle, 12, muted)
        + body
        + f'<path d="M26 246H414" stroke="{border}"/>'
        + text(26, 268, f"PUBLIC DATA · UPDATED {date}", 10, muted)
        + '</g></svg>\n'
    )


def render(repos, user, date):
    repos = [r for r in repos if not r["private"] and not r["fork"]]
    counts = Counter(r["language"] for r in repos if r.get("language"))
    ranked = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    languages = ranked[:5]
    if len(ranked) > 5:
        languages.append(("Other", sum(count for _, count in ranked[5:])))
    files = {}
    for theme, (_, border, fg, muted, accent) in PALETTES.items():
        metrics = [
            (len(repos), "Original repositories"),
            (sum(r["stargazers_count"] for r in repos), "Stars received"),
            (sum(r["forks_count"] for r in repos), "Repository forks"),
            (user["followers"], "GitHub followers"),
        ]
        body = ""
        for i, (number, label) in enumerate(metrics):
            x, y = 26 + (i % 2) * 210, 113 + (i // 2) * 79
            body += text(x, y, f"{number:,}", 34, accent, 650)
            body += text(x, y + 24, label, 12, muted)
        files[f"stats-{theme}.svg"] = card("Building in public", "Becomingw / GitHub", body, theme, date)
        total = sum(counts.values())
        body, x = "", 26
        for i, (language, count) in enumerate(languages):
            width = 388 * count / max(total, 1)
            body += f'<rect x="{x:.2f}" y="83" width="{width:.2f}" height="12" fill="{COLORS[i]}"/>'
            x += width
            y = 121 + i * 21
            body += f'<circle cx="30" cy="{y-4}" r="4" fill="{COLORS[i]}"/>'
            body += text(43, y, language, 13, fg)
            body += text(340, y, f"{count} repos", 12, muted)
        if not languages:
            body += text(26, 140, "No language data yet", 14, muted)
        files[f"languages-{theme}.svg"] = card("Languages across projects", "Primary language / public original repositories", body, theme, date)
    # Validate every asset before replacing any file. API failures preserve old cards.
    for content in files.values():
        ET.fromstring(content)
    target = ROOT / "assets"
    target.mkdir(exist_ok=True)
    for name, content in files.items():
        tmp = target / (name + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(target / name)
    print(f"Rendered {len(files)} cards from {len(repos)} public original repositories.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-dir", type=Path, help="Read repos.json and user.json for local verification")
    args = parser.parse_args()
    if args.fixture_dir:
        repos = json.loads((args.fixture_dir / "repos.json").read_text())
        user = json.loads((args.fixture_dir / "user.json").read_text())
    else:
        owner = os.environ.get("PROFILE_USERNAME", "Becomingw")
        if not re.fullmatch(r"[A-Za-z0-9-]{1,39}", owner):
            raise ValueError("Invalid GitHub username")
        user, repos, page = fetch(f"users/{owner}"), [], 1
        while True:
            batch = fetch(f"users/{owner}/repos?type=owner&per_page=100&page={page}")
            repos.extend(batch)
            if len(batch) < 100:
                break
            page += 1
    render(repos, user, datetime.now(timezone.utc).date().isoformat())


if __name__ == "__main__":
    main()
