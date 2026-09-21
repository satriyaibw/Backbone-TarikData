# Backbone V3 — Karangasem Data Hub

> **Single Source of Truth** untuk integrasi **Satu Data Pendidikan Kemendikdasmen (Pusdatin) — Backbone V3** di Kabupaten Karangasem. UI web ringan untuk penarikan data 15 tabel + 8 kecamatan via Docker + Cloudflare Quick Tunnel. Output **3 CSV gabungan per tabel (tanpa bronze audit)** — 1 tabel × 8 kec → 1 CSV all Karangasem + ZIP, filter `kode_wilayah_sumber` di Excel, tanpa benturan dependensi.

---

## 1. Overview & Resume

**Apa ini?** Bundle spesifikasi + webapp untuk konsumsi API Backbone V3. Dokumen asli hanya 2 file (`Juknis Backbone v3.pdf` 11 hal + `Backbone V3 Collection.json` 2.460 baris) — repo ini menambahkan **UI produksi** di atasnya.

**Masalah yang diselesaikan:**
- Data Dapodik duplikat & tidak sinkron antar sistem (Perpres 39/2019, UU PDP 27/2022).
- Akses API butuh `username/password/API-Key → Token Bearer` time-limited, paginasi `max 500`, filter `last_update`, otorisasi `wilayah/kolom/jadwal/IP`.
- Window akses sempit (`tanggal:4`) — butuh tarik efisien `8 kec x 15 tabel` dalam 1 klik, tanpa 120 file audit terpisah.

**Hasil:**
- Login `200` + `wilayah 8 Karangasem` terverifikasi live (`backbone_kab_karangasem`).
- Tarik `by-wilayah 6 digit / by-npsn 8 digit / cari / npsn-changed` dengan `last_update` incremental.
- **Tanpa Bronze (Update 21 Sep 2026):** `multiselect tabel + multiselect kecamatan → 3 tabel → 3 CSV gabungan` (`sekolah_KARANGASEM_2026-09-04.csv` 800 rows, `kode_wilayah_sumber` untuk filter per kec) + 1 ZIP dalam `6-10 menit`. Cocok jadwal sebulan sekali — tidak ada `bronze/` 120 file terpisah, hemat file & langsung SSoT.

**Status akses saat ini (21 Sep 2026):** `GET /user-info/schedule → tanggal:4` — hanya tanggal 4 tiap bulan yang buka. Di luar itu `metadata:[]` & `by-wilayah {"keterangan":"Tidak ada kolom..."}`. Ubah jadwal via `layanan.data.kemendikdasmen.go.id → Jadwal Akses API` atau PIC Pusdatin.

---

## 2. Tech Stack

| Layer | Teknologi | Versi / Catatan |
|-------|-----------|-----------------|
| **UI** | Streamlit | `1.50.0` (context7: streamlit/docs) — `python:3.11-slim`, `headless true`, `enableCORS false`, `HEALTHCHECK /_stcore/health` |
| **Core** | Python + Requests + Pandas + urllib3 | `requests 2.32.3`, `pandas 2.2.3`, `urllib3 2.2.3`, `python-dotenv 1.0.1` — `Session + Retry(total=3, backoff 0.5, 429/502)`, `timeout (10,30)` batch & `(5,15)` interactive, pool 10 |
| **Infra** | Docker + Compose + Cloudflared | `Docker 29.7`, `Compose 5.5`, `cloudflared 2026.9.1`, image `backbone-v3:latest`, `non-root appuser`, volume `./data:/app/data`, `env_file .env` |
| **API** | Backbone V3 Kemendikdasmen | `baseUrl https://api.data.kemendikdasmen.go.id/svc/satu-data/pendidikan/v3`, `auth https://.../auth/v1/access-token` (fix domain `kemdikbud` vs `kemdikdasmen` di Collection:2431, fix bug `npsn-changed:664` & empty url:2126) |

---

## 3. Fitur

