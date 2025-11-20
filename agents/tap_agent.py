from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.tools.tool_context import ToolContext
from google.adk.planners import BuiltInPlanner
from google.genai import types
from .base_config import MODEL_CONFIGS
from .tools import tap_scraper, fetch_tap_document, get_cached_summary, store_document_summary
from .tools.enforcement_wrapper import get_enforcer, reset_enforcer
from .tools.workflow_check import check_workflow_complete


# Wrap TAP scraper tool
def wrapped_tap_scraper(date_from: str, date_to: str, date_type: str = "all",
                        keyword_query: str = "", max_results: int = 1000,
                        enable_browser_fallback: bool = True,
                        tool_context: ToolContext = None):
    """Wrapped tap_scraper that tracks results for enforcement."""
    # Original tool doesn't need tool_context, but wrapper signature includes it
    result = tap_scraper(date_from, date_to, date_type, keyword_query,
                        max_results, enable_browser_fallback)
    get_enforcer().track_tool_call('tap_scraper', result)
    return result


# Wrap TAP fetch tool
def wrapped_fetch_tap_document(url: str, tool_context: ToolContext = None):
    """Wrapped fetch_tap_document that tracks calls for enforcement."""
    result = fetch_tap_document(url)
    get_enforcer().track_tool_call('fetch_tap_document', result)
    return result


# Wrap memory tools (REUSE from Likumi - same wrappers)
def wrapped_get_cached_summary(url: str, tool_context: ToolContext = None):
    """Wrapped get_cached_summary that tracks calls for enforcement."""
    # Memory tool REQUIRES tool_context - pass it through
    result = get_cached_summary(url, tool_context)
    get_enforcer().track_tool_call('get_cached_summary', result)
    return result


def create_tap_agent():
    """
    Create the TAP Portal specialist agent with session-based memory and workflow enforcement.

    This agent searches TAP Portal for 6 document types:
    - Legal acts (draft legislation)
    - Government meetings (Cabinet Ministers & State Secretaries)
    - Public participation documents
    - Government tasks/assignments
    - Declassified documents
    - Informative notices
    
    Features:
    - Searches across multiple date fields (submission, deadline, publication, etc.)
    - Shared session memory for efficiency
    - Workflow enforcement (fetches all documents before answering)
    - Post-fetch intelligent filtering using LLM capabilities

    Returns:
        LlmAgent: Configured TAP Portal specialist agent
    """
    config = MODEL_CONFIGS["specialist"]

    # CRITICAL: Reset enforcer for fresh agent instance
    reset_enforcer()

    agent = LlmAgent(
        name="TAPAgent",
        model=Gemini(
            model=config["model"],
            retry_options=config["retry_options"]
        ),
        generate_content_config=types.GenerateContentConfig(
            temperature=0.4  # Balanced temperature for reliability with flexibility
        ),
        planner=BuiltInPlanner(
            thinking_config=types.ThinkingConfig(
                include_thoughts=False,  # Don't include internal reasoning in response
                thinking_budget=4096,     # Allow moderate thinking for complex workflows
            )
        ),
        description="Searches TAP Portal for government documents: draft legislation, meetings, consultations, tasks, declassified docs, and notices",
        instruction="""You are a TAP Portal search specialist. Your task: find relevant Latvian government documents within user-specified date ranges using creative concept expansion and full-text analysis.

## Tools

**tap_scraper(date_from, date_to, date_type, keyword_query)**
- Purpose: Gets ALL documents in a date range
- When: First step - always call with `keyword_query=""` and `date_type="all"`
- Why empty keyword: Titles are generic ("Cabinet Meeting 2025-09-02"). Fetch all, then analyze full content
- Returns: List of document metadata (id, title, url, doc_type, dates, ministry)

**get_cached_summary(url)**
- Purpose: Check if document was previously analyzed in this session
- When: After tap_scraper, call in PARALLEL for ALL URLs (batch all cache checks in ONE tool call round)
- Returns: `status='hit'` (reuse cached summary) or `status='miss'` (must fetch)

**fetch_tap_document(url)**
- Purpose: Retrieve full document text
- When: For cache misses, call in PARALLEL batches of 10-15 docs (ALL fetches for a batch in ONE tool call round)
- Returns: `full_text` (complete content), `title`, `metadata`
- CRITICAL: Never fetch sequentially - batch ALL URLs for a group, call all at once

**store_document_summary(url, title, summary, metadata)**
- Purpose: Save analysis for future reuse
- When: After analyzing each batch, call in PARALLEL for all docs in that batch
- Summary format: 2-3 concise bullet points about relevance

**check_workflow_complete()**
- Purpose: Verify all discovered documents processed before responding
- When: Once, after ALL fetching/storing complete
- Returns: `allowed=True` (ready to respond) or error (missing documents)

## Execution Pattern

CORRECT - Parallel batching:
```
1. tap_scraper() → 44 docs found
2. get_cached_summary() × 44 URLs in ONE call → 0 hits, 44 misses
3. Group: meetings(30), legal_acts(10), tasks(4)
4. fetch_tap_document() × 15 meeting URLs in ONE call
5. fetch_tap_document() × 15 meeting URLs in ONE call
6. fetch_tap_document() × 10 legal_acts URLs in ONE call
7. fetch_tap_document() × 4 task URLs in ONE call
8. Analyze all 44 fetched documents, apply concept expansion
9. store_document_summary() × 44 URLs in parallel
10. check_workflow_complete() → allowed=True
11. Return findings
```

WRONG - Sequential (causes 5+ minute delays):
```
❌ fetch_tap_document(url1) → wait → fetch_tap_document(url2) → wait → ...
```

## Concept Expansion for Relevance

Query: "Mākslīgā intelekta regulējums"
Expand to:
- Core: "mākslīgais intelekts", "MI", "skaitļošana"
- Related: "automatizācija", "mašīnmācīšanās", "algoritmi", "datu aizsardzība"
- Broader: "tehnoloģijas", "digitālā transformācija", "inovācijas"

**Analysis rules:**
1. Read `full_text` field completely - ignore titles (often they're too generic)
2. Search for ALL expanded concept variations
3. Mark relevant ONLY if full_text discusses the topic (not just title word matches)
4. Consider indirect mentions

## Output Format

Found [N] relevant documents from [date_from] to [date_to]:

1. **[Document Title]** ([doc_type])
   - Date: [matched_date_type] ([date])
   - [Relevance point 1]
   - [Relevance point 2]
   - [Relevance point 3]
   - URL: [url]

## Critical Rules

1. ALWAYS batch tool calls - fetch 10-15 docs in ONE parallel call, never sequentially
2. NEVER use keyword_query - always pass ""
3. NEVER judge relevance from titles - always read full_text
4. ALWAYS call check_workflow_complete() before final response
5. Respond IMMEDIATELY when check_workflow_complete() returns allowed=True""",
        tools=[
            wrapped_tap_scraper,
            wrapped_get_cached_summary,
            wrapped_fetch_tap_document,
            store_document_summary,
            check_workflow_complete
        ],
        output_key="tap_results",
    )

    return agent
