#!/usr/bin/env python3
"""
Experiment Configuration
Central configuration for chaos injection and mitigation tests.
"""

# Main test configuration
EXPERIMENT_CONFIG = {
    # Target application settings
    "namespace": "app-edge",
    "target_app": "s0-edge-site-1",
    "app_directory": "./APPS",
    
    # Test timing configuration
    "chaos_duration": "240s",  
    "monitoring_duration": 360,
    "baseline_duration": 60,   
    "chaos_wait_duration": 120,
    "recovery_duration": 60,   
    "warmup_duration": 30,     
    
    # Chaos configuration
    "chaos_config": {
        "fault_type": "cpu_stress",
        "intensity": "extreme",  # extreme, high, medium, low
        "seed": 42
    },
    
    # Agent configuration
    "agent_config": {
        "max_rounds": 50,
        "agent_timeout": 90,
        "openai_model": "gpt-4.1"
    },
    
    # Traffic generation configuration
    "traffic_config": {
        "endpoints": [
            "http://172.23.0.5:31115/s0-edge-site-1",
            "http://172.23.0.5:31115/s0-edge-site-2"
        ],
        "requests_per_second": 5,  # Moderate load
        "request_timeout": 5,
        "collect_metrics": True
    },
    
    # Test behavior settings
    "test_settings": {
        "deploy_fresh_app": True,      # Deploy fresh app instances
        "run_warmup_traffic": True,    # Run warmup traffic for pods
        "cleanup_after_test": True,    # Clean up test resources
        "enable_detailed_logging": False,  # Enable more verbose logging
        "pod_ready_timeout": 300       # Timeout for pod readiness in seconds
    }
}

# Alert configuration - what the agent receives
ALERT_CONFIG = {
    "alert_template": "ALERT: High CPU usage detected on {target_app} in namespace {namespace}. Please investigate and resolve any performance issues affecting the application.",
    "context_fields": [
        "namespace",
        "alert_type", 
        "affected_service",
        "timestamp"
    ]
}

# Logging configuration
LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "suppress_libs": [
        "httpx",
        "httpcore"
    ]
}

def get_experiment_config():
    """Get the main experiment configuration."""
    return EXPERIMENT_CONFIG.copy()

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
