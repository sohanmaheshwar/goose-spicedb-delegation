from authz import check


async def _has(client, sub_type, sub_id, permission, env_id) -> bool:
    # Thin wrapper over the production check() so the tests exercise the real path.
    return await check(client, sub_type, sub_id, permission, "environment", env_id)


async def test_alice_can_deploy_both(seeded):
    assert await _has(seeded, "user", "alice", "deploy", "staging")
    assert await _has(seeded, "user", "alice", "deploy", "production")


async def test_alice_can_approve_production(seeded):
    assert await _has(seeded, "user", "alice", "approve", "production")


async def test_alice_cannot_destroy(seeded):
    assert not await _has(seeded, "user", "alice", "destroy", "production")


async def test_agent_can_deploy_staging_in_window(seeded):
    assert await _has(seeded, "agent", "goose_alice", "deploy", "staging")


async def test_agent_cannot_deploy_production(seeded):
    assert not await _has(seeded, "agent", "goose_alice", "deploy", "production")


async def test_agent_cannot_destroy(seeded):
    assert not await _has(seeded, "agent", "goose_alice", "destroy", "production")
