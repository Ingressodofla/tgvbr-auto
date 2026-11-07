import json
from datetime import datetime, timezone
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 11, 7, 0, 0, tzinfo=timezone.utc)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeHttp:
    """Maps URL prefixes to fixture bodies and records every call."""

    def __init__(self, routes: dict[str, str]):
        self.routes = routes
        self.calls: list[tuple[str, dict]] = []

    def _find(self, url):
        for prefix, body in self.routes.items():
            if url.startswith(prefix):
                if isinstance(body, Exception):
                    raise body
                return body
        raise AssertionError(f"unexpected URL {url}")

    def get_text(self, url, params=None, headers=None):
        self.calls.append((url, params or {}))
        return self._find(url)

    def get_json(self, url, params=None, headers=None):
        return json.loads(self.get_text(url, params, headers))

    def post_form(self, url, data, headers=None):
        self.calls.append((url, data))
        return {"access_token": "test-bearer", "token_type": "bearer"}
