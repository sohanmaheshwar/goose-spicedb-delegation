from authzed.api.v1 import WriteRelationshipsRequest

from approve import approve
from authz import Decision, decide
from relationships import rel
from revoke import revoke


async def test_approve_unblocks_production(seeded):
    before = await decide(seeded, "goose_alice", "deploy", "production")
    assert before.decision is Decision.NEEDS_APPROVAL
    assert await approve("alice", "production", "goose_alice", 10) == 0
    after = await decide(seeded, "goose_alice", "deploy", "production")
    assert after.decision is Decision.ALLOWED


async def test_non_approver_refused(seeded):
    assert await approve("bob", "production", "goose_alice", 10) == 1
    # The refused approve must not have written any grant: production still needs approval.
    after = await decide(seeded, "goose_alice", "deploy", "production")
    assert after.decision is Decision.NEEDS_APPROVAL


async def test_revoke_drops_staging_to_needs_approval(seeded):
    before = await decide(seeded, "goose_alice", "deploy", "staging")
    assert before.decision is Decision.ALLOWED
    assert await revoke("alice", "staging", "goose_alice") == 0
    after = await decide(seeded, "goose_alice", "deploy", "staging")
    assert after.decision is Decision.NEEDS_APPROVAL


async def test_approve_rejects_nonpositive_window(seeded):
    # A non-positive window is useless (immediately expired); reject it, don't fake success.
    assert await approve("alice", "production", "goose_alice", 0) == 1
    after = await decide(seeded, "goose_alice", "deploy", "production")
    assert after.decision is Decision.NEEDS_APPROVAL


async def test_approve_refuses_when_delegator_lacks_deploy(seeded):
    # goose_bob's delegator (bob) is not a deployer anywhere. alice IS a production
    # approver, so the approver gate passes — but the grant must still be refused,
    # or we would hand goose_bob authority its principal never had.
    await seeded.WriteRelationships(
        WriteRelationshipsRequest(updates=[rel("agent", "goose_bob", "delegator", "user", "bob")])
    )
    assert await approve("alice", "production", "goose_bob", 10) == 1
    after = await decide(seeded, "goose_bob", "deploy", "production")
    assert after.decision is Decision.BLOCKED


async def test_revoke_requires_manage_authority(seeded):
    # bob is not an operator (direct_deployer) of staging, so he cannot revoke.
    assert await revoke("bob", "staging", "goose_alice") == 1
    after = await decide(seeded, "goose_alice", "deploy", "staging")
    assert after.decision is Decision.ALLOWED


async def test_revoke_prod_only_leaves_staging(seeded):
    # Grant prod, then revoke prod alone: prod drops, staging autonomy is untouched.
    assert await approve("alice", "production", "goose_alice", 10) == 0
    assert (await decide(seeded, "goose_alice", "deploy", "production")).decision is Decision.ALLOWED
    assert await revoke("alice", "production", "goose_alice") == 0
    assert (await decide(seeded, "goose_alice", "deploy", "production")).decision is Decision.NEEDS_APPROVAL
    assert (await decide(seeded, "goose_alice", "deploy", "staging")).decision is Decision.ALLOWED


async def test_revoke_staging_cascades_to_prod(seeded):
    # Grant prod so the agent can autonomously deploy both...
    assert await approve("alice", "production", "goose_alice", 10) == 0
    assert (await decide(seeded, "goose_alice", "deploy", "production")).decision is Decision.ALLOWED
    # ...then revoke the BASE (staging). Production autonomy is gated by staging in the
    # schema, so it suspends automatically — no second delete needed.
    assert await revoke("alice", "staging", "goose_alice") == 0
    assert (await decide(seeded, "goose_alice", "deploy", "staging")).decision is Decision.NEEDS_APPROVAL
    assert (await decide(seeded, "goose_alice", "deploy", "production")).decision is Decision.NEEDS_APPROVAL
