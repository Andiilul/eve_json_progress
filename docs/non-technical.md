# Dokumentasi — JSON Progress Pipeline (Suricata EVE JSON)

Terakhir diperbarui: **28 Februari 2026**  
Jenis dokumen: Fokus pada gambaran sistem, alur, keluaran, dan cara membaca hasil tanpa membahas implementasi kode.

---

## Ringkasan Cepat (1 menit)
**JSON Progress Pipeline** memproses **Suricata EVE JSON (JSONL)** skala besar menjadi:
- **dataset modeling siap ML** (train/test) dengan rasio kelas yang terkendali,
- **baseline model** untuk pembanding awal,
- serta **artefak** (metrics/plot/summary) dan **laporan PDF** untuk audit & pelaporan.

Pipeline ini dibuat untuk data besar: ia mengandalkan **staging berbasis disk (Parquet shards)** agar tidak memaksa semua data masuk RAM.

---

## Daftar Isi
1. [Tujuan Sistem dan Ruang Lingkup](#1-tujuan-sistem-dan-ruang-lingkup)  
2. [Istilah Penting](#2-istilah-penting-non-teknis)  
3. [Input Sistem](#3-input-sistem)  
4. [Output Sistem](#4-output-sistem-apa-saja-yang-dihasilkan)  
5. [Dataset: Mana yang “Siap Dipakai”](#5-dataset-mana-yang-siap-dipakai)  
6. [Alur Pipeline per Fase](#6-alur-pipeline-per-fase-non-teknis-namun-lebih-rinci)  
7. [Cara Menilai Run “Berhasil”](#7-cara-menilai-run-berhasil)  
8. [Batasan & Asumsi](#8-batasan--asumsi-non-teknis)  
9. [Privasi & Etika](#9-privasi--etika-saran-praktis)  
10. [Peta Cepat: Output untuk Kebutuhan Apa](#10-peta-cepat-output-apa-untuk-kebutuhan-apa)  
11. [Lampiran: Metrics yang Umum](#11-lampiran-metrics-yang-umum)  

---

## 1) Tujuan Sistem dan Ruang Lingkup

### 1.1 Tujuan utama
1. Mengubah log EVE JSON mentah menjadi dataset tabular yang **konsisten** dan **lebih siap dipakai** untuk eksperimen ML.
2. Menyediakan hasil yang **reproducible**: output run tersimpan rapi, ada ringkasan per fase, dan ada laporan PDF.
3. Menyediakan baseline yang masuk akal untuk riset/skripsi: **feature selection (opsional) + training + evaluasi**.

### 1.2 Yang “bukan” tujuan utama
- Bukan sistem deteksi real-time / integrasi SIEM.
- Bukan model “terbaik final” (bukan fokus SOTA); model yang disediakan adalah baseline.
- Bukan label ground-truth sempurna: label diturunkan dari sinyal alert Suricata (dengan aturan tertentu).

---

## 2) Istilah Penting
- **EVE JSON / JSONL**: format log Suricata; satu baris = satu event.
- **Attack vs Benign**: target klasifikasi (1 vs 0).
- **Staging dataset**: dataset perantara dari file mentah, biasanya disk-backed dan aman untuk skala besar.
- **Modeling dataset**: dataset train/test yang dipakai training ML.
- **Data leakage**: fitur yang “membocorkan jawaban target” (mis. fitur yang terlalu dekat dengan sinyal alert yang digunakan untuk membuat label).

---

## 3) Input Sistem

### 3.1 Input wajib
- **File log utama:** `*.jsonl` (Suricata EVE JSON Lines)

### 3.2 Input konfigurasi (parameter run)
Beberapa parameter penting (cukup dipahami konsepnya):
- **artifacts_dir**: folder keluaran utama (default umumnya `results/eve_json`, tapi bisa diubah).
- **sample_size**: “tag” untuk penamaan output/report (bukan batas scanning file).
- **max_lines**: batas baca untuk debug (opsional).
- **benign_ratio_to_attack** & **benign_reservoir_max**: mengatur seberapa banyak benign disimpan pada staging.
- **train ratio / pool benign per attack**: mengatur rasio benign pada dataset modeling.
- Toggle fase: bisa mematikan export/viz/corr/modeling/fs/train/eval/pdf.

---

## 4) Output Sistem (Apa saja yang dihasilkan)

Semua output dikumpulkan di bawah satu folder: **`artifacts_dir/`**.

> Default runner biasanya menulis ke: `results/eve_json` (tergantung argumen `--artifacts-dir`).

### 4.1 Struktur folder utama (ringkas)
```text
artifacts_dir/
├─ exports/
│  ├─ phase1_dataset/              # staging disk-backed (Parquet shards) — Phase 1
│  │  ├─ attacks/part-*.parquet
│  │  └─ benign/part-*.parquet
│  ├─ modeling/                    # dataset modeling train/test (+meta) — Phase 8
│  │  ├─ model_<tag>_...__train.csv(.gz)
│  │  ├─ model_<tag>_...__testFAIR.csv(.gz)
│  │  ├─ model_<tag>_...__meta.json
│  │  └─ (opsional) __pool / __stressBENIGN / pasangan _BENIGN*
│  └─ eve_processed_*              # export dataset hasil cleaning (Phase 5; opsional / sample)
├─ figures/                        # plot visualisasi — Phase 6
├─ metrics/                        # ringkasan JSON per fase + final summary
├─ phase7/                         # output korelasi + fitur berisiko/leakage — Phase 7
├─ models/
│  ├─ phase9/                      # artefak feature selection (ranking/feature sets) — Phase 9
│  ├─ phase10/                     # hasil training baseline — Phase 10
│  └─ phase11/                     # evaluasi lanjutan (ROC/AUC, dsb.) — Phase 11
├─ reports/                        # PDF report final
└─ checkpoints/                    # ruang untuk checkpoint/resume (jika dipakai)
```

### 4.2 Jenis output (dalam bahasa “hasil kerja”)
- **Dataset ekspor**:
  - staging dataset (attacks + benign tersampling) untuk skala besar,
  - modeling dataset siap ML (train/test; plus meta).
- **Artefak analitik**: ringkasan statistik per fase (JSON), korelasi, dan ringkasan evaluasi.
- **Gambar/plot**: visualisasi (korelasi, metrik, dsb., tergantung konfigurasi).
- **Hasil model baseline**: metrik + ringkasan hasil training/evaluasi.
- **Laporan PDF**: rangkuman run end-to-end dalam format mudah dibaca.

---

## 5) Dataset: Mana yang “Siap Dipakai”
Pipeline menghasilkan beberapa “level dataset”, masing-masing cocok untuk tujuan berbeda:

### 5.1 Staging dataset (Phase 1) — untuk skala besar & resume
- Lokasi: `exports/phase1_dataset/attacks/` dan `exports/phase1_dataset/benign/`
- Format: **Parquet shards**
- Isi: event yang sudah diringkas menjadi kolom tabular inti + label target.
- Cocok untuk:
  - eksperimen ulang (membangun split berkali-kali tanpa baca JSONL dari awal),
  - run skala besar (hemat RAM).

### 5.2 Processed export (Phase 5) — untuk inspeksi / sharing
- Lokasi: `exports/eve_processed_*`
- Umumnya berupa export sample agar ukuran tetap wajar.
- Cocok untuk:
  - mengecek preprocessing berjalan benar,
  - preview dataset hasil cleaning.

### 5.3 Modeling dataset (Phase 8) — dataset ML siap training ✅
- Lokasi: `exports/modeling/`
- Isi: file **train** dan **test** (plus `__meta.json`).
- Cocok untuk:
  - training baseline,
  - feature selection,
  - evaluasi.

> Catatan: Pada mode disk/staging besar, Phase 8 dapat menulis file attack/benign terpisah (mis. `__train.csv.gz` dan `__train_BENIGN.csv.gz`) karena alasan teknis penulisan file. Dataset ini kemudian dipakai/dirakit saat fase berikutnya berjalan (bergantung konfigurasi runner).

### 5.4 Apakah ada “dataset yang sudah ter-feature selection” (terpisah)?
**Secara default: tidak.**  
Fase feature selection menghasilkan **artefak** (ranking fitur, daftar fitur terpilih, metadata PCA/scaler), lalu artefak tersebut dipakai untuk training/evaluasi. Namun pipeline **tidak wajib mengekspor** file dataset train/test baru yang kolomnya sudah dipangkas hasil feature selection — kecuali kamu menambahkan/menyalakan export khusus untuk itu.

---

## 6) Alur Pipeline per Fase

### Phase 1 — Load & Label (HUGE-DATA SAFE)
**Tujuan:** membangun staging dataset berbasis disk.  
**Yang dilakukan:**
- Membaca file JSONL besar secara streaming.
- Membuat label **Target**: attack vs benign berdasarkan konteks alert Suricata (dengan pengecualian kategori false-positive tertentu).
- Menyimpan:
  - **ALL attacks**, dan
  - **benign tersampling** dengan kontrol rasio dan/atau hard-cap.
- Output utama: `exports/phase1_dataset/` (attacks & benign, Parquet shards).

**Catatan penting:** fase ini adalah fondasi run skala besar dan membuat pipeline bisa diulang tanpa membaca JSONL dari nol.

---

### Phase 2 — Feature Engineering (Encoding & Standarisasi Dasar)
**Tujuan:** membuat dataset lebih seragam untuk ML.  
**Yang dilakukan (konsep):**
- Memastikan kolom-kolom kunci tersedia dan konsisten.
- Mengubah nilai kategorikal/teks menjadi representasi numerik yang stabil.
- Menyimpan sebagian kolom raw untuk kebutuhan inspeksi/visualisasi.

---

### Phase 3 — Computed Features (Fitur Turunan)
**Tujuan:** menambah fitur turunan agar model punya sinyal yang lebih kaya.  
Contoh konsep:
- fitur interaksi,
- transformasi sederhana,
- pemilihan/penambahan fitur turunan sesuai kebutuhan.

---

### Phase 4 — Cleaning (Agresif namun Terkendali)
**Tujuan:** memastikan dataset siap dipakai untuk analisis/training.  
Yang dilakukan:
- perbaikan missing values,
- penyeragaman tipe data numerik,
- mengurangi risiko error pada tahap model/viz/corr.

---

### Phase 5 — Export Dataset (Opsional)
**Tujuan:** menghasilkan file dataset untuk inspeksi atau sharing.  
Catatan:
- Default sering berupa export sample agar ukuran tetap wajar.
- Ini bukan titik “dataset modeling train/test”, melainkan export dataset hasil cleaning (preview).

---

### Phase 6 — Visualisasi (Opsional)
**Tujuan:** memberi gambaran cepat tentang data & hubungan fitur.  
Output: gambar/plot di `figures/`.

---

### Phase 7 — Korelasi & Indikasi Leakage (Opsional)
**Tujuan:** mengukur keterkaitan fitur terhadap target dan menandai fitur “terlalu kuat” yang berisiko leakage.  
Output utama:
- tabel korelasi,
- daftar fitur yang disarankan untuk di-drop (bergantung hasil analisis),
- plot top-k korelasi.

---

### Phase 8 — Modeling Split (Train/Test) ✅
**Tujuan:** membangun dataset ML siap training.  
Yang dilakukan:
- Membentuk pool benign berbasis rasio terhadap attack (opsional).
- Split train/test (berbasis attack, lalu alokasi benign).
- Kontrol rasio benign di train (mis. 1:1 atau 1:3) agar training efektif.
- Menyimpan dataset train/test + meta.

Output utama: `exports/modeling/`.

---

### Phase 9 — Feature Selection (Opsional)
**Tujuan:** memilih fitur terbaik untuk baseline model (mengurangi dimensi dan noise).  
Output: artefak seleksi fitur di `models/phase9/`.

> Catatan penting: Secara default, fase ini menghasilkan daftar fitur/transformasi (artefak), **bukan** file dataset baru yang kolomnya sudah dipangkas, kecuali diekspor secara eksplisit.

---

### Phase 10 — Training Baseline Model (Opsional)
**Tujuan:** melatih model baseline dan menghasilkan ringkasan performa.  
Output: artefak training dan tabel hasil di `models/phase10/`.

---

### Phase 11 — Advanced Evaluation (Opsional)
**Tujuan:** evaluasi lanjutan (mis. ROC/AUC) dan artefak pendukung.  
Output: `models/phase11/`.

---

### Report — Generate PDF ✅
**Tujuan:** menggabungkan ringkasan run menjadi satu laporan PDF.  
Output default:
- `reports/preprocessing_report_<sample_size>_<run_id>-final.pdf`

---

## 7) Cara Menilai Run “Berhasil”
Checklist non-teknis:
1. Folder `metrics/` terisi ringkasan fase (minimal phase1–phase8 + report).
2. `exports/phase1_dataset/` ada dan berisi shard `attacks/` dan `benign/` (untuk mode full).
3. `exports/modeling/` berisi file train/test + `__meta.json`.
4. Jika phase9–phase11 aktif: folder `models/phase9`, `models/phase10`, `models/phase11` berisi artefak.
5. `reports/` berisi PDF final.

---

## 8) Batasan & Asumsi

### 8.1 Asumsi label (Target)
- Label **Target** bergantung pada sinyal **alert** Suricata.
- Jika ruleset/konfigurasi Suricata berbeda, distribusi label dan “makna attack” dapat berubah.

### 8.2 Risiko data leakage
- Karena label berasal dari alert, fitur yang “mewakili alert” bisa menjadi leakage.
- Pipeline menyediakan fase korelasi untuk membantu identifikasi; keputusan final drop-list ada pada peneliti.

### 8.3 Skala besar vs sampel analisis
- Beberapa fase analitik/visualisasi dapat bekerja pada sample agar performa stabil, sehingga hasilnya bersifat indikatif.
- Dataset modeling (train/test) tetap dibangun dari staging/pool sesuai konfigurasi.

### 8.4 Generalisasi hasil
- Model baseline bertujuan untuk pembanding awal, bukan klaim model terbaik.
- Hasil sangat bergantung pada dataset (periode capture, lingkungan jaringan, ruleset Suricata, dsb.).

### 8.5 Sensitivitas data
- Log dapat mengandung IP/port/flow identifier yang sensitif.
- Gunakan pengamanan data (masking, izin akses, kebijakan penyimpanan) sesuai kebutuhan institusi.

---

## 9) Privasi & Etika (Saran Praktis)
Jika dokumen/artefak akan dibagikan (mis. ke pembimbing):
- pertimbangkan masking IP/port pada contoh data,
- hindari mengunggah raw JSONL ke repo publik,
- simpan dataset besar di folder lokal (mis. `data/`) dan pastikan masuk `.gitignore`.

---

## 10) Peta Cepat: Output apa untuk kebutuhan apa?
- **Training ML sekarang** → `exports/modeling/*__train*` dan `exports/modeling/*__testFAIR*`
- **Resume run besar tanpa baca JSONL lagi** → `exports/phase1_dataset/`
- **Cek hasil cleaning cepat** → `exports/eve_processed_*` (Phase 5)
- **Laporan sekali klik** → PDF di `reports/`

---

## 11) Lampiran: Metrics yang Umum
Di `metrics/` biasanya ada (tergantung fase yang diaktifkan):
- `phase1_summary.json`
- `phase2_summary.json`
- `phase3_summary.json`
- `phase4_summary.json`
- `phase5_export_summary.json`
- `phase6_summary.json`
- `phase7_summary.json`
- `phase8_modeling_summary.json`
- `phase8_loaded_paths.json`
- `phase9_summary.json`
- `phase10_summary.json`
- `phase11_summary.json`
- `report_summary.json`
- `final_summary.json`
- (dari runner) `final_summary_main.json`
