"""Download each distinct image once, verify it, and render only immutable local copies."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
import requests
from PIL import Image

ROOT = Path.cwd().resolve()
CACHE = ROOT / "tmp" / "source_cache"
MAX = 20 * 1024 * 1024

def main():
    payload_path = ROOT / "data/_render_normalized.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    scenes = payload.get("scenes", [])
    if not 2 <= len(scenes) <= 5: raise ValueError("Expected 2-5 scenes")
    duration = sum(float(s["duration"]) for s in scenes)
    if not 6 <= duration <= 8: raise ValueError("Duration outside 6-8 seconds")
    if not .5 <= float(scenes[0]["duration"]) <= .9: raise ValueError("Invalid hook")
    CACHE.mkdir(parents=True,exist_ok=True)
    records = {}
    for i, scene in enumerate(scenes, 1):
        src = scene.get("image_url") or scene.get("image_path")
        if not src: raise ValueError(f"Scene {i}: missing source")
        if src not in records:
            if src.startswith(("https://","http://")):
                parsed = urlparse(src)
                if parsed.scheme != "https": raise ValueError("HTTPS required")
                with requests.get(src,stream=True,timeout=30,headers={"User-Agent":"Mozilla/5.0"}) as r:
                    r.raise_for_status()
                    if not r.headers.get("content-type","").lower().startswith("image/"):
                        raise ValueError(f"Non-image response: {src}")
                    data = bytearray()
                    for chunk in r.iter_content(65536):
                        data.extend(chunk)
                        if len(data) > MAX: raise ValueError("Image too large")
                blob = bytes(data)
            else:
                path = (ROOT / src).resolve()
                if not path.is_relative_to(ROOT): raise ValueError("Path outside repo")
                if not path.is_file() or path.stat().st_size > MAX: raise ValueError("Invalid local source")
                blob = path.read_bytes()
            digest = hashlib.sha256(blob).hexdigest()
            ext = ".png" if blob.startswith(bytes([137,80,78,71])) else ".webp" if blob.startswith(b"RIFF") else ".jpg"
            dest = CACHE / (digest + ext)
            dest.write_bytes(blob)
            with Image.open(dest) as im:
                size = im.size
                if max(size) < 720: raise ValueError("Image below 720px")
                im.verify()
            records[src] = {"sha256":digest,"local_path":str(dest.relative_to(ROOT)),
                            "source_url":src,"width":size[0],"height":size[1]}
        rec = records[src]
        scene["original_image_source"] = src
        scene.pop("image_url",None)
        scene["image_path"] = rec["local_path"]
        scene["source_sha256"] = rec["sha256"]
    payload_path.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    (CACHE/"sources.json").write_text(json.dumps(list(records.values()),ensure_ascii=False,indent=2),encoding="utf-8")
    print("SOURCE_CACHE_OK",len(records),"unique images; no second HTTP fetch")

if __name__ == "__main__":
    main()
