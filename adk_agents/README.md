# ADK Web UI Agent Directory

This directory contains agent wrappers for the ADK Web UI.

## Structure

Each subdirectory represents one agent that will appear in the ADK web UI dropdown:

- `coordinator/` - Full multi-agent coordinator (ParallelAgent → Aggregator → Report Pipeline)
- `likumi/` - Likumi.lv specialist agent (legal acts)
- `tap/` - TAP Portal specialist agent (public consultation documents)
- `saeima/` - Saeima.lv specialist agent (parliamentary documents)

## Usage

To launch the ADK web UI with these agents:

```bash
cd likumumekletajs
adk web adk_agents
```

Then open `http://localhost:8000` in your browser.

## How It Works

Each agent directory contains:

- `agent.py` - Defines `root_agent` by calling the corresponding factory function from `agents/agent_registry.py`
- `__init__.py` - Package initialization

This structure allows ADK web to discover and load agents dynamically while reusing the existing agent implementations from the main `agents/` package.

## Note

These are wrapper modules only. The actual agent logic lives in:

- `agents/likumi_agent.py`
- `agents/tap_agent.py`
- `agents/saeima_agent.py`
- `agents/coordinator_agent.py`
- `agents/aggregator_agent.py`
- `agents/report_agent.py`
