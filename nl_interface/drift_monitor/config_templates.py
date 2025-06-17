import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def create_simple_config(namespace: str, metric_type: str, threshold: float, 
                        prometheus_url: str = "http://localhost:9090") -> Dict[str, Any]:
    """Create a simple monitoring config - useful for LLM generation."""
    
    # Map metric types to appropriate units
    unit_map = {
        "pod_cpu": "cores",
        "pod_memory": "MB", 
        "istio_latency": "ms",
        "node_cpu": "cores",
        "node_memory": "MB"
    }
    
    return {
        "version": "1.0",
        "prometheus_url": prometheus_url,
        "loop_id": f"{namespace}-{metric_type}-monitor",
        "namespace": namespace,
        "description": f"Monitor {metric_type} in {namespace}",
        "thresholds": [
            {
                "metric_type": metric_type,
                "threshold_value": threshold,
                "operator": ">",
                "unit": unit_map.get(metric_type, ""),
                "consecutive_violations": 2,
                "description": f"{metric_type} should not exceed {threshold}"
            }
        ],
        "check_interval_seconds": 30,
        "enabled": True
    }

def create_simple_intent_templates() -> Dict[str, str]:
    """Create common intent templates for different scenarios."""
    return {
        "cpu_scaling": "Scale up pods in {namespace} due to high CPU usage: {metric_value} > {threshold_value}",
        "memory_issue": "Handle memory pressure in {namespace}: {metric_value}{unit} exceeds {threshold_value}{unit}",
        "performance_issue": "Fix performance issue in {namespace}: {metric_type} is {metric_value}",
        "generic": "Handle {metric_type} issue in {namespace}: current value {metric_value} exceeds threshold {threshold_value}",
        "edge_critical": "URGENT: Critical resource issue in edge namespace {namespace} - {metric_type}: {metric_value}",
        "investigation": "Investigate {metric_type} anomaly in {namespace} and take corrective action if needed"
    }