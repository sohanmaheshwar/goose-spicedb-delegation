import json

import deploybot_server as server


async def test_deploy_staging_bumps_version(seeded, tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({"staging": {"checkout": 1}}))
    monkeypatch.setattr(server, "STATE_PATH", state_file)
    out = await server.do_deploy("checkout", "staging")
    assert "ALLOWED" in out
    assert json.loads(state_file.read_text())["staging"]["checkout"] == 2


async def test_deploy_production_needs_approval_no_mutation(seeded, tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({"production": {"checkout": 1}}))
    monkeypatch.setattr(server, "STATE_PATH", state_file)
    out = await server.do_deploy("checkout", "production")
    assert "NEEDS APPROVAL" in out
    assert json.loads(state_file.read_text())["production"]["checkout"] == 1


async def test_destroy_blocked_no_mutation(seeded, tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({"production": {"checkout": 1}}))
    monkeypatch.setattr(server, "STATE_PATH", state_file)
    out = await server.do_destroy("production")
    assert "BLOCKED" in out
    assert "production" in json.loads(state_file.read_text())


async def test_rollback_staging_decrements_and_floors(seeded, tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({"staging": {"checkout": 2}}))
    monkeypatch.setattr(server, "STATE_PATH", state_file)
    out = await server.do_rollback("checkout", "staging")
    assert "ALLOWED" in out
    assert json.loads(state_file.read_text())["staging"]["checkout"] == 1
    # rollback again: version floors at 1, never below
    await server.do_rollback("checkout", "staging")
    assert json.loads(state_file.read_text())["staging"]["checkout"] == 1


async def test_rollback_absent_service_is_noop(seeded, tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({"staging": {}}))
    monkeypatch.setattr(server, "STATE_PATH", state_file)
    out = await server.do_rollback("checkout", "staging")
    assert "nothing to roll back" in out.lower()
    # No phantom v1 entry was written.
    assert json.loads(state_file.read_text()) == {"staging": {}}


async def test_list_environments_only_shows_viewable(seeded, tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({"staging": {"checkout": 1}, "production": {"checkout": 1}}))
    monkeypatch.setattr(server, "STATE_PATH", state_file)
    out = await server.do_list_environments()
    # agent:goose_alice may view staging (it has an agent_deployer grant) but not production.
    assert "staging" in out
    assert "production" not in out
