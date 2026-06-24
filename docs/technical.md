# TECHNICAL_DOC_SOURCE_CODE.md
# Technical Documentation — Cara Kerja Source Code (JSON Progress Pipeline)

Terakhir diperbarui: **1 Maret 2026**  
Target pembaca: **developer/maintainer repo** (menjelaskan struktur modul, alur eksekusi, dan kontrak artefak).  
Catatan: Dokumen ini menjelaskan **cara kerja code**; narasi versi skripsi akan dibuat terpisah.

---

## 1) Ringkasan Sistem (Teknis Singkat)
Pipeline ini memproses **Suricata EVE JSONL** menjadi:
- **staging dataset** disk-backed (Parquet shards) untuk data sangat besar,
- **dataset modeling** (train/test) untuk training ML,
- **feature selection artifacts**,
- **baseline training + evaluasi**,
- serta **laporan PDF**.

Desain kunci:
- **Phase 1** disk-backed untuk menjaga RAM.
- **Phase 8** membangun train/test dan *menulis full dataset ke disk* namun hanya *mengembalikan sample kecil* untuk langkah lanjutan, agar pipeline stabil.

---

## 2) Peta Modul (Source Layout)
Struktur utama:

- `src/main.py`  
  Entry point CLI + *one-click defaults* (VSCode Run). Menghasilkan `RunConfig`, memanggil pipeline, dan menulis `metrics/final_summary_main.json`.

- `src/cbr/pipeline.py`  
  Orkestrator pipeline: buat folder artefak, jalankan Phase 1–11 sesuai toggle, simpan ringkasan per fase ke `metrics/`.

- `src/cbr/phases/phase1.py` s/d `phase11_*.py`  
  Implementasi tiap fase preprocessing/modeling.

- `src/scripts/generate_pdf/`  
  Generator PDF report modular (title + section per fase).

---

## 3) Entry Point: `src/main.py`

### 3.1 Dependency preflight
- Wajib: numpy, pandas, tqdm, scikit-learn, matplotlib, reportlab
- Opsional: psutil, seaborn, xgboost/lightgbm/catboost, pyarrow/fastparquet (khusus jika dipilih engine parquet)

Jika `--strict-deps` aktif, optional deps juga diperlakukan wajib.

### 3.2 Default input untuk one-click run
Jika tidak mengisi `--input-file`, default dipilih dari kandidat berikut (urut):
1) env `EVE_JSONL`
2) path hardcoded default (contoh: `D:/fadilul/datas/eve_sample_10000000.jsonl`)
3) fallback lokal: `data/eve.jsonl` atau `eve.jsonl`

Jika file tidak ada, program akan berhenti dengan instruksi perbaikan.

### 3.3 CLI args penting (default utama)
- `--artifacts-dir` default: `results/eve_json`
- `--run-id` default: `eve_json`
- `--sample-size` default: `800_000_000` (**tag** untuk penamaan output/report)
- `--phase1-mode` default: `full`  
  - `full`: Phase 8 membaca Parquet staging (big-run)
  - `model`: Phase 8 memakai `df_clean` in-memory (dev-run)
- `--export-mode` default: `sample_csv`
- `--export-sample-rows` default: `200_000`
- `--train-ratio` default: `3` (interpretasi internal: train benign per attack = 3.0)
- `--pool-benign-per-attack` default: `10.0`
- Phase 1 benign policy:
  - `--benign-ratio-to-attack` default: `1.2`
  - `--benign-reservoir-max` default: `0` (uncapped)
- Parquet:
  - `--phase1-engine` default: `pyarrow`
  - `--phase1-compression` default: `snappy`
- Resume:
  - default **skip Phase 1 jika shards sudah ada**
  - `--force-phase1` untuk memaksa rebuild

### 3.4 Snapshot konfigurasi
Setelah run (berhasil/gagal), main menulis:
- `results/eve_json/metrics/final_summary_main.json`

---

## 4) Orkestrator: `src/cbr/pipeline.py`

