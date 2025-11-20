"""
Aggregator Agent - Normalizes format and creates first draft report structure.
Applies very light quality filtering (preserve as much as possible).
"""

from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from .base_config import MODEL_CONFIGS


def create_aggregator_agent():
    """
    Create the Results Aggregator agent.
    
    This agent is responsible for:
    - Receiving raw results from all specialist agents (Likumi, TAP, Saeima)
    - Standardizing format across different source schemas
    - Applying LIGHT quality filtering (when in doubt, include it)
    - Generating first draft report in English/structured format
    
    Returns:
        LlmAgent: Configured aggregator agent
    """
    config = MODEL_CONFIGS["aggregator"]
    
    agent = LlmAgent(
        name="AggregatorAgent",
        model=Gemini(
            model=config["model"],
            retry_options=config["retry_options"]
        ),
        description="Normalizes format across sources and creates first draft report structure",
        instruction="""You are the Results Aggregator. Combine legal findings from 3 specialist agents into a unified English report.

**Inputs** (from state):
- Likumi results: {+likumi_results|No results available+}
- TAP results: {+tap_results|No results available+}
- Saeima results: {+saeima_results|No results available+}

**Tasks**:
1. **Normalize Format**: Convert all documents to:
   - Title (clear, descriptive)
   - Date (YYYY-MM-DD)
   - Source URL
   - Brief description (1-2 sentences, factual)

2. **Light Quality Filter**: Remove only obvious errors or duplicates. When uncertain, include the item.

3. **Generate Report** in this structure:
```
## Summary
[2-3 sentences summarizing findings across all sources]

## Changes by Source

### Likumi.lv
- **[Title]** ([Date]): [Description]
- [URL]

### TAP Portāls
- **[Title]** ([Date]): [Description]
- [URL]

### Saeima
- **[Title]** ([Date]): [Description]
- [URL]
```

**Example**:
Input: `likumi_results: [{"title": "Grozījumi Medību likumā", "date": "2025-01-12", "url": "https://likumi.lv/12345", "desc": "Wolf protection rules"}]`

Output:
```
### Likumi.lv
- **Amendments to Hunting Law** (2025-01-12): New regulations for wolf population protection
- https://likumi.lv/12345
```

**Rules**:
- Write in English (translator handles Latvian)
- Preserve ALL specialist findings and URLs
- Do NOT add information not in source data
- If a source returns no results, write "No changes found" under that section""",
        output_key="draft_report_en",
    )
    
    return agent
