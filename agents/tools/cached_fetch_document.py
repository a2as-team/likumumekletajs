"""Caching wrapper tool for Likumi.lv document fetches.

Reduces duplicate fetch_likumi_document calls within an agent session.
Uses an in-module cache keyed by URL. Returns a flag 'cached': True when
serving from cache. Keeps the original structure of fetch_likumi_document
responses so the agent can treat both identically.

Note: Session-level persistence can be reinforced by agent instructions
to also store summarized documents in session.state['likumi_docs'].
"""

from typing import Dict, Any

from .likumi_fetch_document import fetch_likumi_document

_cache: Dict[str, Dict[str, Any]] = {}


def cached_fetch_document(url: str) -> Dict[str, Any]:
    """Return cached document fetch result or fetch and store if missing.

    Args:
        url: Full Likumi.lv or Vestnesis document URL.

    Returns:
        Dict with keys: url, title, full_text, metadata, cached (bool)
    """
    if url in _cache:
        result = dict(_cache[url])
        result['cached'] = True
        return result

    fetched = fetch_likumi_document(url)
    fetched['cached'] = False
    _cache[url] = fetched
    return fetched
