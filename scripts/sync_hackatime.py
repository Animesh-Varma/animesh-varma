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
    "aetherion": "Aetherion-App",
    "aetherion-home": "Aetherion",
}

GROUPS_CONFIG = {
    "Project Aetherion": {
        "tag": "Cluster",
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
    footer = f"\n*Last synced: {last_str} | Next sync: ~{next_str} via [Hackatime](https://hackatime.hackclub.com/@{GITHUB_USERNAME}).*"

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
    active_groups = {}

    for g_name, bucket in group_buckets.items():
        if bucket["total_seconds"] > 0:
            active_groups[g_name] = bucket
            cfg = GROUPS_CONFIG[g_name]
            tag_label = cfg.get("tag", "Cluster")
            main_rows.append({
                "name": f"**{g_name}** ({tag_label})",
                "time_text": format_seconds(bucket["total_seconds"]),
                "percent": bucket["total_percent"],
                "is_group": True,
            })

    main_rows.sort(key=lambda r: r["percent"], reverse=True)

    # 1. Main Segmented Table
    lines = [
        "| Project | Time | Share |",
        "| :--- | :--- | :--- |",
    ]

    for r in main_rows[:8]:
        bar = make_bar(r["percent"])
        if r["is_group"]:
            name_cell = r["name"]
        else:
            name_cell = f"[{r['name']}]({r['url']})"
        lines.append(f"| {name_cell} | {r['time_text']} | `{bar}` {r['percent']:>5.1f}% |")

    # 2. Collapsible Details Block
    details_blocks = []
    for g_name, bucket in active_groups.items():
        cfg = GROUPS_CONFIG[g_name]
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

        details_blocks.extend([
            "",
            "<details>",
            f"<summary><strong>{g_name} Sub-projects</strong> ▾ (click to expand)</summary>",
            "<br>",
            "",
            "| Sub-project | Time | Share of Cluster |",
            "| :--- | :--- | :--- |",
        ])

        for s in sub_records:
            s_bar = make_bar(s["share"])
            details_blocks.append(f"| [{s['name']}]({s['url']}) | {s['time_text']} | `{s_bar}` {s['share']:>5.1f}% |")

        details_blocks.append("")
        details_blocks.append("</details>")

    return "\n".join(lines) + ("\n" + "\n".join(details_blocks) if details_blocks else "") + f"\n{footer}"

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
