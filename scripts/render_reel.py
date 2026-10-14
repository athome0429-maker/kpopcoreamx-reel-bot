import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
MAX_IMAGE_BYTES = 20 * 1024 * 1024


def run(cmd, capture=False):
    print("$", " ".join(map(str, cmd)))
    return subprocess.run(cmd, check=True, text=True, capture_output=capture)


def load_payload(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def ext_from_src(src):
    ext = os.path.splitext(urlparse(src).path)[1].lower()
    return ext if ext in {".jpg", ".jpeg", ".png", ".webp"} else ".jpg"


def http_session():
    s = requests.Session()
    retry = Retry(total=3, connect=3, read=3, backoff_factor=0.7, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    s.headers.update({"User-Agent": "Mozilla/5.0 (KPOP-Corea-MX-ReelBot/2.2)"})
    return s


def download_or_copy(src, out_path):
    if src.startswith(("http://", "https://")):
        with http_session().get(src, timeout=30, stream=True) as r:
            r.raise_for_status()
            ctype = (r.headers.get("content-type") or "").lower()
            if ctype and not ctype.startswith("image/"):
                raise ValueError(f"URL did not return an image: {src} ({ctype})")
            total = 0
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(1024 * 256):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > MAX_IMAGE_BYTES:
                        raise ValueError(f"Image too large (>20MB): {src}")
                    f.write(chunk)
    else:
        shutil.copy(src, out_path)


def validate_image(path, scene_no):
    try:
        with Image.open(path) as im:
            w, h = im.size
            if max(w, h) < 720:
                raise ValueError(f"Scene {scene_no} image resolution too low: {w}x{h}")
            im.verify()
    except Exception as e:
        raise ValueError(f"Scene {scene_no} invalid image: {e}") from e


def font(size, bold=True):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


def fit_text(draw, text, max_w, max_h, start=108, minimum=34, spacing=6):
    for size in range(start, minimum - 1, -2):
        f = font(size)
        b = draw.multiline_textbbox((0, 0), text, font=f, spacing=spacing, align="center")
        if b[2] - b[0] <= max_w and b[3] - b[1] <= max_h:
            return f
    return font(minimum)


def prepare_photo(scene, src_path, out_path, width, height):
    """Keep the source image intact: no crop, blur, recolor or zoom."""
    src = ImageOps.exif_transpose(Image.open(src_path)).convert("RGB")
    src.thumbnail((width, height), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (width, height), (0, 0, 0))
    canvas.paste(src, ((width - src.width) // 2, (height - src.height) // 2))
    canvas.save(out_path, quality=95)


def add_gradient(im, top_y):
    width, height = im.size
    gh = height - top_y
    line = Image.new("RGBA", (1, gh), (0, 0, 0, 0))
    p = line.load()
    for y in range(gh):
        t = y / max(1, gh - 1)
        p[0, y] = (0, 0, 0, int(210 * (t ** 1.7)))
    im.alpha_composite(line.resize((width, gh)), (0, top_y))


def make_overlay(scene, brand, width, height, out_path):
    im = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    add_gradient(im, int(height * 0.54))
    d = ImageDraw.Draw(im, "RGBA")
    headline = scene.get("headline", "").strip()
    sub = scene.get("subheadline", "").strip()
    headline_y, sub_y, brand_y = int(height * 0.67), int(height * 0.81), int(height * 0.88)
    accent = (246, 207, 40, 255)

    d.rounded_rectangle((width // 2 - 96, headline_y - 42, width // 2 + 96, headline_y - 30), radius=6, fill=accent)
    hf = fit_text(d, headline, width - 130, 250, 106, 40)
    d.multiline_text((width // 2, headline_y + 6), headline, font=hf, anchor="mm", align="center", fill=(0, 0, 0, 125), spacing=4)
    d.multiline_text((width // 2, headline_y), headline, font=hf, anchor="mm", align="center", fill="white", spacing=4, stroke_width=2, stroke_fill=(0, 0, 0, 115))

    if sub and sub != brand:
        sf = fit_text(d, sub, width - 180, 120, 42, 28, 3)
        b = d.multiline_textbbox((0, 0), sub, font=sf, spacing=3, align="center")
        sw, sh = b[2] - b[0], b[3] - b[1]
        if sw + 52 < width - 120 and sh < 80:
            x1, x2 = width // 2 - sw // 2 - 26, width // 2 + sw // 2 + 26
            y1, y2 = sub_y - sh // 2 - 13, sub_y + sh // 2 + 13
            d.rounded_rectangle((x1, y1, x2, y2), radius=(y2 - y1) // 2, fill=(0, 0, 0, 105), outline=(255, 255, 255, 55), width=2)
        d.multiline_text((width // 2, sub_y), sub, font=sf, anchor="mm", align="center", fill=(255, 255, 255, 245), spacing=3)

    d.text((width // 2, brand_y), brand, font=font(29), anchor="mm", fill=(255, 255, 255, 190))
    im.save(out_path)


def render_scene(base_path, overlay_path, out_path, duration, width, height, fps, scene):
    """Show the original image unchanged, with only a separate text overlay."""
    run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(fps),
         "-i", str(base_path), "-loop", "1", "-framerate", str(fps),
         "-i", str(overlay_path), "-filter_complex",
         "[0:v][1:v]overlay=0:0:format=auto",
         "-t", str(duration), "-r", str(fps), "-an", "-c:v", "libx264",
         "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", str(out_path)])


def concat_segments(paths, out_path):
    list_path = out_path.parent / "concat.txt"
    with open(list_path, "w", encoding="utf-8") as f:
        for p in paths:
            f.write(f"file '{p.resolve()}'\n")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path), "-c", "copy", "-movflags", "+faststart", str(out_path)])


def probe_video(path):
    p = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name,width,height,r_frame_rate,pix_fmt", "-show_entries", "format=duration", "-of", "json", str(path)], capture=True)
    info = json.loads(p.stdout)
    stream = info["streams"][0]
    duration = float(info["format"]["duration"])
    if stream.get("codec_name") != "h264":
        raise ValueError(f"Output codec is not H.264: {stream.get('codec_name')}")
    if (int(stream.get("width", 0)), int(stream.get("height", 0))) != (1080, 1920):
        raise ValueError(f"Output dimensions invalid: {stream.get('width')}x{stream.get('height')}")
    if not 5.8 <= duration <= 8.2:
        raise ValueError(f"Output duration invalid: {duration:.2f}s")
    return {"codec": stream.get("codec_name"), "width": stream.get("width"), "height": stream.get("height"), "fps": stream.get("r_frame_rate"), "pixel_format": stream.get("pix_fmt"), "duration": round(duration, 3)}


def validate_payload(payload):
    scenes = payload.get("scenes") or []
    if not 2 <= len(scenes) <= 5:
        raise ValueError(f"Renderer v3.2 requires 2-5 scenes, got {len(scenes)}")
    total = sum(float(s.get("duration", 0)) for s in scenes)
    if not 6.0 <= total <= 8.0:
        raise ValueError(f"Total duration {total:.2f}s outside 6.0-8.0s")
    first = float(scenes[0].get("duration", 0))
    if not 0.5 <= first <= 0.9:
        raise ValueError(f"First hook duration must be 0.5-0.9s, got {first:.2f}s")
    for i, s in enumerate(scenes, 1):
        if not (s.get("image_url") or s.get("image_path")):
            raise ValueError(f"Scene {i} missing image source")
        if not s.get("headline", "").strip():
            raise ValueError(f"Scene {i} missing headline")
        if len(s.get("headline", "").replace("\n", " ")) > 52:
            raise ValueError(f"Scene {i} headline too long")
        if len(s.get("subheadline", "").replace("\n", " ")) > 58:
            raise ValueError(f"Scene {i} subheadline too long")
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--payload", required=True)
    args = ap.parse_args()
    payload = load_payload(args.payload)
    total = validate_payload(payload)
    slug = payload.get("slug", "reel_output")
    brand = payload.get("brand", "@kpopcoreamx")
    width, height, fps = int(payload.get("width", 1080)), int(payload.get("height", 1920)), int(payload.get("fps", 30))
    if (width, height, fps) != (1080, 1920, 30):
        raise ValueError("Renderer v2.2 requires 1080x1920 at 30fps")
    scenes = payload["scenes"]

    root = Path(__file__).resolve().parents[1]
    tmp, out_dir = root / "tmp" / slug, root / "out"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*"):
        if old.is_file():
            old.unlink()

    segments = []
    source_manifest = []
    for idx, scene in enumerate(scenes, 1):
        src = scene.get("image_url") or scene.get("image_path")
        raw = tmp / f"raw_{idx}{ext_from_src(src)}"
        base, overlay, segment = tmp / f"base_{idx}.jpg", tmp / f"overlay_{idx}.png", tmp / f"segment_{idx}.mp4"
        download_or_copy(src, raw)
        validate_image(raw, idx)
        prepare_photo(scene, raw, base, width, height)
        make_overlay(scene, brand, width, height, overlay)
        render_scene(base, overlay, segment, float(scene["duration"]), width, height, fps, scene)
        segments.append(segment)
        source_manifest.append({"scene": idx, "image_url": scene.get("image_url"), "source_url": scene.get("source_url"), "image_credit": scene.get("image_credit"), "headline": scene.get("headline"), "duration": scene.get("duration"), "fit_mode": scene.get("fit_mode", "auto")})

    final = out_dir / f"{slug}.mp4"
    concat_segments(segments, final)
    info = probe_video(final)
    cover = out_dir / f"{slug}_cover.jpg"
    run(["ffmpeg", "-y", "-ss", "0.10", "-i", str(final), "-frames:v", "1", "-q:v", "2", str(cover)])
    manifest = out_dir / f"{slug}_manifest.json"
    manifest.write_text(json.dumps({"slug": slug, "brand": brand, "target_duration": total, "output": info, "news_id": payload.get("news_id"), "verified_at": payload.get("verified_at"), "scenes": source_manifest}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {final}")
    print(f"Cover: {cover}")
    print(f"Verified: {json.dumps(info)}")


if __name__ == "__main__":
    main()
