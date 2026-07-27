from approve import approve
from authz import Decision, decide
from revoke import revoke


async def test_full_delegation_arc(seeded):
    # 1. Delegated staging deploy is autonomous.
    assert (await decide(seeded, "goose_alice", "deploy", "staging")).decision is Decision.ALLOWED
    # 2. Production deploy needs human approval.
    assert (await decide(seeded, "goose_alice", "deploy", "production")).decision is Decision.NEEDS_APPROVAL
    # 3. A human approves; the agent may now deploy production.
    assert await approve("alice", "production", "goose_alice", 10) == 0
    assert (await decide(seeded, "goose_alice", "deploy", "production")).decision is Decision.ALLOWED
    # 4. Destroy is hard-blocked: no human in the chain can do it.
    assert (await decide(seeded, "goose_alice", "destroy", "production")).decision is Decision.BLOCKED
    # 5. Revoke the staging delegation (as alice, an env operator): autonomy is gone,
    #    falls back to approval.
    assert await revoke("alice", "staging", "goose_alice") == 0
    assert (await decide(seeded, "goose_alice", "deploy", "staging")).decision is Decision.NEEDS_APPROVAL
