# Overview — JSON Progress Pipeline (Suricata EVE JSON)

## A. Judul Proyek & Tagline
**JSON Progress Pipeline** — Mengubah log **Suricata EVE JSON** skala besar menjadi **dataset ML siap pakai** + **baseline model** + **laporan PDF**.

---

## B. Ringkasan Proyek
Proyek ini adalah sistem pipeline yang memproses file **Suricata EVE JSON (JSON Lines / JSONL)** dalam skala besar untuk membangun dataset pembelajaran mesin (ML) yang dapat dipakai untuk eksperimen **deteksi traffic berbahaya/serangan**.

Pipeline mencakup: pembacaan data mentah, pemilahan record yang relevan, pelabelan **attack vs benign**, pembersihan data, rekayasa fitur, pemeriksaan korelasi (termasuk indikasi **data leakage**), pembentukan dataset modeling **train/test**, seleksi fitur (opsional), pelatihan model baseline, evaluasi, serta pembuatan artefak hasil (metrics, plot, ekspor dataset) dan **laporan PDF**.

---

## C. Untuk Siapa Sistem Ini
- **Mahasiswa/peneliti** yang ingin membangun dataset dari EVE JSON untuk eksperimen ML (mis. skripsi/riset).
- **Pengembang** yang membutuhkan pipeline end-to-end dari **raw log → dataset → model baseline → laporan**.
- **Operator/analyst** yang ingin menjalankan preprocessing data besar dengan jejak artefak yang jelas (hasil bisa diaudit lewat **metrics** dan **report**).

---

## D. Input dan Output

### Input
- **File log utama:** `*.jsonl` (Suricata EVE JSON Lines)
- **Konfigurasi run:** parameter (mis. sample size, lokasi output, rasio benign vs attack, split train/test, dan opsi fase)

### Output
- **Dataset ekspor**
  - dataset staging (attacks + benign tersampling) untuk skala besar
  - dataset modeling siap ML (pool/train/test)
- **Artefak analitik:** ringkasan statistik per fase (JSON), tabel korelasi, daftar fitur berisiko/leakage, dan ringkasan evaluasi
- **Gambar/plot:** visualisasi korelasi dan hasil evaluasi (tergantung konfigurasi)
- **Hasil model baseline:** metrik evaluasi dan ringkasannya
- **Laporan PDF:** rangkuman run end-to-end dalam format yang mudah dibaca

> Catatan: Secara umum, semua output dikumpulkan di folder `results/...` (nama folder/struktur dapat berbeda tergantung konfigurasi `artifacts_dir`).

---

## E. Gambaran Alur Kerja (Big Picture Workflow)
Secara konsep, pipeline bekerja seperti “jalur produksi”:

1. Membaca **EVE JSONL** (skala besar).
2. **Staging & pelabelan:** membedakan record **attack vs benign** berdasarkan sinyal alert Suricata, sambil mengontrol volume benign agar tidak meledakkan ukuran data.
3. **Rekayasa fitur:** membentuk fitur numerik/kategorikal agar lebih siap untuk ML.
4. **Pembersihan & standarisasi:** merapikan missing value, tipe data, dan konsistensi kolom.
5. **Analisis korelasi:** mengukur hubungan fitur terhadap target; menandai fitur yang berpotensi **leakage**.
6. **Membangun dataset modeling:** membentuk pool (opsional), lalu split **train/test** dengan rasio tertentu.
7. **Seleksi fitur (opsional):** memilih subset fitur terbaik atau transformasi (mis. MI/RFE/PCA) untuk eksperimen.
8. **Training model baseline:** menjalankan classifier baseline (mis. KNN / RandomForest / DecisionTree) sebagai pembanding awal.
9. **Evaluasi & ringkasan:** menghasilkan metrik dan artefak evaluasi.
10. **Generate laporan PDF:** menggabungkan hasil penting menjadi dokumentasi run.

---

## F. Konsep Kunci yang Perlu Dipahami

### 1) Pelabelan “Attack vs Benign”
Label target dibuat dari konteks event Suricata (terutama **alert**). Sistem juga memiliki mekanisme untuk mengurangi “noise” dari kategori alert tertentu yang berpotensi sering menjadi false-positive (sesuai konfigurasi).

### 2) Ketidakseimbangan Data (Imbalance)
Traffic benign biasanya jauh lebih banyak daripada attack. Pipeline mengatasi ini dengan:
- mengontrol sampling benign pada tahap staging, dan
- mengatur rasio train/test agar training tetap “belajar” tanpa tenggelam oleh benign.

### 3) Risiko Data Leakage
Karena label dibuat dari sinyal alert, sebagian fitur bisa “membocorkan jawaban” (contoh: kolom yang secara langsung merepresentasikan alert). Pipeline punya tahap korelasi untuk mendeteksi dan membantu menandai fitur semacam ini agar evaluasi lebih realistis.

### 4) Aman untuk Data Besar
Pipeline dirancang agar tidak memaksa seluruh data berada di RAM. Pendekatannya cenderung:
- menulis hasil intermediate ke disk (shard/export),
- memproses bertahap, dan
- menjaga workflow tetap stabil pada mesin lokal.

---

## G. Deliverables yang Menandakan Run Berhasil
Run yang “sehat” biasanya menghasilkan:
- folder artefak berisi **metrics JSON** per fase,
- ekspor dataset untuk modeling (**pool/train/test**, sesuai konfigurasi),
- output seleksi fitur dan evaluasi model baseline,
- **PDF report** yang merangkum proses dan hasil.