### 4.1 Folder artefak yang dibuat
Pipeline selalu membuat folder berikut:
```text
artifacts_dir/
├─ exports/
│  ├─ modeling/
├─ figures/
├─ metrics/
├─ models/
│  ├─ phase9/
│  ├─ phase10/
│  └─ phase11/
├─ phase7/
├─ reports/
└─ checkpoints/
```

### 4.2 Sistem ringkasan (metrics)
Setiap fase menghasilkan `summary dict` yang disimpan ke `metrics/phaseX_summary.json`.  
Report juga punya `metrics/report_summary.json`.

### 4.3 Mode Phase 1
- Jika `skip_phase1_if_exists=True` dan shards Phase 1 sudah ada → Phase 1 dilewati, pipeline akan *sampling df_p1 dari shards* untuk Phase 2–4.
- Jika belum ada shards → Phase 1 dijalankan dan menulis shards baru.

### 4.4 Ketergantungan fase
- Phase 2–4 membutuhkan `df_p1` (sample kecil) agar aman di RAM.
- Phase 8 membutuhkan **full dataset** (disk staging atau `df_clean` kalau mode dev).
- Phase 9 membutuhkan `df_train` dari Phase 8.
- Phase 10 membutuhkan `df_train`, `df_test`, dan `feature_sets` (Phase 9).
- Phase 11 membutuhkan `df_train`, `df_test`, `feature_sets`, dan `results_df` (Phase 10).

---

## 5) Phase-by-Phase: Input → Output → Artefak

## Phase 1 — `phase1_load_and_label` (HUGE-DATA SAFE)
**Lokasi:** `src/cbr/phases/phase1.py`  
**Tujuan:** membaca JSONL besar, membentuk label, dan menulis staging dataset ke disk.

**Mekanisme:**
- PASS 1: hitung total attack/benign dan statistik dasar.
- PASS 2: tulis **ALL attacks** ke Parquet shards + sampling benign dengan batas:
  - benign ≤ `benign_ratio_to_attack * attack_total`
  - dan/atau cap `benign_reservoir_max` (jika >0)

**Output disk:**
- `exports/phase1_dataset/attacks/part-*.parquet`
- `exports/phase1_dataset/benign/part-*.parquet`

**Output in-memory:**
- hanya `df_sample` kecil (`return_df_sample`) untuk menjaga Phase 2–4 dan PDF tetap bisa jalan.

**Output metrics:**
- `metrics/phase1_summary.json`

---

## Phase 2 — `phase2_advanced_feature_engineering`
**Lokasi:** `src/cbr/phases/phase2.py`  
**Tujuan:** standardisasi kolom inti + encoding/hashing stabil.

**Inti operasi:**
- memastikan kolom flow/alert canonical tersedia (`pkts_*`, `bytes_*`, `duration`, `total_*`, `has_alert`, dll.)
- mengubah kolom kategorikal/teks jadi fitur numerik stabil dengan hashing (`hash_pandas_object`)
- menjaga beberapa kolom raw untuk visualisasi (`*_raw`)

**Output:**
- `df_p2` (in-memory)
- `metrics/phase2_summary.json`

---

## Phase 3 — `phase3_computed_features`
**Lokasi:** `src/cbr/phases/phase3.py`  
**Tujuan:** menambah fitur turunan (interaction/ratio/normalization) dengan kontrol leakage.

**Inti operasi:**
- memastikan semua kolom non-raw menjadi numerik (hash jika object)
- mengecualikan kolom leakage-prone dari pembuatan fitur (default: `has_alert`, `alert_severity`, `alert_category`)
- menambah interaksi fitur dan fitur statistik/rasio tambahan

**Output:**
- `df_p3` (in-memory)
- `metrics/phase3_summary.json`

---

## Phase 4 — `phase4_clean_aggressive`
**Lokasi:** `src/cbr/phases/phase4.py`  
**Tujuan:** cleaning agresif terhadap NaN/Inf, penyeragaman tipe, dan defensive guard.

**Inti operasi:**
- numeric: coerce → inf→nan→0
- string/object: jadikan string dengan default `"unknown"`
- memastikan `Target` menjadi binary int (0/1)

**Output:**
- `df_clean` (in-memory)
- `metrics/phase4_summary.json`

