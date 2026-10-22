"""Create a persona through the AstrBot dashboard API.

Requires the current dashboard password in the environment:

    $env:ASTRBOT_DASHBOARD_PASSWORD = "..."
    .\\.venv\\Scripts\\python.exe scripts\\setup_persona.py

Note: the DB path (scripts/setup_dafeiyu.py) does not need the password and is
what this project actually uses; keep this script only for API-based workflows.
"""

import http.cookiejar
import io
import json
import os
import re
import sys
import urllib.request

BASE = "http://127.0.0.1:6185"
USER = os.environ.get("ASTRBOT_DASHBOARD_USER", "astrbot")
PASS = os.environ.get("ASTRBOT_DASHBOARD_PASSWORD", "")
PERSONA_ID = "群友小D"

if not PASS:
    sys.exit("ASTRBOT_DASHBOARD_PASSWORD is not set")

# pull the system prompt out of the markdown template
with io.open("persona-ai-groupmate.md", encoding="utf-8") as f:
    md = f.read()
m = re.search(r"```text\n(.*?)\n```", md, re.S)
prompt = m.group(1).strip() if m else md
print(f"system prompt: {len(prompt)} chars")

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
token = None


def call(path, payload=None, method="GET"):
    url = BASE + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with opener.open(req, timeout=20) as r:
        return json.loads(r.read().decode())


# login
body = json.dumps({"username": USER, "password": PASS}).encode()
req = urllib.request.Request(BASE + "/api/auth/login", data=body, method="POST")
req.add_header("Content-Type", "application/json")
with opener.open(req, timeout=20) as r:
    auth = json.loads(r.read().decode())
print("login ->", json.dumps(auth, ensure_ascii=False)[:200])
token = (auth.get("data") or {}).get("token") or auth.get("token")

existing = call("/api/personas")
names = [p.get("persona_id") for p in (existing.get("data") or {}).get("personas", [])]
print("existing personas:", names)

if PERSONA_ID in names:
    print("persona exists, updating ...")
    call("/api/personas/by-id", {"persona_id": PERSONA_ID, "system_prompt": prompt}, "PUT")
else:
    resp = call(
        "/api/personas",
        {
            "persona_id": PERSONA_ID,
            "system_prompt": prompt,
            "begin_dialogs": [],
            "tools": None,
            "skills": None,
        },
        "POST",
    )
    print("create ->", json.dumps(resp, ensure_ascii=False)[:200])

final = call("/api/personas")
personas = (final.get("data") or {}).get("personas", [])
print("personas now:", [(p.get("persona_id"), len(p.get("system_prompt") or "")) for p in personas])
