"""
Backbone V3 - Streamlit UI Opsi B Tanpa Bronze: 3 CSV per Tabel All Kecamatan
Best practice: lazy wilayah, cache_resource, token persist, masking
"""
import os
import time
import zipfile
from pathlib import Path
from datetime import date, timedelta

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from core.backbone_client import BackboneClient

load_dotenv()

st.set_page_config(page_title="Backbone V3 - Penarikan Data", layout="wide", page_icon="📚")

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

BASE_URL = os.getenv("BASE_URL", "https://api.data.kemendikdasmen.go.id/svc/satu-data/pendidikan/v3")
BASE_URL_LOGIN = os.getenv("BASE_URL_LOGIN", "https://api.data.kemendikdasmen.go.id/svc/satu-data/auth/v1")
USERNAME = os.getenv("USERNAME", "")
PASSWORD = os.getenv("PASSWORD", "")
API_KEY = os.getenv("API_KEY", "")

TABEL_OPTIONS = [
    "sekolah", "yayasan", "peserta_didik", "ptk", "alat", "angkutan", "bangunan",
    "buku", "pembelajaran", "rombongan_belajar", "ruang", "sanitasi", "tanah",
    "rekap_sekolah", "anak_tidak_sekolah",
]

FALLBACK_WILAYAH = [
    "220801 - Kec. Rendang", "220802 - Kec. Sidemen", "220803 - Kec. Manggis",
    "220804 - Kec. Karangasem", "220805 - Kec. Abang", "220806 - Kec. Bebandem",
    "220807 - Kec. Selat", "220808 - Kec. Kubu",
]
FALLBACK_MAP = {label: label.split(" - ")[0] for label in FALLBACK_WILAYAH}
# Reverse for nama
CODE_TO_NAMA = {v: k.split(" - ")[1] if " - " in k else "" for k,v in FALLBACK_MAP.items()}

st.title("📚 Backbone V3 — Penarikan Data Pendidikan")
st.caption("Tanpa Bronze • 3 CSV per Tabel All Kecamatan • Gabung + Filter Excel • 8 Kec Karangasem")

with st.sidebar:
    st.header("⚙️ Konfigurasi")
    st.text_input("BASE_URL", value=BASE_URL, disabled=True)
    st.text_input("BASE_URL_LOGIN", value=BASE_URL_LOGIN, disabled=True)
    st.text_input("USERNAME", value="***" if USERNAME else "(kosong)", disabled=True)
    st.text_input("API_KEY", value="***" if API_KEY else "(kosong)", disabled=True)
    st.caption("Jadwal: tanggal 4 • Output: 1 CSV per tabel all kec (filter kode_wilayah_sumber di Excel)")
    st.divider()
    st.markdown("**Public Tunnel:** `cloudflared tunnel --url http://localhost:8501`")

@st.cache_resource(show_spinner=False)
def get_client_cached():
    return BackboneClient(BASE_URL, BASE_URL_LOGIN, USERNAME, PASSWORD, API_KEY)

def get_client():
    if not USERNAME or not PASSWORD or not API_KEY:
        st.error("Kredensial belum lengkap di .env")
        st.stop()
    c = get_client_cached()
    if "bb_token" in st.session_state and st.session_state.bb_token:
        c.token = st.session_state.bb_token
    return c

def save_token_to_session(token: str):
    st.session_state.bb_token = token

@st.cache_data(ttl=3600, show_spinner=False)
def load_wilayah_cached(cache_key: str):
    c = get_client()
    try:
        data = c.get_wilayah_akses(interactive=True)
        opts, mp = [], {}
        for w in data:
            kode = w.get("kode_wilayah","").strip()
            nama = w.get("nama","").strip()
            if not kode:
                continue
            label = f"{kode} - {nama}" if nama else kode
            opts.append(label)
            mp[label] = kode
        if opts:
            return opts, mp, "API"
    except Exception:
        pass
    return FALLBACK_WILAYAH, FALLBACK_MAP, "FALLBACK"

