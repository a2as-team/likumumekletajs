"""
Root agent definition for ADK API server.

This file defines the root_agent variable that the ADK API server expects.
It also configures middleware for API key authentication.
"""

import os
from .coordinator_agent import create_coordinator_agent
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse


# Create the root agent - this is what ADK API server will use
root_agent = create_coordinator_agent()


# API Key Authentication Middleware
class APIKeyMiddleware(BaseHTTPMiddleware):
    """Validates API key from X-API-Key header."""
    
    def __init__(self, app):
        super().__init__(app)
        self.api_key = os.getenv("API_KEY")
        if not self.api_key:
            raise ValueError("API_KEY environment variable must be set")
    
    async def dispatch(self, request, call_next):
        # Skip auth for health check
        if request.url.path == "/health":
            return await call_next(request)
        
        # Get API key from header
        provided_key = request.headers.get("X-API-Key")
        
        # Validate
        if not provided_key or provided_key != self.api_key:
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized - Invalid or missing API key"}
            )
        
        # Continue processing
        return await call_next(request)


# Middleware configuration for ADK
def configure_middleware(app):
    """Add CORS and API key authentication middleware to the FastAPI app."""
    # Add CORS middleware FIRST (processes requests before API key check)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins - restrict this in production!
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
    
    # Add API key authentication middleware
    app.add_middleware(APIKeyMiddleware)
    return app


# Export middleware configurator for ADK
middleware = [configure_middleware]
