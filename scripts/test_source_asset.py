"""Fetch and validate a real, unmodified photo for a non-posting test."""
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlparse
import requests
from PIL import Image

URLS = [
    "https://cdn.shopify.com/s/files/1/0469/3927/5428/files/Bildschirmfoto_2026-05-19_um_13.21.41.jpg?v=1779189829",
    "https://cdn2.chicmagazine.com.mx/uploads/media/2026/05/13/katseye-regresa-a-mexico-imagen.png",
]
OUT = Path("asset-test-output")
MAX_BYTES = 20 * 1024 * 1024

def main():
    OUT.mkdir(exist_ok=True)
    attempts = []
    for index, url in enumerate(URLS, 1):
        try:
            with requests.get(url, timeout=25, stream=True, headers={"User-Agent":"Mozilla/5.0"}) as response:
                response.raise_for_status()
                ct = response.headers.get("content-type", "").lower()
                if not ct.startswith("image/"):
                    raise ValueError("Non-image content type: " + ct)
                suffix = ".png" if "png" in ct else ".jpg"
                destination = OUT / ("katseye_original" + suffix)
                digest = hashlib.sha256()
                size = 0
                with destination.open("wb") as handle:
                    for chunk in response.iter_content(65536):
                        if not chunk: continue
                        size += len(chunk)
                        if size > MAX_BYTES: raise ValueError("Image exceeds 20 MB")
                        handle.write(chunk)
                        digest.update(chunk)
            with Image.open(destination) as im:
                width, height = im.size
                im.verify()
            if max(width, height) < 720:
                raise ValueError("Image below minimum resolution")
            manifest = {"source_url": url, "sha256":digest.hexdigest(),
                        "bytes":size,"width":width,"height":height,
                        "asset_file":destination.name,"test_only":True,
                        "instagram_auto_post":False}
            (OUT/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
            print("ASSET_TEST_OK",json.dumps(manifest))
            return
        except Exception as exc:
            attempts.append({"url":url,"error":str(exc)})
            print("ASSET_ATTEMPT_FAILED",index,str(exc))
            for path in OUT.glob("katseye_original.*"): path.unlink()
    (OUT/"failures.json").write_text(json.dumps(attempts,indent=2),encoding="utf-8")
    raise RuntimeError("No validated source image could be downloaded")

if __name__ == "__main__":
    main()
