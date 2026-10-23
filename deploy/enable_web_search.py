#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Enable AstrBot's builtin web search in cmd_config.json.

Run this on the ECS host *while the astrbot container is stopped*: a running
AstrBot rewrites cmd_config.json from memory when it exits, so edits made
without stopping it are silently lost.

AstrBot (4.29.x) only injects a search tool into the model when BOTH hold:

    provider_settings.web_search          == true
    provider_settings.websearch_provider  == "<backend>"

plus the backend's key field is non-empty. `anysearch` is the exception: it
serves anonymous traffic with a daily free quota, so its key list may stay [].

Note: unlike `provider_sources[].key`, the `websearch_*_key` fields do NOT
support the `$ENV_VAR` form (only provider loading expands it, see
astrbot/core/provider/manager.py::_resolve_env_key_list). A literal "$FOO"
here would be sent as the bearer token and fail with 401.

Usage:
    python3 enable_web_search.py --config data/astrbot/cmd_config.json --check
    python3 enable_web_search.py --config ... --provider deepseek
    python3 enable_web_search.py --config ... --provider deepseek --key sk-xxx
    python3 enable_web_search.py --config ... --provider anysearch
    python3 enable_web_search.py --config ... --disable
"""
import argparse
import json
import os
import sys
import tempfile

# backend -> (key field, whether a key is required)
BACKENDS = {
    "deepseek": ("websearch_deepseek_key", True),
    "tavily": ("websearch_tavily_key", True),
    "bocha": ("websearch_bocha_key", True),
    "brave": ("websearch_brave_key", True),
    "firecrawl": ("websearch_firecrawl_key", True),
    "exa": ("websearch_exa_key", True),
    "serpapi": ("websearch_serpapi_key", True),
    "anysearch": ("websearch_anysearch_key", False),
    "baidu_ai_search": ("websearch_baidu_app_builder_key", "str"),
}

# tool the model actually gets, for the post-change summary
TOOLS = {
    "deepseek": ["web_search_deepseek", "deepseek_fetch_web_page"],
    "tavily": ["web_search_tavily", "tavily_extract_web_page"],
    "bocha": ["web_search_bocha"],
    "brave": ["web_search_brave"],
    "firecrawl": ["web_search_firecrawl", "firecrawl_extract_web_page"],
    "exa": ["web_search_exa", "exa_get_contents"],
    "serpapi": ["web_search_serpapi", "image_search_serpapi",
                "finance_search_serpapi", "scholar_search_serpapi"],
    "anysearch": ["web_search_anysearch"],
    "baidu_ai_search": ["web_search_baidu"],
}


def mask(value):
    if not value:
        return "<empty>"
    return value[:6] + "..." + value[-4:] if len(value) > 12 else value[:3] + "..."


def load(path):
    raw = open(path, "rb").read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    return json.loads(raw.decode("utf-8-sig")), bom


def save(path, cfg, bom):
    cfg_dir = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=cfg_dir, prefix=".cmd_config.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8-sig" if bom else "utf-8", newline="\n") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.chmod(tmp, os.stat(path).st_mode & 0o777)
    os.replace(tmp, path)


def key_from_provider_sources(cfg, provider):
    for src in cfg.get("provider_sources", []) or []:
        if not isinstance(src, dict) or src.get("provider") != provider:
            continue
        for k in src.get("key", []) or []:
            if isinstance(k, str) and k and not k.startswith("$"):
                return k
    return ""


def current_state(cfg):
    ps = cfg.get("provider_settings", {}) or {}
    backend = ps.get("websearch_provider", "")
    field, _req = BACKENDS.get(backend, (None, True))
    key = ps.get(field) if field else None
    if isinstance(key, str):
        n = 1 if key else 0
    else:
        n = len(key or [])
    return {
        "web_search": ps.get("web_search"),
        "websearch_provider": backend,
        "key_field": field,
        "key_count": n,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--provider", choices=sorted(BACKENDS))
    ap.add_argument("--key", action="append", default=[],
                    help="API key (repeatable). Falls back to the plaintext "
                         "DeepSeek key in provider_sources[] when omitted.")
    ap.add_argument("--disable", action="store_true")
    ap.add_argument("--check", action="store_true", help="print state, write nothing")
    a = ap.parse_args()

    if not (a.check or a.disable or a.provider):
        ap.error("one of --provider / --disable / --check is required")

    cfg, bom = load(a.config)
    ps = cfg.setdefault("provider_settings", {})

    if a.check:
        st = current_state(cfg)
        print("config           : %s (bom=%s)" % (a.config, bom))
        print("web_search       : %r" % st["web_search"])
        print("websearch_provider: %r" % st["websearch_provider"])
        print("key field        : %r  count=%d" % (st["key_field"], st["key_count"]))
        enabled = bool(st["web_search"]) and st["websearch_provider"] in BACKENDS and (
            st["key_count"] > 0
            or BACKENDS[st["websearch_provider"]][1] is False
        )
        print("=> tool injection: %s" % ("ON" if enabled else "OFF"))
        return 0

    if a.disable:
        ps["web_search"] = False
        save(a.config, cfg, bom)
        print("web_search = False (saved)")
        return 0

    backend = a.provider
    field, req = BACKENDS[backend]

    if a.key:
        keys = a.key
    elif backend == "deepseek":
        k = key_from_provider_sources(cfg, "deepseek")
        keys = [k] if k else []
    else:
        keys = []

    if req is True and not keys:
        if backend == "anysearch":
            keys = []
        else:
            print("ERROR: no key for backend %r." % backend, file=sys.stderr)
            print("       pass --key sk-xxx (or --provider anysearch, which needs none).",
                  file=sys.stderr)
            return 2

    ps["web_search"] = True
    ps["websearch_provider"] = backend
    ps[field] = keys[0] if req == "str" else list(keys)

    save(a.config, cfg, bom)

    print("saved: %s (bom=%s)" % (a.config, bom))
    print("  web_search          = True")
    print("  websearch_provider  = %r" % backend)
    if req == "str":
        print("  %s = %s" % (field, mask(ps[field])))
    else:
        print("  %s = [%s]" % (field, ", ".join(mask(k) for k in keys) or "anonymous"))
    print("  model gets          = %s" % ", ".join(TOOLS[backend]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
