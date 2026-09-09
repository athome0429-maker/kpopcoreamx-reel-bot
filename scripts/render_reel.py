import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def run(cmd):
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True)


def load_payload(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def ext_from_src(src):
    return os.path.splitext(urlparse(src).path)[1].lower() or ".jpg"


def download_or_copy(src, out_path):
    if src.startswith(("http://", "https://")):
        r = requests.get(src, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        out_path.write_bytes(r.content)
    else:
        shutil.copy(src, out_path)


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
    src = ImageOps.exif_transpose(Image.open(src_path)).convert("RGB")
    mode = scene.get("fit_mode", "auto")
    fx = min(1.0, max(0.0, float(scene.get("focus_x", 0.5))))
    fy = min(1.0, max(0.0, float(scene.get("focus_y", 0.38))))
    ratio = src.width / max(1, src.height)
    if mode == "auto":
        mode = "contain" if ratio >= 0.85 else "cover"

    if mode == "contain":
        bg = ImageOps.fit(src, (width, height), Image.Resampling.LANCZOS, centering=(fx, fy))
        bg = bg.filter(ImageFilter.GaussianBlur(34))
        bg = Image.blend(bg, Image.new("RGB", (width, height), "black"), 0.22).convert("RGBA")
        fg = src.copy()
        fg.thumbnail((width, int(height * 0.70)), Image.Resampling.LANCZOS)
        x, y = (width - fg.width) // 2, max(70, int(height * 0.08))
        shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        sh = Image.new("RGBA", fg.size, (0, 0, 0, 175)).filter(ImageFilter.GaussianBlur(20))
        shadow.alpha_composite(sh, (x, y + 18))
        bg.alpha_composite(shadow)
        bg.alpha_composite(fg.convert("RGBA"), (x, y))
        bg.convert("RGB").save(out_path, quality=95)
    else:
        ImageOps.fit(src, (width, height), Image.Resampling.LANCZOS, centering=(fx, fy)).save(out_path, quality=95)


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

    if sub:
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
    frames = max(1, int(round(duration * fps)))
    zoom_end = min(1.16, max(1.03, float(scene.get("zoom", 1.09))))
    step = max(0.0002, (zoom_end - 1.0) / frames)
    pan_x, pan_y = float(scene.get("pan_x", 0.0)), float(scene.get("pan_y", 0.0))
    vf = (
        f"zoompan=z='min(zoom+{step:.7f},{zoom_end:.4f})':"
        f"x='max(0,min(iw-iw/zoom,iw/2-(iw/zoom/2)+{pan_x:.2f}))':"
        f"y='max(0,min(ih-ih/zoom,ih/2-(ih/zoom/2)+{pan_y:.2f}))':"
        f"d={frames}:s={width}x{height}:fps={fps},"
        f"eq=contrast=1.03:brightness=-0.01:saturation=1.03[bg];"
        f"[1:v]format=rgba[fg];[bg][fg]overlay=0:0:format=auto"
    )
    run(["ffmpeg", "-y", "-loop", "1", "-i", str(base_path), "-i", str(overlay_path), "-filter_complex", vf, "-t", str(duration), "-r", str(fps), "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_path)])


def concat_segments(paths, out_path):
    list_path = out_path.parent / "concat.txt"
    with open(list_path, "w", encoding="utf-8") as f:
        for p in paths:
            f.write(f"file '{p.resolve()}'\n")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path), "-c", "copy", "-movflags", "+faststart", str(out_path)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--payload", required=True)
    args = ap.parse_args()
    payload = load_payload(args.payload)
    slug = payload.get("slug", "reel_output")
    brand = payload.get("brand", "@kpopcoreamx")
    width, height, fps = int(payload.get("width", 1080)), int(payload.get("height", 1920)), int(payload.get("fps", 30))
    scenes = payload["scenes"]
    total = sum(float(s["duration"]) for s in scenes)
    if not 5.5 <= total <= 8.5:
        raise ValueError(f"Total duration {total:.2f}s outside target range 5.5-8.5s")

    root = Path(__file__).resolve().parents[1]
    tmp, out_dir = root / "tmp" / slug, root / "out"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    segments = []

    for idx, scene in enumerate(scenes, 1):
        src = scene.get("image_url") or scene.get("image_path")
        if not src:
            raise ValueError(f"Scene {idx} missing image source")
        raw = tmp / f"raw_{idx}{ext_from_src(src)}"
        base, overlay, segment = tmp / f"base_{idx}.jpg", tmp / f"overlay_{idx}.png", tmp / f"segment_{idx}.mp4"
        download_or_copy(src, raw)
        prepare_photo(scene, raw, base, width, height)
        make_overlay(scene, brand, width, height, overlay)
        render_scene(base, overlay, segment, float(scene["duration"]), width, height, fps, scene)
        segments.append(segment)

    final = out_dir / f"{slug}.mp4"
    concat_segments(segments, final)
    print(f"Saved: {final}")


if __name__ == "__main__":
    main()
