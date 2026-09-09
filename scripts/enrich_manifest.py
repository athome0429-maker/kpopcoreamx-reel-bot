import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--payload", required=True)
    ap.add_argument("--out-dir", default="out")
    args = ap.parse_args()

    payload = json.loads(Path(args.payload).read_text(encoding="utf-8"))
    out_dir = Path(args.out_dir)
    manifests = list(out_dir.glob("*_manifest.json"))
    if len(manifests) != 1:
        raise SystemExit(f"Expected exactly one manifest, found {len(manifests)}")

    path = manifests[0]
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["strategy"] = {
        "version": payload.get("strategy_version"),
        "topic_type": payload.get("topic_type"),
        "final_score": payload.get("final_score"),
        "mexico_utility_score": payload.get("mexico_utility_score"),
        "follow_score": payload.get("follow_score"),
        "winning_hook_type": payload.get("winning_hook_type"),
        "winning_hook": payload.get("winning_hook"),
    }
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Enriched manifest: {path}")


if __name__ == "__main__":
    main()
