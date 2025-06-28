#!/usr/bin/env python3
"""
Experiment Utilities
Helper functions for experiment configuration and validation.
"""

from .experiment_config import EXPERIMENT_CONFIG, ALERT_CONFIG, LOGGING_CONFIG

def calculate_chaos_duration(config=None):
    """Calculate chaos duration to cover all chaos phases with buffer."""
    if config is None:
        config = EXPERIMENT_CONFIG
    
    # Chaos needs to cover:
    # - chaos_warmup_duration: metrics during active chaos
    # - agent_timeout: agent execution during chaos  
    # - recovery_duration: recovery monitoring (chaos may still be active)
    # - buffer: safety margin
    
    chaos_duration_seconds = (
        config["chaos_warmup_duration"] +
        config["agent_config"]["agent_timeout"] +
        config["recovery_duration"] +
        30  # 30s buffer
    )
    
    return f"{chaos_duration_seconds}s"

def calculate_monitoring_duration(config=None):
    """Calculate total monitoring duration based on all phases."""
    if config is None:
        config = EXPERIMENT_CONFIG
    
    # Calculate total based on simplified phases
    total_duration = (
        config["pod_warmup_duration"] +
        config["baseline_duration"] +
        config["chaos_warmup_duration"] +
        config["agent_config"]["agent_timeout"] +  # Max time for agent
        config["recovery_duration"] +
        30  # Buffer time for transitions
    )
    
    return total_duration

def get_experiment_config():
    """Get the main experiment configuration with calculated values."""
    config = EXPERIMENT_CONFIG.copy()
    
    # Add calculated chaos duration and monitoring duration
    config["chaos_duration"] = calculate_chaos_duration(config)
    config["monitoring_duration"] = calculate_monitoring_duration(config)
    
    return config

def get_alert_config():
    """Get the alert configuration."""
    return ALERT_CONFIG.copy()

def get_logging_config():
    """Get the logging configuration."""
    return LOGGING_CONFIG.copy()

def validate_config():
    """Validate that all required configuration is present."""
    required_fields = [
        "namespace", "target_app", "chaos_duration",
        "agent_config", "traffic_config"
    ]
    
    config = get_experiment_config()
    missing_fields = []
    
    for field in required_fields:
        if field not in config:
            missing_fields.append(field)
    
    if missing_fields:
        raise ValueError(f"Missing required configuration fields: {missing_fields}")
    
    # Validate agent config
    agent_required = ["max_rounds", "agent_timeout", "openai_model"]
    for field in agent_required:
        if field not in config["agent_config"]:
            missing_fields.append(f"agent_config.{field}")
    
    # Validate traffic config
    traffic_required = ["endpoints", "requests_per_second", "request_timeout"]
    for field in traffic_required:
        if field not in config["traffic_config"]:
            missing_fields.append(f"traffic_config.{field}")
    
    if missing_fields:
        raise ValueError(f"Missing required configuration fields: {missing_fields}")
    
    return True 