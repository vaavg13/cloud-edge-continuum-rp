#!/usr/bin/env python3
"""
Configuration settings for the Kubernetes Agent.
"""

import os

# OpenAI API key (can be overridden by environment variable)
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', 
    'sk-proj-DiA9-QUBGXsMxJGD4khuFmpH9bm7Ww-'
    'D2hWzAPREKhsQaLf2bcBN1awr32g4kMT63LMmy5kmGeT3BlbkFJQUGUw-'
    '40noCLugjh0hDoU94R0Iz6BLzAxwRcsybW7CjQS8bOKzhBS2EZp7-'
    'B3ZmRHNk8znukoA'
)

# MCP Server configuration
MCP_SERVER_COMMAND = ["npx", "mcp-server-kubernetes"]

# OpenAI model settings
OPENAI_MODEL = "gpt-4.1"
OPENAI_MAX_TOKENS = 4096

# Default deployment settings for demos
DEFAULT_DEPLOYMENT_NAME = "s0-edge-site-1"
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