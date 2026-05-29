"""
Gemini Store

Session-scoped state management and file I/O for AI analysis.
Keeps per-session works/extracts/progress and persists extracts
to temp files keyed by session + author.
"""

import json
import os
import tempfile
import time
from typing import Optional


# ---------------------------------------------------------------------------
# In-memory state (session scoped)
# ---------------------------------------------------------------------------

_SESSION_TTL_SECONDS = 60 * 60 * 6  # 6h inactivity window
_session_state: dict[str, dict] = {}


def _new_state() -> dict:
    return {
        "stored_works": [],
        "author_name": None,
        "author_id": None,
        "cached_extracts": [],
        "extraction_in_progress": False,
        "last_access": time.time(),
    }


def _touch_session(session_scope: str) -> dict:
    state = _session_state.get(session_scope)
    if not state:
        state = _new_state()
        _session_state[session_scope] = state
    state["last_access"] = time.time()
    return state


def prune_expired_sessions():
    """Best-effort cleanup for old in-memory session state."""
    now = time.time()
    expired = [
        scope for scope, state in _session_state.items()
        if now - state.get("last_access", now) > _SESSION_TTL_SECONDS
    ]
    for scope in expired:
        _session_state.pop(scope, None)


def store_works(
    works: list[dict],
    author_name: str = None,
    author_id: str = None,
    session_scope: str = "global",
):
    """Store works for later analysis for a specific session scope."""
    prune_expired_sessions()
    state = _touch_session(session_scope)
    state["stored_works"] = works
    state["author_name"] = author_name
    state["author_id"] = author_id
    state["cached_extracts"] = []
    print(f"📦 Stored {len(works)} works for {author_name or 'unknown author'}")


def get_stored_works(session_scope: str = "global") -> tuple[list[dict], Optional[str]]:
    prune_expired_sessions()
    state = _touch_session(session_scope)
    return state["stored_works"], state["author_name"]


def get_cached_extracts(session_scope: str = "global") -> list[dict]:
    prune_expired_sessions()
    state = _touch_session(session_scope)
    return state["cached_extracts"]


def set_cached_extracts(extracts: list[dict], session_scope: str = "global"):
    prune_expired_sessions()
    state = _touch_session(session_scope)
    state["cached_extracts"] = extracts
    print(f"💾 Cached {len(extracts)} extracts")


def is_extraction_in_progress(session_scope: str = "global") -> bool:
    prune_expired_sessions()
    state = _touch_session(session_scope)
    return state["extraction_in_progress"]


def set_extraction_in_progress(value: bool, session_scope: str = "global"):
    prune_expired_sessions()
    state = _touch_session(session_scope)
    state["extraction_in_progress"] = value


def clear_stored(session_scope: str = "global"):
    _session_state[session_scope] = _new_state()


# ---------------------------------------------------------------------------
# File I/O (temp-dir cache)
# ---------------------------------------------------------------------------

def get_extraction_cache_path(
    author_id: str = None,
    session_scope: str = "global",
) -> str:
    state = _touch_session(session_scope)
    aid = author_id or state.get("author_id") or "unknown"
    safe_scope = "".join(ch for ch in session_scope if ch.isalnum() or ch in ("-", "_"))[:64]
    return os.path.join(tempfile.gettempdir(), f"openalex_extracts_{safe_scope}_{aid}.json")


def save_extracts_to_file(
    extracts: list[dict],
    author_id: str = None,
    session_scope: str = "global",
) -> str:
    state = _touch_session(session_scope)
    path = get_extraction_cache_path(author_id, session_scope=session_scope)
    with open(path, 'w') as f:
        json.dump({
            'author_id': author_id or state.get("author_id"),
            'author_name': state.get("author_name"),
            'extracts': extracts,
            'count': len(extracts),
            'session_scope': session_scope,
        }, f)
    print(f"💾 Saved {len(extracts)} extracts to {path}")
    return path


def load_extracts_from_file(
    author_id: str = None,
    session_scope: str = "global",
) -> list[dict]:
    path = get_extraction_cache_path(author_id, session_scope=session_scope)
    try:
        with open(path, 'r') as f:
            data = json.load(f)
            return data.get('extracts', [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []
