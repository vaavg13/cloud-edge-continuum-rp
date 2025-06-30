#!/usr/bin/env python3
"""
Prometheus Metrics Formatting Utilities
Helper functions for formatting Prometheus metrics data for display and agent context.
"""

from typing import Dict, Any, Optional

def format_pod_cpu(prometheus_metrics: Dict[str, Any], namespace: str) -> str:
    """Format pod CPU metrics for display."""
    if not prometheus_metrics or not prometheus_metrics.get("metrics", {}).get("pod_cpu"):
        return "unavailable"
    
    pod_cpu_data = prometheus_metrics["metrics"]["pod_cpu"].get("data", [])
    if not pod_cpu_data:
        return "no data"
    
    # Filter for target namespace
    target_pods = [p for p in pod_cpu_data if p.get("namespace") == namespace]
    if not target_pods:
        return "no pods in target namespace"
    
    # Format summary - CPU is in millicores format like "5m"
    total_cpu_millicores = 0
    for pod in target_pods:
        cpu_str = pod.get("cpu_millicores", "0m")
        if cpu_str.endswith("m"):
            total_cpu_millicores += int(cpu_str[:-1])
    total_cpu_cores = total_cpu_millicores / 1000
    
    return f"{len(target_pods)} pods, {total_cpu_cores:.3f} total CPU cores ({total_cpu_millicores}m)"

def format_pod_memory(prometheus_metrics: Dict[str, Any], namespace: str) -> str:
    """Format pod memory metrics for display."""
    if not prometheus_metrics or not prometheus_metrics.get("metrics", {}).get("pod_memory"):
        return "unavailable"
    
    pod_memory_data = prometheus_metrics["metrics"]["pod_memory"].get("data", [])
    if not pod_memory_data:
        return "no data"
    
    # Filter for target namespace
    target_pods = [p for p in pod_memory_data if p.get("namespace") == namespace]
    if not target_pods:
        return "no pods in target namespace"
    
    # Format summary - extract numeric value from "XXMi" format
    total_memory_mib = 0
    for pod in target_pods:
        memory_str = pod.get("memory_working_set_mib", "0Mi")
        if memory_str.endswith("Mi"):
            total_memory_mib += int(memory_str[:-2])
    
    return f"{len(target_pods)} pods, {total_memory_mib}Mi total memory"

def format_istio_latency(prometheus_metrics: Dict[str, Any], namespace: str) -> str:
    """Format Istio latency metrics for display."""
    if not prometheus_metrics or not prometheus_metrics.get("metrics", {}).get("istio_latency"):
        return "unavailable"
    
    istio_data = prometheus_metrics["metrics"]["istio_latency"].get("data", [])
    if not istio_data:
        return "no data"
    
    # Filter for target namespace
    target_services = [s for s in istio_data if s.get("namespace") == namespace]
    if not target_services:
        return "no services in target namespace"
    
    # Format summary
    avg_latency = sum(s.get("p95_latency_ms", 0) for s in target_services) / len(target_services)
    return f"{len(target_services)} services, {avg_latency:.2f}ms avg P95 latency"

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

def extract_prometheus_cpu(prometheus_metrics: Dict[str, Any], namespace: str) -> str:
    """Extract total CPU cores as simple number."""
    if not prometheus_metrics or not prometheus_metrics.get("metrics", {}).get("pod_cpu"):
        return "unknown"
    
    pod_cpu_data = prometheus_metrics["metrics"]["pod_cpu"].get("data", [])
    if not pod_cpu_data:
        return "unknown"
    
    # Filter for target namespace
    target_pods = [p for p in pod_cpu_data if p.get("namespace") == namespace]
    if not target_pods:
        return "unknown"
    
    # Calculate total CPU cores
    total_cpu_millicores = 0
    for pod in target_pods:
        cpu_str = pod.get("cpu_millicores", "0m")
        if cpu_str.endswith("m"):
            total_cpu_millicores += int(cpu_str[:-1])
    total_cpu_cores = total_cpu_millicores / 1000
    
    return f"{total_cpu_cores:.3f}" 