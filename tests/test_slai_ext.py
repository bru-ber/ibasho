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


def test_daemon_logout_and_relogin_after_logged_out_note():
    from ibasho.daemon import Daemon

    d = object.__new__(Daemon)
    d.login_state = "STATE_STARTED"
    d.login_failed = False
    d.logged_out = ""
    d.self_id = "11111111-1111-1111-1111-111111111111"
    d.self_names = {"display_name": "Comp"}
    d.vstate = types.SimpleNamespace(logged_in=True)
    appended = []
    d.events = types.SimpleNamespace(append=lambda kind, data: appended.append((kind, data)))
    relogins = []

    async def fake_on_logged_in():
        relogins.append(True)

    d.on_logged_in = fake_on_logged_in

    # Normal logout to login screen clears stale identity and emits daemon logged-out event.
    d.on_startup_state({"str": "STATE_LOGIN_WAIT"})
    assert d.vstate.logged_in is False
    assert d.self_id == "" and d.self_names == {}
    assert any(k == "daemon" and dta.get("msg") == "viewer logged out" for k, dta in appended)

    # Grid YouHaveBeenLoggedOut followed by fresh STATE_STARTED triggers on_logged_in().
    d.vstate.logged_in = True
    d.logged_out = "You have been logged out"

    async def run_relogin():
        d.on_startup_state({"str": "STATE_STARTED"})
        await asyncio.sleep(0)

    asyncio.run(run_relogin())
    assert d.logged_out == "" and relogins == [True]


def test_wait_structured_since_cursor_closes_status_gap_and_wakes_on_logout(tmp_path):
    from ibasho.cli.hear import Watcher, wake_worthy

    assert wake_worthy({"kind": "daemon", "data": {"msg": "viewer logged out"}}, me=None) is True

    # Simulate event seq=11 arriving between status(seq=10) and wait_events(since=10).
    all_events = [
        {"seq": 11, "t": 1.0, "kind": "daemon", "data": {"msg": "in world", "id": "11111111-1111-1111-1111-111111111111"}},
    ]

    class _FakeApi:
        ibasho = True

        def status(self, fresh=False):
            return {"seq": 11, "self": {"id": "11111111-1111-1111-1111-111111111111"}}

        def events(self, since, wait=0):
            return [e for e in all_events if e["seq"] > since]

        def op(self, *a, **kw):
            return {"people": [], "sessions": []}

    ctx = types.SimpleNamespace(
        api=_FakeApi(),
        cfg=types.SimpleNamespace(name="Comp", name_words=lambda: []),
        state_file=lambda name: tmp_path / name,
    )
    watcher = Watcher(ctx, wake_all_in_world=True, since=10)
    assert watcher.since == 10
    wakes = watcher.poll_wakes(wait=0.1)
    assert len(wakes) == 1 and wakes[0].seq == 11


