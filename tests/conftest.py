from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _dashboard_answers_the_test_client(monkeypatch):
    """Starlette's TestClient addresses the app as `testserver`, a name the dashboard refuses in real use
    (dashboard.app.ALLOWED_HOSTS). Each test gets its own copy of the set with that name added, so a test may
    also change the set freely."""
    try:
        from oeisbot.dashboard import app as dashboard
    except ImportError:         # the dashboard extra is not installed; its tests skip themselves
        return
    # what a real server starts with. Asserted here because every test below runs with a replaced set, so
    # nothing else would notice the real one being loosened; it also catches a test that leaked its own.
    assert dashboard.ALLOWED_HOSTS == {"127.0.0.1", "localhost", "::1"}
    monkeypatch.setattr(dashboard, "ALLOWED_HOSTS", set(dashboard.ALLOWED_HOSTS) | {"testserver"})
