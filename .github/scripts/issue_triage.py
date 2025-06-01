#!/usr/bin/env python
from __future__ import annotations
from openai import OpenAI
import requests, os, json, datetime, textwrap, pathlib, sys

REPO = "voideditor/void"
CACHE_FILE = pathlib.Path(".github/triage_cache.json")
STAMP_FILE = pathlib.Path(".github/last_triage.txt")
THEMES_MD = textwrap.dedent("""
1. 🧠 LLM Integration & Provider Support
2. 🖥 App Build & Platform Compatibility
3. 🎯 Prompt, Token, and Cost Management
4. 🧩 Editor UX & Interaction Design
5. 🤖 Agent & Automation Features
6. ⚙️ System Config & Environment Setup
7. 🗃 Meta: Feature Comparison, Structure, and Naming
""").strip()

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
headers = {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"}

# ------------------------------------------------------------------ helpers
def utc_iso_now() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0, tzinfo=datetime.timezone.utc).isoformat()

def read_stamp() -> str:
    if STAMP_FILE.exists():
        return STAMP_FILE.read_text().strip()
    return "1970-01-01T00:00:00Z"

def save_stamp():
    STAMP_FILE.parent.mkdir(parents=True, exist_ok=True)
    STAMP_FILE.write_text(utc_iso_now())

def load_cache() -> dict[int, str]:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())
    return {}

def save_cache(cache: dict[int, str]):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, indent=2))

def fetch_changed_issues(since_iso: str) -> list[dict]:
    issues, page = [], 1
    while True:
        url = (
            f"https://api.github.com/repos/{REPO}/issues"
            f"?state=open&since={since_iso}&per_page=100&page={page}"
        )
        chunk = requests.get(url, headers=headers).json()
        if not chunk or isinstance(chunk, dict) and chunk.get("message"):
            break
        issues.extend([i for i in chunk if "pull_request" not in i])
        page += 1
    return issues

# ------------------------------------------------------------------ main
last_stamp = read_stamp()
changed = fetch_changed_issues(last_stamp)

if not changed:
    print(f"✅ No issues updated since {last_stamp}. Nothing to classify.")
    save_stamp()
    sys.exit(0)

# Build prompt with only changed issues
prompt_issues = "\n".join(f"- {i['title']} ({i['html_url']})" for i in changed)
prompt = textwrap.dedent(f"""
You are an AI assistant helping triage GitHub issues into exactly 7 predefined themes.

Each issue must go into exactly one of the themes below:

{THEMES_MD}

Format your output in Markdown like:
## 🎯 Prompt, Token, and Cost Management
- [#123](https://github.com/org/repo/issues/123) – Title here

Classify these issues:
{prompt_issues}
""")

# GPT call
resp = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.2,
)
md_output = resp.choices[0].message.content

# Parse GPT result to map {issue_number: theme_title}
new_map: dict[int, str] = {}
current_theme = None
for line in md_output.splitlines():
    if line.startswith("##"):
        current_theme = line.lstrip("# ").strip()
    elif line.lstrip().startswith("- [#"):
        try:
            issue_no = int(line.split("[#")[1].split("]")[0])
            new_map[issue_no] = current_theme
        except Exception:
            pass  # tolerate malformed lines

# Merge into cache & save
cache = load_cache()
cache.update(new_map)
save_cache(cache)
save_stamp()

# Regenerate full roadmap from cache
themes_order = [
    "🧠 LLM Integration & Provider Support",
    "🖥 App Build & Platform Compatibility",
    "🎯 Prompt, Token, and Cost Management",
    "🧩 Editor UX & Interaction Design",
    "🤖 Agent & Automation Features",
    "⚙️ System Config & Environment Setup",
    "🗃 Meta: Feature Comparison, Structure, and Naming",
]

sections: dict[str, list[str]] = {t: [] for t in themes_order}
for issue_no, theme in cache.items():
    sections[theme].append(issue_no)

# fetch titles/urls for all issues in cache (cheap: one API call per 100)
title_map: dict[int, tuple[str, str]] = {}
for page in range(1, 10):
    url = f"https://api.github.com/repos/{REPO}/issues?state=open&per_page=100&page={page}"
    batch = requests.get(url, headers=headers).json()
    if not batch or isinstance(batch, dict) and batch.get("message"):
        break
    for it in batch:
        if "pull_request" not in it:
            title_map[it["number"]] = (it["title"], it["html_url"])

# Print roadmap
for theme in themes_order:
    if sections[theme]:
        print(f"## {theme}")
        for n in sorted(sections[theme]):
            title, url = title_map.get(n, ("(missing)", f"https://github.com/{REPO}/issues/{n}"))
            print(f"- [#{n}]({url}) – {title}")
        print()
