import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import requests
from PIL import Image, ImageDraw, ImageFont

W = 1080
H = 1920
FPS = 30
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def run(cmd):
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True)


def load_payload(path: str):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def ext_from_src(src: str):
    p = urlparse(src).path
    ext = os.path.splitext(p)[1].lower()
    return ext or ".jpg"


def download_or_copy(src: str, out_path: Path):
    if src.startswith("http://") or src.startswith("https://"):
        r = requests.get(src, timeout=30)
        r.raise_for_status()
        out_path.write_bytes(r.content)
    else:
        shutil.copy(src, out_path)


def pick_font(size: int, bold: bool = True):
    path = FONT_BOLD if bold else FONT_REG
    return ImageFont.truetype(path, size)


def fit_multiline(draw, text, max_width, start_size, min_size, spacing=8):
    size = start_size
    while size >= min_size:
        f = pick_font(size, True)
        bbox = draw.multiline_textbbox((0, 0), text, font=f, spacing=spacing, align="center")
        if bbox[2] - bbox[0] <= max_width:
            return f
        size -= 2
    return pick_font(min_size, True)


def make_overlay(scene, brand, width, height, out_path: Path):
    im = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(im, "RGBA")

    # Top and bottom accent bars
    accent = (246, 207, 40, 255)
    d.rectangle((0, 0, width, 26), fill=accent)
    d.rectangle((0, height - 26, width, height), fill=accent)

    # Readability panel
    panel_top = 1090
    panel_bottom = 1660
    d.rounded_rectangle((55, panel_top, width - 55, panel_bottom), radius=42, fill=(0, 0, 0, 175))

    headline = scene["headline"]
    sub = scene.get("subheadline", "")
    main_font = fit_multiline(d, headline, width - 150, 92, 42)
    sub_font = pick_font(36, True)
    brand_font = pick_font(34, True)

    d.multiline_text(
        (width // 2, 1285),
        headline,
        font=main_font,
        anchor="mm",
        align="center",
        fill=(255, 255, 255, 255),
        spacing=8,
        stroke_width=3,
        stroke_fill=(0, 0, 0, 220),
    )
    d.rounded_rectangle((width // 2 - 170, 1480, width // 2 + 170, 1496), radius=8, fill=accent)
    if sub:
        d.text((width // 2, 1565), sub, font=sub_font, anchor="mm", fill=(235, 238, 240, 255))
    d.text((width // 2, 1780), brand, font=brand_font, anchor="mm", fill=(255, 255, 255, 220))

    im.save(out_path)


def render_scene(image_path: Path, overlay_path: Path, out_path: Path, duration: float, width: int, height: int, fps: int):
    frames = max(1, int(round(duration * fps)))
    vf = (
        f"scale=w='if(gt(a,{width}/{height}),-2,{width})':h='if(gt(a,{width}/{height}),{height},-2)',"
        f"crop={width}:{height},"
        f"zoompan=z='min(zoom+0.0012,1.10)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={width}x{height}:fps={fps},"
        f"format=yuv420p[bg];"
        f"[bg][1:v]overlay=0:0:format=auto"
    )
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(image_path),
        "-loop", "1", "-i", str(overlay_path),
        "-filter_complex", vf,
        "-t", f"{duration}",
        "-r", str(fps),
        "-an",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        str(out_path),
    ]
    run(cmd)


def concat_segments(segment_paths, out_path: Path):
    list_path = out_path.parent / "concat.txt"
    with open(list_path, "w", encoding="utf-8") as f:
        for p in segment_paths:
            f.write(f"file '{p.resolve()}'\n")
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path),
        "-c", "copy", str(out_path)
    ]
    run(cmd)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", required=True)
    args = parser.parse_args()

    payload = load_payload(args.payload)
    width = int(payload.get("width", W))
    height = int(payload.get("height", H))
    fps = int(payload.get("fps", FPS))
    slug = payload.get("slug", "reel_output")
    brand = payload.get("brand", "@kpopcoreamx")
    scenes = payload["scenes"]

    root = Path(__file__).resolve().parents[1]
    tmp = root / "tmp" / slug
    out_dir = root / "out"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    segments = []
    for idx, scene in enumerate(scenes, start=1):
        src = scene.get("image_url") or scene.get("image_path")
        if not src:
            raise ValueError(f"Scene {idx} missing image_url/image_path")
        img_path = tmp / f"scene_{idx}{ext_from_src(src)}"
        ov_path = tmp / f"overlay_{idx}.png"
        seg_path = tmp / f"segment_{idx}.mp4"
        download_or_copy(src, img_path)
        make_overlay(scene, brand, width, height, ov_path)
        render_scene(img_path, ov_path, seg_path, float(scene["duration"]), width, height, fps)
        segments.append(seg_path)

    final_path = out_dir / f"{slug}.mp4"
    concat_segments(segments, final_path)
    print(f"Saved: {final_path}")


if __name__ == "__main__":
    main()
