"""Download each distinct image once, verify it, and render only immutable local copies."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
import requests
from io import BytesIO
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
        if selected is None and scene.get("screenshot_page_url"):
            page_url = scene["screenshot_page_url"]
            if not page_url.startswith("https://"):
                raise ValueError("Screenshot source must be HTTPS")
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=True)
                    page = browser.new_page(viewport={"width": 1365, "height": 1000}, device_scale_factor=1)
                    page.goto(page_url, wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(2500)
                    imgs = page.locator("img")
                    best = None
                    best_area = 0
                    for index in range(min(imgs.count(), 60)):
                        img = imgs.nth(index)
                        try:
                            box = img.bounding_box(timeout=1200)
                            if box and box["width"] >= 500 and box["height"] >= 280:
                                area = box["width"] * box["height"]
                                if area > best_area:
                                    best = img
                                    best_area = area
                        except Exception:
                            continue
                    if best is None:
                        raise ValueError("No sufficiently large displayed image found")
                    blob = best.screenshot(timeout=12000)
                    browser.close()
                with Image.open(BytesIO(blob)) as im:
                    size = im.size
                    im.verify()
                if max(size) < 720: raise ValueError("Screenshot below 720px")
                digest = hashlib.sha256(blob).hexdigest()
                dest = CACHE / (digest + ".png")
                dest.write_bytes(blob)
                selected = "screenshot:" + page_url
                records[selected] = {"sha256":digest,"local_path":str(dest.relative_to(ROOT)),
                                     "source_url":selected,"width":size[0],"height":size[1]}
                print("SCREENSHOT_FALLBACK_OK",i,page_url,digest)
            except Exception as exc:
                failures.append("Screenshot fallback: " + type(exc).__name__ + ": " + str(exc)[:220])
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
