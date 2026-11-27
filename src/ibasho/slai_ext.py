"""Isolated slAI Companion extensions for the Ibasho V0 fork.

Keeping slAI-specific helpers isolated here minimizes merge conflicts with
upstream ``ibasho`` while preserving default upstream tool behavior.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

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
    line = str(getattr(wake, "line", "") or "")
    event = wake.event if isinstance(getattr(wake, "event", None), dict) else {}
    raw_data = event.get("data") if isinstance(event.get("data"), dict) else {}
    digest_raw = getattr(wake, "digest", None)
    digest = str(digest_raw) if digest_raw not in (None, "") else None
    raw_who = getattr(wake, "who", None)
    who: dict[str, Any] | None = None
    if isinstance(raw_who, (tuple, list)) and len(raw_who) == 2:
        who = {
            "id": _bound_json_value(str(raw_who[0] or ""), max_str=256),
            "name": _bound_json_value(str(raw_who[1] or ""), max_str=256),
        }

    kind = str(event.get("kind") or "")
    if not kind and digest:
        kind = f"{digest}_digest"
    elif not kind and not event and getattr(wake, "seq", 0) in (None, 0) and line.startswith("unread:"):
        kind = "unread_summary"

    subtype = (
        raw_data.get("name")
        or raw_data.get("what")
        or raw_data.get("type")
        or (raw_data.get("msg") if kind == "daemon" else None)
    )
    direction = raw_data.get("dir") or raw_data.get("direction")
    notification_id = raw_data.get("id") if kind == "notify" else None
    replay = bool(raw_data.get("replayed"))

    raw_seq = getattr(wake, "seq", None)
    seq = raw_seq if (raw_seq not in (None, 0) or event or digest) else None
    raw_t = getattr(wake, "t", None)
    if not raw_t and isinstance(event.get("t"), (int, float)):
        raw_t = event.get("t")
    event_t = raw_t if isinstance(raw_t, (int, float)) and not isinstance(raw_t, bool) and raw_t > 0 else None

    sender: dict[str, Any] = {}
    for field in _SENDER_FIELDS:
        if field in raw_data and raw_data[field] not in (None, ""):
            sender[field] = _bound_json_value(raw_data[field], max_str=256)

    bounded_data = _bound_json_value(raw_data)
    serialized_data = json.dumps(bounded_data, ensure_ascii=False, separators=(",", ":"))
    if len(serialized_data.encode("utf-8")) > _MAX_DATA_BYTES:
        bounded_data = {"_truncated": True, "keys": sorted(str(k) for k in raw_data)[:40]}

    return {
        "text": line,
        "seq": seq,
        "t": event_t,
        "kind": kind or None,
        "subtype": str(subtype) if subtype not in (None, "") else None,
        "digest": digest,
        "who": who,
        "direction": str(direction) if direction not in (None, "") else None,
        "notification_id": str(notification_id) if notification_id not in (None, "") else None,
        "replay": replay,
        "sender": sender,
        "data": bounded_data,
    }


def wait_structured(waiter: Any, ctx: Any, timeout: float, since: int | None = None) -> str:
    """Format collected ``Waiter`` wakes as structured JSON alongside plain text."""
    wakes, push_msg = waiter.collect(ctx, timeout, since=since)
    if push_msg is not None:
        return json.dumps({"v": 1, "quiet": True, "text": push_msg, "events": []}, ensure_ascii=False)
    events = [serialize_wake(w) for w in wakes]
    lines = [str(getattr(w, "line", "") or "") for w in wakes]
    payload = {
        "v": 1,
        "quiet": not events,
        "text": "\n".join(lines) if lines else f"(nothing in {timeout:g} s)",
        "events": events,
    }
    return json.dumps(payload, ensure_ascii=False)
