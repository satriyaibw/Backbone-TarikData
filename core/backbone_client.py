"""
Backbone V3 Client - Core Engine
Best practice: requests Session + Retry + timeout tuple (context7: psf/requests)
Fix bug collection.json:664 (npsn-changed path) & 2126 (empty url), handle 422 detail
"""
import csv
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry


class BackboneClient:
    """Client untuk Backbone V3 Kemendikdasmen."""

    def __init__(
        self,
        base_url: str,
        base_url_login: str,
        username: str,
        password: str,
        api_key: str,
        timeout: Tuple[int, int] = (10, 30),
        timeout_interactive: Tuple[int, int] = (5, 15),
    ):
        self.base_url = base_url.rstrip("/")
        self.base_url_login = base_url_login.rstrip("/")
        self.username = username
        self.password = password
        self.api_key = api_key
        self.timeout = timeout
        self.timeout_interactive = timeout_interactive
        self.token: Optional[str] = None
        self.session = self._build_session()

    def _build_session(self) -> requests.Session:
        """Session dengan retry backoff (context7 best practice) - tuned for batch vs interactive."""
        session = requests.Session()
        # Interactive: fail fast (total=1), Batch: total=3 via _get timeout param
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 502, 503, 504],
            allowed_methods={"GET", "POST"},
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _headers(self, with_auth: bool = True) -> Dict[str, str]:
        h = {"Accept": "application/json"}
        if self.api_key:
            h["X-API-Key"] = self.api_key
        if with_auth and self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def login(self, interactive: bool = False) -> Dict[str, Any]:
        """POST /access-token — Juknis:2, Collection.json:2142. interactive=True uses shorter timeout."""
        url = f"{self.base_url_login}/access-token"
        data = {"username": self.username, "password": self.password}
        timeout = self.timeout_interactive if interactive else self.timeout
        resp = self.session.post(
            url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
            timeout=timeout,
        )
        if resp.status_code == 422:
            try:
                detail = resp.json().get("detail", [])
            except Exception:
                detail = resp.text[:500]
            raise ValueError(f"Login 422 validation error: {detail}")
        if resp.status_code == 500:
            body = resp.text[:500] if resp.text else "Internal Server Error"
            raise RuntimeError(
                f"Server 500 — Pusdatin auth sedang gangguan/maintenance (bukan salah password). "
                f"Coba lagi 1-2 menit, jika tetap 500 hubungi PIC Pusdatin (Juknis:7). Body: {body}"
            )
        resp.raise_for_status()
        j = resp.json()
        self.token = j.get("access_token")
        if not self.token:
            # Scrub token from error (security)
            raise ValueError(f"Login gagal status {resp.status_code}")
        return j

    def ensure_token(self, interactive: bool = False):
        if not self.token:
            self.login(interactive=interactive)

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None, interactive: bool = False) -> requests.Response:
        self.ensure_token(interactive=interactive)
        url = f"{self.base_url}{path}"
        timeout = self.timeout_interactive if interactive else self.timeout
        resp = self.session.get(url, headers=self._headers(), params=params, timeout=timeout)
        # Auto-refresh on 401
        if resp.status_code == 401:
            self.login(interactive=interactive)
            resp = self.session.get(url, headers=self._headers(), params=params, timeout=timeout)
        if resp.status_code == 422:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text[:500]
            raise ValueError(f"422 Unprocessable Entity at {path} detail={detail}")
        resp.raise_for_status()
        return resp

    # --- User Info endpoints (Juknis:4, Collection user-info) ---
    def get_wilayah_akses(self, interactive: bool = True) -> List[Dict[str, Any]]:
        resp = self._get("/wilayah-akses-kecamatan", interactive=interactive)
        data = resp.json()
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        if isinstance(data, list):
            return data
        return [data] if data else []

    def get_metadata(self, last_update: Optional[str] = None, interactive: bool = True) -> List[Dict[str, Any]]:
        params = {}
        if last_update:
            params["last_update"] = last_update
        resp = self._get("/metadata", params=params, interactive=interactive)
        data = resp.json()
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return data if isinstance(data, list) else [data]

    def get_metadata_last_update(self, interactive: bool = True) -> Any:
        resp = self._get("/metadata/last-update", interactive=interactive)
        return resp.json()

    def get_referensi_daftar(self, interactive: bool = True) -> List[Any]:
        resp = self._get("/referensi/daftar", interactive=interactive)
        data = resp.json()
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return data if isinstance(data, list) else [data]

    def get_referensi(self, ref: str, page: int = 1, per_page: int = 50, interactive: bool = True) -> Dict[str, Any]:
        resp = self._get("/referensi", params={"ref": ref, "page": page, "per_page": per_page}, interactive=interactive)
        return resp.json()

    def get_user_schedule(self, page: int = 1, per_page: int = 10, interactive: bool = True) -> Dict[str, Any]:
        resp = self._get("/user-info/schedule", params={"page": page, "per_page": per_page}, interactive=interactive)
        return resp.json()

    def get_whitelist(self, page: int = 1, per_page: int = 10, interactive: bool = True) -> Dict[str, Any]:
        resp = self._get("/user-info/whitelist", params={"page": page, "per_page": per_page}, interactive=interactive)
        return resp.json()

    # --- Data endpoints (Juknis:5, Collection Data) ---
    def fetch_by_npsn(
        self,
        npsn: str,
        tbl_name: str,
        page: int = 1,
        per_page: int = 500,
        last_update: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"npsn": npsn, "tbl_name": tbl_name, "page": page, "per_page": per_page}
        if last_update:
            params["last_update"] = last_update
        resp = self._get("/data/by-npsn", params=params)
        return resp.json()

    def fetch_by_wilayah(
        self,
        kode_wilayah: str,
        tbl_name: str,
        page: int = 1,
        per_page: int = 500,
        last_update: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"kode_wilayah": kode_wilayah, "tbl_name": tbl_name, "page": page, "per_page": per_page}
        if last_update:
            params["last_update"] = last_update
        resp = self._get("/data/by-wilayah", params=params)
        return resp.json()

    def fetch_cari(
        self,
        tbl_name: str,
        kolom_induk: str,
        nomor_induk: str,
        kolom_verifikasi: Optional[str] = None,
        nilai_verifikasi: Optional[str] = None,
        page: int = 1,
        per_page: int = 500,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "tbl_name": tbl_name,
            "kolom_induk": kolom_induk,
            "nomor_induk": nomor_induk,
            "page": page,
            "per_page": per_page,
        }
        if kolom_verifikasi:
            params["kolom_verifikasi"] = kolom_verifikasi
        if nilai_verifikasi:
            params["nilai_verifikasi"] = nilai_verifikasi
        resp = self._get("/data/cari", params=params)
        return resp.json()

    def fetch_npsn_changed(
        self,
        tbl_name: str,
        last_update: str,
        kolom_verifikasi: Optional[str] = None,
        nilai_verifikasi: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fix bug Collection.json:664 — query harus di params, bukan path."""
        params: Dict[str, Any] = {"tbl_name": tbl_name, "last_update": last_update}
        if kolom_verifikasi:
            params["kolom_verifikasi"] = kolom_verifikasi
        if nilai_verifikasi:
            params["nilai_verifikasi"] = nilai_verifikasi
        resp = self._get("/data/npsn-changed", params=params)
        return resp.json()

    def fetch_all_pages(
        self,
        fetch_fn,
        *args,
        per_page: int = 500,
        max_pages: int = 200,
        delay: float = 0.2,
        last_update: Optional[str] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """Generic pagination loop — handles 'data' key variations."""
        all_rows: List[Dict[str, Any]] = []
        for page in range(1, max_pages + 1):
            kwargs_page = {**kwargs, "page": page, "per_page": per_page}
            if last_update:
                kwargs_page["last_update"] = last_update
            result = fetch_fn(*args, **kwargs_page)
            # Extract rows
            rows = []
            if isinstance(result, dict):
                # Common patterns: {"data": [...], "total": ...} or {"result": [...]}
                for key in ("data", "result", "items", "rows"):
                    if key in result and isinstance(result[key], list):
                        rows = result[key]
                        break
                else:
                    # If dict but no list key, treat as single row or empty
                    if not result:
                        rows = []
                    elif isinstance(result, dict) and any(isinstance(v, list) for v in result.values()):
                        rows = []
                    else:
                        # Fallback: if result itself is row-like
                        rows = [result] if result else []
            elif isinstance(result, list):
                rows = result
            if not rows:
                break
            all_rows.extend(rows)
            # If fewer than per_page, last page
            if len(rows) < per_page:
                break
            time.sleep(delay)
        return all_rows

    @staticmethod
    def save_csv(rows: List[Dict[str, Any]], path: Path):
        if not rows:
            # Create empty file with no header
            path.write_text("", encoding="utf-8")
            return
        # Collect all keys
        fieldnames = sorted({k for r in rows for k in r.keys()})
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