def test_serialize_wake_native_dir_timestamp_and_digests():
    from ibasho.cli.hear import GroupDigest, ObjectDigest, Wake

    im_wake = Wake(
        line="im Bob: hello",
        seq=21,
        t=1700000000.5,
        event={
            "kind": "im",
            "seq": 21,
            "t": 1700000000.5,
            "data": {"dir": "in", "from": "Bob", "from_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "message": "hello"},
        },
    )
    im_item = slai_ext.serialize_wake(im_wake)
    assert im_item["kind"] == "im"
    assert im_item["direction"] == "in"
    assert im_item["t"] == 1700000000.5
    assert im_item["digest"] is None
    assert im_item["who"] is None

    gd = GroupDigest(None)
    assert gd.take({
        "seq": 22,
        "t": 1700000010.25,
        "kind": "im",
        "data": {
            "session_type": "group",
            "session_id": "11111111-1111-1111-1111-111111111111",
            "session_name": "Builders",
            "dir": "in",
            "from": "Alice",
            "message": "check the bridge",
        },
    }) is False
    g_wakes = gd.flush(force=True)
    assert len(g_wakes) == 1
    g_item = slai_ext.serialize_wake(g_wakes[0])
    assert g_item["kind"] == "group_digest"
    assert g_item["digest"] == "group"
    assert g_item["who"] == {"id": "11111111-1111-1111-1111-111111111111", "name": "Builders"}
    assert g_item["seq"] == 22
    assert g_item["t"] == 1700000010.25

    from ibasho.cli.hear import OBJECT_REPEAT

    od = ObjectDigest(None)
    oid = "22222222-2222-2222-2222-222222222222"
    for i in range(OBJECT_REPEAT + 1):
        od.take({
            "seq": 30 + i,
            "t": 1700000020.0 + i,
            "kind": "chat",
            "data": {"source": 2, "from_id": oid, "from": "Tram", "message": f"Stop {i}"},
        })
    o_wakes = od.flush(force=True)
    assert len(o_wakes) == 1
    o_item = slai_ext.serialize_wake(o_wakes[0])
    assert o_item["kind"] == "object_digest"
    assert o_item["digest"] == "object"
    assert o_item["who"] == {"id": oid, "name": "Tram"}
    assert o_item["seq"] == 30 + OBJECT_REPEAT
    assert o_item["t"] == 1700000020.0 + OBJECT_REPEAT

    unread_item = slai_ext.serialize_wake(Wake("unread: 1 IM in 1 conversation ('Bob') (`ibasho ims`)"))
    assert unread_item["kind"] == "unread_summary"
    assert unread_item["seq"] is None
    assert unread_item["t"] is None
    assert unread_item["digest"] is None


def test_waiter_collect_unifies_plain_and_structured_paths(tmp_path):
    import pytest

    from ibasho.api import Down
    from ibasho.mcp_server import Failed, Waiter

    ev_log = [
        {
            "seq": 11,
            "t": 1700000001.0,
            "kind": "im",
            "data": {"session_type": "p2p", "dir": "in", "from": "Bob", "message": "hi"},
        },
        {"seq": 12, "t": 1700000002.0, "kind": "daemon", "data": {"msg": "in world", "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"}},
    ]
    unread_sessions = [{"unread": 2, "type": "p2p", "name": "Bob"}]
    fail_down = False

    class _FakeApi:
        ibasho = True

        def status(self, fresh=False):
            return {"seq": 12, "self": {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"}}

        def events(self, since, wait=0):
            if fail_down:
                raise Down("daemon down")
            return [e for e in ev_log if e["seq"] > since]

        def op(self, svc, op, *a, **kw):
            if svc == "IbashoIM" and op == "sessions":
                return {"sessions": list(unread_sessions)}
            return {"people": []}

    ctx = types.SimpleNamespace(
        api=_FakeApi(),
        cfg=types.SimpleNamespace(name="Comp", name_words=list),
        state_file=lambda name: tmp_path / name,
    )
    waiter = Waiter()

    # First call (structured with since=10) initializes Watcher and returns unread summary first.
    first_raw = slai_ext.wait_structured(waiter, ctx, 0.05, since=10)
    first = json.loads(first_raw)
    assert first["quiet"] is False
    assert first["events"][0]["kind"] == "unread_summary"
    shared_watcher = waiter.watcher
    assert shared_watcher is not None and shared_watcher.since == 10

    # Plain-text wait reuses the same Watcher instance and cursor.
    unread_sessions.clear()
    plain = waiter.wait(ctx, 0.05)
    assert waiter.watcher is shared_watcher
    assert "hi" in plain and "in world" in plain
    assert shared_watcher.since == 12

    # Quiet timeout formats consistently for both modes.
    assert waiter.wait(ctx, 0.0) == "(nothing in 0 s)"
    quiet_obj = json.loads(slai_ext.wait_structured(waiter, ctx, 0.0))
    assert quiet_obj == {"v": 1, "quiet": True, "text": "(nothing in 0 s)", "events": []}

    # Busy lock raises Failed for both plain and structured waits.
    assert waiter.busy.acquire(blocking=False)
    try:
        with pytest.raises(Failed, match="another wait_events is still running"):
            slai_ext.wait_structured(waiter, ctx, 0.05)
    finally:
        waiter.busy.release()

    # Down resets waiter.watcher so the next call re-initializes from cursor.
    fail_down = True
    with pytest.raises(Down):
        slai_ext.wait_structured(waiter, ctx, 0.05)
    assert waiter.watcher is None

    # MCPL push bridge short-circuits both plain and structured modes identically.
    bridge = types.SimpleNamespace(pushing=True, not_pushed=lambda: ["ibasho.chat"])
    push_waiter = Waiter(bridge=bridge)
    plain_push = push_waiter.wait(ctx, 1.0)
    struct_push = json.loads(slai_ext.wait_structured(push_waiter, ctx, 1.0))
    assert struct_push["quiet"] is True
    assert struct_push["events"] == []
    assert struct_push["text"] == plain_push


