from __future__ import annotations

"""
Single-click launcher for the CBR / Suricata EVE pipeline.

All orchestration settings are controlled from:
    src/cbr/config.py -> create_default_large_config()

Normal usage:
    python src/main.py
"""

import sys
from importlib.util import find_spec


REQUIRED_DEPS = {
    "numpy": "numpy",
    "pandas": "pandas",
    "sklearn": "scikit-learn",
    "matplotlib": "matplotlib",
}

OPTIONAL_DEPS = {
    "psutil": "psutil",
    "xgboost": "xgboost",
    "joblib": "joblib",
    "threadpoolctl": "threadpoolctl",
    "orjson": "orjson",
}


def _preflight(strict: bool = False) -> None:
    if sys.version_info < (3, 10):
        raise SystemExit(f"Python >= 3.10 required. Current: {sys.version.split()[0]}")

    missing_required = []
    missing_optional = []

    for mod, pip_name in REQUIRED_DEPS.items():
        if find_spec(mod) is None:
            missing_required.append((mod, pip_name))

    for mod, pip_name in OPTIONAL_DEPS.items():
        if find_spec(mod) is None:
            missing_optional.append((mod, pip_name))

    if missing_required or (strict and missing_optional):
        lines = ["Missing dependencies:"]
        for mod, pip_name in missing_required:
            lines.append(f" - {mod}  (pip install {pip_name})")
        if strict:
            for mod, pip_name in missing_optional:
                lines.append(f" - {mod}  (pip install {pip_name})")
        lines += ["", "Fix:", "   python -m pip install -r requirements.txt"]
        raise SystemExit("\n".join(lines))

    if missing_optional:
        print("Optional deps not installed:")
        for mod, pip_name in missing_optional:
            print(f" - {mod}  (pip install {pip_name})")
        print("Pipeline can still run if those paths are not needed.\n")


def _print_config(cfg) -> None:
    print("\n" + "=" * 88)
    print("RUN SETTINGS FROM src/cbr/config.py")
    print("=" * 88)
    print(f"Apps              : {cfg.selected_apps}")
    print(f"Split app dir     : {cfg.storage.split_app_dir}")
    print(f"Prepipeline sum.  : {cfg.prepipeline_summary_path}")
    print(f"Internal work     : {cfg.storage.internal_work_root}")
    print(f"Archive/output    : {cfg.storage.archive_output_dir}")
    print(f"Copy app input    : {cfg.copy_app_to_internal_before_run}")
    print(f"Target            : {cfg.split.target_column}")
    print(f"Split strategy    : {cfg.split.strategy}")
    print(f"Export format     : {cfg.export.format}, compression={cfg.export.compression}")
    print(f"Viz sample rows   : {cfg.export.visualization_sample_rows:,}")
    print(f"Corr sample rows  : {cfg.export.corr_leak_sample_rows:,}")
    print(f"FS sample rows    : {cfg.modeling.fs_sample_rows:,}")
    print(f"Train sample rows : {cfg.modeling.modeling_train_rows:,}")
    print(f"Test sample rows  : {cfg.modeling.modeling_test_rows:,}")
    print(f"Enabled phases    : {cfg.enabled_phases()}")
    print("=" * 88 + "\n")


def main() -> None:
    _preflight(strict=False)

    from cbr.config import create_default_large_config
    from cbr.pipeline import run_pipeline

    cfg = create_default_large_config()
    _print_config(cfg)
    run_pipeline(cfg)


if __name__ == "__main__":
    main()
