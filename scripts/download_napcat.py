"""Download the NapCat one-key package through the local proxy."""

import os
import sys
import urllib.request

TAG = "v4.18.38"
ASSET = "NapCat.Shell.Windows.OneKey.zip"
URL = f"https://github.com/NapNeko/NapCatQQ/releases/download/{TAG}/{ASSET}"
DEST_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "napcat")
DEST = os.path.join(DEST_DIR, ASSET)

os.makedirs(DEST_DIR, exist_ok=True)
if os.path.exists(DEST) and os.path.getsize(DEST) > 1024 * 1024:
    print(f"already downloaded: {DEST} ({os.path.getsize(DEST)/1048576:.1f} MB)")
    sys.exit(0)

proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
handlers = [urllib.request.ProxyHandler({"https": proxy, "http": proxy})] if proxy else []
opener = urllib.request.build_opener(*handlers)
opener.addheaders = [("User-Agent", "Mozilla/5.0")]
print(f"proxy: {proxy}")
print(f"downloading: {URL}")


def hook(blocks, block_size, total):
    if total > 0:
        done = blocks * block_size
        pct = min(100, done * 100 // total)
        if blocks % 50 == 0:
            print(f"  {pct:3d}%  {done/1048576:.1f}/{total/1048576:.1f} MB", flush=True)


with opener.open(URL, timeout=120) as resp, open(DEST, "wb") as f:
    total = int(resp.headers.get("Content-Length") or 0)
    print(f"size: {total/1048576:.1f} MB")
    blocks = 0
    while True:
        chunk = resp.read(1024 * 256)
        if not chunk:
            break
        f.write(chunk)
        blocks += 1
        if total and blocks % 100 == 0:
            done = blocks * 1024 * 256
            print(f"  {min(100, done*100//total):3d}%  {done/1048576:.1f}/{total/1048576:.1f} MB", flush=True)

print("DONE", DEST, f"{os.path.getsize(DEST)/1048576:.1f} MB")
