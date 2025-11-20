"""Agent Registry for Multi-Agent Orchestration

Provides a single place to obtain agent instances keyed by role/name.
Implements lazy instantiation, optional singleton retention, and utilities
to build composite coordinator structures while reusing existing agents.

Design Goals:
1. Separation of Concerns: Construction logic lives here, not notebooks.
2. Reuse: Avoid recreating agents repeatedly (preserve instruction state).
3. Extensibility: Easy to add new roles or swap implementations.
4. Session Compatibility: Caller supplies runner/session; registry only creates agents.

NOTE: This registry does not manage Runner or session lifecycles; that stays
      with application initialization to allow different session strategies.
"""

from typing import Dict, Optional, List

from google.adk.agents import ParallelAgent, SequentialAgent

# Import factory functions (lazy via mapping to keep lookup simple)
from .likumi_agent import create_likumi_agent
from .tap_agent import create_tap_agent
from .saeima_agent import create_saeima_agent
from .aggregator_agent import create_aggregator_agent
from .report_agent import create_report_agent


_REGISTRY: Dict[str, object] = {}

_FACTORIES: Dict[str, callable] = {
    'likumi': create_likumi_agent,
    'tap': create_tap_agent,
    'saeima': create_saeima_agent,
    'aggregator': create_aggregator_agent,
    'report': create_report_agent,
}


def get_agent(role: str):
    """Return (and cache) an agent instance for given role key.

    Args:
        role: one of 'likumi','tap','saeima','aggregator','report'
    Returns:
        Agent instance
    Raises:
        KeyError if role unknown
    """
    key = role.lower()
    if key not in _FACTORIES:
        raise KeyError(f"Unknown agent role '{role}'. Known: {list(_FACTORIES.keys())}")
    if key not in _REGISTRY:
        _REGISTRY[key] = _FACTORIES[key]()
    return _REGISTRY[key]


def reset_agent(role: str):
    """Force re-creation of a specific agent role (e.g., after instruction changes)."""
    key = role.lower()
    if key in _REGISTRY:
        del _REGISTRY[key]
    return get_agent(key)


def list_registered() -> List[str]:
    """List roles currently instantiated in registry."""
    return list(_REGISTRY.keys())


def get_parallel_specialists(include: Optional[List[str]] = None) -> ParallelAgent:
    """Build a ParallelAgent of specialist data collectors.

    Args:
        include: optional subset of ['likumi','tap','saeima']
    Returns:
        ParallelAgent instance
    """
    roles = include or ['likumi','tap','saeima']
    subs = [get_agent(r) for r in roles]
    return ParallelAgent(name="ParallelDataCollection", sub_agents=subs)


def get_coordinator(sequential_name: str = "LatvianLegalMonitorCoordinator") -> SequentialAgent:
    """Compose full coordinator using registry-managed agents.

    Returns:
        SequentialAgent root coordinator
    """
    parallel_team = get_parallel_specialists()
    aggregator = get_agent('aggregator')
    report = get_agent('report')
    return SequentialAgent(
        name=sequential_name,
        sub_agents=[parallel_team, aggregator, report]
    )


def reset_all():
    """Clear registry completely (e.g., for test isolation)."""
    _REGISTRY.clear()
