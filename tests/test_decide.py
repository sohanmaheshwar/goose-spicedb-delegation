from authz import Decision, decide


async def test_staging_deploy_allowed(seeded):
    r = await decide(seeded, "goose_alice", "deploy", "staging")
    assert r.decision is Decision.ALLOWED


async def test_production_deploy_needs_approval(seeded):
    r = await decide(seeded, "goose_alice", "deploy", "production")
    assert r.decision is Decision.NEEDS_APPROVAL


async def test_destroy_blocked(seeded):
    r = await decide(seeded, "goose_alice", "destroy", "production")
    assert r.decision is Decision.BLOCKED


async def test_expired_window_drops_staging_to_needs_approval(seed_env):
    # Seed an already-expired staging delegation (window_minutes=0); SpiceDB's built-in
    # relationship expiration treats the grant as absent, so the agent's autonomous
    # deploy falls back to NEEDS_APPROVAL (alice can still deploy staging). Guards the
    # headline time-bound-delegation feature.
    client = await seed_env(0)
    r = await decide(client, "goose_alice", "deploy", "staging")
    assert r.decision is Decision.NEEDS_APPROVAL
