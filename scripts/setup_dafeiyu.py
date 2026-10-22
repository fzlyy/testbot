"""Write the 大肥鱼 persona into AstrBot's SQLite DB and wire it up in the config."""

import io
import json
import re
import sqlite3

DB = r"data/data_v4.db"
CFG = r"data/cmd_config.json"
MD = r"persona-dafeiyu.md"
PERSONA_ID = "大肥鱼"

with io.open(MD, encoding="utf-8") as f:
    md = f.read()
prompt = re.search(r"```text\n(.*?)\n```", md, re.S).group(1).strip()
print(f"prompt: {len(prompt)} chars")

db = sqlite3.connect(DB)
cur = db.cursor()
row = cur.execute("select id, sort_order from personas where persona_id = ?", (PERSONA_ID,)).fetchone()
if row:
    cur.execute(
        "update personas set system_prompt = ?, updated_at = datetime('now') where persona_id = ?",
        (prompt, PERSONA_ID),
    )
    print("updated existing persona")
else:
    cur.execute(
        """insert into personas
           (created_at, updated_at, persona_id, system_prompt, begin_dialogs, tools, skills,
            custom_error_message, folder_id, sort_order)
           values (datetime('now'), datetime('now'), ?, ?, '[]', 'null', 'null', null, null, 1)""",
        (PERSONA_ID, prompt),
    )
    print("inserted persona")
db.commit()

for r in cur.execute("select persona_id, length(system_prompt) from personas"):
    print("  persona:", r)
db.close()

# point the bot at this persona + turn off deepseek thinking for snappy replies
with io.open(CFG, encoding="utf-8-sig") as f:
    cfg = json.load(f)
cfg["provider_settings"]["default_personality"] = PERSONA_ID
for p in cfg.get("provider", []):
    p["custom_extra_body"] = {"thinking": {"type": "disabled"}}
cfg["provider_settings"]["enable"] = True

with io.open(CFG, "w", encoding="utf-8-sig", newline="\n") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)

print("default_personality ->", cfg["provider_settings"]["default_personality"])
print("custom_extra_body ->", cfg["provider"][0].get("custom_extra_body"))
