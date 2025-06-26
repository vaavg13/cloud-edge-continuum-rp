#!/usr/bin/env python3
"""
Default configuration values for Kubernetes Agent.
Simple dictionary-based configuration.
"""

import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Default agent configuration
DEFAULT_AGENT_CONFIG = {
    "openai_api_key": os.getenv("OPENAI_API_KEY"),
    "openai_model": "gpt-4.1", 
    "openai_max_tokens": 4096,
    "mcp_server_command": ["npx", "mcp-server-kubernetes"],
    "max_rounds": 10,
    "agent_timeout": 120,
    "agent_verbose": True
}

def create_agent_config(**kwargs) -> Dict[str, Any]:
    """
    Create agent configuration by merging defaults with provided values.
    
    Args:
        **kwargs: Configuration overrides
        
    Returns:
        Dict with agent configuration
    """
    config = DEFAULT_AGENT_CONFIG.copy()
    config.update(kwargs)
    return config

def validate_agent_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Basic validation for agent config.
    
    Args:
        config: Agent configuration dict
        
    Returns:
        Validated configuration dict
        
    Raises:
        ValueError: If configuration is invalid
    """
    if not config.get("openai_api_key"):
        raise ValueError("OpenAI API key must be provided either as parameter or OPENAI_API_KEY environment variable")
    
    if config.get("max_rounds", 0) <= 0:
        raise ValueError("max_rounds must be greater than 0")
        
    if config.get("agent_timeout", 0) <= 0:
        raise ValueError("agent_timeout must be greater than 0")
    
    return config