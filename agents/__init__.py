"""
Agent modules for the Latvian Legal Changes Multi-Agent System.
"""

# Import agent for ADK API server compatibility
from . import agent

from .coordinator_agent import create_coordinator_agent
from .likumi_agent import create_likumi_agent
from .tap_agent import create_tap_agent
from .saeima_agent import create_saeima_agent
from .aggregator_agent import create_aggregator_agent
from .report_agent import create_report_agent

__all__ = [
    "agent",
    "create_coordinator_agent",
    "create_likumi_agent",
    "create_tap_agent",
    "create_saeima_agent",
    "create_aggregator_agent",
    "create_report_agent",
]