@st.fragment
def status_buttons():
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("🔐 Test Login", use_container_width=True):
            t0=time.perf_counter()
            try:
                c=get_client()
                res=c.login(interactive=True)
                save_token_to_session(res.get("access_token",""))
                dt=time.perf_counter()-t0
                st.success(f"✅ Login OK ({dt:.2f}s)")
                st.metric("Login", f"{dt:.2f}s")
            except Exception as e:
                dt=time.perf_counter()-t0
                st.error(f"Gagal ({dt:.2f}s): {e}")
    with col2:
        if st.button("📍 Cek Wilayah", use_container_width=True):
            t0=time.perf_counter()
            try:
                opts, mp, src = load_wilayah_cached(USERNAME)
                dt=time.perf_counter()-t0
                st.success(f"✅ {len(opts)} kec dari {src} ({dt:.2f}s)")
                st.json([{"label":k,"kode":v} for k,v in list(mp.items())[:5]])
                st.metric("Wilayah", f"{dt:.2f}s")
            except Exception as e:
                dt=time.perf_counter()-t0
                st.error(f"Gagal ({dt:.2f}s): {e}")
    with col3:
        if st.button("📅 Cek Jadwal", use_container_width=True):
            t0=time.perf_counter()
            try:
                c=get_client()
                sch=c.get_user_schedule(page=1, per_page=100, interactive=True)
                dt=time.perf_counter()-t0
                tgls=[d.get("tanggal") for d in sch.get("data",[])]
                if tgls:
                    st.info(f"Jadwal: {tgls} ({dt:.2f}s)")
                    st.success("✅ Hari ini BUKA" if date.today().day in tgls else f"⛔ TUTUP — buka {tgls}")
                else:
                    st.warning(f"Tidak ada jadwal ({dt:.2f}s)")
                st.json(sch)
            except Exception as e:
                dt=time.perf_counter()-t0
                st.error(f"Gagal ({dt:.2f}s): {e}")
    with col4:
        if st.button("🗂️ Cek Metadata", use_container_width=True):
            t0=time.perf_counter()
            try:
                c=get_client()
                meta=c.get_metadata(interactive=True)
                dt=time.perf_counter()-t0
                if meta:
                    st.dataframe(pd.DataFrame(meta[:20]), use_container_width=True)
                else:
                    st.warning(f"Metadata kosong ({dt:.2f}s) — jadwal block?")
            except Exception as e:
                dt=time.perf_counter()-t0
                st.error(f"Gagal ({dt:.2f}s): {e}")

status_buttons()
st.divider()
st.subheader("📥 Penarikan Data — Tanpa Bronze (3 CSV)")

with st.spinner("Memuat wilayah..."):
    try:
        wilayah_options, wilayah_map, wilayah_src = load_wilayah_cached(USERNAME or "fallback")
    except Exception:
        wilayah_options, wilayah_map, wilayah_src = FALLBACK_WILAYAH, FALLBACK_MAP, "FALLBACK"
st.caption(f"Wilayah source: **{wilayah_src}** • {len(wilayah_options)} kec • Cache 1 jam")

if "tbl_selected" not in st.session_state:
    st.session_state.tbl_selected=["sekolah"]
if "wil_selected" not in st.session_state:
    st.session_state.wil_selected=wilayah_options

