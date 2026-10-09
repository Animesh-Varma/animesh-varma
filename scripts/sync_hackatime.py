import json
import os
import re
import urllib.request
from datetime import datetime, timezone, timedelta

API_KEY = os.environ.get("HACKATIME_API_KEY")
GITHUB_USERNAME = "animesh-varma"
README_PATH = "README.md"
START_TAG = "<!-- HACKATIME-START -->"
END_TAG = "<!-- HACKATIME-END -->"

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

PROJECT_ALIASES = {
    "plotter": "BambuScribe",
    "Aetherion": "Aetherion-App",
    "Aetherion-home": "Aetherion",
}

GROUPS_CONFIG = {
    "Project Aetherion": {
        "tag": "Cluster",
        "anchor_id": "project-aetherion",
        "keywords": ["aetherion"],
        "known_projects": [
            "Aetherion",
            "Aetherion-App",
            "Aetherion-SDK",
            "Aetherion-Internal",
            "Aetherion-hub",
        ],
    },
}

CUSTOM_URLS = {
    "Aetherion-App": f"https://github.com/{GITHUB_USERNAME}/aetherion-app",
    "Aetherion": f"https://github.com/{GITHUB_USERNAME}/Aetherion",
}

IGNORE_PROJECTS = set()

# ---------------------------------------------------------------------------
# CORE LOGIC
# ---------------------------------------------------------------------------

def fetch_hackatime_stats():
    if not API_KEY:
        raise ValueError("Missing HACKATIME_API_KEY environment variable.")

    url = f"https://hackatime.hackclub.com/api/hackatime/v1/users/current/stats/last_7_days?api_key={API_KEY}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "User-Agent": "Profile-Readme-Sync",
        },
    )

    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def make_bar(percent, bar_len=18):
    filled = int(round((percent / 100.0) * bar_len))
    return "█" * filled + "░" * (bar_len - filled)

def format_seconds(seconds):
    hours = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    if hours > 0:
        return f"{hours} hrs {mins} mins" if mins > 0 else f"{hours} hrs"
    elif mins > 0:
        return f"{mins} mins"
    return "0 mins"

def resolve_display_name(raw_name):
    return PROJECT_ALIASES.get(raw_name.lower().strip(), raw_name)

def resolve_group(display_name):
    lower_name = display_name.lower()
    for group_name, cfg in GROUPS_CONFIG.items():
        if any(kw.lower() in lower_name for kw in cfg.get("keywords", [])):
            return group_name
    return None

def resolve_url(display_name):
    return CUSTOM_URLS.get(display_name, f"https://github.com/{GITHUB_USERNAME}/{display_name}")

