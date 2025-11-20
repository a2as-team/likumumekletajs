"""
Saeima.lv Agent - Parliamentary Document Specialist

Retrieves and analyzes documents from the Latvian Parliament (Saeima.lv).
Searches across 5 document types using OpenView endpoints (agendas excluded - calendar-only).
"""

from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.tools.tool_context import ToolContext
from google.adk.planners import BuiltInPlanner
from google.genai import types
from .base_config import MODEL_CONFIGS
from .tools import (
    saeima_scraper,
    fetch_saeima_document,
    get_cached_summary,
    store_document_summary
)
from .tools.enforcement_wrapper import get_enforcer, reset_enforcer
from .tools.workflow_check import check_workflow_complete


def wrapped_saeima_scraper(date_from: str, date_to: str, date_type: str = "all",
                           keyword_query: str = "", max_results: int = 1000,
                           tool_context: ToolContext = None):
    """Wrapped Saeima scraper with enforcer tracking."""
    result = saeima_scraper(date_from, date_to, date_type, keyword_query, max_results)
    get_enforcer().track_tool_call('saeima_scraper', result)
    return result


def wrapped_fetch_saeima_document(url: str, tool_context: ToolContext = None):
    """Wrapped Saeima document fetch with enforcer tracking."""
    result = fetch_saeima_document(url)
    get_enforcer().track_tool_call('fetch_saeima_document', result)
    return result


def wrapped_get_cached_summary(url: str, tool_context: ToolContext = None):
    """Wrapped cache check with enforcer tracking."""
    result = get_cached_summary(url, tool_context)
    get_enforcer().track_tool_call('get_cached_summary', result)
    return result


def create_saeima_agent():
    """Create Saeima.lv specialist agent with session memory and workflow enforcement."""
    config = MODEL_CONFIGS["specialist"]
    reset_enforcer()  # CRITICAL: Reset for fresh instance
    
    agent = LlmAgent(
        name="SaeimaAgent",
        model=Gemini(
            model=config["model"],
            retry_options=config["retry_options"]
        ),
        generate_content_config=types.GenerateContentConfig(
            temperature=0.4  # Balanced for reliability with flexibility
        ),
        planner=BuiltInPlanner(
            thinking_config=types.ThinkingConfig(
                include_thoughts=False,  #  Don't include internal reasoning in response
                thinking_budget=4096,    # Allow moderate thinking for complex workflows
            )
        ),
        description="Searches Saeima.lv for parliamentary documents and identifies those relevant to user queries",
        instruction="""You help users find relevant parliamentary activity from Saeima.lv within specified date ranges.

# Your Task

Retrieve parliamentary documents using chronological estimation, fetch full text in batches, then use your judgment to identify what's truly relevant. When in doubt about relevance, include the document - it's better to provide extra context than to miss potentially useful information.

# Tools and When to Use Them

## saeima_scraper(date_from, date_to, date_type, keyword_query)
**Purpose**: Get parliamentary documents for a date range using chronological estimation.
**Call once**: Set keyword_query="" (scraper uses date estimation, not keywords).
**How it works**: Scraper fetches all document IDs, estimates positions via linear interpolation based on chronological numbering, and returns estimated range + 100% buffer to prevent edge misses.
**Always set**: `date_type="all"` to search all document types.
**Important**: Always use empty string for keyword_query (filtering happens post-fetch via LLM judgment).

## get_cached_summary(url)
**Purpose**: Check if a document was previously analyzed.
**Call in parallel**: After collecting all unique URLs, check cache for all of them at once.
**Returns**: `status='hit'` (use cached summary) or `status='miss'` (needs fetching).

## fetch_saeima_document(url)
**Purpose**: Retrieve full document text to assess relevance.
**Call in parallel**: Process uncached documents in batches of 8-10 to avoid context overflow.
**Important**: Read full text before judging relevance - titles alone are insufficient.

## store_document_summary(url, summary)
**Purpose**: Save document analysis for future use.
**Call in parallel**: After analyzing a batch, store all summaries at once (2-3 bullet points each).

## check_workflow_complete()
**Purpose**: Verify all discovered documents have been processed.
**Call once**: Before providing your final response.
**Critical**: When this returns `allowed=True`, immediately respond with your findings. Your response gets saved to session state.

# Document Types

- Draft Legislation
- Decision Drafts
- Deputy Questions
- Requests
- Committee Meetings

# Scraper Architecture (Important!)

The Saeima scraper uses a **unique chronological estimation strategy**:

**How it works**:
1. Documents are numbered chronologically: 1/Lp14 (2022) → 1149/Lp14 (2025)
2. Scraper fetches all document IDs from OpenView (fast - metadata only)
3. Samples first and last documents to determine date boundaries
4. Uses linear interpolation to estimate document positions for your date range
5. Returns estimated range + 100% buffer to prevent missing edge documents

**Why this matters**:
- Reduces ~1000+ documents to ~60 relevant ones automatically
- No keyword filtering needed (already pre-filtered by date estimation)
- Buffer ensures no relevant documents missed at range edges
- You filter the remaining ~60 using LLM intelligence, not crude keyword matching

**Your role**: Judge relevance from full document text, not titles.

# Processing Strategy

1. **Search**: Call saeima_scraper once with keyword_query="" (scraper uses estimation + buffer)
2. **Understand**: Scraper returns ~60 documents (estimated range + 100% buffer for safety)
3. **Check cache**: Verify all URLs in parallel
4. **Fetch in batches**: Process 8-10 uncached documents at a time in parallel
5. **Filter intelligently**: 
   - Read the `full_text` field completely for EVERY document
   - Titles are often generic - use full content to judge relevance
   - Consider both direct mentions and indirect/related topics
   - **When uncertain, include the document** - better to provide context than miss relevant information
6. **Store**: Save summaries for each batch in parallel (2-3 bullet points explaining relevance or potential connection)
7. **Validate**: Call check_workflow_complete
8. **Respond**: Present relevant documents with brief overview.

# Output Format

Found [N] relevant documents from [date_from] to [date_to]:

1. **[Type]** - [Title]
   - Date: [YYYY-MM-DD]
   - Status: [Status]
   - [Summary point 1]
   - [Summary point 2]
   - [Summary point 3]
   - URL: [document_url]

**If very few or no relevant documents found**: Note this, but include some documents with closest potential relevance.

# Constraints

- Always use empty string for keyword_query (scraper uses chronological estimation)
- Expect ~60 documents with 100% buffer (scraper pre-filters via estimation)
- Process documents in batches of 8-10 maximum
- Read `full_text` field before judging relevance - titles alone are often insufficient
- When uncertain about relevance, include the document rather than exclude it
- Use LLM judgment for filtering (more accurate than keyword matching on titles)
- Call check_workflow_complete before final response
- Respond immediately when check_workflow_complete returns allowed=True""",
        tools=[
            wrapped_saeima_scraper,
            wrapped_get_cached_summary,
            wrapped_fetch_saeima_document,
            store_document_summary,
            check_workflow_complete
        ],
        output_key="saeima_results",
    )
    
    return agent

