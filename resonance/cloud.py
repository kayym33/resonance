"""Minimal Supabase client: email/password auth and the items table.

Uses urllib rather than supabase-py to keep the build free of extra
dependencies. Methods block, so call them from the worker pool.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .constants import SUPABASE_KEY, SUPABASE_URL
from .paths import DATA_DIR

SESSION_PATH = DATA_DIR / "session.json"
# Refresh this long before the access token actually expires.
REFRESH_MARGIN: int = 60
REQUEST_TIMEOUT: int = 15
PAGE_SIZE: int = 1000


class CloudError(Exception):
    """The server couldn't be reached or refused a request."""


class AuthError(CloudError):
    """The credentials or session are no longer valid; sign in again."""


@dataclass
class Session:
    access_token: str
    refresh_token: str
    expires_at: float
    user_id: str
    email: str

    @classmethod
    def from_response(cls, data: dict[str, Any]) -> Session:
        return cls(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=time.time() + float(data.get("expires_in", 3600)),
            user_id=data["user"]["id"],
            email=data["user"].get("email", ""),
        )


def load_session() -> Session | None:
    try:
        with SESSION_PATH.open(encoding="utf-8") as session_file:
            return Session(**json.load(session_file))
    except (OSError, ValueError, TypeError):
        return None


def save_session(session: Session | None) -> None:
    if session is None:
        SESSION_PATH.unlink(missing_ok=True)
        return
    SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    # The refresh token signs in as the user, so keep it private.
    descriptor = os.open(SESSION_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as session_file:
        json.dump(asdict(session), session_file)


def error_message(body: bytes, fallback: str) -> str:
    try:
        data = json.loads(body)
    except ValueError:
        return fallback
    if isinstance(data, dict):
        for key in ("msg", "message", "error_description", "error"):
            if isinstance(data.get(key), str):
                return data[key]
    return fallback


class Cloud:
    def __init__(self, url: str = SUPABASE_URL, key: str = SUPABASE_KEY) -> None:
        self.url = url.rstrip("/")
        self.key = key
        self.session: Session | None = load_session()
        self.lock = threading.Lock()

    @property
    def signed_in(self) -> bool:
        return self.session is not None

    def request(
        self,
        method: str,
        path: str,
        body: Any = None,
        headers: dict[str, str] | None = None,
        authorized: bool = True,
    ) -> Any:
        request_headers = {"apikey": self.key, "Content-Type": "application/json"}
        if authorized:
            request_headers["Authorization"] = f"Bearer {self.access_token()}"
        request_headers.update(headers or {})
        request = Request(
            f"{self.url}{path}",
            data=None if body is None else json.dumps(body).encode(),
            headers=request_headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                payload = response.read()
        except HTTPError as error:
            message = error_message(error.read(), f"server error {error.code}")
            if error.code in (400, 401, 403) and "/auth/" in path:
                raise AuthError(message) from error
            if error.code == 401:
                raise AuthError(message) from error
            raise CloudError(message) from error
        except (URLError, OSError) as error:
            raise CloudError("can't reach the sync server") from error
        return json.loads(payload) if payload else None

    # Auth

    def sign_in(self, email: str, password: str) -> Session:
        data = self.request(
            "POST",
            "/auth/v1/token?grant_type=password",
            {"email": email, "password": password},
            authorized=False,
        )
        with self.lock:
            self.session = Session.from_response(data)
            save_session(self.session)
            return self.session

    def forget_session(self) -> Session | None:
        """Sign out on this device straight away; returns the old session."""
        with self.lock:
            session, self.session = self.session, None
            save_session(None)
        return session

    def revoke(self, session: Session | None) -> None:
        """Ask the server to end a forgotten session (blocking)."""
        if session is None:
            return
        try:
            self.request(
                "POST",
                "/auth/v1/logout",
                headers={"Authorization": f"Bearer {session.access_token}"},
                authorized=False,
            )
        except CloudError:
            pass  # Signed out on this device either way.

    def access_token(self) -> str:
        with self.lock:
            if self.session is None:
                raise AuthError("not signed in")
            if self.session.expires_at - REFRESH_MARGIN < time.time():
                self.refresh_locked()
            return self.session.access_token

    def refresh_locked(self) -> None:
        assert self.session is not None
        try:
            data = self.request(
                "POST",
                "/auth/v1/token?grant_type=refresh_token",
                {"refresh_token": self.session.refresh_token},
                authorized=False,
            )
        except AuthError:
            # The refresh token was revoked or expired.
            self.session = None
            save_session(None)
            raise
        self.session = Session.from_response(data)
        save_session(self.session)

    def change_password(self, password: str) -> None:
        self.request("PUT", "/auth/v1/user", {"password": password})

    # Phone

    def send_to_phone(self, title: str, body: str) -> int:
        """Push a notification to the phones this account installed the
        phone app on (supabase/functions/push). Returns how many got it."""
        result = self.request(
            "POST",
            "/functions/v1/push",
            {"title": title, "body": body},
        )
        return int(result.get("sent", 0)) if isinstance(result, dict) else 0

    # Items

    def push(self, records: list[dict[str, Any]]) -> None:
        if not records or self.session is None:
            return
        user_id = self.session.user_id
        self.request(
            "POST",
            "/rest/v1/items?on_conflict=user_id,kind,id",
            [{**record, "user_id": user_id} for record in records],
            headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
        )

    def pull(self, since: str | None) -> list[dict[str, Any]]:
        """Rows stored at or after ``since`` (server time), oldest first.

        Supabase caps each response at 1000 rows and a batch upload gives
        every row the same timestamp, so page with offsets on an inclusive
        cursor; rows on the boundary come back again, which is harmless.
        """
        rows: list[dict[str, Any]] = []
        while True:
            query: dict[str, str | int] = {
                "select": "kind,id,data,deleted,updated_at,server_updated_at",
                "order": "server_updated_at.asc,kind.asc,id.asc",
                "limit": PAGE_SIZE,
                "offset": len(rows),
            }
            if since:
                query["server_updated_at"] = f"gte.{since}"
            page = self.request("GET", f"/rest/v1/items?{urlencode(query)}") or []
            rows.extend(page)
            if len(page) < PAGE_SIZE:
                return rows