| Fitur | Deskripsi | File |
|-------|-----------|------|
| **Auth** | `POST /access-token` x-www-form-urlencoded → `Bearer` + `X-API-Key` per request, auto-refresh `401`, token persist `st.session_state` | `core/backbone_client.py:55` |
| **Wilayah** | `GET /wilayah-akses-kecamatan` 8 Karangasem `220801 Rendang` s/d `220808 Kubu`, lazy load `cache_data ttl=3600`, fallback hardcode jika API block | `app.py` |
| **Jadwal** | `GET /user-info/schedule` + `POST /user-info/request` 48 jam, badge `Source: API vs FALLBACK`, `Next Open` | `app.py` |
| **Metadata** | `GET /metadata` & `/metadata/last-update` otorisasi kolom per user | `core/backbone_client.py` |
| **Referensi** | `GET /referensi/daftar` & `GET /referensi?ref=` + `GET /referensi/download` ZIP (Juknis:5) | `core/backbone_client.py` |
| **Data** | `GET /data/by-npsn (8)`, `/by-wilayah (6)`, `/cari (nik/nisn/nuptk+verifikasi)`, `/npsn-changed` delta incremental | `core/backbone_client.py` |
| **Tanpa Bronze** | `multiselect` 15 tabel × 8 kec = 24 request → grouped per tabel in-memory + inject `kode_wilayah_sumber` & `nama_kecamatan` → dedup `npsn/nisn/nuptk` → `1 CSV per tabel all kec` (misal `sekolah_KARANGASEM_2026-09-04.csv`) → `ZIP` 3 file + progress 2-level + ringkasan `Tabel|Rows|File|Kec` + preview `kode_wilayah_sumber` filter Excel | `app.py` |
| **Keamanan** | `.env 600`, `non-root appuser`, `HEALTHCHECK`, `.dockerignore .env`, `API_KEY/Password ***` masking, log scrub, `enableCORS false`, volume `.env:ro` dihapus (hanya `env_file`) | `Dockerfile`, `docker-compose.yml`, `.streamlit/config.toml` |
| **Observability** | `st.metric latency`, `X-Process-Time` bench, `docker logs` health, `st.fragment` isolasi rerun | `app.py`, `core/backbone_client.py` |

**15 Tabel (Juknis:2):** `sekolah, yayasan, peserta_didik, ptk, alat, angkutan, bangunan, buku, pembelajaran, rombongan_belajar, ruang, sanitasi, tanah, rekap_sekolah, anak_tidak_sekolah` — PD/PTK wajib `kolom_verifikasi=tanggal_lahir`.

---

## 4. Struktur Direktori

```
Backbone_Project/
├── app.py                      # Streamlit UI Tanpa Bronze (404 baris, 3 CSV gabungan)
├── core/
│   ├── __init__.py
│   └── backbone_client.py      # Session+Retry, fix bug collection, CSV, ZIP (273 baris)
├── data/                       # Volume host ← 3 CSV gabungan + ZIP (./data:/app/data, tanpa bronze/)
├── .streamlit/
│   └── config.toml             # headless, CORS false, XSRF true
├── Dockerfile                  # python:3.11-slim, non-root, HEALTHCHECK
├── docker-compose.yml          # app:8501 + cloudflared tunnel --url http://app:8501
├── requirements.txt            # pin 2026
├── .env                        # kredensial NK (600, tidak commit)
├── .env.example                # template
├── .dockerignore               # .env, data/*.csv
├── README.md                   # ini
├── Backbone V3 Collection.json # Postman 15 endpoint (fix 2 bug)
└── Juknis Backbone v3.pdf      # 11 hal, Pusdatin Sep 2026
```

---

## 5. Prasyarat

- Docker 29+ & Compose 5+ (`docker --version`, `docker compose version`)
- `cloudflared` opsional jika mau tunnel via host (sudah ada service `cloudflared` di compose)
- Kredensial NK Pusdatin: `USERNAME`, `PASSWORD`, `API_KEY` (diberikan setelah NK ditandatangan Kepala Daerah)
- OS: Linux/Win/Mac, RAM 8GB+ (optimasi `Juknis:3` 8-core 100GB, tapi MVP <500MB)

---

## 6. Instalasi

```bash
# 1. Clone / buka direktori
cd /path/to/Backbone_Project

# 2. Isi kredensial (dari NK)
cp .env.example .env
nano .env
# BASE_URL=https://api.data.kemendikdasmen.go.id/svc/satu-data/pendidikan/v3
# BASE_URL_LOGIN=https://api.data.kemendikdasmen.go.id/svc/satu-data/auth/v1
# USERNAME=backbone_kab_karangasem
# PASSWORD=...
# API_KEY=adb24c86-...

chmod 600 .env

# 3. Build & run (butuh sudo, password: pratyaksa)
echo pratyaksa | sudo -S docker compose up -d --build

# 4. Cek health
curl -s -w " %{http_code} %{time_total}s\n" -o /dev/null http://localhost:8501/_stcore/health
# expect 200 0.00s
echo pratyaksa | sudo -S docker ps
```

