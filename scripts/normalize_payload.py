import argparse
import json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        payload = json.load(f)

    account = (payload.get("brand") or "@kpopcoreamx").strip()
    scenes = payload.get("scenes") or []
    if scenes:
        last = scenes[-1]
        headline = (last.get("headline") or "").strip()
        sub = (last.get("subheadline") or "").strip()
        # Keep the CTA, but move it into the final headline so the account can
        # appear once, only on the last cut.
        if sub and sub != account:
            combined = f"{headline}\n{sub}" if headline else sub
            if len(combined.replace("\n", " ")) <= 52:
                last["headline"] = combined
                last["subheadline"] = account
            else:
                last["subheadline"] = f"{sub}  {account}"
        elif not sub:
            last["subheadline"] = account

    # The renderer normally repeats the global brand on every scene. Blank it
    # here because the final scene now carries the account explicitly.
    payload["brand"] = ""
    payload["account_brand"] = account

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
