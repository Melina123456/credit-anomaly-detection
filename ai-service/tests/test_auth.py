import pytest
from fastapi import HTTPException

from app.auth import require_api_key


def test_raises_503_when_admin_api_key_not_configured(monkeypatch):
    # fail-closed: a missing server-side key must never be treated the same
    # as "no auth required" — the endpoint should be unreachable, not open.
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)

    with pytest.raises(HTTPException) as exc_info:
        require_api_key(x_api_key="anything")

    assert exc_info.value.status_code == 503


def test_raises_401_when_header_missing(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "secret-key")

    with pytest.raises(HTTPException) as exc_info:
        require_api_key(x_api_key=None)

    assert exc_info.value.status_code == 401


def test_raises_401_when_header_does_not_match(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "secret-key")

    with pytest.raises(HTTPException) as exc_info:
        require_api_key(x_api_key="wrong-key")

    assert exc_info.value.status_code == 401


def test_succeeds_when_header_matches(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "secret-key")

    # no exception raised = success, this is a FastAPI dependency with no
    # meaningful return value
    require_api_key(x_api_key="secret-key")