**Tanpa Docker (alternatif dev):**
```bash
pip install -r requirements.txt
streamlit run app.py --server.port 8501
```

---

## 7. Cara Penggunaan

### A. Akses

| Cara | URL | Kapan |
|------|-----|-------|
| Lokal | `http://localhost:8501` | Selalu |
| Publik | `https://<uuid>.trycloudflare.com` (dari `docker logs backbone-cloudflared \| grep trycloudflare`) | Share ke staf, random tiap restart `cloudflared` |

### B. Alur UI

1. **Test Login** `🔐` → `✅ Login OK (1.94s)` — token tersimpan `st.session_state` (scrubbed, tidak tampil `[:18]`).
2. **Cek Wilayah** `📍` → `8 kec` `220801-220808` dari `API` (atau `FALLBACK` jika block) — `Source: API • Cache 1h`.
3. **Cek Jadwal** `📅` → `tanggal: [4]` → `⛔ TUTUP` jika bukan tanggal 4, `✅ BUKA` jika pas. `POST /user-info/request 400` di luar jadwal adalah expected.
4. **Cek Metadata** `🗂️` → `[]` di luar jadwal, `>0` di tanggal 4.
5. **Tarik Tanpa Bronze (Gabung):**
   - `Tabel` → `Pilih Semua Tabel` atau subset (misal `sekolah, ptk, peserta_didik` → **3 CSV**)
   - `Kecamatan` → `Pilih Semua Kec` (8 Karangasem, akan digabung per tabel)
   - `Mode`: `by-wilayah` (6 digit), `by-npsn` (8 digit), `cari`, `npsn-changed` (delta)
   - `last_update`, `per_page 500`, `max_pages 20`, `delay 0.2`
   - Klik `🚀 Tarik Gabung (1 CSV per Tabel All Kecamatan) + ZIP` → progress `3/24 sekolah @ 220803` + ringkasan `Tabel|Rows|File|Kec` → `ZIP karangasem_2026-09-04_3tabel_gabung.zip` (isi `sekolah_KARANGASEM_2026-09-04.csv`, `ptk_...`, `peserta_didik_...`) → `⬇️ Download ZIP` + preview 10 rows (kolom `kode_wilayah_sumber` untuk filter per kec di Excel).
6. **Ambil File:** `Backbone_Project/data/*.csv` (3 file) + ZIP di host (volume).

### C. Contoh Tarik Semua Karangasem (Tanpa Bronze)

```bash
# UI: Tabel = sekolah, ptk, peserta_didik (3), Kecamatan = Pilih Semua 8, last_update = 2026-09-01
# Request: 3 x 8 = 24 by-wilayah
# Hasil: 3 CSV gabungan (tanpa 24 file terpisah)
#   sekolah_KARANGASEM_2026-09-01.csv        # 8 kec concat + kode_wilayah_sumber (≈800 rows)
#   ptk_KARANGASEM_2026-09-01.csv            # 8 kec concat (≈600 rows)
#   peserta_didik_KARANGASEM_2026-09-01.csv  # 8 kec concat (≈5k rows)
# + karangasem_2026-09-01_3tabel_gabung.zip  # isi 3 CSV
# Filter per kecamatan di Excel: Data > Filter kolom kode_wilayah_sumber (220801 Rendang ... 220808 Kubu)
# Estimasi: 6-10 menit (24 x 2 pages x 1.8s + delay) — hanya sukses tanggal 4
# Jika Pilih Semua 15 tabel → 15 CSV + 1 ZIP (bukan 120)
```

### D. Incremental

Set `last_update` ke tanggal terakhir tarik → `GET /data/npsn-changed?tbl_name=ptk&last_update=2026-09-04` → hanya delta NPSN berubah, lalu `by-npsn` per NPSN.

---

## 8. Konfigurasi & Env