---

## Phase 5 — `phase5_export_dataset` (Opsional)
**Lokasi:** `src/cbr/phases/phase5.py`  
**Tujuan:** export dataset hasil cleaning untuk inspeksi/sharing.

**Mode:**
- `none`: skip
- `sample_csv`: export sample acak/stratified (default)
- `csv_gz`: export full + gzip
- `csv`: export full (besar)

**Output disk (contoh):**
- `exports/eve_processed_<sample_size>_sample<N>.csv` (sample_csv)
- `exports/eve_processed_<sample_size>.csv.gz` (csv_gz)
- `exports/eve_processed_<sample_size>.csv` (csv)

**Metrics:**
- `metrics/phase5_export_summary.json`

---

## Phase 6 — `phase6_visualize_phase4` (Opsional)
**Lokasi:** `src/cbr/phases/phase6.py`  
**Tujuan:** menghasilkan visualisasi overview dan heatmap korelasi untuk sample.

**Output disk:**
- `figures/visualization_overview_<tag>_n<...>.png`
- `figures/correlation_heatmap_<tag>_n<...>.png`

**Metrics:**
- `metrics/phase6_summary.json`

---

## Phase 7 — `phase7_correlation_analysis` (Opsional)
**Lokasi:** `src/cbr/phases/phase7_corr.py`  
**Tujuan:** korelasi fitur vs target, sekaligus deteksi indikasi leakage.

**Konsep output ganda:**
- **ALL**: termasuk kolom leakage (untuk mendeteksi leakage)
- **NOLEAK**: mengecualikan leakage denylist (untuk insight normal)

**Output disk (utama):**
- `phase7/corr_df_ALL_<tag>.csv`
- `phase7/corr_df_NOLEAK_<tag>.csv`
- `phase7/top_features_correlation_ALL_<tag>.png`
- `phase7/top_features_correlation_NOLEAK_<tag>.png`
- `phase7/features_to_drop_<tag>.json`
- tambahan: `phase7_meta_<tag>.json`, `nan_issues_<tag>.json`, `features_phase7_<tag>.{txt,json}`

**Metrics:**
- `metrics/phase7_summary.json`

---

## Phase 8 — `phase8_build_model_splits` ✅ (Modeling Dataset Final)
**Lokasi:** `src/cbr/phases/phase8_modeling_split.py`  
**Tujuan:** membangun dataset train/test untuk ML + menulisnya ke disk.

**Mode input:**
- `phase1_mode=full` → baca dari `exports/phase1_dataset/` (disk)
- `phase1_mode=model` → pakai `df_clean` in-memory

**Split & ratio:**
- attack displit train/test (default 80/20)
- benign dialokasikan berdasarkan:
  - `pool_benign_per_attack` (budget benign di pool)
  - `train_benign_per_attack` (undersampling train)
  - `test_benign_per_attack` (test “fair” biasanya lebih besar)
- opsional: `stress_benign_n` untuk dataset benign-only

**Leakage drop (modeling):**
- drop kolom leakage proxy (mis. `has_alert`, `alert_category`, `alert_severity`, `event_type`, dsb.)
- jika `phase7/features_to_drop_<tag>.json` ada, akan dipakai sebagai tambahan drop.

**Output disk:**
- `exports/modeling/model_<tag>_<key>__train.csv(.gz)`
- `exports/modeling/model_<tag>_<key>__testFAIR.csv(.gz)`
- `exports/modeling/model_<tag>_<key>__meta.json`
- opsional:
  - `__stressBENIGN.csv(.gz)` (jika stress aktif)
  - `__pool.csv(.gz)` (jika export_pool=True)

**Catatan penting (sharded benign companion):**
Dalam beberapa kondisi, Phase 8 bisa menulis file `_BENIGN` terpisah lalu pipeline akan **menggabungkan** saat load:
- `__train_BENIGN...`
- `__testFAIR_BENIGN...`

Pipeline menangani ini via helper `_ensure_phase8_dfs_from_exports()` dan menyimpan path terpakai ke:
- `metrics/phase8_loaded_paths.json`

