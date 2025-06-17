#!/usr/bin/env python3
"""
Configuration settings for the Kubernetes Agent.
"""

import os
from dotenv import load_dotenv

# OpenAI API key (can be overridden by environment variable)
# Load environment variables from .env file
load_dotenv()

# Access environment variable
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# MCP Server configuration
MCP_SERVER_COMMAND = ["npx", "mcp-server-kubernetes"]

# OpenAI model settings
OPENAI_MODEL = "gpt-4.1"
OPENAI_MAX_TOKENS = 4096

# Default deployment settings for demos
DEFAULT_DEPLOYMENT_NAME = "s0-edge-site-2"
DEFAULT_NAMESPACE = "app-edge-2"

# Agent behavior settings
AGENT_VERBOSE = True
AGENT_TIMEOUT = 30  # seconds

# Kubernetes validation settings
MAX_DEPLOYMENT_NAME_LENGTH = 253
VALID_RESOURCE_TYPES = [
    "namespace", "deployment", "pod", "service", 
    "hpa", "configmap", "secret", "ingress"
] 