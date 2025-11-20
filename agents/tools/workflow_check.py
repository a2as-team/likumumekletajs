"""
Workflow check tool - agent must call this before returning final answer.
"""

from google.adk.tools.tool_context import ToolContext
from .enforcement_wrapper import get_enforcer
import logging

logger = logging.getLogger(__name__)


def check_workflow_complete() -> dict:
    """
    Check if all mandatory workflow steps have been completed.
    
    IMPORTANT: Call this tool before providing your final answer to the user.
    This ensures you've fetched all documents from the search results.
    
    Returns:
        dict with 'allowed' (bool) and 'message' (str)
    """
    enforcer = get_enforcer()
    allowed, reason = enforcer.can_complete()
    
    if allowed:
        logger.info("✅ Workflow check PASSED")
        return {
            "allowed": True,
            "message": reason,
            "can_return_to_user": True
        }
    else:
        logger.warning(f"❌ Workflow check FAILED: {reason}")
        return {
            "allowed": False,
            "message": reason,
            "can_return_to_user": False,
            "action_required": "Continue calling get_cached_summary or fetch_likumi_document for remaining documents"
        }

