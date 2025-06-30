#!/usr/bin/env python3
"""
Experiment Utilities
Helper functions for experiment configuration and validation.
"""

from .experiment_config import EXPERIMENT_CONFIG, ALERT_CONFIG, LOGGING_CONFIG

def calculate_chaos_duration(config=None):
    """Set chaos duration to run indefinitely until manually cleaned up.
    
    The agent execution time is unpredictable - it could finish in 30 seconds
    or take several minutes depending on the complexity of the issue and 
    number of diagnostic steps required. We set a very long duration and
    clean up the chaos experiment manually after the agent completes.
    """
    if config is None:
        config = EXPERIMENT_CONFIG
    
    # Set chaos to run for 1 hour (practically infinite for our experiments)
    # This ensures chaos is ALWAYS active during agent execution
    # and we manually clean it up when the experiment ends
    chaos_duration_seconds = 3600  # 1 hour
    
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