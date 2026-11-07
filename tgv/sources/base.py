"""HTTP access and the connector contract.

Every connector receives an ``Http`` object so tests can replace the network
with fixtures. Credentials are read from environment variables by the
connector itself; they are never logged, stored in the database or written
to config files.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Iterable, Protocol

from tgv.models import ContentItem

USER_AGENT = "TGVBRAuto/0.1 (content research for The Game Verse BR)"


class SourceNotConfigured(Exception):
    """Raised when a connector lacks the credentials it needs. Not an error: it is skipped."""


class Http(Protocol):
    def get_text(self, url: str, params: dict | None = None, headers: dict | None = None) -> str: ...
    def get_json(self, url: str, params: dict | None = None, headers: dict | None = None) -> dict: ...
    def post_form(self, url: str, data: dict, headers: dict | None = None) -> dict: ...


class UrllibHttp:
    def __init__(self, timeout: float = 20.0):
        self.timeout = timeout

    def _open(self, req: urllib.request.Request) -> bytes:
        req.add_header("User-Agent", USER_AGENT)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310 (https URLs from config)
            return resp.read()

    @staticmethod
    def _url(url: str, params: dict | None) -> str:
        if not params:
            return url
        return f"{url}{'&' if '?' in url else '?'}{urllib.parse.urlencode(params)}"

    def get_text(self, url, params=None, headers=None):
        req = urllib.request.Request(self._url(url, params), headers=headers or {})
        return self._open(req).decode("utf-8", errors="replace")

    def get_json(self, url, params=None, headers=None):
        return json.loads(self.get_text(url, params, headers))

    def post_form(self, url, data, headers=None):
        body = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(url, data=body, headers=headers or {}, method="POST")
        return json.loads(self._open(req).decode("utf-8"))


class Connector(Protocol):
    name: str

    def fetch(self, http: Http, now: datetime) -> Iterable[ContentItem]: ...


def env(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None
