from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.tools.tool_context import ToolContext
from google.adk.planners import BuiltInPlanner
from google.genai import types
from .base_config import MODEL_CONFIGS
from .tools import likumi_scraper, fetch_likumi_document, get_cached_summary, store_document_summary
from .tools.enforcement_wrapper import get_enforcer, reset_enforcer
from .tools.workflow_check import check_workflow_complete


# Wrap tools to track enforcement
def wrapped_likumi_scraper(date_from: str, date_to: str, date_type: str = "all", 
                          keyword_query: str = "", max_results: int = 1000, 
                          enable_browser_fallback: bool = True, tool_context: ToolContext = None):
    """Wrapped likumi_scraper that tracks results for enforcement."""
    # likumi_scraper doesn't need tool_context
    result = likumi_scraper(date_from, date_to, date_type, keyword_query, max_results, enable_browser_fallback)
    get_enforcer().track_tool_call('likumi_scraper', result)
    return result


def wrapped_get_cached_summary(url: str, tool_context: ToolContext = None):
    """Wrapped get_cached_summary that tracks calls for enforcement."""
    # get_cached_summary REQUIRES tool_context
    result = get_cached_summary(url, tool_context)
    get_enforcer().track_tool_call('get_cached_summary', result)
    return result


def wrapped_fetch_likumi_document(url: str, tool_context: ToolContext = None):
    """Wrapped fetch_likumi_document that tracks calls for enforcement."""
    # fetch_likumi_document doesn't need tool_context
    result = fetch_likumi_document(url)
    get_enforcer().track_tool_call('fetch_likumi_document', result)
    return result


def create_likumi_agent():
    """
    Create the Likumi.lv specialist agent with session-based memory and workflow enforcement.
    
    This agent is responsible for:
    - Searching Likumi.lv for documents within a date range (gets list of IDs/titles/URLs)
    - Fetching full text for promising documents
    - Analyzing relevance using LLM capabilities
    - Storing relevant findings in session state
    
    Returns:
        LlmAgent: Configured Likumi.lv agent
    """
    config = MODEL_CONFIGS["specialist"]
    
    # Reset enforcer for fresh agent instance
    reset_enforcer()
    
    agent = LlmAgent(
        name="LikumiAgent",
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
        description="Searches Likumi.lv for Latvian legal documents and analyzes their relevance to user queries",
        instruction="""You help users find relevant legal changes from Likumi.lv within specified date ranges.

# Your Task

Search broadly with keyword variations, fetch all unique documents, then use your judgment to identify what's truly relevant.

# Tools and When to Use Them

## likumi_scraper(date_from, date_to, date_type, keyword_query)
**Purpose**: Get initial document list for a date range.
**Call in parallel**: Generate 3-5 keyword variations from the user's query (synonyms, related terms, morphological forms) and search with each keyword simultaneously. Search for keywords related to the user's core idea/goal, not assisting/clarifying words or words given to provide additional context.
**Always set**: `date_type="all"` to search all date fields.

## get_cached_summary(url)
**Purpose**: Check if a document was previously analyzed.
**Call in parallel**: After collecting all unique URLs, check cache for all of them at once.
**Returns**: `status='hit'` (use cached summary) or `status='miss'` (needs fetching).

## fetch_likumi_document(url)
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

# Processing Strategy

1. **Search**: Run 3-5 parallel searches with different keywords
2. **Deduplicate**: Combine results and remove duplicates
3. **Check cache**: Verify all URLs in parallel
4. **Fetch in batches**: Process 8-10 uncached documents at a time in parallel
5. **Store**: Save summaries for each batch in parallel
6. **Validate**: Call check_workflow_complete
7. **Respond**: Present only the relevant documents

# Output Format

Found [N] relevant documents from [date_from] to [date_to]:

1. **[Document Title]** (ID: [doc_id])
   - Date: [matched_date_type] ([date])
   - [Concise summary point 1]
   - [Concise summary point 2]
   - [Concise summary point 3]
   - URL: [document_url]

# Constraints

- Always use multiple keyword variations (never just one)
- Process documents in batches of 8-10 maximum
- Read full text before judging relevance
- Call check_workflow_complete before final response
- Respond immediately when check_workflow_complete returns allowed=True""",
        tools=[wrapped_likumi_scraper, wrapped_get_cached_summary, wrapped_fetch_likumi_document, store_document_summary, check_workflow_complete],
        output_key="likumi_results",
    )
    
    return agent
