"""Focused tests for slAI V0 fork extensions in ibasho.slai_ext."""

from __future__ import annotations

import argparse
import asyncio
import json
import types

from ibasho import slai_ext


def test_clear_stale_self_identity_resets_daemon_fields():
    dummy = types.SimpleNamespace(self_id="11111111-1111-1111-1111-111111111111", self_names={"display_name": "Old"})
    slai_ext.clear_stale_self_identity(dummy)
    assert dummy.self_id == ""
    assert dummy.self_names == {}


def test_daemon_on_startup_state_clears_stale_self_identity():
    from ibasho.daemon import Daemon

    d = object.__new__(Daemon)
    d.login_state = ""
    d.login_failed = True
    d.logged_out = "previous"
    d.self_id = "stale-avatar-id"
    d.self_names = {"display_name": "Stale"}
    d.vstate = types.SimpleNamespace(logged_in=False)

    created = []

    async def fake_on_logged_in():
        return None

    d.on_logged_in = fake_on_logged_in

    async def run():
        orig = asyncio.create_task

        def capture(coro):
            task = orig(coro)
            created.append(task)
            return task

        asyncio.create_task = capture
        try:
            d.on_startup_state({"str": "STATE_STARTED"})
            assert d.self_id == ""
            assert d.self_names == {}
            assert d.vstate.logged_in is True
            for t in created:
                await t
        finally:
            asyncio.create_task = orig

    asyncio.run(run())


def test_status_json_skips_money_balance(monkeypatch):
    from ibasho.cli import lifecycle, money

    calls = []

    monkeypatch.setattr(
        lifecycle,
        "status",
        lambda ctx, ns: calls.append(("status", ns.json)),
    )
    monkeypatch.setattr(
        money,
        "balance",
        lambda ctx, ns: calls.append(("balance", None)),
    )
    ctx = types.SimpleNamespace(
        cfg=types.SimpleNamespace(token_file=types.SimpleNamespace(exists=lambda: True)),
        api=types.SimpleNamespace(is_up=lambda: {"logged_in": True}),
    )

    slai_ext.run_status(ctx, json_output=True)
    assert calls == [("status", True)]

    calls.clear()
    slai_ext.run_status(ctx, json_output=False)
    assert calls == [("status", False), ("balance", None)]


def test_serialize_wake_includes_raw_metadata():
    wake = types.SimpleNamespace(
        line="notify TeleportLure from Bob",
        seq=42,
        t=1700000000.5,
        event={
            "kind": "notify",
            "seq": 42,
            "t": 1700000000.5,
            "data": {
                "id": "notif-123",
                "name": "TeleportLure",
                "from_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "from_name": "Bob",
                "region": "Meadow",
                "replayed": True,
                "direction": "in",
            },
        },
    )
    item = slai_ext.serialize_wake(wake)
    assert item["text"] == "notify TeleportLure from Bob"
    assert item["seq"] == 42
    assert item["kind"] == "notify"
    assert item["subtype"] == "TeleportLure"
    assert item["notification_id"] == "notif-123"
    assert item["replay"] is True
    assert item["direction"] == "in"
    assert item["sender"]["from_id"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert item["sender"]["region"] == "Meadow"
    assert item["data"]["name"] == "TeleportLure"


def test_watcher_wake_all_in_world_unconditional(world_connected):
    from ibasho.cli.common import Ctx
    from ibasho.cli.hear import Watcher

    w = world_connected
    ctx = Ctx(argparse.Namespace(config=str(w.cfg.path)))
    default_watcher = Watcher(ctx)
    unconditional_watcher = Watcher(ctx, wake_all_in_world=True)

    ev = {"seq": 999, "t": 1.0, "kind": "daemon", "data": {"msg": "in world"}}
    assert default_watcher.wake(ev) is None
    wake = unconditional_watcher.wake(ev)
    assert wake is not None
    assert "in world" in wake.line


def test_mcp_status_json_and_wait_events_structured(world_connected):
    w = world_connected
    from mcp.shared.memory import create_connected_server_and_client_session

    from ibasho import mcp_server

    async def exercise():
        server = mcp_server.build(config=str(w.cfg.path))
        async with create_connected_server_and_client_session(server._mcp_server) as client:
            st_res = await client.call_tool("status", {"json": True})
            st_text = "\n".join(b.text for b in st_res.content if getattr(b, "type", "") == "text")
            st_obj = json.loads(st_text)
            assert st_obj["logged_in"] is True
            assert st_obj["self"]["id"] == w.viewer.self_id
            assert "L$" not in st_text

            w.call(w.daemon.events.append, "daemon", {"msg": "in world"})
            ev_res = await client.call_tool("wait_events", {"timeout": 2, "structured": True})
            ev_text = "\n".join(b.text for b in ev_res.content if getattr(b, "type", "") == "text")
            ev_obj = json.loads(ev_text)
            assert ev_obj["v"] == 1
            assert ev_obj["quiet"] is False
            assert any(e["kind"] == "daemon" and e["subtype"] == "in world" for e in ev_obj["events"])

    asyncio.run(exercise())
