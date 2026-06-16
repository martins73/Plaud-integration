"""Minimal client for the unofficial PLAUD cloud API.

PLAUD does not publish a public API. The endpoints used here were
reverse-engineered from traffic between the PLAUD web app
(https://web.plaud.ai) and https://api.plaud.ai, and are the same ones used
by community projects. They can change without notice.

Only the read paths needed by this project are implemented: list recordings
and fetch a temporary download URL for the raw audio. Authentication is a
bearer token (the ``tokenstr`` JWT from the web app's local storage).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

KNOWN_REGIONS = {
    "default": "https://api.plaud.ai",
    "apse1": "https://api-apse1.plaud.ai",
}

# Endpoint paths (relative to the regional base URL).
FILE_SIMPLE = "/file/simple/web"  # GET: paginated list of recordings
FILE_LIST = "/file/list"  # POST [ids]: full details for specific recordings
FILE_TEMP_URL = "/file/temp-url"  # GET /{file_id}: presigned download URL

# Headers the reverse-engineered API expects to look like the web app.
_BROWSER_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://web.plaud.ai",
    "Referer": "https://web.plaud.ai/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15"
    ),
    "app-platform": "web",
    "edit-from": "web",
}


class PlaudError(Exception):
    """Raised on API or authentication errors."""


@dataclass(slots=True)
class CloudRecording:
    """A recording as returned by the PLAUD cloud list endpoint."""

    id: str
    title: str
    created_at: datetime
    duration_ms: int
    raw: dict[str, Any]


def _make_session(token: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(_BROWSER_HEADERS)
    session.headers["Authorization"] = f"bearer {token}"
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


class PlaudCloudClient:
    def __init__(self, token: str, *, region: str = "default", timeout: int = 30) -> None:
        if not token:
            raise PlaudError(
                "No PLAUD token. Set PLAUD_TOKEN in your .env or run `plaud-brain auth`."
            )
        self.base_url = KNOWN_REGIONS.get(region, region).rstrip("/")
        self.timeout = timeout
        self._session = _make_session(token)

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = dict(params or {})
        params.setdefault("r", random.random())  # cache-buster the web app sends
        resp = self._session.get(f"{self.base_url}{path}", params=params, timeout=self.timeout)
        return self._handle(resp)

    def _post(self, path: str, json: Any) -> dict[str, Any]:
        resp = self._session.post(f"{self.base_url}{path}", json=json, timeout=self.timeout)
        return self._handle(resp)

    @staticmethod
    def _handle(resp: requests.Response) -> dict[str, Any]:
        if resp.status_code == 401:
            raise PlaudError(
                "PLAUD authentication failed (401). Your token is likely expired — "
                "grab a fresh one from web.plaud.ai and run `plaud-brain auth`."
            )
        if resp.status_code >= 400:
            raise PlaudError(f"PLAUD API error {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        if isinstance(data, dict):
            status = data.get("status")
            msg = data.get("msg") or data.get("message")
            if status == -302 or msg == "user region mismatch":
                raise PlaudError(
                    "PLAUD says 'user region mismatch'. Set region = \"apse1\" "
                    "(or your region) under [plaud] in config.toml."
                )
        return data

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_recordings(self, *, limit: int = 50, skip: int = 0) -> list[CloudRecording]:
        """Return recent recordings, most recent first."""
        data = self._get(
            FILE_SIMPLE,
            params={
                "skip": skip,
                "limit": limit,
                "is_trash": 0,
                "sort_by": "start_time",
                "is_desc": "true",
            },
        )
        files = data.get("data_file_list") or []
        return [self._parse(f) for f in files]

    def get_audio_url(self, file_id: str) -> str:
        """Return a temporary presigned URL for downloading the raw audio."""
        data = self._get(f"{FILE_TEMP_URL}/{file_id}")
        url = data.get("temp_url")
        if not url:
            raise PlaudError(f"No download URL returned for recording {file_id}")
        return str(url)

    def download_audio(self, file_id: str, dest: Any) -> None:
        """Stream the raw audio for ``file_id`` to the path ``dest``."""
        url = self.get_audio_url(file_id)
        with requests.get(url, stream=True, timeout=self.timeout * 4) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1 << 16):
                    if chunk:
                        f.write(chunk)

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse(f: dict[str, Any]) -> CloudRecording:
        file_id = str(f.get("id") or f.get("file_id") or "")
        ts = f.get("start_time") or 0
        if isinstance(ts, (int, float)) and ts > 0:
            created = datetime.fromtimestamp(ts / 1000, tz=UTC)
        else:
            created = datetime.now(tz=UTC)
        title = (f.get("filename") or f.get("name") or "").strip() or f"Recording {file_id}"
        return CloudRecording(
            id=file_id,
            title=title,
            created_at=created,
            duration_ms=int(f.get("duration") or 0),
            raw=f,
        )
