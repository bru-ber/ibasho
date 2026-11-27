"""Isolated slAI Companion extensions for the Ibasho V0 fork.

Keeping slAI-specific helpers isolated here minimizes merge conflicts with
upstream ``ibasho`` while preserving default upstream tool behavior.
"""

from __future__ import annotations

import argparse
import json
import time
from typing import Any

from .api import Down

_MAX_DATA_BYTES = 4096
_SENDER_FIELDS = (
    "from_id",
    "from_name",
    "from",
    "sender_id",
    "sender",
    "requester_id",
    "requester",
    "agent_id",
    "session_id",
    "object_id",
    "object_name",
    "region",
)


def clear_stale_self_identity(daemon_obj: Any) -> None:
    """Clear cached viewer avatar identity on disconnect or fresh login start."""
    daemon_obj.self_id = ""
    daemon_obj.self_names = {}


def run_status(ctx: Any, *, json_output: bool = False) -> None:
    """Execute ``status`` with optional raw JSON output.

    When ``json_output=True``, reuse ``lifecycle.status(..., json=True)`` and
    skip ``money.balance(...)`` so status checks remain pure JSON and avoid an
    extra balance call.
    """
    from .cli import lifecycle, money

    lifecycle.status(ctx, argparse.Namespace(json=bool(json_output)))
    if json_output:
        return
    st = ctx.api.is_up() if ctx.cfg.token_file.exists() else None
    if st and st.get("logged_in"):
        money.balance(ctx, argparse.Namespace())


def _bound_json_value(value: Any, *, max_str: int = 1024, depth: int = 0) -> Any:
    if depth >= 4:
        return "<truncated>"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value if len(value) <= max_str else value[:max_str] + "...[truncated]"
    if isinstance(value, (list, tuple)):
        return [_bound_json_value(v, max_str=max_str, depth=depth + 1) for v in value[:32]]
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for idx, (k, v) in enumerate(value.items()):
            if idx >= 40:
                out["_truncated_keys"] = True
                break
            out[str(k)] = _bound_json_value(v, max_str=max_str, depth=depth + 1)
        return out
    return str(value)[:max_str]


def serialize_wake(wake: Any) -> dict[str, Any]:
    """Serialize a ``cli.hear.Wake`` into structured metadata alongside text."""
    event = wake.event if isinstance(getattr(wake, "event", None), dict) else {}
    raw_data = event.get("data") if isinstance(event.get("data"), dict) else {}
    kind = str(event.get("kind") or "")
    subtype = (
        raw_data.get("name")
        or raw_data.get("what")
        or raw_data.get("type")
        or (raw_data.get("msg") if kind == "daemon" else None)
    )
    direction = raw_data.get("direction")
    notification_id = raw_data.get("id") if kind == "notify" else None
    replay = bool(raw_data.get("replayed"))

    sender: dict[str, Any] = {}
    for field in _SENDER_FIELDS:
        if field in raw_data and raw_data[field] not in (None, ""):
            sender[field] = _bound_json_value(raw_data[field], max_str=256)

    bounded_data = _bound_json_value(raw_data)
    serialized_data = json.dumps(bounded_data, ensure_ascii=False, separators=(",", ":"))
    if len(serialized_data.encode("utf-8")) > _MAX_DATA_BYTES:
        bounded_data = {"_truncated": True, "keys": sorted(str(k) for k in raw_data)[:40]}

    return {
        "text": str(getattr(wake, "line", "") or ""),
        "seq": getattr(wake, "seq", None),
        "t": getattr(wake, "t", None),
        "kind": kind or None,
        "subtype": str(subtype) if subtype not in (None, "") else None,
        "direction": str(direction) if direction not in (None, "") else None,
        "notification_id": str(notification_id) if notification_id not in (None, "") else None,
        "replay": replay,
        "sender": sender,
        "data": bounded_data,
    }


def wait_structured(
    waiter: Any, ctx: Any, timeout: float, failed_cls: type[Exception], since: int | None = None
) -> str:
    """Wait for events like ``Waiter.wait``, returning structured JSON alongside text."""
    from .cli.hear import Watcher, unread_line

    if waiter.bridge and waiter.bridge.pushing:
        waiter.watcher = None
        left = waiter.bridge.not_pushed()
        msg = (
            "(events come to you by themselves here: your host takes them as MCPL pushes, so there's no "
            "need to wait for them. When there's nothing else to do, end your turn, and the world will "
            "wake you" + (f"; not pushed: {', '.join(left)}" if left else "") + ")"
        )
        return json.dumps({"v": 1, "quiet": True, "text": msg, "events": []}, ensure_ascii=False)

    if not waiter.busy.acquire(blocking=False):
        raise failed_cls("another wait_events is still running")
    try:
        events: list[dict[str, Any]] = []
        lines: list[str] = []
        if waiter.watcher is None or since is not None:
            waiter.watcher = Watcher(ctx, wake_all_in_world=True, since=since)
            if line := unread_line(ctx):
                lines.append(line)
                events.append({
                    "text": line,
                    "seq": None,
                    "t": None,
                    "kind": "unread_summary",
                    "subtype": None,
                    "direction": None,
                    "notification_id": None,
                    "replay": False,
                    "sender": {},
                    "data": {},
                })
        end = time.time() + timeout
        while not events and (left := end - time.time()) > 0:
            wakes = waiter.watcher.poll_wakes(min(25.0, left))
            for w in wakes:
                lines.append(w.line)
                events.append(serialize_wake(w))
        quiet = not events
        payload = {
            "v": 1,
            "quiet": quiet,
            "text": "\n".join(lines) if lines else f"(nothing in {timeout:g} s)",
            "events": events,
        }
        return json.dumps(payload, ensure_ascii=False)
    except Down:
        waiter.watcher = None
        raise
    finally:
        waiter.busy.release()
