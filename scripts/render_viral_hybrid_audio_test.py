import argparse
import json
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


def probe(path):
    p = run([
        "ffprobe", "-v", "error",
        "-show_entries", "stream=index,codec_type,codec_name,width,height,r_frame_rate",
        "-show_entries", "format=duration",
        "-of", "json", str(path)
    ], capture=True)
    return json.loads(p.stdout)


def download_with_ytdlp(page_url, dest):
    tmpl = str(dest.with_suffix(".%(ext)s"))
    run([
        "yt-dlp", "--no-playlist", "--merge-output-format", "mp4",
        "-f", "bv*+ba/b", "-o", tmpl, page_url
    ])
    candidates = list(dest.parent.glob(dest.stem + ".*"))
    media = [p for p in candidates if p.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"}]
    if not media:
        raise RuntimeError("yt-dlp produced no video file")
    src = max(media, key=lambda p: p.stat().st_size)
    if src != dest:
        run(["ffmpeg", "-y", "-i", str(src), "-c", "copy", str(dest)])
    return dest.stat().st_size, "yt-dlp"


def fx_find_video_url(obj):
    if isinstance(obj, dict):
        for key in ("url", "video_url", "playback_url", "download_url"):
            val = obj.get(key)
            if isinstance(val, str) and (".mp4" in val or "video.twimg.com" in val):
                return val
        for key in ("videos", "video", "media", "all", "tweet"):
            if key in obj:
                found = fx_find_video_url(obj[key])
                if found:
                    return found
        for val in obj.values():
            found = fx_find_video_url(val)
            if found:
                return found
    elif isinstance(obj, list):
        ranked = []
        for item in obj:
            if isinstance(item, dict):
                u = fx_find_video_url(item)
                if u:
                    score = int(item.get("bitrate") or 0) + int(item.get("width") or 0) * 1000
                    ranked.append((score, u))
        if ranked:
            ranked.sort(reverse=True)
            return ranked[0][1]
        for item in obj:
            found = fx_find_video_url(item)
            if found:
                return found
    return None


def download_fxtwitter(page_url, dest):
    parts = page_url.rstrip("/").split("/")
    if "status" not in parts:
        raise RuntimeError("Could not parse X status ID")
    i = parts.index("status")
    status_id = parts[i + 1]
    author = parts[i - 1] if i > 0 else "i"
    headers = {"User-Agent": "Mozilla/5.0 (KPOP-Corea-MX-ViralHybrid/0.2)"}
    last_error = None
    for api_url in (
        f"https://api.fxtwitter.com/{author}/status/{status_id}",
        f"https://api.fxtwitter.com/i/status/{status_id}",
    ):
        try:
            r = requests.get(api_url, headers=headers, timeout=30)
            r.raise_for_status()
            media_url = fx_find_video_url(r.json())
            if not media_url:
                continue
            with requests.get(media_url, headers=headers, timeout=60, stream=True) as vr:
                vr.raise_for_status()
                total = 0
                with open(dest, "wb") as f:
                    for chunk in vr.iter_content(1024 * 256):
                        if chunk:
                            total += len(chunk)
                            if total > 100 * 1024 * 1024:
                                raise RuntimeError("Source video exceeds 100MB limit")
                            f.write(chunk)
            if total > 100_000:
                return total, "fxtwitter"
        except Exception as e:
            last_error = e
    raise RuntimeError(f"FxTwitter fallback failed: {last_error!r}")


def esc(path):
    return str(path).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--payload", required=True)
    args = ap.parse_args()
    payload = load_json(args.payload)

    root = Path(__file__).resolve().parents[1]
    slug = payload.get("slug", "viral_hybrid_audio_test")
    tmp = root / "tmp" / slug
    out = root / "out"
    tmp.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)

    source_page = payload["source_page"]
    source = tmp / "source.mp4"
    try:
        size_bytes, resolver = download_with_ytdlp(source_page, source)
    except Exception as first:
        print("yt-dlp failed, trying FxTwitter:", repr(first))
        size_bytes, resolver = download_fxtwitter(source_page, source)

    src = probe(source)
    src_duration = float(src["format"]["duration"])
    src_audio = [s for s in src.get("streams", []) if s.get("codec_type") == "audio"]
    if not src_audio:
        raise RuntimeError("Source has no audio stream; cannot preserve original audio")

    trim_start = max(0.0, float(payload.get("trim_start", 0.0)))
    requested = float(payload.get("duration", 10.3))
    duration = min(requested, max(0.1, src_duration - trim_start))
    if duration < 8.0:
        raise RuntimeError(f"Source section too short for hybrid test: {duration:.2f}s")

    source_credit = payload.get("source_credit", "FUENTE: @multishow · X")
    brand = payload.get("brand", "@kpopcoreamx")
    overlays = payload.get("overlays", [])

    credit_file = tmp / "credit.txt"
    credit_file.write_text(source_credit, encoding="utf-8")
    brand_file = tmp / "brand.txt"
    brand_file.write_text(brand, encoding="utf-8")
    text_files = []
    for i, item in enumerate(overlays):
        p = tmp / f"overlay_{i}.txt"
        p.write_text(item["text"], encoding="utf-8")
        text_files.append(p)

    base = (
        "[0:v]split=2[bgsrc][fgsrc];"
        "[bgsrc]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        "gblur=sigma=28,eq=brightness=-0.22:saturation=0.75[bg];"
        "[fgsrc]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,fps=30,eq=contrast=1.03:saturation=1.04[v0]"
    )
    filters = [base]
    chain = "[v0]"
    step = 1

    def draw(text_path, fontsize, y, boxcolor, enable=None, color="white", fontfile=FONT_BOLD):
        nonlocal chain, step
        out_label = f"[v{step}]"
        en = f":enable='{enable}'" if enable else ""
        filters.append(
            f"{chain}drawtext=fontfile='{fontfile}':textfile='{esc(text_path)}':"
            f"fontcolor={color}:fontsize={fontsize}:x=(w-text_w)/2:y={y}:"
            f"box=1:boxcolor={boxcolor}:boxborderw=18:shadowcolor=black@0.75:shadowx=3:shadowy=3{en}{out_label}"
        )
        chain = out_label
        step += 1

    draw(credit_file, 25, "64", "black@0.24", fontfile=FONT_REG)
    for i, item in enumerate(overlays):
        start = float(item["start"])
        end = min(float(item["end"]), duration)
        if start >= duration or end <= start:
            continue
        y = "155" if item.get("position", "top") == "top" else "h-345"
        draw(
            text_files[i], int(item.get("fontsize", 58)), y,
            "black@0.38", f"between(t,{start:.3f},{end:.3f})", item.get("color", "white")
        )

    brand_start = max(0.0, duration - 1.6)
    draw(brand_file, 32, "h-145", "black@0.24", f"between(t,{brand_start:.3f},{duration:.3f})")

    final = out / f"{slug}.mp4"
    run([
        "ffmpeg", "-y", "-ss", str(trim_start), "-i", str(source), "-t", f"{duration:.3f}",
        "-filter_complex", ";".join(filters),
        "-map", chain, "-map", "0:a:0",
        "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-shortest", str(final)
    ])

    info = probe(final)
    video_streams = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
    audio_streams = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
    if not video_streams or not audio_streams:
        raise RuntimeError("Output verification failed: missing video or preserved audio stream")
    video = video_streams[0]
    audio = audio_streams[0]
    if video.get("codec_name") != "h264" or (int(video.get("width", 0)), int(video.get("height", 0))) != (1080, 1920):
        raise RuntimeError("Output video verification failed")

    cover = out / f"{slug}_cover.jpg"
    run(["ffmpeg", "-y", "-ss", "0.45", "-i", str(final), "-frames:v", "1", "-q:v", "2", str(cover)])

    manifest = {
        "kind": "viral_hybrid_audio_test",
        "strategy": "VIRAL_HYBRID_v0.2",
        "slug": slug,
        "source_page": source_page,
        "source_credit": source_credit,
        "resolver": resolver,
        "source_bytes": size_bytes,
        "source_duration": round(src_duration, 3),
        "trim_start": trim_start,
        "output_duration": round(float(info["format"]["duration"]), 3),
        "output": {
            "video_codec": video.get("codec_name"),
            "width": video.get("width"),
            "height": video.get("height"),
            "fps": video.get("r_frame_rate"),
            "audio_codec": audio.get("codec_name"),
            "audio_preserved": True
        },
        "overlays": overlays,
        "note": "Emotion-first hybrid test: motion and source audio are preserved, text is minimized, Mexico utility is added late, and CTA is brief. Main Scout/render history is untouched."
    }
    manifest_path = out / f"{slug}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
