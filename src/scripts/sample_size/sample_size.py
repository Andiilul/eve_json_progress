import pandas as pd

# contoh: ambil sample dari train export (atau parquet)
from pathlib import Path
import pandas as pd

p = Path(r"D:\fadilul\New folder\eve-json-progress\results\eve_json\exports\modeling\model_800000000_atk32907642_benPOOL98722926_tr80_te20_trainMODEbalanced_testMODEremainder_trainUB1.0_testUB10.0_stress0_seed42__train.csv.gz")

df = pd.read_csv(p, nrows=200_000)
print(df.shape)
bytes_total = df.memory_usage(deep=True).sum()
bytes_per_row = bytes_total / len(df)

# 32GB RAM, pakai 60% untuk proses, lalu kasih headroom 3x untuk copy sementara
max_rows = int((32 * 1024**3 * 0.65) / (bytes_per_row * 3.0))

print("bytes_per_row:", bytes_per_row)
print("max_rows (safe-ish):", max_rows)