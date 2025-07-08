# Main test configuration
EXPERIMENT_CONFIG = {
    # Target application settings
    "namespace": "app-edge",
    "target_app": "s2-cloud",
    "app_directory": "./APPS",
    
    # Test timing configuration - simplified phases with longer warmup
    "pod_warmup_duration": 300,     # Extended warmup with smart monitoring for service stabilization  
    "baseline_duration": 60,        # Record baseline metrics
    "chaos_warmup_duration": 60,    # Chaos impact + warmup before agent (record metrics during chaos)
    "recovery_duration": 60,        # Recovery after agent execution (record metrics)
    
    # Chaos configuration
    # Note: chaos_duration is calculated automatically based on phases
    
    # PREVIOUS CPU STRESS EXPERIMENT (commented out):
    # "chaos_config": {
    #     "fault_type": "cpu_stress",
    #     "intensity": "extreme",  # extreme, high, medium, low
    #     "seed": 42,
    #     "target_mode": "one",  # "one", "all", "fixed", "fixed-percent", "random-max-percent"
    #     "target_value": "",    # Used with fixed/fixed-percent/random-max-percent modes
    # },
    
    # POD FAILURE EXPERIMENT:
    "chaos_config": {
        "fault_type": "pod_failure",
        "intensity": "medium",   # Not directly used for pod failure but kept for consistency
        "duration": "600s",      # Really big duration - pod stays down for 10 minutes
        "seed": 42,
        "target_mode": "all",    # "one", "all", "fixed", "fixed-percent", "random-max-percent"
        "target_value": "",      # Used with fixed/fixed-percent/random-max-percent modes
    },
    
    # Agent configuration
    "agent_config": {
        "max_rounds": 50,
        "agent_timeout": 90,
        "openai_model": "gpt-4.1",
        "show_reasoning": True,  # Enable reasoning summaries for better explainability
        "reasoning_in_context": False
    },
    
    # Traffic generation configuration
    "traffic_config": {
        "endpoints": [
            "http://172.23.0.5:31115/s0-edge-site-1",
            "http://172.23.0.5:31115/s0-edge-site-2"
        ],
        "requests_per_second": 5,  # 2 req/s per endpoint = 4 req/s total = 240 req per 60s phase (conservative)
        "request_timeout": 10,
        "collect_metrics": True
    },
    
    # Test behavior settings
    "test_settings": {
        "deploy_fresh_app": True,      # Deploy fresh app instances
        "cleanup_after_test": True,    # Clean up test resources
        "pod_ready_timeout": 300,      # Timeout for pod readiness in seconds
        "skip_warmup_baseline": False, # Skip warmup and baseline phases for faster testing
    }
}

# Alert configuration - what the agent receives
ALERT_CONFIG = {
    "alert_template": "🚨 CRITICAL INCIDENT: Performance degradation detected in namespace '{namespace}' at {timestamp}. ALERT TRIGGERS: Service latency degraded from {baseline_latency_p95} to {current_latency_p95} (degradation threshold exceeded), Success rate dropped from {baseline_success_rate}% to {current_success_rate}% (availability threshold exceeded). IMMEDIATE INVESTIGATION AND CORRECTIVE ACTION REQUIRED. You must: 1) Investigate and identify which specific services/deployments are affected and causing this degradation, 2) Determine root cause of the performance issues, 3) Implement appropriate remediation actions, 4) Validate that service performance is restored to acceptable levels. Use Prometheus metrics and Kubernetes tools to diagnose the situation systematically.",
    "context_fields": [
        "namespace",
        "alert_type", 
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
