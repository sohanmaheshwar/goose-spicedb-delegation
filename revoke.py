"""revoke.py — delete an agent's deploy delegation on an environment."""
import argparse
import asyncio

from authzed.api.v1 import DeleteRelationshipsRequest

from authz import check
from relationships import agent_deployer_filter
from spicedb_client import make_client


async def revoke(revoker: str, environment: str, agent_id: str) -> int:
    client = make_client()
    if not await check(client, "user", revoker, "manage", "environment", environment):
        print(f"❌ Refused: user:{revoker} may not manage environment:{environment} (revocation requires an env operator)")
        return 1
    await client.DeleteRelationships(
        DeleteRelationshipsRequest(
            relationship_filter=agent_deployer_filter(agent_id, environment)
        )
    )
    print(f"✅ Revoked: agent:{agent_id} agent_deployer on environment:{environment}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Revoke an agent deploy delegation.")
    parser.add_argument("--revoker", default="alice")
    parser.add_argument("--env", default="staging")
    parser.add_argument("--agent", default="goose_alice")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(revoke(args.revoker, args.env, args.agent)))
