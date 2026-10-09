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
        "keywords": ["aetherion"],
        "main_url": f"https://github.com/{GITHUB_USERNAME}/Aetherion",
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
        return f"*No tracked coding activity recorded for the past
