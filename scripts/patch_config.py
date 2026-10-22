import io
import json

P = r"data/cmd_config.json"

with io.open(P, encoding="utf-8-sig") as f:
    cfg = json.load(f)

# 1) dashboard only binds localhost
cfg["dashboard"]["host"] = "127.0.0.1"

# 2) DeepSeek connection (key left empty; user pastes it in WebUI)
cfg["provider_sources"] = [
    {
        "id": "deepseek",
        "type": "openai_chat_completion",
        "provider": "deepseek",
        "provider_type": "chat_completion",
        "enable": True,
        "key": [],
        "api_base": "https://api.deepseek.com/v1",
        "timeout": 120,
        "proxy": "",
        "custom_headers": {},
    }
]

# 3) model instance
cfg["provider"] = [
    {
        "id": "deepseek-flash",
        "provider_source_id": "deepseek",
        "type": "openai_chat_completion",
        "provider_type": "chat_completion",
        "enable": True,
        "model": "deepseek-flash",
    }
]
cfg["provider_settings"]["default_provider_id"] = "deepseek-flash"

# 4) QQ via OneBot v11 reverse websocket
cfg["platform"] = [
    {
        "id": "qq",
        "type": "aiocqhttp",
        "enable": True,
        "ws_reverse_host": "0.0.0.0",
        "ws_reverse_port": 6199,
        "ws_reverse_token": "",
    }
]

# 5) group-mate behaviour
cfg["provider_settings"]["identifier"] = True
cfg["provider_settings"]["group_name_display"] = True
cfg["provider_settings"]["max_context_length"] = 30
cfg["provider_ltm_settings"]["group_icl_enable"] = True
cfg["provider_ltm_settings"]["group_message_max_cnt"] = 30
cfg["provider_ltm_settings"]["active_reply"] = {
    "enable": True,
    "method": "possibility_reply",
    "possibility_reply": 0.08,
    "whitelist": [],
}
ps = cfg["platform_settings"]
ps["reply_with_quote"] = True
ps["segmented_reply"]["enable"] = True
ps["segmented_reply"]["interval"] = "1.0,2.5"

with io.open(P, "w", encoding="utf-8-sig", newline="\n") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)

print("OK written")
print("dashboard.host =", cfg["dashboard"]["host"])
print("provider      =", json.dumps(cfg["provider"], ensure_ascii=False))
print("platform      =", json.dumps(cfg["platform"], ensure_ascii=False))
