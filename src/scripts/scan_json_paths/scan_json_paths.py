#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def walk_paths(obj, prefix=""):
    """Yield dotted key paths for dict/list JSON."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else str(k)
            yield p
            yield from walk_paths(v, p)
    elif isinstance(obj, list):
        p = f"{prefix}[]" if prefix else "[]"
        yield p
        if obj:
            yield from walk_paths(obj[0], p)


def parse_args():
    ap = argparse.ArgumentParser(
        description="Scan JSONL and export all dotted key paths to a text file."
    )
    ap.add_argument(
        "--jsonl",
        required=True,
        type=Path,
        help="Path to input JSONL file (e.g., eve_sample_1000000.jsonl)",
    )
    ap.add_argument(
        "--max-lines",
        type=int,
        default=200_000,
        help="Max lines to scan (default: 200000). Use 0 to scan full file.",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("artifacts/analysis/raw_paths.txt"),
        help="Output .txt path (default: artifacts/analysis/raw_paths.txt)",
    )
    ap.add_argument(
        "--tokens",
        type=str,
        default="pkt,pkts,packet,byte,bytes,flow,alert,severity",
        help="Comma-separated tokens to filter and print sample hits.",
    )
    ap.add_argument(
        "--show-token-sample",
        type=int,
        default=40,
        help="How many token-matched paths to print (default: 40).",
    )
    return ap.parse_args()


def main():
    args = parse_args()
    jsonl_path: Path = args.jsonl
    out_path: Path = args.out
    max_lines: int = args.max_lines

    if not jsonl_path.exists():
        raise FileNotFoundError(f"Not found: {jsonl_path.resolve()}")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    paths = set()
    top_keys = set()

    total = 0
    ok = 0

    with jsonl_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            total += 1
            if max_lines and total > max_lines:
                break

            line = line.strip()
            if not line:
                continue

            try:
                obj = json.loads(line)
            except Exception:
                continue

            if not isinstance(obj, dict):
                continue

            ok += 1
            top_keys.update(obj.keys())
            for p in walk_paths(obj):
                paths.add(p)

    out_path.write_text("\n".join(sorted(paths)), encoding="utf-8")

    print("\n✅ DONE")
    cap = f"{max_lines:,}" if max_lines else "FULL"
    print(f"Scanned lines : {total:,} (cap={cap})")
    print(f"Parsed OK     : {ok:,}")
    print(f"Top-level keys: {len(top_keys)}")
    print(f"All paths     : {len(paths):,}")
    print(f"Saved paths   : {out_path.resolve()}")

    tokens = tuple(t.strip() for t in args.tokens.split(",") if t.strip())
    hits = [p for p in paths if any(t in p.lower() for t in tokens)]
    print(f"\nToken paths {tokens} = {len(hits)}")
    print("Sample token paths:")
    for p in sorted(hits)[: args.show_token_sample]:
        print(" -", p)


if __name__ == "__main__":
    main()