with st.form("tarik_form_b"):
    c1,c2=st.columns(2)
    with c1:
        col_a,col_b=st.columns([3,1])
        with col_a:
            tbls=st.multiselect("Tabel (bisa pilih banyak, hasil 1 CSV per tabel)", TABEL_OPTIONS, default=st.session_state.tbl_selected, key="tbl_mult")
        with col_b:
            st.write(""); st.write("")
            pilih_semua_tbl=st.checkbox("Pilih Semua Tabel")
        if pilih_semua_tbl:
            tbls=TABEL_OPTIONS
        mode=st.radio("Mode", ["by-wilayah (6 digit)", "by-npsn (8 digit)", "cari (individu)", "npsn-changed (delta)"], index=0)
    with c2:
        if mode.startswith("by-wilayah"):
            col_c,col_d=st.columns([3,1])
            with col_c:
                wils=st.multiselect("Kecamatan (akan digabung per tabel)", wilayah_options, default=st.session_state.wil_selected, key="wil_mult")
            with col_d:
                st.write(""); st.write("")
                pilih_semua_wil=st.checkbox("Pilih Semua Kec")
            if locals().get("pilih_semua_wil"):
                wils=wilayah_options
        else:
            wils=[]
            st.info("Mode bukan by-wilayah")
        last_update=st.date_input("last_update", value=date.today()-timedelta(days=7))
        per_page=st.slider("per_page",50,500,500)
    npsn=""
    if mode.startswith("by-npsn"):
        npsn=st.text_input("NPSN (8 digit)", placeholder="50100275")
    with st.expander("Field cari/npsn-changed (PD/PTK)"):
        cc1,cc2=st.columns(2)
        with cc1:
            kolom_induk=st.selectbox("kolom_induk",["","npsn","nbpn","nisn","nik","nuptk","nip"], index=0)
            nomor_induk=st.text_input("nomor_induk")
        with cc2:
            kolom_verifikasi=st.selectbox("kolom_verifikasi",["","tanggal_lahir"], index=0)
            nilai_verifikasi=st.text_input("nilai_verifikasi (YYYY-MM-DD)")
    c3,c4=st.columns(2)
    with c3:
        max_pages=st.slider("max_pages per kombinasi",1,200,20)
    with c4:
        delay=st.slider("delay antar page",0.0,1.0,0.2, step=0.1)
    submitted=st.form_submit_button("🚀 Tarik Gabung (1 CSV per Tabel All Kecamatan) + ZIP", use_container_width=True, type="primary")
    if submitted:
        if mode.startswith("by-wilayah") and not wils:
            st.error("Pilih minimal 1 kecamatan"); st.stop()
        if not tbls:
            st.error("Pilih minimal 1 tabel"); st.stop()
        if mode.startswith("by-npsn") and (not npsn or len(npsn)!=8):
            st.error("NPSN 8 digit"); st.stop()
        st.session_state.tbl_selected=tbls
        if wils:
            st.session_state.wil_selected=wils

