import os

# Dummy settings so the app imports without a real .env. Nothing in the tests touches the network.
for k, v in {
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_SERVICE_KEY": "dummy",
    "LLM_API_KEY": "k",
    "LLM_MODEL": "test-model",
    "TAVILY_API_KEY": "t",
    "RESEARCH_DELAY_SECONDS": "0",
}.items():
    os.environ.setdefault(k, v)

import pytest

from tests.fakes import FakeRepo


@pytest.fixture
def fake(monkeypatch):
    f = FakeRepo()
    f.install(monkeypatch)
    return f
