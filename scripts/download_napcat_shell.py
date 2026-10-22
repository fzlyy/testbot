"""Download NapCat.Shell.zip through the local proxy."""

import os
import sys
import urllib.request

TAG = "v4.18.38"
URL = f"https://github.com/NapNeko/NapCatQQ/releases/download/{TAG}/NapCat.Shell.zip"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, "napcat", "NapCat.Shell.zip")

os.makedirs(os.path.dirname(DEST), exist_ok=True)
if os.path.exists(DEST) and os.path.getsize(DEST) > 5 * 1024 * 1024:
    print(f"already downloaded: {DEST} ({os.path.getsize(DEST)/1048576:.1f} MB)")
    sys.exit(0)

proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
handlers = [urllib.request.ProxyHandler({"https": proxy, "http": proxy})] if proxy else []
opener = urllib.request.build_opener(*handlers)
opener.addheaders = [("User-Agent", "Mozilla/5.0")]
print(f"proxy: {proxy}")
print(f"downloading: {URL}")

with opener.open(URL, timeout=120) as resp, open(DEST, "wb") as f:
    total = int(resp.headers.get("Content-Length") or 0)
    print(f"size: {total/1048576:.1f} MB", flush=True)
    done = 0
    while True:
        chunk = resp.read(1024 * 256)
        if not chunk:
            break
        f.write(chunk)
        done += len(chunk)
        if total and done % (10 * 1024 * 1024) < 1024 * 256:
            print(f"  {done*100//total:3d}%  {done/1048576:.1f}/{total/1048576:.1f} MB", flush=True)

print("DONE", DEST, f"{os.path.getsize(DEST)/1048576:.1f} MB")
