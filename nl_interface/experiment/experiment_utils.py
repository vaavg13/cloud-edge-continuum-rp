#!/usr/bin/env python3
"""
Experiment Utilities
Helper functions for experiment configuration and validation.
"""

import asyncio
from typing import Dict, Any
from .experiment_config import EXPERIMENT_CONFIG, ALERT_CONFIG, LOGGING_CONFIG

async def smart_warmup_with_monitoring(config, traffic_generator):
    """Smart warmup that monitors latency until it stabilizes.
    
    Args:
        config: Experiment configuration containing pod_warmup_duration
        traffic_generator: Traffic generator instance with reset_phase_metrics() and get_phase_metrics() methods
    """
    max_warmup_time = config["pod_warmup_duration"]  # Safety limit
    check_interval = 30  # Check every 30 seconds
    stability_window = 3  # Need 3 stable measurements
    stability_threshold = 0.3  # Latency variation < 30% to consider stable
    min_success_rate = 70  # Minimum success rate to consider healthy
    
    latency_history = []
    elapsed_time = 0
    stable_count = 0
    
    print(
        f"🔄 Monitoring warmup (max {max_warmup_time}s, "
        f"checking every {check_interval}s)"
    )
    print(
        f"📊 Looking for latency stabilization: <{stability_threshold * 100}% "
        f"variation for {stability_window} measurements"
    )
    
    # Reset metrics at start of warmup
    traffic_generator.reset_phase_metrics()
    
    while elapsed_time < max_warmup_time:
        await asyncio.sleep(check_interval)
        elapsed_time += check_interval
        
        # Get current metrics for this check interval
        metrics = traffic_generator.get_phase_metrics(check_interval)
        
        # Reset metrics after reading (so next measurement is clean)
        traffic_generator.reset_phase_metrics()
        
        if not metrics or metrics.get('total_requests', 0) == 0:
            print(f"⏳ {elapsed_time}s: No requests yet, continuing warmup...")
            continue
            
        current_latency = metrics.get('p95_latency_seconds', 0)
        success_rate = metrics.get('success_rate_percent', 0)
        
        print(
            f"📈 {elapsed_time}s: P95={current_latency:.3f}s, "
            f"Success={success_rate:.1f}%, Req={metrics.get('total_requests', 0)}"
        )
        
        # Check if service is healthy enough to measure
        if success_rate < min_success_rate:
            print(
                f"⚠️  Success rate too low ({success_rate:.1f}% < {min_success_rate}%), "
                f"continuing warmup..."
            )
            latency_history.clear()  # Reset history due to unhealthy state
            stable_count = 0
            continue
        
        # Add to latency history
        latency_history.append(current_latency)
        
        # Only start checking stability after we have enough history
        if len(latency_history) < stability_window:
            continue
            
        # Keep only recent history
        if len(latency_history) > stability_window:
            latency_history.pop(0)
        
        # Check if latency is stable (low variation)
        if len(latency_history) == stability_window:
            min_latency = min(latency_history)
            max_latency = max(latency_history)
            
            # Avoid division by zero
            if min_latency > 0:
                variation = (max_latency - min_latency) / min_latency
                
                if variation <= stability_threshold:
                    stable_count += 1
                    print(f"✅ Stable measurement {stable_count}: variation {variation:.2%} (threshold: {stability_threshold:.0%})")
                    
                    # Consider stable if we have enough consecutive stable measurements
                    if stable_count >= 2:  # At least 2 consecutive stable intervals
                        print(f"🎯 Latency stabilized at ~{current_latency:.3f}s after {elapsed_time}s")
                        print(f"✅ Warmup complete - services ready for baseline measurement")
                        return
                else:
                    stable_count = 0
                    print(f"📊 Variation {variation:.2%} > {stability_threshold:.0%}, waiting for stability...")
    
    # If we exit the loop, we hit max time
    if latency_history:
        avg_latency = sum(latency_history) / len(latency_history)
        print(f"⏰ Max warmup time reached ({max_warmup_time}s)")
        print(f"📊 Final average latency: {avg_latency:.3f}s")
    else:
        print(f"⚠️  Warmup completed without stable measurements")
    
    print(f"✅ Proceeding to baseline measurement")

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
        "namespace", "chaos_duration",
        "agent_config", "traffic_config"
    ]
    
    config = get_experiment_config()
    missing_fields = []
    
    for field in required_fields:
        if field not in config:
            missing_fields.append(field)
    
    # Validate chaos config based on mode
    chaos_config = config.get("chaos_config", {})
    mode = chaos_config.get("mode")
    
    if mode == "chaos_only":
        # For chaos_only mode, target_app is required
        if "target_app" not in chaos_config:
            missing_fields.append("chaos_config.target_app")
    
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

def extract_prometheus_latency(prometheus_metrics: Dict[str, Any], namespace: str) -> str:
    """Extract average P95 latency value as simple number."""
    if not prometheus_metrics or not prometheus_metrics.get("metrics", {}).get("istio_latency"):
        return "unknown"
    
    istio_data = prometheus_metrics["metrics"]["istio_latency"].get("data", [])
    if not istio_data:
        return "unknown"
    
    # Filter for target namespace
    target_services = [s for s in istio_data if s.get("namespace") == namespace]
    if not target_services:
        return "unknown"
    
    # Return average latency as a simple number
    avg_latency = sum(s.get("p95_latency_ms", 0) for s in target_services) / len(target_services)
    return f"{avg_latency:.1f}" 