**Metrics:**
- `metrics/phase8_modeling_summary.json`

---

## Phase 9 — `phase9_feature_selection`
**Lokasi:** `src/cbr/phases/phase9_fs.py`  
**Tujuan:** seleksi fitur pada **df_train** saja (menghindari leakage dari test).

Metode:
- Mutual Information (MI) ranking
- RFE (default estimator: RandomForestClassifier)
- PCA + StandardScaler (untuk feature-set “pca”)

**Output disk (artefak):**
- `models/phase9/phase9_mi_ranking_<tag>.csv`
- `models/phase9/phase9_rfe_ranking_<tag>.csv`
- `models/phase9/phase9_feature_sets_<tag>.json`
- `models/phase9/phase9_meta_<tag>.json`
- `models/phase9/phase9_pca_meta_<tag>.json`
- opsional (default OFF): `phase9_train_sample_<tag>_n....csv`

**Catatan:**
Secara default Phase 9 menghasilkan **artefak seleksi fitur**, bukan file dataset train/test baru yang sudah dipangkas kolomnya.

**Metrics:**
- `metrics/phase9_summary.json`

---

## Phase 10 — `phase10_train_and_evaluate`
**Lokasi:** `src/cbr/phases/phase10_train.py`  
**Tujuan:** training baseline model + evaluasi (CV + optional holdout).

**Model baseline:**
- KNN
- DecisionTree
- RandomForest

**CPU execution (scikit-learn)**

Phase 10 menggunakan scikit-learn, sehingga baseline training berjalan di CPU (bukan GPU). Performa dipengaruhi oleh:

- Jumlah core/thread CPU,

- Frekuensi (turbo/throttle),

- Konfigurasi paralelisme (n_jobs) dan thread numerik (BLAS/OpenMP).

**CPU yang digunakan (contoh perangkat uji): `13th Gen Intel(R) Core(TM) i9-13900K`**

- **24 cores** dan **32 logical processors** (threads).

- Nilai “Speed” di Task Manager bersifat dinamis (naik saat turbo, turun saat thermal/power limit).

- Karena itu, pipeline menyediakan kontrol untuk menjaga stabilitas suhu dan mencegah CPU throttle saat CV berjalan lama.

**Fitur Stabilitas dan Kontrol Mesin**
- **Thread limiting (BLAS/OpenMP = 1):** pipeline membatasi thread numerik ke 1 thread untuk menghindari oversubscription (misalnya `n_jobs` tinggi tetapi tiap worker juga membuat banyak thread BLAS/MKL/OpenBLAS). Dengan BLAS/OpenMP diset 1, paralelisme utama dikendalikan oleh n_jobs estimator sehingga pemakaian CPU lebih stabil dan prediktif.

  - Default: blas_thread_limit = 1

  - Dampak: mengurangi lonjakan thread ekstrem, menjaga suhu/CPU throttle lebih terkendali, dan biasanya membuat runtime CV lebih konsisten.

- **Parallelism via `n_jobs` (configurable):**

  - RandomForest memakai `n_jobs` = `rfc_n_jobs` (default: 16) untuk mempercepat training/evaluasi.

  - KNN memakai `n_jobs` = `knn_n_jobs` (default: 20) untuk mempercepat scoring/fit (tergantung implementasi sklearn yang dipakai).

  - Jika mesin terlalu panas / CPU 100% terus-menerus, turunkan `rfc_n_jobs` dan/atau `knn_n_jobs`.

- **Cooldown antar fold**: ada jeda antar fold CV untuk meredam spike resource dan membantu stabilitas (mengurangi risiko throttle/overheat).
**Output disk:**
- `models/phase10/results_comparison_<tag>.csv`
- `models/phase10/feature_importance_rfc_<tag>.csv`
- `models/phase10/feature_importance_dt_<tag>.csv`
- `models/phase10/phase10_summary_<tag>.json`

**Metrics:**
- `metrics/phase10_summary.json`

---

## Phase 11 — `phase11_advanced_evaluation`
**Lokasi:** `src/cbr/phases/phase11_advanced_eval.py`  
**Tujuan:** evaluasi lanjutan, terutama ROC/AUC dan artefak visual.