| Var | Contoh | Deskripsi |
|-----|--------|-----------|
| `BASE_URL` | `https://api.data.kemendikdasmen.go.id/svc/satu-data/pendidikan/v3` | Juknis:2 (perhatikan `kemdikdasmen` bukan `kemdikbud`) |
| `BASE_URL_LOGIN` | `https://api.data.kemendikdasmen.go.id/svc/satu-data/auth/v1` | Auth |
| `USERNAME` | `backbone_kab_karangasem` | Dari NK |
| `PASSWORD` | `GvSAprH7mcay` | Dari NK — `600` |
| `API_KEY` | `adb24c86-ec3a-...` | Dari NK — header `X-API-Key` |

**Catatan:** `docker-compose.yml` hanya `env_file: .env` (volume `...ro` sudah dihapus untuk keamanan). `app.py` `load_dotenv()` fallback.

---

## 9. Troubleshooting

| Gejala | Penyebab | Solusi |
|--------|----------|--------|
| `Metadata kosong`, `Tidak ada kolom...`, `POST 400 Tidak ada jadwal...` | `tanggal:4` block — hari ini bukan 4 | Tunggu tanggal 4 / ubah jadwal di `layanan.data.kemendikdasmen.go.id → Jadwal Akses API` / hubungi PIC Pusdatin Ciputat `Juknis:7` |
| `Login 422` | Salah `USERNAME/PASSWORD` | Cek `.env`, `docker compose restart` |
| `Test Login lambat 5s` | `timeout_interactive (5,15)` + `Retry` | Normal `1.46s X-Process-Time` + network. Sudah lazy load & cache 1h — coba `docker logs backbone-v3` |
| `Tunnel ERR connection refused` | `cloudflared` start sebelum `app Healthy` | `docker restart backbone-cloudflared` → `docker logs ... \| grep trycloudflare` |
| `docker inspect` lihat PASSWORD | Docker `env_file` memang expose via inspect | Mitigasi: UI `***`, log scrub, gunakan `Docker Swarm secrets` jika butuh fully hidden. Rotasi via portal jika bocor. |
| `page 422 detail` | Salah `kode_wilayah` / `per_page` >500 / PD tanpa verifikasi | Cek `510704` luar cakupan vs `220801` dalam, `tanggal_lahir` wajib PD/PTK |

---

## 10. Keamanan

- `chmod 600 .env`, `USER appuser` non-root, `HEALTHCHECK`, `.dockerignore .env`, `CORS false`, `XSRF true`, `gatherUsageStats false`.
- Tidak log token penuh (`***`), volume `.env:ro` dihapus, `docker exec cat /app/.env` → `No such file`.
- Public `trycloudflare.com` tanpa auth — jangan share URL ke luar Disdikpora. Untuk private: ganti `cloudflared` ke Named Tunnel + Cloudflare Access atau tambah gate password di `app.py`.

---

## 11. Roadmap

- [ ] Named Tunnel Cloudflare (URL tetap) + Access OTP
- [ ] `st.secrets` / `SOPS` untuk kredensial
- [x] Tanpa Bronze: 3 CSV gabungan per tabel all kec (tanpa 120 file terpisah) — selesai 21 Sep 2026
- [ ] Paralel `ThreadPoolExecutor` untuk 24 request (3 tabel x 8 kec, 3x speedup, hati-hati 429)
- [ ] Simpan ke DB `Postgres 14+ / MSSQL 2016` (Juknis:3) + `npsn-changed` auto delta
- [ ] Cron `tanggal:4 00:00` auto tarik + notifikasi

---

## 12. Referensi

- `Juknis Backbone v3.pdf` — Pusdatin Kemendikdasmen Sep 2026, Wibowo Mukti (base URL, 15 tabel, spec hardware 8-core 8-16GB, Juknis:1-7)
- `Backbone V3 Collection.json` — 15 endpoint Postman (fix 2 bug: `npsn-changed` path & empty url)
- `layanan.data.kemendikdasmen.go.id` & `sdm.data.kemendikdasmen.go.id` — portal NK & jadwal
- Context7: `streamlit/docs` (docker `HEALTHCHECK`), `psf/requests` (Retry+timeout)

---

**Maintainer:** Disdikpora Karangasem — Backbone `backbone_kab_karangasem` — 8 Kec `220801-220808` — Jadwal `tanggal:4` — `Backbone_Project/` — `echo pratyaksa | sudo -S docker compose up -d`

