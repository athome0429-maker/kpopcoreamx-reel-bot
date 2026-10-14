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
        primary = scene.get("image_url") or scene.get("image_path")
        candidates = [primary] + list(scene.get("image_fallback_urls") or [])
        candidates = list(dict.fromkeys(x for x in candidates if x))
        if not candidates: raise ValueError(f"Scene {i}: missing source")
        failures = []
        selected = None
        for src in candidates:
            try:
                if src not in records:
                    if src.startswith(("https://", "http://")):
                        parsed = urlparse(src)
                        if parsed.scheme != "https": raise ValueError("HTTPS required")
                        with requests.get(src, stream=True, timeout=25,
                                          headers={"User-Agent":"Mozilla/5.0 (compatible; KpopCoreaMXMediaBot/1.0)"}) as response:
                            response.raise_for_status()
                            if not response.headers.get("content-type", "").lower().startswith("image/"):
                                raise ValueError("Non-image response")
                            data = bytearray()
                            for chunk in response.iter_content(65536):
                                data.extend(chunk)
                                if len(data) > MAX: raise ValueError("Image too large")
                        blob = bytes(data)
                    else:
                        source_path = (ROOT / src).resolve()
                        if not source_path.is_relative_to(ROOT): raise ValueError("Path outside repo")
                        if not source_path.is_file() or source_path.stat().st_size > MAX:
                            raise ValueError("Invalid local source")
                        blob = source_path.read_bytes()
                    digest = hashlib.sha256(blob).hexdigest()
                    ext = ".png" if blob.startswith(bytes([137,80,78,71])) else ".webp" if blob.startswith(b"RIFF") else ".jpg"
                    dest = CACHE / (digest + ext)
                    dest.write_bytes(blob)
                    try:
                        with Image.open(dest) as im:
                            size = im.size
                            if max(size) < 720: raise ValueError("Image below 720px")
                            im.verify()
                    except Exception:
                        dest.unlink(missing_ok=True)
                        raise
                    records[src] = {"sha256": digest, "local_path": str(dest.relative_to(ROOT)),
                                    "source_url": src, "width": size[0], "height": size[1]}
                selected = src
                break
            except (requests.RequestException, ValueError, OSError) as exc:
                failures.append(f"{src}: {type(exc).__name__}: {str(exc)[:180]}")
                print("SOURCE_ATTEMPT_FAILED", i, len(failures), failures[-1])
        if selected is None:
            raise RuntimeError(f"Scene {i}: all {len(candidates)} sources failed: " + " | ".join(failures))
        rec = records[selected]
        scene["original_image_source"] = selected
        scene.pop("image_url", None)
        scene.pop("image_fallback_urls", None)
        scene["image_path"] = rec["local_path"]
        scene["source_sha256"] = rec["sha256"]
        print("SCENE_SOURCE_SELECTED", i, selected, rec["sha256"])
    payload_path.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    (CACHE/"sources.json").write_text(json.dumps(list(records.values()),ensure_ascii=False,indent=2),encoding="utf-8")
    print("SOURCE_CACHE_OK",len(records),"unique images; no second HTTP fetch")

if __name__ == "__main__":
    main()
