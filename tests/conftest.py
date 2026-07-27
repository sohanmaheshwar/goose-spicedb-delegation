import pytest

from spicedb_client import make_client

# The schema never changes between tests, so write it once per session; only the
# seed data is reset per test (idempotently, via bootstrap._reset_agent_grants).
_schema_written = False


@pytest.fixture
async def client():
    return make_client()


@pytest.fixture
async def seed_env(client):
    """Factory fixture: ensure the schema is written (once per session), then (re)seed
    the delegation graph with the given staging window. Returns the seeded client."""
    from bootstrap import seed, write_schema

    async def _seed(window_minutes: int = 60):
        global _schema_written
        if not _schema_written:
            await write_schema(client)
            _schema_written = True
        await seed(client, window_minutes=window_minutes)
        return client

    return _seed


@pytest.fixture
async def seeded(seed_env):
    """The common case: schema + a 60-minute staging delegation, reset before each test."""
    return await seed_env()
