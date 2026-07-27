"""authz.py — SpiceDB-backed delegation helpers and decision engine."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

from google.protobuf.timestamp_pb2 import Timestamp
from authzed.api.v1 import (
    CheckPermissionRequest,
    CheckPermissionResponse,
    Consistency,
    ObjectReference,
    ReadRelationshipsRequest,
    RelationshipFilter,
    SubjectReference,
)


def expiry_from_now(minutes: int) -> Timestamp:
    """A protobuf Timestamp `minutes` from now, for a relationship's optional_expires_at.

    Uses SpiceDB's built-in relationship expiration (schema: `... with expiration`),
    which is more efficient than a caveat and evaluated server-side — so callers need
    not pass any request-time context to have expiry enforced.
    """
    ts = Timestamp()
    ts.FromDatetime(datetime.now(timezone.utc) + timedelta(minutes=minutes))
    return ts


class Decision(str, Enum):
    ALLOWED = "ALLOWED"
    NEEDS_APPROVAL = "NEEDS_APPROVAL"
    BLOCKED = "BLOCKED"


@dataclass
class AuthzResult:
    decision: Decision
    reason: str


async def check(client, sub_type, sub_id, permission, res_type, res_id) -> bool:
    resp = await client.CheckPermission(
        CheckPermissionRequest(
            consistency=Consistency(fully_consistent=True),
            resource=ObjectReference(object_type=res_type, object_id=res_id),
            permission=permission,
            subject=SubjectReference(
                object=ObjectReference(object_type=sub_type, object_id=sub_id)
            ),
        )
    )
    return resp.permissionship == CheckPermissionResponse.PERMISSIONSHIP_HAS_PERMISSION


async def read_delegator(client, agent_id) -> str | None:
    req = ReadRelationshipsRequest(
        consistency=Consistency(fully_consistent=True),
        relationship_filter=RelationshipFilter(
            resource_type="agent",
            optional_resource_id=agent_id,
            optional_relation="delegator",
        ),
    )
    async for resp in client.ReadRelationships(req):
        return resp.relationship.subject.object.object_id
    return None


async def decide(client, agent_id, permission, environment_id, action=None) -> AuthzResult:
    # `action` is the operator-facing verb for the reason text (e.g. "rollback");
    # it defaults to the permission actually checked (e.g. "deploy").
    action = action or permission
    if await check(client, "agent", agent_id, permission, "environment", environment_id):
        return AuthzResult(
            Decision.ALLOWED,
            f"agent:{agent_id} holds delegated '{action}' on environment:{environment_id}",
        )
    delegator = await read_delegator(client, agent_id)
    if delegator and await check(
        client, "user", delegator, permission, "environment", environment_id
    ):
        return AuthzResult(
            Decision.NEEDS_APPROVAL,
            f"agent:{agent_id} lacks '{action}'; delegator user:{delegator} holds it "
            f"— human approval required",
        )
    return AuthzResult(
        Decision.BLOCKED,
        f"neither agent:{agent_id} nor its delegator may '{action}' "
        f"environment:{environment_id}",
    )
