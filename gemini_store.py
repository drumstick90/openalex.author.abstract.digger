"""
Gemini Store

Global state management and file I/O for Gemini analysis.
Keeps session data (works, extracts, progress flag) and handles
persistence to a temp-dir JSON cache keyed by author ID.
"""

import json
import os
import tempfile
from typing import Optional


# ---------------------------------------------------------------------------
# In-memory state
# ---------------------------------------------------------------------------

_stored_works: list[dict] = []
_author_name: Optional[str] = None
_author_id: Optional[str] = None
_cached_extracts: list[dict] = []
_extraction_in_progress: bool = False


def store_works(works: list[dict], author_name: str = None, author_id: str = None):
    """Store works for later analysis. Clears any previous extract cache."""
    global _stored_works, _author_name, _author_id, _cached_extracts
    _stored_works = works
    _author_name = author_name
    _author_id = author_id
    _cached_extracts = []
    print(f"📦 Stored {len(works)} works for {author_name or 'unknown author'}")


def get_stored_works() -> tuple[list[dict], Optional[str]]:
    return _stored_works, _author_name


def get_cached_extracts() -> list[dict]:
    return _cached_extracts


def set_cached_extracts(extracts: list[dict]):
    global _cached_extracts
    _cached_extracts = extracts
    print(f"💾 Cached {len(extracts)} extracts")


def is_extraction_in_progress() -> bool:
    return _extraction_in_progress


def set_extraction_in_progress(value: bool):
    global _extraction_in_progress
    _extraction_in_progress = value


def clear_stored():
    global _stored_works, _author_name, _author_id, _cached_extracts
    _stored_works = []
    _author_name = None
    _author_id = None
    _cached_extracts = []


# ---------------------------------------------------------------------------
# File I/O (temp-dir cache)
# ---------------------------------------------------------------------------

def get_extraction_cache_path(author_id: str = None) -> str:
    aid = author_id or _author_id or "unknown"
    return os.path.join(tempfile.gettempdir(), f"openalex_extracts_{aid}.json")


def save_extracts_to_file(extracts: list[dict], author_id: str = None) -> str:
    path = get_extraction_cache_path(author_id)
    with open(path, 'w') as f:
        json.dump({
            'author_id': author_id or _author_id,
            'author_name': _author_name,
            'extracts': extracts,
            'count': len(extracts),
        }, f)
    print(f"💾 Saved {len(extracts)} extracts to {path}")
    return path


def load_extracts_from_file(author_id: str = None) -> list[dict]:
    path = get_extraction_cache_path(author_id)
    try:
        with open(path, 'r') as f:
            data = json.load(f)
            return data.get('extracts', [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []
