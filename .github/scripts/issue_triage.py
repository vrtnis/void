from openai import OpenAI
import requests
from textwrap import dedent
import os

REPO = "voideditor/void"
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# Step 1: Fetch issues
headers = {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"}
issues = []
page = 1

while True:
    url = f"https://api.github.com/repos/{REPO}/issues?state=open&per_page=100&page={page}"
    resp = requests.get(url, headers=headers).json()
    if not resp or isinstance(resp, dict) and resp.get("message"):
        break
    for issue in resp:
        if "pull_request" not in issue:
            issues.append(f"- {issue['title']} ({issue['html_url']})")
    page += 1

# Step 2: Build prompt
themes = dedent("""
1. 🧠 LLM Integration & Provider Support
2. 🖥 App Build & Platform Compatibility
3. 🎯 Prompt, Token, and Cost Management
4. 🧩 Editor UX & Interaction Design
5. 🤖 Agent & Automation Features
6. ⚙️ System Config & Environment Setup
7. 🗃 Meta: Feature Comparison, Structure, and Naming
""")

prompt = dedent(f"""
You are an AI assistant helping triage GitHub issues into exactly 7 predefined themes.

Each issue must go into exactly one of the themes below:

{themes}

Format your output in Markdown like this:

## 🎯 Prompt, Token, and Cost Management
- [#123](https://github.com/org/repo/issues/123) – Title here

Issues:
{chr(10).join(issues)}
""")

# Step 3: Call GPT and print output directly
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.2,
)

print(response.choices[0].message.content)
