"""
Coordinator Agent - Orchestrates the entire multi-agent workflow.
Uses Sequential + Parallel pattern to manage specialist agents.
"""

from google.adk.agents import SequentialAgent, ParallelAgent
from google.adk.tools.agent_tool import AgentTool
from .likumi_agent import create_likumi_agent
from .tap_agent import create_tap_agent
from .saeima_agent import create_saeima_agent
from .aggregator_agent import create_aggregator_agent
from .report_agent import create_report_agent


def create_coordinator_agent():
    """
    Create the main coordinator agent using Sequential + Parallel pattern.
    
    Architecture:
    1. Parallel execution of specialist agents (Likumi, TAP, Saeima)
    2. Sequential aggregation and report generation
    
    Workflow:
        User Input: {query, date_range}
            ↓
        Parallel Specialists (Likumi, TAP, Saeima)
            ↓
        Aggregator (filters and combines results)
            ↓
        Report Generator (creates final output)
            ↓
        Output: {summary, sources[]}
    
    Returns:
        SequentialAgent: The root coordinator agent
    """
    
    # Create specialist agents
    likumi_agent = create_likumi_agent()
    tap_agent = create_tap_agent()
    saeima_agent = create_saeima_agent()
    
    # Create parallel team for data collection
    parallel_data_collection = ParallelAgent(
        name="ParallelDataCollection",
        sub_agents=[likumi_agent, tap_agent, saeima_agent],
    )
    
    # Create aggregator and report agents
    aggregator_agent = create_aggregator_agent()
    report_agent = create_report_agent()
    
    # Create the root coordinator as a sequential agent
    coordinator = SequentialAgent(
        name="LatvianLegalMonitorCoordinator",
        sub_agents=[
            parallel_data_collection,  # Step 1: Collect data from all sources in parallel
            aggregator_agent,           # Step 2: Filter and combine results
            report_agent,               # Step 3: Generate final report (Refiner's output streams via SSE)
        ],
    )
    
    return coordinator


def create_coordinator_with_logging():
    """
    Create the coordinator agent with logging plugin enabled.
    Use this version for production or when detailed logging is needed.
    
    Returns:
        tuple: (coordinator_agent, logging_plugin)
    """
    from google.adk.plugins.logging_plugin import LoggingPlugin
    
    coordinator = create_coordinator_agent()
    logging_plugin = LoggingPlugin()
    
    return coordinator, logging_plugin
