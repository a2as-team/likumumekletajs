# Latvian Legal Changes Multi-Agent System

[![License: CC BY-SA 4.0](https://img.shields.io/badge/License-CC%20BY--SA%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-sa/4.0/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Google ADK](https://img.shields.io/badge/Google-ADK-4285F4.svg)](https://google.github.io/adk-docs/)

> **Kaggle Competition Entry**: [Google Agents Intensive Capstone Project](https://www.kaggle.com/competitions/agents-intensive-capstone-project)

**🌐 Web Version Available**: Non-programmers can access this service at **[likumumekletajs.lv](https://likumumekletajs.lv)** - submit queries and pay for running code without hassle of local setup.

Open-source multi-agent system using Google's ADK to automatically

---

## 🎯 Overview

**Problem Statement**: Latvian organisations and legal practitioners need a reliable, automated way to track published, announced, and draft changes to laws and regulations that affect a given company or institution during a specified time window.

**Solution**: An open-source multi-agent system built with Google's Agent Development Kit (ADK) in Python that collects, classifies, and summarises legal changes. Tracks Latvian legal changes across [Likumi.lv](https://likumi.lv), [TAP Portal](https://tapportals.mk.gov.lv), and [Saeima.lv](https://saeima.lv). Searches 3 government sources in parallel, generates professional Latvian reports with source citations.

**Input**: Natural language query + date range → **Output**: Latvian Markdown report with direct source links

**Architecture**: Sequential coordinator orchestrates 3 parallel specialist agents → Aggregator → Translation pipeline with quality loop

| Component        | Implementation                                            | Files                            |
| ---------------- | --------------------------------------------------------- | -------------------------------- |
| ✅ Multi-Agent   | Parallel (3 specialists) + Sequential + Loop (quality)    | `agents/coordinator_agent.py`    |
| ✅ Custom Tools  | 12 tools (3 scrapers, 3 fetchers, 3 shared, 3 workflow)   | `tools/{likumi,tap,saeima}_*.py` |
| ✅ Sessions      | InMemorySessionService with per-source document caching   | `tools/memory_tools.py`          |
| ✅ Observability | LoggingPlugin + DEBUG file logging + workflow enforcement | `utils/logging_config.py`        |
| ✅ Evaluation    | Unit + integration tests, production validation           | `tests/*.py`                     |

**Key Innovation**: Progressive batching (15-20 docs/turn) prevents context overflow. Validated with 69-document query processed in 4 batches without errors

---

## 🚀 Quick Start

```bash
# Setup (5 minutes)
git clone https://github.com/olavs69/likumumekletajs.git && cd likumumekletajs
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Add your GOOGLE_API_KEY

# Run (Jupyter recommended)
jupyter notebook LV_legal.ipynb
```

**Models**: Uses Gemini 2.5 Flash (specialists/coordinator) and Flash Lite (aggregator/report pipeline)

**Python API**:

```python
from agents import create_coordinator_agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

coordinator = create_coordinator_agent()
runner = Runner(agent=coordinator, session_service=InMemorySessionService())
session = runner.create_session()

result = runner.run(session_id=session.id, content={
    "query": "environmental regulations",
    "date_from": "2024-01-01",
    "date_to": "2024-01-31"
})
print(result.messages[-1].content)  # Latvian report with sources
```

**Non-Programmers**: Use [likumumekletajs.lv](https://likumumekletajs.lv) - no setup required

---

## 📊 Architecture Details

**5-Stage Pipeline**:

1. **Parallel Collection**: 3 specialists search simultaneously with different strategies:
   - **Likumi**: Parallel keyword variations (3-5 synonyms/morphological forms)
   - **TAP**: Empty keyword + post-fetch concept expansion filtering
   - **Saeima**: Chronological estimation with 100% buffer
2. **Aggregation**: Normalize schemas, light relevance filtering
3. **Translation**: English draft → Latvian (professional terminology)
4. **Quality Loop**: LoopAgent validates translation (Critic → Refiner, max 4 iterations)
5. **Output**: Structured Markdown with source citations

**17 Document Types Covered**:

- **Likumi**: Published legal acts (3 date dimensions)
- **TAP**: Drafts, meetings, tasks, declassified docs, notices (6 types, 8+ date fields)
- **Saeima**: Legislation, questions, requests, agendas, committees (6 types, JavaScript-rendered)

**Production Validation**: 69-document query → 4 batches → 3 relevant results, 0 errors

### Agent Roles

- **LikumiAgent**: Searches Likumi.lv using 3-5 parallel keyword variations (synonyms, morphological forms)
- **TAPAgent**: Searches TAP Portal with empty keyword, applies post-fetch concept expansion
- **SaeimaAgent**: Searches Saeima.lv using chronological estimation (linear interpolation + 100% buffer)
- **AggregatorAgent**: Normalizes schemas, applies light relevance filtering
- **ReportAgent**: SequentialAgent with 3 sub-agents:
  - **Translator**: English → Latvian
  - **LoopAgent** (Critic → Refiner, max 4 iterations):
    - **Critic**: Validates translation quality, responds "APSTIPRINĀTS" if perfect
    - **Refiner**: Fixes issues OR exits loop via `exit_report_loop()` if approved

---

## 🔧 Technical Highlights

**Progressive Batching** (Critical Innovation):

- Agents instructed to fetch 8-15 documents in parallel batches
- Prevents context overflow on large result sets
- Validated: 69 docs → 4 batches = 100% success
- Prevents `MALFORMED_FUNCTION_CALL` errors
- Implementation: Agent instructions enforce batch size limits

**Session Memory System**:

- Per-source document caching via `tool_context.state["temp:{source}_docs"]`
- Sources: `likumi`, `tap`, `saeima` (non-overlapping URL domains)
- Prevents re-fetching within same session/conversation
- Tools: `get_cached_summary(url)` → `status='hit'|'miss'`, `store_document_summary(url, summary)`

**Workflow Enforcement**:

- `WorkflowEnforcer` singleton tracks scraper results vs fetch/cache calls
- `check_workflow_complete()` validates 100% coverage before agent responds
- Wrapped tools in each agent file inject tracking via `enforcement_wrapper.py`
- Returns `allowed=False` if documents remain unprocessed
- Agent instructions mandate calling `check_workflow_complete()` before final response

**Resilient Scraping**:

- Browser fallback (Playwright) for JavaScript-rendered content
- Exponential backoff retry (max 5 attempts)
- Rate limiting (1 sec/request) + 429 handling
- In-module caching for fetched documents

---

## 📂 Project Structure

```
agents/          # 7 agents: coordinator, 3 specialists, aggregator, translator, critic, refiner
  tools/         # 12 tools: 3 scrapers, 3 fetchers, 2 memory, 1 enforcement, 1 workflow, 1 cached, 1 shared init
utils/           # Date parsing, logging configuration
tests/           # Unit tests (scrapers) + integration tests (workflows)
LV_legal.ipynb   # Interactive demo with examples
```

**Key Files**:

- `agents/coordinator_agent.py` - SequentialAgent with ParallelAgent for data collection
- `agents/report_agent.py` - SequentialAgent with LoopAgent (Critic → Refiner, max 4 iterations)
- `agents/base_config.py` - Model configurations (Gemini 2.5 Flash/Flash Lite)
- `tools/enforcement_wrapper.py` - `WorkflowEnforcer` singleton tracks scraper → fetch/cache calls
- `tools/memory_tools.py` - `get_cached_summary`, `store_document_summary` with `temp:{source}_docs`
- `tools/workflow_check.py` - `check_workflow_complete()` validates 100% coverage

---

## 🧪 Performance & Testing

**Typical Query (7-day range)**:

- 50-200 documents searched across 3 sources
- 45-90 seconds execution time
- 15-25 LLM API calls (with caching)
- > 90% relevance accuracy (manual validation)

**Run Tests**: `pytest tests/` (unit tests for scrapers, integration tests for workflows)

---

## 🎓 Implementation Lessons

### Critical Design Patterns

**1. Progressive Batching (MANDATORY for Production)**

Large result sets (50+ documents) cause context overflow errors. The solution is processing in batches of 15-20 documents per turn:

- **Problem**: 69 documents = 70k tokens → `MALFORMED_FUNCTION_CALL`
- **Solution**: 4 batches × 17k tokens → 100% success
- **Implementation**: Agent instructions enforce batch size limits
- **When**: ANY query that could return 30+ documents

**2. Search Strategy Patterns (Source-Specific)**

Different sources require different search approaches:

- **Likumi**: Parallel keyword variations (3-5 synonyms/morphological forms) for precision
- **TAP**: Empty keyword (`keyword_query=""`) + post-fetch concept expansion for recall
- **Saeima**: Chronological estimation (no keyword filtering) + LLM-based relevance
- **Why**: TAP/Saeima have generic titles ("Cabinet Meeting 2025-01-15"), full text needed for relevance
- **Pattern**: Fetch broadly, filter intelligently with LLM reading full text

**3. Session Memory Architecture**

Per-source document caching prevents redundant fetches within a session:

- **Storage**: `tool_context.state["temp:{source}_docs"]` (sources: `likumi`, `tap`, `saeima`)
- **Scope**: Session-specific (`temp:` prefix) - isolated per conversation
- **Tools**:
  - `get_cached_summary(url, tool_context)` → `{"status": "hit"|"miss", "summary": "..."}`
  - `store_document_summary(url, summary, tool_context)` → saves to session state
- **Benefit**: Documents cached within session, agents call `get_cached_summary` in parallel for all URLs

**4. Workflow Enforcement**

Agent cannot respond until ALL documents processed:

- **Singleton**: `WorkflowEnforcer` (via `get_enforcer()`) tracks scraper results vs fetch/cache calls
- **Wrapped Tools**: Each agent wraps its tools to inject tracking (e.g., `wrapped_likumi_scraper`)
- **Validation Tool**: `check_workflow_complete()` returns `{"allowed": bool, "message": str}`
- **Agent Instructions**: Mandate calling `check_workflow_complete()` before final response
- **Impact**: Prevents incomplete analysis (validated: 69/69 documents processed)

### Resilient Scraping Principles

**Date Buffer (100% recommended)**:

- Edge documents at midnight boundaries need safety margin
- Implementation: `estimated_pos += int(estimated_pos * 1.0)`
- Impact: 98% → 100% coverage

**JavaScript-Rendered Content**:

- Browser fallback (Playwright) architecture for Lotus Notes/Domino
- Graceful degradation: requests → selenium if needed
- Proven with Saeima.lv (6 document types, all JavaScript)

### Multi-Source Pattern Comparison

| Aspect          | Likumi                          | TAP                          | Saeima                          |
| --------------- | ------------------------------- | ---------------------------- | ------------------------------- |
| Document Types  | 1                               | 6 (varying structures)       | 5 (JavaScript-rendered)         |
| Date Dimensions | 3 (uniform)                     | 8+ (per type)                | 4+ (per type)                   |
| Scraper Pattern | Daily endpoints                 | Type-specific functions      | Chronological estimation        |
| Search Strategy | 3-5 parallel keyword variations | Empty keyword (fetch all)    | Empty keyword (estimated range) |
| Filtering       | LLM post-fetch                  | Concept expansion post-fetch | LLM post-fetch                  |
| Fetch Pattern   | Single uniform                  | Generic field_patterns dict  | Type-specific parsing           |
| Batching        | 8-10 docs/batch                 | 10-15 docs/batch             | 8-10 docs/batch                 |

**Decision Rule**: Use simple pattern (Likumi) for uniform sources, complex pattern (TAP/Saeima) for multi-type with varying structures.

---

## 📄 License

**CC BY-SA 4.0** - Free to use, modify, and commercialize with attribution.

**Live Service**: [likumumekletajs.lv](https://likumumekletajs.lv) - Web interface for non-programmers (pay-per-query)

**Full license**: https://creativecommons.org/licenses/by-sa/4.0/

---

## 🤝 Contributing

**Welcome contributions**:

- More efficient retrieval, batching & caching for longer date ranges
- Enhanced evaluation
- Performance optimizations

Fork → Feature branch → Tests → Pull request

---

## 📧 Resources

- **Documentation**: [Google ADK Docs](https://google.github.io/adk-docs/)
- **Demo Notebook**: [LV_legal.ipynb](LV_legal.ipynb)
- **Issues**: [GitHub Issues](https://github.com/olavs69/likumumekletajs/issues)
- **Competition**: [Kaggle Discussion](https://www.kaggle.com/competitions/agents-intensive-capstone-project/discussion)
