import io
import json

P = r"data/cmd_config.json"

with io.open(P, encoding="utf-8-sig") as f:
    cfg = json.load(f)

# keep the user's provider (deepseek + key), just make it the default model
providers = cfg.get("provider") or []
if providers:
    pid = providers[0].get("id")
    cfg["provider_settings"]["default_provider_id"] = pid
    print("default_provider_id ->", pid)

# add the QQ / OneBot v11 platform (only if not already there)
platforms = cfg.get("platform") or []
if not any(p.get("type") == "aiocqhttp" for p in platforms):
    platforms.append(
        {
            "id": "qq",
            "type": "aiocqhttp",
            "enable": True,
            "ws_reverse_host": "0.0.0.0",
            "ws_reverse_port": 6199,
            "ws_reverse_token": "",
        }
    )
    cfg["platform"] = platforms
print("platform count ->", len(cfg["platform"]))

# dashboard only on localhost, and write logs to file so failures are visible
cfg["dashboard"]["host"] = "127.0.0.1"
cfg["log_file_enable"] = True

with io.open(P, "w", encoding="utf-8-sig", newline="\n") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)

print("host ->", cfg["dashboard"]["host"])
print("log_file_enable ->", cfg["log_file_enable"])
print("platform ->", json.dumps(cfg["platform"], ensure_ascii=False))
