import argparse
import json
import os
import subprocess
from pathlib import Path

import requests

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def run(cmd, capture=False):
    print("$", " ".join(map(str, cmd)))
    return subprocess.run(cmd, check=True, text=True, capture_output=capture)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def ffprobe(path):
    p = run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,r_frame_rate",
        "-show_entries", "format=duration", "-of", "json", str(path)
    ], capture=True)
    return json.loads(p.stdout)


def get_tikwm_media(payload):
    tiktok_url = payload["tiktok_url"]
    video_id = payload.get("tiktok_id", "")
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
        "Referer": "https://www.tiktok.com/",
    }
    session = requests.Session()
    session.headers.update(headers)

    try:
        r = session.get("https://www.tikwm.com/api/", params={"url": tiktok_url, "hd": "1"}, timeout=30)
        r.raise_for_status()
        body = r.json()
        if body.get("code") == 0 and body.get("data"):
            data = body["data"]
            # Prefer the attributed/watermarked source when available.
            media_url = data.get("wmplay") or data.get("play") or data.get("hdplay")
            if media_url:
                return media_url, "tikwm_api", data
    except Exception as e:
        print("TikWM API lookup failed:", repr(e))

    if video_id:
        fallback = f"https://www.tikwm.com/video/media/wmplay/{video_id}.mp4"
        return fallback, "tikwm_watermark_fallback", {}
    raise RuntimeError("Could not resolve public source video URL")


def download_video(url, dest):
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
        "Referer": "https://www.tiktok.com/",
    }
    with requests.get(url, headers=headers, timeout=60, stream=True, allow_redirects=True) as r:
        r.raise_for_status()
        total = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1024 * 256):
                if not chunk:
                    continue
                total += len(chunk)
                if total > 80 * 1024 * 1024:
                    raise RuntimeError("Source video exceeds 80MB test limit")
                f.write(chunk)
    if total < 100_000:
        raise RuntimeError(f"Downloaded source is unexpectedly small: {total} bytes")
    return total


def escape_filter_path(path):
    return str(path).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--payload", required=True)
    args = ap.parse_args()
    payload = load_json(args.payload)

    root = Path(__file__).resolve().parents[1]
    slug = payload.get("slug", "viral_test")
    tmp = root / "tmp" / slug
    out = root / "out"
    tmp.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)

    source = tmp / "source.mp4"
    media_url, resolver, resolver_data = get_tikwm_media(payload)
    size_bytes = download_video(media_url, source)
    src_info = ffprobe(source)
    src_duration = float(src_info["format"]["duration"])

    trim_start = max(0.0, float(payload.get("trim_start", 0.0)))
    requested_duration = float(payload.get("duration", 8.8))
    available = max(0.1, src_duration - trim_start)
    duration = min(requested_duration, available)
    if duration < 6.0:
        raise RuntimeError(f"Source section too short for Reel test: {duration:.2f}s")

    overlays = payload.get("overlays", [])
    source_credit = payload.get("source_credit", "FUENTE: @calvinklein · TikTok")
    brand = payload.get("brand", "@kpopcoreamx")

    # Write text to files so Spanish punctuation and accents are safe in FFmpeg filters.
    text_files = []
    for i, item in enumerate(overlays):
        p = tmp / f"overlay_{i}.txt"
        p.write_text(item["text"], encoding="utf-8")
        text_files.append(p)
    credit_file = tmp / "credit.txt"
    credit_file.write_text(source_credit, encoding="utf-8")
    brand_file = tmp / "brand.txt"
    brand_file.write_text(brand, encoding="utf-8")

    filters = [
        "scale=1080:1920:force_original_aspect_ratio=increase",
        "crop=1080:1920",
        "fps=30",
        "setsar=1",
        "eq=contrast=1.03:saturation=1.03",
    ]

    # Persistent attribution: small, readable, does not cover the subject.
    filters.append(
        "drawtext="
        f"fontfile='{FONT_REG}':textfile='{escape_filter_path(credit_file)}':"
        "fontcolor=white@0.90:fontsize=28:x=54:y=70:"
        "box=1:boxcolor=black@0.30:boxborderw=10"
    )

    for i, item in enumerate(overlays):
        start = float(item["start"])
        end = min(float(item["end"]), duration)
        if start >= duration or end <= start:
            continue
        position = item.get("position", "top")
        y = "170" if position == "top" else "h-470"
        fontsize = int(item.get("fontsize", 74))
        color = item.get("color", "white")
        filters.append(
            "drawtext="
            f"fontfile='{FONT_BOLD}':textfile='{escape_filter_path(text_files[i])}':"
            f"fontcolor={color}:fontsize={fontsize}:"
            "x=(w-text_w)/2:"
            f"y={y}:"
            "box=1:boxcolor=black@0.42:boxborderw=24:"
            "shadowcolor=black@0.75:shadowx=3:shadowy=3:"
            f"enable='between(t,{start:.3f},{end:.3f})'"
        )

    brand_start = max(0.0, duration - 2.2)
    filters.append(
        "drawtext="
        f"fontfile='{FONT_BOLD}':textfile='{escape_filter_path(brand_file)}':"
        "fontcolor=white@0.95:fontsize=34:x=(w-text_w)/2:y=h-160:"
        "box=1:boxcolor=black@0.25:boxborderw=10:"
        f"enable='between(t,{brand_start:.3f},{duration:.3f})'"
    )

    vf = ",".join(filters)
    final = out / f"{slug}.mp4"
    run([
        "ffmpeg", "-y", "-ss", str(trim_start), "-i", str(source),
        "-t", f"{duration:.3f}", "-vf", vf,
        "-an", "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(final)
    ])

    out_info = ffprobe(final)
    stream = out_info["streams"][0]
    if stream.get("codec_name") != "h264":
        raise RuntimeError("Output codec is not H.264")
    if (int(stream.get("width", 0)), int(stream.get("height", 0))) != (1080, 1920):
        raise RuntimeError("Output is not 1080x1920")

    cover = out / f"{slug}_cover.jpg"
    run(["ffmpeg", "-y", "-ss", "0.35", "-i", str(final), "-frames:v", "1", "-q:v", "2", str(cover)])

    manifest = {
        "kind": "viral_video_test",
        "strategy": payload.get("strategy", "VIRAL_TEST_v0.1"),
        "slug": slug,
        "source_original": payload["tiktok_url"],
        "source_page": payload.get("source_page"),
        "source_credit": source_credit,
        "resolver": resolver,
        "resolver_metadata": {
            "id": resolver_data.get("id"),
            "author": (resolver_data.get("author") or {}).get("unique_id") if isinstance(resolver_data.get("author"), dict) else None,
            "title": resolver_data.get("title"),
        },
        "source_bytes": size_bytes,
        "source_duration": round(src_duration, 3),
        "trim_start": trim_start,
        "output_duration": round(float(out_info["format"]["duration"]), 3),
        "output": {
            "codec": stream.get("codec_name"),
            "width": stream.get("width"),
            "height": stream.get("height"),
            "fps": stream.get("r_frame_rate"),
        },
        "audio": "muted_for_cross-platform_test; add licensed Instagram audio manually",
        "overlays": overlays,
        "note": "Transformative test edit with Spanish fan-context overlays and persistent source attribution. Main Scout/render history is not modified."
    }
    manifest_path = out / f"{slug}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
