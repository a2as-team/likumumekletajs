"""
Enforcement wrapper to ensure agents follow mandatory workflow steps.
This is a temporary measure until LLM instruction adherence improves.
"""

import logging
from typing import Any, Dict, List
from google.adk.tools.tool_context import ToolContext

logger = logging.getLogger(__name__)


class WorkflowEnforcer:
    """
    Tracks tool calls and enforces minimum workflow requirements.
    
    For document retrieval agents, this ensures:
    - If likumi_scraper returns N documents, agent must call fetch/cache tools N times
    - Agent cannot return empty responses when documents are found
    """
    
    def __init__(self):
        self.search_results_count = 0
        self.fetch_calls_count = 0
        self.last_search_tool = None
        
    def track_tool_call(self, tool_name: str, tool_result: Any) -> None:
        """
        Track tool calls and update enforcement state.
        
        Args:
            tool_name: Name of the tool that was called
            tool_result: The result returned by the tool
        """
        if 'scraper' in tool_name.lower():
            # This is a search tool
            self.last_search_tool = tool_name
            if isinstance(tool_result, dict) and 'results' in tool_result:
                self.search_results_count = len(tool_result['results'])
                logger.info(f"🔍 Enforcer: {tool_name} returned {self.search_results_count} documents")
                
        elif any(k in tool_name.lower() for k in ['get_cached', 'fetch', 'cached']):
            # Consider any fetch/cache-style tool as a fetch call.
            # This keeps the enforcer robust to different tool names
            # (e.g., fetch_tap_document, fetch_likumi_document, get_cached_summary).
            self.fetch_calls_count += 1
            logger.info(f"📄 Enforcer: Fetch/cache call '{tool_name}' #{self.fetch_calls_count}/{self.search_results_count}")
    
    def can_complete(self) -> tuple[bool, str]:
        """
        Check if the agent can complete (return final response).
        
        Returns:
            (allowed, reason): True if agent can complete, False with reason if not
        """
        if self.search_results_count == 0:
            # No search performed yet or search returned 0 results
            return True, "No documents to process"
            
        if self.fetch_calls_count < self.search_results_count:
            missing = self.search_results_count - self.fetch_calls_count
            reason = (
                f"WORKFLOW VIOLATION: Search found {self.search_results_count} documents "
                f"but only {self.fetch_calls_count} were fetched. "
                f"You MUST call get_cached_summary or fetch_likumi_document "
                f"for the remaining {missing} documents before returning a response."
            )
            logger.warning(f"❌ Enforcer blocking completion: {reason}")
            return False, reason
            
        logger.info(f"✅ Enforcer: Workflow complete ({self.fetch_calls_count}/{self.search_results_count} documents processed)")
        return True, "All documents processed"
    
    def reset(self) -> None:
        """Reset enforcement state for new agent run."""
        self.search_results_count = 0
        self.fetch_calls_count = 0
        self.last_search_tool = None
        logger.debug("🔄 Enforcer reset")


# Global enforcer instance (one per agent run)
_enforcer = WorkflowEnforcer()


def get_enforcer() -> WorkflowEnforcer:
    """Get the global enforcer instance."""
    return _enforcer


def reset_enforcer() -> None:
    """Reset the global enforcer."""
    _enforcer.reset()