def format_stats(data):
    payload = data.get("data", data)
    raw_projects = payload.get("projects", [])

    now_utc = datetime.now(timezone.utc)
    current_slot_hour = (now_utc.hour // 3) * 3
    next_slot = now_utc.replace(hour=current_slot_hour, minute=15, second=0, microsecond=0)
    while next_slot <= now_utc:
        next_slot += timedelta(hours=3)

    last_str = now_utc.strftime("%b %d, %H:%M UTC")
    next_str = next_slot.strftime("%b %d, %H:%M UTC")
    footer = f"\n*Last synced: {last_str} | Next sync: ~{next_str} (every 3h) via [Hackatime](https://hackatime.hackclub.com/@{GITHUB_USERNAME}).*"

    if not raw_projects:
        return f"*No tracked coding activity recorded for the past 7 days.*\n{footer}"

    group_buckets = {
        g_name: {
            "total_seconds": 0.0,
            "total_percent": 0.0,
            "tracked_projects": {},
        }
        for g_name in GROUPS_CONFIG
    }

    standalone_records = []

    for p in raw_projects:
        raw_name = p.get("name", "Unknown")
        if raw_name in IGNORE_PROJECTS or raw_name.lower() in IGNORE_PROJECTS:
            continue

        display_name = resolve_display_name(raw_name)
        total_sec = float(p.get("total_seconds", 0.0))
        pct = float(p.get("percent", 0.0))
        time_text = p.get("text", format_seconds(total_sec))

        group_name = resolve_group(display_name)
        if group_name:
            bucket = group_buckets[group_name]
            bucket["total_seconds"] += total_sec
            bucket["total_percent"] += pct
            bucket["tracked_projects"][display_name.lower()] = {
                "display_name": display_name,
                "seconds": total_sec,
                "time_text": time_text,
            }
        else:
            standalone_records.append({
                "name": display_name,
                "url": resolve_url(display_name),
                "time_text": time_text,
                "percent": pct,
                "is_group": False,
            })

    main_rows = list(standalone_records)
    for g_name, bucket in group_buckets.items():
        if bucket["total_seconds"] > 0:
            main_rows.append({
                "name": g_name,
                "bucket": bucket,
                "time_text": format_seconds(bucket["total_seconds"]),
                "percent": bucket["total_percent"],
                "is_group": True,
            })

    main_rows.sort(key=lambda r: r["percent"], reverse=True)

    # Build HTML table
    lines = [
        "<table>",
        "  <thead>",
        "    <tr>",
        '      <th align="left">Project</th>',
        '      <th align="left">Time Invested</th>',
        '      <th align="left">Share</th>',
        "    </tr>",
        "  </thead>",
        "  <tbody>",
    ]

    for r in main_rows[:8]:
        bar = make_bar(r["percent"])
        if not r["is_group"]:
            lines.append("    <tr>")
            lines.append(f'      <td><a href="{r["url"]}">{r["name"]}</a></td>')
            lines.append(f'      <td>{r["time_text"]}</td>')
            lines.append(f'      <td><code>{bar}</code> {r["percent"]:>5.1f}%</td>')
            lines.append("    </tr>")
        else:
            g_name = r["name"]
            bucket = r["bucket"]
            cfg = GROUPS_CONFIG[g_name]
            tag_label = cfg.get("tag", "Cluster")
            total_sec = bucket["total_seconds"]

            sub_records = []
            seen = set()

            for known in cfg.get("known_projects", []):
                k_lower = known.lower()
                seen.add(k_lower)
                if k_lower in bucket["tracked_projects"]:
                    item = bucket["tracked_projects"][k_lower]
                    sec = item["seconds"]
                    t_str = item["time_text"]
                    d_name = item["display_name"]
                else:
                    sec = 0.0
                    t_str = "0 mins"
                    d_name = known

                share = (sec / total_sec * 100.0) if total_sec > 0 else 0.0
                sub_records.append({
                    "name": d_name,
                    "url": resolve_url(d_name),
                    "time_text": t_str,
                    "share": share,
                    "seconds": sec,
                })

            for k_lower, item in bucket["tracked_projects"].items():
                if k_lower not in seen:
                    share = (item["seconds"] / total_sec * 100.0) if total_sec > 0 else 0.0
                    sub_records.append({
                        "name": item["display_name"],
                        "url": resolve_url(item["display_name"]),
                        "time_text": item["time_text"],
                        "share": share,
                        "seconds": item["seconds"],
                    })

            sub_records.sort(key=lambda s: s["seconds"], reverse=True)

            lines.append("    <tr>")
            lines.append('      <td colspan="3">')
            lines.append("        <details>")
            lines.append(f'          <summary><strong>{g_name} ({tag_label})</strong> ▾ &nbsp;&nbsp; {r["time_text"]} &nbsp;&nbsp; <code>{bar}</code> {r["percent"]:>5.1f}%</summary>')
            lines.append("          <br>")
            lines.append("          <table>")
            lines.append("            <thead>")
            lines.append("              <tr>")
            lines.append('                <th align="left">Sub-project</th>',
                         '                <th align="left">Time Invested</th>',
                         '                <th align="left">Share of Cluster</th>')
            lines.append("              </tr>")
            lines.append("            </thead>")
            lines.append("            <tbody>")
            for s in sub_records:
                s_bar = make_bar(s["share"])
                lines.append("              <tr>")
                lines.append(f'                <td><a href="{s["url"]}">{s["name"]}</a></td>')
                lines.append(f'                <td>{s["time_text"]}</td>')
                lines.append(f'                <td><code>{s_bar}</code> {s["share"]:>5.1f}%</td>')
                lines.append("              </tr>")
            lines.append("            </tbody>")
            lines.append("          </table>")
            lines.append("          <br>")
            lines.append("        </details>")
            lines.append("      </td>")
            lines.append("    </tr>")

    lines.append("  </tbody>")
    lines.append("</table>")

    return "\n".join(lines) + f"\n{footer}"

def update_readme():
    stats = fetch_hackatime_stats()
    block = format_stats(stats)

    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = re.compile(f"{re.escape(START_TAG)}[\\s\\S]*?{re.escape(END_TAG)}")
    if not pattern.search(content):
        raise ValueError("Anchor tags not found in README.md")

    replacement = f"{START_TAG}\n{block}\n{END_TAG}"
    updated = pattern.sub(replacement, content)

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(updated)

if __name__ == "__main__":
    update_readme()
