# Main test configuration
EXPERIMENT_CONFIG = {
    # Target application settings
    "namespace": "app-edge",
    "target_app": "s2-cloud",
    "app_directory": "./APPS",
    
    # Test timing configuration - simplified phases
    "pod_warmup_duration": 60,      # Warmup pods (no metrics recorded)
    "baseline_duration": 60,        # Record baseline metrics
    "chaos_warmup_duration": 60,    # Chaos impact + warmup before agent (record metrics during chaos)
    "recovery_duration": 60,        # Recovery after agent execution (record metrics)
    
    # Chaos configuration
    # Note: chaos_duration is calculated automatically based on phases
    "chaos_config": {
        "fault_type": "cpu_stress",
        "intensity": "extreme",  # extreme, high, medium, low
        "seed": 42,
        "target_mode": "all",  # "one", "all", "fixed", "fixed-percent", "random-max-percent"
        "target_value": "",    # Used with fixed/fixed-percent/random-max-percent modes
    },
    
    # Agent configuration
    "agent_config": {
        "max_rounds": 50,
        "agent_timeout": 90,
        "openai_model": "gpt-4.1",
        "show_reasoning": True  # Enable reasoning summaries for better explainability
    },
    
    # Traffic generation configuration
    "traffic_config": {
        "endpoints": [
            "http://172.23.0.5:31115/s0-edge-site-1",
            "http://172.23.0.5:31115/s0-edge-site-2"
        ],
        "requests_per_second": 20,  # Moderate load
        "request_timeout": 5,
        "collect_metrics": True
    },
    
    # Test behavior settings
    "test_settings": {
        "deploy_fresh_app": True,      # Deploy fresh app instances
        "cleanup_after_test": True,    # Clean up test resources
        "pod_ready_timeout": 300,      # Timeout for pod readiness in seconds
    }
}

# Alert configuration - what the agent receives
ALERT_CONFIG = {
    "alert_template": "CRITICAL: Performance degradation detected on deployment {target_app} in namespace {namespace}. IMMEDIATE CORRECTIVE ACTION REQUIRED to restore performance to baseline levels. Current performance vs baseline: Latency {current_latency_p95}s (baseline: {baseline_latency_p95}s), Success rate {current_success_rate}% (baseline: {baseline_success_rate}%). You must implement corrective actions and validate improvement.",
    "context_fields": [
        "namespace",
        "alert_type", 
        "affected_service",
        "timestamp",
        "baseline_latency_p95",
        "baseline_success_rate",
        "current_latency_p95", 
        "current_success_rate"
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