**Output disk:**
- `models/phase11/roc_curves_<tag>.png`
- `models/phase11/model_performance_comparison_<tag>.png`
- `models/phase11/confusion_matrix_best_model_<tag>.png`
- `models/phase11/roc_auc_summary_<tag>.json`
- `models/phase11/phase11_summary_<tag>.json`

**Metrics:**
- `metrics/phase11_summary.json`

---

## Report — PDF Generation
**Lokasi:** `src/scripts/generate_pdf/generate_pdf.py` + subfolder builder  
**Tujuan:** merangkum run dan artefak ke laporan PDF.

**Sumber data report:**
- `metrics/*.json` via `build_context(artifacts_dir)`
- file gambar dari `figures/`, `phase7/`, `models/phase11/`, dsb.
- optional: `df_clean/df_train/df_test/results_df` yang dipass dari pipeline

**Output disk:**
- default: `reports/preprocessing_report_<sample_size>_<run_id>-final.pdf`

**Metrics:**
- `metrics/report_summary.json`

---

## 6) Kontrak “Dataset Final”
Jika yang dimaksud **final dataset untuk eksperimen ML**, maka default-nya adalah output Phase 8:
- `exports/modeling/*__train.csv(.gz)`
- `exports/modeling/*__testFAIR.csv(.gz)`
- `exports/modeling/*__meta.json`

Phase 5 hanyalah export “preview/inspection”.  
Phase 9 adalah artefak seleksi fitur (tidak selalu export dataset baru).

---

## 7) Reproducibility
Hal yang mempengaruhi reproducibility:
- `cfg.seed` (default 42) untuk sampling/split
- `sample_size` dipakai sebagai **tag** penamaan artefak
- snapshot run dari main: `metrics/final_summary_main.json`
- meta split dari Phase 8: `exports/modeling/*__meta.json`

---

## 8) Debugging Cepat (Failure Modes yang umum)

### 8.1 Input file tidak ditemukan
Gejala: `Input file not found` dari main/pipeline.  
Solusi: set `--input-file` atau env `EVE_JSONL`.

### 8.2 Train/Test single-class (Phase 9/10 gagal)
Gejala: Phase 9 error “Target has only one class”.  
Cek: `metrics/phase8_modeling_summary.json` + `metrics/phase8_loaded_paths.json`  
Solusi: pastikan ada attack cukup (`model_min_attack_required`), benign sampling benar, dan concat _BENIGN berjalan.

### 8.3 Phase 7 corr kosong
Cek: `phase7/nan_issues_<tag>.json` dan `phase7/phase7_meta_<tag>.json`  
Solusi: pastikan sample punya dua kelas, dan cukup kolom numerik.

### 8.4 PDF gagal karena field ctx/summary kosong
Cek: `metrics/report_summary.json` dan file `metrics/phase*_summary.json`  
Solusi: pastikan phase summary ada dan formatnya sesuai yang dibaca report builder.

---

## 9) Catatan Maintainer: Menambah Fase Baru
Checklist:
1. Buat modul `src/cbr/phases/phaseX_*.py` dengan signature yang stabil.
2. Tambahkan pemanggilan di `src/cbr/pipeline.py`:
   - jalankan fase
   - simpan summary ke `metrics/phaseX_summary.json`
3. Jika perlu masuk PDF:
   - tambahkan builder di `src/scripts/generate_pdf/` dan panggil di `generate_pdf.py`.

<!-- ---

## 10) Catatan tentang “Export Dataset Setelah Feature Selection”
Jika kamu ingin “final dataset terolah” setelah Phase 9:
- MI/RFE → bisa ekspor subset kolom terpilih sebagai `train_FS` dan `test_FS`.
- PCA → ekspor dataset dalam ruang komponen (`PC1..PCk`) sebagai `train_PCA` dan `test_PCA`.

Ini tidak wajib untuk pipeline berjalan, tetapi membantu:
- memperjelas definisi “final dataset”,
- memudahkan eksperimen di luar pipeline (mis. training model lain). -->
