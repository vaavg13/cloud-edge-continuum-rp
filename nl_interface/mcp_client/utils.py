#!/usr/bin/env python3
"""
Basic utility functions for the Kubernetes agent.
These are simple helpers - the AI agent handles complex logic itself.
"""

import json
import re
from typing import Dict, Any, Optional

def is_successful_response(response: Dict[str, Any]) -> bool:
    """
    Check if a response indicates success.
    
    Args:
        response: Response from MCP call
        
    Returns:
        True if successful, False otherwise
    """
    if "error" in response:
        return False
    
    result = response.get("result", {})
    if result.get("isError"):
        return False
    
    return True

def get_response_text(response: Dict[str, Any]) -> str:
    """
    Extract text content from MCP response.
    
    Args:
        response: Response from MCP call
        
    Returns:
        Text content or empty string
    """
    if not is_successful_response(response):
        return ""
    
    result = response.get("result", {})
    content = result.get("content", [])
    
    if content and len(content) > 0:
        return content[0].get("text", "")
    
    return ""

def validate_kubernetes_name(name: str) -> bool:
    """
    Validate a Kubernetes resource name follows naming conventions.
    
    Args:
        name: Resource name to validate
        
    Returns:
        True if valid, False otherwise
    """
    # Kubernetes names must be lowercase alphanumeric with dashes and dots
    # Must start and end with alphanumeric character
    pattern = r'^[a-z0-9]([a-z0-9\-\.]*[a-z0-9])?$'
    
    if not re.match(pattern, name):
        return False
    
    # Check length (max 253 characters for most Kubernetes names)
    if len(name) > 253:
        return False
    
    return True

def format_action_summary(actions: list) -> str:
    """
    Format a list of actions into a readable summary.
    
    Args:
        actions: List of action strings
        
    Returns:
        Formatted summary
    """
    if not actions:
        return "No actions taken."
    
    summary = "Actions taken:\n"
    for i, action in enumerate(actions, 1):
        summary += f"  {i}. {action}\n"
    
    return summary

def safe_json_parse(text: str) -> Optional[Dict[str, Any]]:
    """
    Safely parse JSON text, returning None if invalid.
    
    Args:
        text: JSON text to parse
        
    Returns:
        Parsed JSON dict or None if invalid
    """
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None

def truncate_text(text: str, max_length: int = 200) -> str:
    """
    Truncate text to a maximum length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        
    Returns:
        Truncated text with ellipsis if needed
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length] + "..." 