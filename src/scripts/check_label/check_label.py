import pandas as pd

def check_label_distribution(
    df: pd.DataFrame,
    label_col: str = "Target",
    label_map: dict | None = None,
) -> pd.DataFrame:
    if label_col not in df.columns:
        raise ValueError(f"Kolom '{label_col}' tidak ditemukan. Kolom tersedia: {list(df.columns)}")

    counts = df[label_col].value_counts(dropna=False).sort_index()
    percents = (df[label_col].value_counts(dropna=False, normalize=True).sort_index() * 100)

    result = pd.DataFrame({
        "label": counts.index,
        "count": counts.values,
        "percent": percents.values.round(4),
    })

    if label_map is not None:
        result["label_name"] = result["label"].map(label_map).fillna(result["label"].astype(str))
        result = result[["label", "label_name", "count", "percent"]]

    total = len(df)
    print("=" * 60)
    print(f"Total rows: {total:,}")
    print(result.to_string(index=False))
    print("=" * 60)

    return result