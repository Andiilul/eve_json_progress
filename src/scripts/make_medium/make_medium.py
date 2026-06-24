from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


# ============================================================
# CONFIG
# ============================================================
BASE_DIR = Path("results/eve_json")
MODELING_DIR = BASE_DIR / "exports" / "modeling"

# medium target
TRAIN_ROWS = 8_000_000
TEST_ROWS = 2_000_000

# balanced split
TRAIN_ATTACK_ROWS = TRAIN_ROWS // 2
TRAIN_BENIGN_ROWS = TRAIN_ROWS - TRAIN_ATTACK_ROWS
TEST_ATTACK_ROWS = TEST_ROWS // 2
TEST_BENIGN_ROWS = TEST_ROWS - TEST_ATTACK_ROWS

SEED = 42
OUT_DIR_NAME = "phase8_dataset_for_p10"


# ============================================================
# HELPERS
# ============================================================
def find_latest_meta(modeling_dir: Path) -> Path:
    metas = sorted(modeling_dir.glob("model_*__meta.json"))
    if not metas:
        raise FileNotFoundError(
            f"Tidak menemukan file meta Phase 8 di: {modeling_dir}"
        )
    return metas[-1]


def require_existing_path(raw_path: str | None, label: str) -> Path:
    if not raw_path:
        raise RuntimeError(f"Path untuk {label} tidak ada di meta.")
    path = Path(raw_path)
    if not path.exists():
        raise FileNotFoundError(f"File {label} tidak ditemukan: {path}")
    return path


def read_first_n_rows(csv_path: Path, n: int) -> pd.DataFrame:
    if n <= 0:
        return pd.DataFrame()

    compression = "gzip" if csv_path.suffix == ".gz" else "infer"
    return pd.read_csv(csv_path, compression=compression, nrows=n)


def build_medium_from_split(
    attack_path: Path,
    benign_path: Path,
    n_attack: int,
    n_benign: int,
    seed: int,
) -> pd.DataFrame:
    print(f"[INFO] Read attack  : {attack_path.name} | nrows={n_attack:,}")
    df_attack = read_first_n_rows(attack_path, n_attack)

    print(f"[INFO] Read benign  : {benign_path.name} | nrows={n_benign:,}")
    df_benign = read_first_n_rows(benign_path, n_benign)

    if df_attack.empty and df_benign.empty:
        raise RuntimeError("Kedua dataframe kosong. Medium gagal dibuat.")

    df = pd.concat([df_attack, df_benign], ignore_index=True)
    df = df.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    return df


def main() -> None:
    modeling_dir = MODELING_DIR
    out_dir = modeling_dir / OUT_DIR_NAME
    out_dir.mkdir(parents=True, exist_ok=True)

    meta_path = find_latest_meta(modeling_dir)
    print(f"[INFO] Meta found   : {meta_path}")

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    paths_extra = meta.get("paths_extra") or {}

    train_attack_path = require_existing_path(
        paths_extra.get("train_attack_csv"), "train_attack_csv"
    )
    train_benign_path = require_existing_path(
        paths_extra.get("train_benign_csv"), "train_benign_csv"
    )
    test_attack_path = require_existing_path(
        paths_extra.get("test_attack_csv"), "test_attack_csv"
    )
    test_benign_path = require_existing_path(
        paths_extra.get("test_benign_csv"), "test_benign_csv"
    )

    train_out = out_dir / "train.csv"
    test_out = out_dir / "test.csv"

    print("[INFO] Building train medium...")
    df_train = build_medium_from_split(
        attack_path=train_attack_path,
        benign_path=train_benign_path,
        n_attack=TRAIN_ATTACK_ROWS,
        n_benign=TRAIN_BENIGN_ROWS,
        seed=SEED,
    )
    df_train.to_csv(train_out, index=False)
    print(f"[OK] Saved train   : {train_out} | rows={len(df_train):,}")

    print("[INFO] Building test medium...")
    df_test = build_medium_from_split(
        attack_path=test_attack_path,
        benign_path=test_benign_path,
        n_attack=TEST_ATTACK_ROWS,
        n_benign=TEST_BENIGN_ROWS,
        seed=SEED + 1,
    )
    df_test.to_csv(test_out, index=False)
    print(f"[OK] Saved test    : {test_out} | rows={len(df_test):,}")

    meta["phase_8_export_medium"] = True
    meta["paths_medium_for_phase10"] = {
        "format": "csv",
        "dir": str(out_dir),
        "train_csv": str(train_out),
        "test_csv": str(test_out),
        "train_parquet": None,
        "test_parquet": None,
        "train_rows": int(len(df_train)),
        "test_rows": int(len(df_test)),
    }

    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"[OK] Updated meta  : {meta_path}")

    print("\nDONE")
    print(f"Train medium: {train_out}")
    print(f"Test medium : {test_out}")


if __name__ == "__main__":
    main()