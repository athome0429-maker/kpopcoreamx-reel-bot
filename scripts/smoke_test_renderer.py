import json
import subprocess
import tempfile
from pathlib import Path
from PIL import Image
from render_reel import prepare_photo, make_overlay, render_scene, probe_video

def main():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        source = p / "original.png"
        Image.new("RGB", (900, 1200), (45, 90, 140)).save(source)
        scene = {"headline": "PRUEBA CDMX", "subheadline": "SIN PUBLICAR", "duration": 6.4}
        base, overlay, video = p / "base.jpg", p / "overlay.png", p / "test.mp4"
        prepare_photo(scene, source, base, 1080, 1920)
        make_overlay(scene, "", 1080, 1920, overlay)
        with Image.open(base) as im:
            assert im.getpixel((540, 600))[2] > 100, "Original photo missing"
            assert max(im.getpixel((540, 1700))) < 10, "Caption area must be separate"
        with Image.open(overlay) as im:
            assert im.getpixel((540, 600))[3] == 0, "Overlay obstructs original photo"
        render_scene(base, overlay, video, 6.4, 1080, 1920, 30, scene)
        result = probe_video(video)
        assert video.stat().st_size > 10000
        print("SMOKE_TEST_OK", json.dumps(result))
if __name__ == "__main__":
    main()