if 'submitted' in locals() and submitted:
    client=get_client()
    if client.token:
        save_token_to_session(client.token)
    last_update_str=last_update.strftime("%Y-%m-%d") if last_update else None

    if mode.startswith("by-wilayah"):
        combos=[(tbl, wilayah_map.get(label, label.split(" - ")[0].strip())) for tbl in tbls for label in wils]
        total_combos=len(combos)
        st.info(f"🔄 Akan tarik {len(tbls)} tabel x {len(wils)} kec = {total_combos} request → **{len(tbls)} CSV gabungan** (tanpa bronze)")
    elif mode.startswith("by-npsn"):
        combos=[(tbl, npsn) for tbl in tbls]
        total_combos=len(combos)
    else:
        combos=[(tbl,"cari") for tbl in tbls]
        total_combos=len(combos)

    overall_progress=st.progress(0, text="Memulai...")
    current_text=st.empty()
    log_area=st.empty()
    t_start=time.perf_counter()

    # Grouped per tabel (tanpa bronze)
    grouped={tbl: [] for tbl in tbls}
    combo_summary=[]
    total_rows_all=0

    try:
        for idx,(tbl,kode) in enumerate(combos, start=1):
            current_text.markdown(f"**{idx}/{total_combos}: `{tbl}` @ `{kode}`**")
            overall_progress.progress((idx-1)/total_combos, text=f"{idx}/{total_combos} {tbl} @ {kode}")
            rows=[]; err_msg=""; t_combo=time.perf_counter()
            try:
                if mode.startswith("by-wilayah"):
                    for page in range(1, max_pages+1):
                        try:
                            res=client.fetch_by_wilayah(kode, tbl, page=page, per_page=per_page, last_update=last_update_str)
                        except ValueError as e:
                            err_msg=str(e)[:300]; break
                        chunk=[]
                        if isinstance(res, dict):
                            for k in ("data","result","items","rows"):
                                if k in res and isinstance(res[k], list):
                                    chunk=res[k]; break
                            else:
                                if "data" in res and isinstance(res["data"], list) and res["data"] and isinstance(res["data"][0], dict) and "keterangan" in res["data"][0]:
                                    err_msg=res["data"][0]["keterangan"]; break
                        elif isinstance(res,list):
                            chunk=res
                        if not chunk: break
                        if chunk and isinstance(chunk[0], dict) and "keterangan" in chunk[0] and len(chunk)==1:
                            err_msg=chunk[0]["keterangan"]; rows=[]; break
                        # Inject kode_wilayah untuk filter Excel
                        for r in chunk:
                            if isinstance(r, dict):
                                r["kode_wilayah_sumber"]=kode
                                r["nama_kecamatan"]=CODE_TO_NAMA.get(kode,"")
                        rows.extend(chunk)
                        if len(chunk)<per_page: break
                        if delay>0: time.sleep(delay)
                elif mode.startswith("by-npsn"):
                    for page in range(1, max_pages+1):
                        try:
                            res=client.fetch_by_npsn(kode, tbl, page=page, per_page=per_page, last_update=last_update_str)
                        except ValueError as e:
                            err_msg=str(e)[:300]; break
                        chunk=[]
                        if isinstance(res, dict):
                            for k in ("data","result","items"):
                                if k in res and isinstance(res[k], list):
                                    chunk=res[k]; break
                        elif isinstance(res,list):
                            chunk=res
                        if not chunk or (chunk and isinstance(chunk[0], dict) and "keterangan" in chunk[0]):
                            if chunk: err_msg=chunk[0].get("keterangan",""); break
                        for r in chunk if isinstance(chunk,list) else [chunk]:
                            if isinstance(r, dict):
                                r["kode_wilayah_sumber"]=kode
                        rows.extend(chunk if isinstance(chunk,list) else [chunk])
                        if isinstance(chunk,list) and len(chunk)<per_page: break
                        if delay>0: time.sleep(delay)
                elif mode.startswith("cari"):
                    if not kolom_induk or not nomor_induk:
                        err_msg="kolom_induk & nomor_induk wajib"
                    else:
                        res=client.fetch_cari(tbl, kolom_induk, nomor_induk, kolom_verifikasi or None, nilai_verifikasi or None, page=1, per_page=per_page)
                        chunk=res.get("data", res.get("result", [])) if isinstance(res, dict) else res
                        rows=chunk if isinstance(chunk,list) else [chunk] if chunk else []
                elif mode.startswith("npsn-changed"):
                    res=client.fetch_npsn_changed(tbl, last_update_str, kolom_verifikasi or None, nilai_verifikasi or None)
                    chunk=res.get("data", res.get("result", [])) if isinstance(res, dict) else res
                    rows=chunk if isinstance(chunk,list) else [chunk] if chunk else []
            except Exception as e:
                err_msg=str(e)[:500].replace(API_KEY,"***").replace(PASSWORD,"***")

            dt_combo=time.perf_counter()-t_combo
            # Jika keterangan error, rows kosong
            if rows and len(rows)==1 and isinstance(rows[0], dict) and "keterangan" in rows[0]:
                err_msg=rows[0]["keterangan"]; rows=[]
            if rows:
                grouped[tbl].extend(rows)
                total_rows_all+=len(rows)
                status="✅"
            else:
                status=f"⚠️ {err_msg[:60]}" if err_msg else "⚠️ kosong"
            combo_summary.append({"Tabel":tbl,"Kode":kode,"Rows":len(rows),"Status":status,"Waktu":f"{dt_combo:.2f}s"})
            log_area.dataframe(pd.DataFrame(combo_summary), use_container_width=True, hide_index=True)
            if client.token:
                save_token_to_session(client.token)

        overall_progress.progress(1.0, text=f"Fetch selesai — {total_rows_all} rows dari {total_combos} request ({time.perf_counter()-t_start:.1f}s)")

        # Save 1 CSV per tabel gabungan (tanpa bronze)
        final_paths=[]
        final_summary=[]
        for tbl in tbls:
            all_rows=grouped[tbl]
            # Filter keterangan tetap
            if not all_rows:
                # Create empty with note
                fname=f"{tbl}_KARANGASEM_{last_update_str or date.today().isoformat()}_KOSONG.csv"
                p=DATA_DIR/fname
                p.write_text("# Tidak ada data (jadwal tanggal:4 atau metadata kosong)\n", encoding="utf-8")
                final_summary.append({"Tabel":tbl,"Rows":0,"File":fname,"Kec":len(wils) if mode.startswith("by-wilayah") else 1})
                continue
            # Dedup by npsn/nisn/nuptk if exists (best practice)
            # Collect keys
            keys_available=set().union(*(r.keys() for r in all_rows)) if all_rows else set()
            # Dedup
            seen=set()
            deduped=[]
            dedup_keys=None
            if "npsn" in keys_available and tbl=="sekolah":
                dedup_keys=["npsn"]
            elif "nisn" in keys_available and tbl=="peserta_didik":
                dedup_keys=["nisn"]
            elif "nuptk" in keys_available and tbl=="ptk":
                dedup_keys=["nuptk"]
            for r in all_rows:
                if dedup_keys:
                    key=tuple(r.get(k) for k in dedup_keys)
                    if key in seen: continue
                    seen.add(key)
                deduped.append(r)
            if dedup_keys and len(deduped)!=len(all_rows):
                st.caption(f"Dedup {tbl}: {len(all_rows)} → {len(deduped)} (key {dedup_keys})")
                all_rows=deduped
            # Sort by kode_wilayah_sumber
            all_rows.sort(key=lambda x: x.get("kode_wilayah_sumber",""))
            fname=f"{tbl}_KARANGASEM_{last_update_str or date.today().isoformat()}.csv"
            # sanitize
            fname="".join(c if c.isalnum() or c in "._-" else "_" for c in fname)
            p=DATA_DIR/fname
            BackboneClient.save_csv(all_rows, p)
            final_paths.append(p)
            final_summary.append({"Tabel":tbl,"Rows":len(all_rows),"File":fname,"Kec":len(wils) if mode.startswith("by-wilayah") else 1})
            total_rows_all=len(all_rows)  # for display per table

        if final_summary:
            # ZIP hanya 3 file final
            zip_name=f"karangasem_{(last_update_str or date.today().isoformat())}_{len(tbls)}tabel_gabung.zip"
            zip_path=DATA_DIR/zip_name
            with zipfile.ZipFile(zip_path,"w", zipfile.ZIP_DEFLATED) as z:
                for s in final_summary:
                    p=DATA_DIR/s["File"]
                    if p.exists() and p.stat().st_size>0 and "KOSONG" not in s["File"]:
                        z.write(p, arcname=p.name)
                    elif p.exists():
                        z.write(p, arcname=p.name)
            st.success(f"✅ Selesai Tanpa Bronze — {len(tbls)} tabel, {len(final_paths)} CSV gabungan, {time.perf_counter()-t_start:.1f}s. Filter di Excel kolom `kode_wilayah_sumber`.")
            st.dataframe(pd.DataFrame(final_summary), use_container_width=True, hide_index=True)
            st.dataframe(pd.DataFrame(combo_summary), use_container_width=True, hide_index=True, height=200)
            with open(zip_path,"rb") as f:
                st.download_button("⬇️ Download ZIP (3 CSV Gabungan)", f, file_name=zip_name, mime="application/zip", use_container_width=True)
            # Preview first non-empty
            for s in final_summary:
                if s["Rows"]>0:
                    p=DATA_DIR/s["File"]
                    try:
                        df_prev=pd.read_csv(p).head(10)
                        st.markdown(f"**Preview `{s['File']}` ({s['Rows']} rows) — filter `kode_wilayah_sumber` di Excel:**")
                        st.dataframe(df_prev, use_container_width=True)
                        break
                    except Exception:
                        pass
        else:
            st.warning("Tidak ada data.")

    except Exception as e:
        msg=str(e).replace(API_KEY,"***").replace(PASSWORD,"***")
        st.error(f"Gagal: {msg}")

st.divider()
st.markdown("**Tanpa Bronze:** 1 tabel × 8 kec → 1 CSV (misal `sekolah_KARANGASEM_2026-09-04.csv` 800 rows, kolom `kode_wilayah_sumber` untuk filter per kecamatan). Cocok untuk jadwal sebulan sekali.")
