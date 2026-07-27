# goose × SpiceDB: Delegated Agent Authorization

A DevOps deployment agent built on [goose](https://github.com/aaif-goose/goose) (AAIF) whose every
mutating action is authorized by [SpiceDB](https://github.com/authzed/spicedb). The agent can only do what a
human explicitly, and revocably, delegated to it — even though goose runs with your full machine
credentials.

## The model

- `user:alice` (SRE) can deploy staging + production and approve production deploys.
- `agent:goose_alice` acts *for* alice, delegated a **staging-only, 1-hour** deploy grant.
- Every tool call resolves to one of three outcomes:
  - **✅ ALLOWED** — the agent holds the delegated permission (within its time window).
  - **⏸️ NEEDS APPROVAL** — the agent can't, but its delegator can → escalate to a human.
  - **🚫 BLOCKED** — neither the agent nor its delegator can (e.g. `destroy`).

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d
python bootstrap.py
```

(Python 3.10–3.12 recommended; 3.14 had dependency-build issues during development.)

Register the extension in goose (see `goose-extension.md`), then `goose session`.

Installing and running goose is optional. This repo does not require goose or an LLM API key —
the decision arc goose would drive is proven deterministically by `tests/test_arc.py` (run via
`pytest -v`), which
calls the same `authz.decide` function `deploybot_server.py` calls on every tool invocation.
`goose-extension.md` includes a manual verification checklist for anyone who does have goose and
an LLM key handy, but it was not run as part of building this repo.

## The demo arc

| Ask goose | Outcome | Why |
|-----------|---------|-----|
| Deploy checkout to staging | ✅ ALLOWED | delegated, in-window |
| Deploy checkout to production | ⏸️ NEEDS APPROVAL | alice can, the agent can't |
| `python approve.py --approver alice --env production`, retry | ✅ ALLOWED | 10-min grant written |
| Tear down production | 🚫 BLOCKED | no agent path to `destroy`; alice can't either |
| `python revoke.py --env staging`, retry staging | ⏸️ NEEDS APPROVAL | autonomy revoked instantly |

## Web front end

A goose-style chat UI that drives the whole arc in the browser — useful for demos and screen
recordings. It's a thin FastAPI shell (`web.py`) over the *same* code the MCP server uses, so what
you see is exactly what SpiceDB decides.

```bash
python web.py     # then open http://127.0.0.1:8000
```

Type requests (or click the preset chips): *"Deploy checkout to staging"*, *"…to production"*,
*"Tear down production"*. A live **authority bar** shows the delegation chain
`user:alice ──▶ agent:goose_alice ──▶ staging` with an expiry countdown; **Approve prod**,
**Revoke staging**, and **Revoke prod** buttons trigger the human-in-the-loop, and **Reset**
re-seeds for a clean take. Revoke staging and you'll see the production grant drop to a dashed
**suspended** chip — the cascade below, live. No LLM key needed — requests are parsed by a small
rule-based matcher, not a model.

## Time-bound delegation

The staging grant uses SpiceDB's built-in [relationship expiration](https://authzed.com/docs/spicedb/concepts/expiring-relationships)
(`relation agent_deployer: agent with expiration`), written with an `optional_expires_at` timestamp
rather than a caveat. It's evaluated server-side (no request-time `now` to pass) and garbage-collected
automatically — which is why SpiceDB's best practices prefer it over a caveat for expiry logic.

`bootstrap.py --window-minutes 0` seeds an already-expired staging grant; SpiceDB then treats it as
absent, so the agent's autonomous staging deploy drops to NEEDS APPROVAL — the same mechanism that
expires a real incident-window grant, shown without waiting.

> Expiration is still an experimental feature in SpiceDB (v1.40+), so `docker-compose.yml` starts the
> server with `--enable-experimental-relationship-expiration`. Setup stays one-command.

## Contingent autonomy (the cascade)

Production autonomy is *contingent on* staging autonomy: revoke the agent's staging delegation and
its production autonomy disappears too — with no second delete. This lives in the schema, not app code:

```zed
relation gated_by: environment                              // production -> staging (staging -> itself)
permission agent_deploy = agent_deployer & gated_by->agent_deployer
permission deploy = direct_deployer + agent_deploy
```

`agent_deploy` requires the agent to hold *this* environment's grant **and** the gating environment's
grant. Staging gates itself (base case); production is gated by staging. So the moment staging's
`agent_deployer` tuple is gone, `production#agent_deploy` evaluates false — the agent drops to
NEEDS APPROVAL for production automatically.

Because it's contingent *evaluation* rather than a delete, the production grant is **suspended**, not
erased: if staging autonomy returns while production's window is still open, production resumes. The
UI shows a suspended grant as a dashed chip; `tests/test_lifecycle.py::test_revoke_staging_cascades_to_prod`
and the `goose_prodonly` assertions in `validation.yaml` pin the behavior.

## How it works

`deploybot_server.py` is a stdio MCP server goose loads as an extension. Each tool calls
`authz.decide(...)`, which runs a SpiceDB `CheckPermission` for `agent:goose_alice`; on denial it
reads the agent's `delegator` and re-checks as that human to distinguish NEEDS APPROVAL from BLOCKED.

## Tests

```bash
pytest -v                      # integration: 18 tests against a live SpiceDB (needs docker compose up)
zed validate validation.yaml   # schema-logic unit test of the delegation matrix (no server needed)
```

`validation.yaml` references `schema.zed` directly via `schemaFile:`, so the schema tests can't drift
from what the app actually writes.

## The authorization spectrum (for context)

- **This demo — enforced:** the tool checks SpiceDB before acting; the agent can't bypass it.
- **Advisory:** the agent *asks* SpiceDB and self-censors — a naive/adversarial agent can skip it.
- **Proxy:** a gateway in front of a real deploy API enforces per request — how this evolves in prod.
