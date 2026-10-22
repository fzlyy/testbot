"""Download the QQ NT installer (used by NapCat) directly from Tencent CDN."""

import os
import sys
import urllib.request

URL = "https://qqdl.gtimg.cn/qqfile/QQNT/9.9.33/release/497e2f1f/QQ_9.9.33_260813_x64_01.exe"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, "napcat", "QQ_installer.exe")

os.makedirs(os.path.dirname(DEST), exist_ok=True)
if os.path.exists(DEST) and os.path.getsize(DEST) > 100 * 1024 * 1024:
    print(f"already downloaded: {DEST} ({os.path.getsize(DEST)/1048576:.1f} MB)")
    sys.exit(0)

print(f"downloading: {URL}")
opener = urllib.request.build_opener()
opener.addheaders = [("User-Agent", "Mozilla/5.0")]

with opener.open(URL, timeout=120) as resp, open(DEST, "wb") as f:
    total = int(resp.headers.get("Content-Length") or 0)
    print(f"size: {total/1048576:.1f} MB", flush=True)
    done = 0
    while True:
        chunk = resp.read(1024 * 512)
        if not chunk:
            break
        f.write(chunk)
        done += len(chunk)
        if total and done % (20 * 1024 * 1024) < 1024 * 512:
            print(f"  {done*100//total:3d}%  {done/1048576:.1f}/{total/1048576:.1f} MB", flush=True)

print("DONE", DEST, f"{os.path.getsize(DEST)/1048576:.1f} MB")
