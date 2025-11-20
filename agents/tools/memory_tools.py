"""Session-aware document summary caching helpers.

Best practice alignment:
- Use `tool_context: ToolContext` parameter name (ADK examples)
- Return structured dicts with a `status` field
- Use scoped key prefix `temp:` for session-specific data (ADK scopes: temp/user/app)
- Cap list size to prevent unbounded growth
- Agent-specific keys since URLs never overlap between domains

Schema:
  temp:likumi_docs: [ { url, title, summary, metadata } ]
  temp:tap_docs: [ { url, title, summary, metadata } ]
  temp:saeima_docs: [ { url, title, summary, metadata } ]
"""
from typing import Dict, Any, List
from google.adk.tools.tool_context import ToolContext

MAX_DOCS = 100


def _get_docs_key(url: str) -> str:
	"""Determine storage key based on URL domain."""
	if "likumi.lv" in url:
		return "temp:likumi_docs"
	elif "tapportals.mk.gov.lv" in url or "tap.gov.lv" in url:
		return "temp:tap_docs"
	elif "saeima.lv" in url or "titania.saeima.lv" in url:
		return "temp:saeima_docs"
	else:
		# Fallback for unknown domains
		return "temp:other_docs"

def get_cached_summary(url: str, tool_context: ToolContext) -> Dict[str, Any]:
	"""Lookup a previously stored document summary.

	Args:
		url: Document URL to retrieve.
		tool_context: ADK ToolContext providing session state access.

	Returns:
		{"status": "hit", "doc": {...}} if found
		{"status": "miss"} if not found
	"""
	docs_key = _get_docs_key(url)
	docs: List[Dict[str, Any]] = tool_context.state.get(docs_key, [])
	for doc in docs:
		if doc.get("url") == url:
			return {"status": "hit", "doc": doc}
	return {"status": "miss"}


def store_document_summary(
	url: str,
	title: str,
	summary: str,
	metadata: Dict[str, Any],
	tool_context: ToolContext,
) -> Dict[str, Any]:
	"""Store a document summary if not already present.

	Args:
		url: Document URL.
		title: Document title.
		summary: Short relevance summary.
		metadata: Additional metadata dict.
		tool_context: ADK ToolContext for state access.

	Returns:
		{"status": "stored"} when added
		{"status": "exists"} if already present
		{"status": "trimmed"} if added after trimming oldest
	"""
	docs_key = _get_docs_key(url)
	docs: List[Dict[str, Any]] = tool_context.state.setdefault(docs_key, [])
	for doc in docs:
		if doc.get("url") == url:
			return {"status": "exists"}
	docs.append({"url": url, "title": title, "summary": summary, "metadata": metadata})
	trimmed = False
	if len(docs) > MAX_DOCS:
		docs.pop(0)
		trimmed = True
	return {"status": "trimmed" if trimmed else "stored"}

