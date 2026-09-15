"""Persistent hourly email digest. Failed delivery keeps queued events."""
import hashlib
import time
from pathlib import Path

from base_xi import read_cache, write_cache


def hourly_digest(data_dir, config, events, sender, now=None):
    now = time.time() if now is None else now
    path = Path(data_dir) / "email_digest.json"
    state = read_cache(path)
    pending = state.get("pending", {})
    seen = state.get("seen", {})
    seen = {key: stamp for key, stamp in seen.items() if now - stamp < 72 * 3600}
    if not config.get("email_notifications"):
        return {"sent": False, "reason": "E-Mail deaktiviert"}
    for event in events:
        key = hashlib.sha256(event["id"].encode("utf-8")).hexdigest()
        if key not in seen and key not in pending:
            pending[key] = {"text": event["text"], "time": now}
    interval = max(60, int(config.get("email_digest_minutes", 60))) * 60
    # First digest waits one full hour; even a restart preserves this boundary.
    next_at = state.get("next_at", now + interval)
    result = {"sent": False, "reason": "Für stündliche Sammelmail vorgemerkt",
              "pending": len(pending), "next_at": next_at}
    state.update(pending=pending, seen=seen, next_at=next_at)
    write_cache(path, state)
    if pending and now >= next_at:
        # Persist the attempt before SMTP; no retry storm after ambiguous delivery.
        state["next_at"] = now + interval
        write_cache(path, state)
        lines = ["KICKBASE – Zusammenfassung seit der letzten Sammelmail", ""]
        lines.extend(item["text"] for item in pending.values())
        receipt = sender(config, "KICKBASE – stündliche Zusammenfassung", lines)
        result.update(receipt, next_at=state["next_at"])
        if receipt.get("sent"):
            state["seen"].update({key: now for key in pending})
            state["pending"] = {}
            state["last_sent"] = now
            result["pending"] = 0
        write_cache(path, state)
    return result
