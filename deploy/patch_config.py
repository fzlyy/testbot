#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Set the AstrBot dashboard password and pre-wire the NapCat platform entry.

Run on the ECS host (python3 stdlib only) *while the astrbot container is stopped*,
because AstrBot rewrites cmd_config.json on exit.

    python3 patch_config.py --config <cmd_config.json> --password <plain>

What it writes:
  dashboard.username / password(md5) / pbkdf2_password / password_storage_upgraded
  dashboard.password_change_required = False
  platform[] += {id: napcat, type: aiocqhttp, ws_reverse_host: 0.0.0.0, ws_reverse_port: 6199}

Hash format matches AstrBot 4.29 (astrbot/core/utils/auth_password.py):
  pbkdf2_sha256$600000$<salt hex>$<digest hex>
"""
import argparse
import hashlib
import json
import os
import secrets
import sys
import tempfile

PBKDF2_ITERATIONS = 600000


def hash_pbkdf2(raw: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", raw.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS
    ).hex()
    return "pbkdf2_sha256$%d$%s$%s" % (PBKDF2_ITERATIONS, salt, digest)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--username", default="astrbot")
    ap.add_argument("--ws-port", type=int, default=6199)
    a = ap.parse_args()

    raw = open(a.config, "rb").read()
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    cfg = json.loads(raw.decode("utf-8-sig"))

    dash = cfg.setdefault("dashboard", {})
    dash["enable"] = True
    dash["host"] = "0.0.0.0"
    dash["port"] = 6185
    dash["username"] = a.username
    dash["password"] = hashlib.md5(a.password.encode("utf-8")).hexdigest()
    dash["pbkdf2_password"] = hash_pbkdf2(a.password)
    dash["password_storage_upgraded"] = True
    dash["password_change_required"] = False

    entry = {
        "id": "napcat",
        "type": "aiocqhttp",
        "enable": True,
        "ws_reverse_host": "0.0.0.0",
        "ws_reverse_port": a.ws_port,
        "ws_reverse_token": "",
    }
    platforms = cfg.setdefault("platform", [])
    if not isinstance(platforms, list):
        platforms = []
        cfg["platform"] = platforms
    for i, p in enumerate(platforms):
        if isinstance(p, dict) and p.get("id") == "napcat":
            platforms[i] = entry
            break
    else:
        platforms.append(entry)

    cfg_dir = os.path.dirname(os.path.abspath(a.config))
    fd, tmp = tempfile.mkstemp(dir=cfg_dir, prefix=".cmd_config.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8-sig" if has_bom else "utf-8", newline="\n") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")
    shutil_owner = os.stat(a.config)
    os.chmod(tmp, shutil_owner.st_mode & 0o777)
    os.replace(tmp, a.config)

    print("patched dashboard: user=%s host=0.0.0.0 port=6185 change_required=False" % a.username)
    print("patched platform : aiocqhttp napcat ws_reverse 0.0.0.0:%d" % a.ws_port)
    print("platform entries : %s" % [p.get("id") for p in platforms if isinstance(p, dict)])
    return 0


if __name__ == "__main__":
    sys.exit(main())
