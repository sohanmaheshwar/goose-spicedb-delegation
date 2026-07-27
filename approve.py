"""approve.py — human-in-the-loop: grant the agent a short-lived deploy window."""
import argparse
import asyncio

from authzed.api.v1 import WriteRelationshipsRequest

from authz import check, expiry_from_now, read_delegator
from relationships import rel
from spicedb_client import make_client


async def approve(approver: str, environment: str, agent_id: str, minutes: int) -> int:
    if minutes <= 0:
        print(f"❌ Refused: --minutes must be positive (got {minutes})")
        return 1
    client = make_client()
    if not await check(client, "user", approver, "approve", "environment", environment):
        print(f"❌ Refused: user:{approver} is not an approver on environment:{environment}")
        return 1
    # An approver may only extend an agent authority its own delegator holds — never
    # grant it something its human principal couldn't do (prevents privilege escalation).
    delegator = await read_delegator(client, agent_id)
    if not (delegator and await check(client, "user", delegator, "deploy", "environment", environment)):
        who = f"user:{delegator}" if delegator else "(no delegator)"
        print(
            f"❌ Refused: agent:{agent_id}'s delegator {who} may not deploy "
            f"environment:{environment}; cannot grant authority its principal lacks"
        )
        return 1
    update = rel(
        "environment", environment, "agent_deployer", "agent", agent_id,
        expires_at=expiry_from_now(minutes),
    )
    await client.WriteRelationships(WriteRelationshipsRequest(updates=[update]))
    print(f"✅ Approved: agent:{agent_id} may deploy environment:{environment} for {minutes} min")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Approve a short-lived agent deploy window.")
    parser.add_argument("--approver", default="alice")
    parser.add_argument("--env", default="production")
    parser.add_argument("--agent", default="goose_alice")
    parser.add_argument("--minutes", type=int, default=10)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(approve(args.approver, args.env, args.agent, args.minutes)))
