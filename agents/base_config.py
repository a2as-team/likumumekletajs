"""
Base configuration for all agents in the system.
Provides consistent retry options and model settings.
"""

from google.genai import types

# Standard retry configuration for all agents
RETRY_CONFIG = types.HttpRetryOptions(
    attempts=5,  # Maximum retry attempts
    exp_base=7,  # Delay multiplier for exponential backoff
    initial_delay=1,  # Initial delay in seconds
    http_status_codes=[429, 500, 503, 504],  # Retry on these HTTP errors
)

# Default model for all agents
DEFAULT_MODEL = "gemini-2.5-flash-lite"

# Model configuration for different agent types
MODEL_CONFIGS = {
    "coordinator": {
        "model": "gemini-2.5-flash",
        "retry_options": RETRY_CONFIG,
    },
    "specialist": {  # For Likumi, TAP, Saeima agents
        "model": "gemini-2.5-flash", 
        "retry_options": RETRY_CONFIG,
    },
    "aggregator": {
        "model": "gemini-2.5-flash-lite",
        "retry_options": RETRY_CONFIG,
    },
    "report": {
        "model": "gemini-2.5-flash-lite",
        "retry_options": RETRY_CONFIG,
    },
    "translator": {
        "model": "gemini-2.5-flash-lite", 
        "retry_options": RETRY_CONFIG,
    },
    "critic": {
        "model": "gemini-2.5-flash-lite",
        "retry_options": RETRY_CONFIG,
    },
    "refiner": {
        "model": "gemini-2.5-flash-lite",
        "retry_options": RETRY_CONFIG,
    },
}
