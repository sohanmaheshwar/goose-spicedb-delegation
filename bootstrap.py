"""bootstrap.py — write the schema and seed the delegation graph."""
import argparse
import asyncio
from pathlib import Path

from authzed.api.v1 import (
    DeleteRelationshipsRequest,
    WriteRelationshipsRequest,
    WriteSchemaRequest,
)

from authz import expiry_from_now
from relationships import agent_deployer_filter, rel
from spicedb_client import make_client

SCHEMA_PATH = Path(__file__).parent / "schema.zed"
AGENT_ID = "goose_alice"


async def write_schema(client) -> None:
    await client.WriteSchema(WriteSchemaRequest(schema=SCHEMA_PATH.read_text()))


async def _reset_agent_grants(client) -> None:
    """Remove all agent_deployer grants for the agent so seeding is idempotent."""
    await client.DeleteRelationships(
        DeleteRelationshipsRequest(relationship_filter=agent_deployer_filter(AGENT_ID))
    )


async def seed(client, window_minutes: int = 60) -> None:
    await _reset_agent_grants(client)
    updates = [
        # Alice (SRE) can deploy both environments and approve production.
        rel("environment", "staging", "direct_deployer", "user", "alice"),
        rel("environment", "production", "direct_deployer", "user", "alice"),
        rel("environment", "production", "approver", "user", "alice"),
        # Destroy is a human-only power, and NOT one alice holds.
        rel("environment", "staging", "destroyer", "user", "sre_admin"),
        rel("environment", "production", "destroyer", "user", "sre_admin"),
        # Autonomy dependency: staging is the base (gates itself); production's
        # agent-autonomy is contingent on staging's, so revoking staging cascades.
        rel("environment", "staging", "gated_by", "environment", "staging"),
        rel("environment", "production", "gated_by", "environment", "staging"),
        # The agent acts on behalf of alice.
        rel("agent", AGENT_ID, "delegator", "user", "alice"),
        # Delegation: staging-only, time-bound via built-in relationship expiration.
        rel(
            "environment", "staging", "agent_deployer", "agent", AGENT_ID,
            expires_at=expiry_from_now(window_minutes),
        ),
    ]
    await client.WriteRelationships(WriteRelationshipsRequest(updates=updates))


async def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap the goose x SpiceDB delegation demo.")
    parser.add_argument(
        "--window-minutes", type=int, default=60,
        help="Minutes the agent's staging delegation stays valid (set <= 0 to demo expiry).",
    )
    args = parser.parse_args()

    client = make_client()
    print("Writing schema...")
    await write_schema(client)
    print(f"Seeding delegation graph (staging window = {args.window_minutes} min)...")
    await seed(client, window_minutes=args.window_minutes)
    print("Done. agent:goose_alice may deploy staging autonomously until the window expires.")


if __name__ == "__main__":
    asyncio.run(main())
