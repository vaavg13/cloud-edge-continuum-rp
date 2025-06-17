#!/usr/bin/env python3
"""
Prometheus Metrics Tool for Agent
Provides current metric values from Prometheus for pods, nodes, CPU, memory, and latency.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from mu_bench.metrics_exporter.prometheus_exporter import PrometheusExporter
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
import json

def format_timestamp(unix_timestamp: float) -> Dict[str, Any]:
    """Convert Unix timestamp to human-readable format for LLM consumption."""
    dt = datetime.fromtimestamp(unix_timestamp, tz=timezone.utc)
    return {
        "unix": int(unix_timestamp),
        "datetime": dt.isoformat(),
        "human_readable": dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    }

class PrometheusMetricsTool:
    """
    Tool for getting current Prometheus metrics.
    """
    
    def __init__(self, prometheus_url="http://localhost:9090"):
        """Initialize the Prometheus metrics tool."""
        # Create exporter but don't initialize CSV files
        self.exporter = PrometheusExporter(
            prometheus_url=prometheus_url,
            create_output_dir=False,
            verbose=False
        )
    
    def get_current_node_cpu(self, rate_window="1m") -> Dict[str, Any]:
        """Get current CPU usage for all nodes."""
        query = f'sum by (instance) (rate(container_cpu_usage_seconds_total{{image!="", container!="POD"}}[{rate_window}]))'
        data = self.exporter._query_prometheus(query)
        
        if not data or data.get('status') != 'success':
            return {"error": "Failed to query node CPU metrics", "data": []}
        
        results = []
        for item in data['data']['result']:
            node_id = item['metric'].get('instance', 'unknown_instance').split(':')[0]
            cpu_cores = round(float(item['value'][1]), 3)
            results.append({
                "node": node_id,
                "cpu_cores_used": cpu_cores,
                "timestamp": format_timestamp(float(item['value'][0]))
            })
        
        return {"status": "success", "data": results}
    
    def get_current_node_memory(self) -> Dict[str, Any]:
        """Get current memory usage for all nodes."""
        query = 'sum by (instance) (container_memory_working_set_bytes{image!="", container!="POD"})'
        data = self.exporter._query_prometheus(query)
        
        if not data or data.get('status') != 'success':
            return {"error": "Failed to query node memory metrics", "data": []}
        
        results = []
        for item in data['data']['result']:
            node_id = item['metric'].get('instance', 'unknown_instance').split(':')[0]
            memory_bytes = int(float(item['value'][1]))
            memory_mb = round(memory_bytes / (1024 * 1024), 2)
            results.append({
                "node": node_id,
                "memory_working_set_bytes": memory_bytes,
                "memory_working_set_mb": memory_mb,
                "timestamp": format_timestamp(float(item['value'][0]))
            })
        
        return {"status": "success", "data": results}
    
    def get_current_pod_cpu(self, namespace: Optional[str] = None, rate_window="1m") -> Dict[str, Any]:
        """Get current CPU usage for pods."""
        # Build namespace filter
        if namespace:
            namespace_filter = f'namespace="{namespace}"'
            base_selector = 'image!="", container!="POD"'
            full_selector = f'{base_selector}, {namespace_filter}'
        else:
            full_selector = 'image!="", container!="POD"'
        
        query = f'sum by (namespace, pod) (rate(container_cpu_usage_seconds_total{{{full_selector}}}[{rate_window}]))'
        data = self.exporter._query_prometheus(query)
        
        if not data or data.get('status') != 'success':
            return {"error": "Failed to query pod CPU metrics", "data": []}
        
        results = []
        for item in data['data']['result']:
            namespace_val = item['metric'].get('namespace', 'unknown_namespace')
            pod_val = item['metric'].get('pod', 'unknown_pod')
            cpu_cores = round(float(item['value'][1]), 3)
            results.append({
                "namespace": namespace_val,
                "pod": pod_val,
                "cpu_cores_used": cpu_cores,
                "timestamp": format_timestamp(float(item['value'][0]))
            })
        
        return {"status": "success", "data": results}
    
    def get_current_pod_memory(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """Get current memory usage for pods."""
        # Build namespace filter
        if namespace:
            namespace_filter = f'namespace="{namespace}"'
            base_selector = 'image!="", container!="POD"'
            full_selector = f'{base_selector}, {namespace_filter}'
        else:
            full_selector = 'image!="", container!="POD"'
        
        query = f'sum by (namespace, pod) (container_memory_usage_bytes{{{full_selector}}})'
        data = self.exporter._query_prometheus(query)
        
        if not data or data.get('status') != 'success':
            return {"error": "Failed to query pod memory metrics", "data": []}
        
        results = []
        for item in data['data']['result']:
            namespace_val = item['metric'].get('namespace', 'unknown_namespace')
            pod_val = item['metric'].get('pod', 'unknown_pod')
            memory_bytes = int(float(item['value'][1]))
            memory_mb = round(memory_bytes / (1024 * 1024), 2)
            results.append({
                "namespace": namespace_val,
                "pod": pod_val,
                "memory_usage_bytes": memory_bytes,
                "memory_usage_mb": memory_mb,
                "timestamp": format_timestamp(float(item['value'][0]))
            })
        
        return {"status": "success", "data": results}
    
    def get_current_istio_latency(self, namespace: Optional[str] = None, percentile="0.95", rate_window="1m") -> Dict[str, Any]:
        """Get current Istio latency metrics for services."""
        # Build namespace filter
        if namespace:
            namespace_filter = f'destination_workload_namespace="{namespace}"'
            base_selector = 'reporter="destination"'
            full_selector = f'{base_selector}, {namespace_filter}'
        else:
            full_selector = 'reporter="destination"'
        
        query = f'''histogram_quantile({percentile},
            sum(rate(istio_request_duration_milliseconds_bucket{{{full_selector}}}[{rate_window}]))
            by (le, destination_workload, destination_workload_namespace)
        )'''
        data = self.exporter._query_prometheus(query)
        
        if not data or data.get('status') != 'success':
            return {"error": "Failed to query Istio latency metrics", "data": []}
        
        results = []
        for item in data['data']['result']:
            pod_name_val = item['metric'].get('destination_workload', 'unknown_pod')
            namespace_val = item['metric'].get('destination_workload_namespace', 'unknown_namespace')
            latency_ms = float(item['value'][1])
            
            if latency_ms != float('inf'):  # Filter out +Inf values
                results.append({
                    "namespace": namespace_val,
                    "workload": pod_name_val,
                    "p95_latency_ms": round(latency_ms, 2),
                    "timestamp": format_timestamp(float(item['value'][0]))
                })
        
        return {"status": "success", "data": results}
    
    def get_metrics_summary(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """Get a summary of all current metrics for a namespace or all namespaces."""
        now = datetime.now(timezone.utc)
        summary = {
            "namespace_filter": namespace or "all_namespaces",
            "summary_generated_at": {
                "unix": int(now.timestamp()),
                "datetime": now.isoformat(),
                "human_readable": now.strftime("%Y-%m-%d %H:%M:%S UTC")
            },
            "metrics": {}
        }
        
        # Get all metrics
        summary["metrics"]["node_cpu"] = self.get_current_node_cpu()
        summary["metrics"]["node_memory"] = self.get_current_node_memory()
        summary["metrics"]["pod_cpu"] = self.get_current_pod_cpu(namespace)
        summary["metrics"]["pod_memory"] = self.get_current_pod_memory(namespace)
        summary["metrics"]["istio_latency"] = self.get_current_istio_latency(namespace)
        
        return summary

# Global instance to be used by agent
_prometheus_tool = None

def get_prometheus_tool(prometheus_url="http://localhost:9090") -> PrometheusMetricsTool:
    """Get or create global PrometheusMetricsTool instance."""
    global _prometheus_tool
    if _prometheus_tool is None:
        _prometheus_tool = PrometheusMetricsTool(prometheus_url)
    return _prometheus_tool

def prometheus_get_node_cpu(rate_window: str = "1m") -> Dict[str, Any]:
    """Get current CPU usage for all nodes."""
    tool = get_prometheus_tool()
    return tool.get_current_node_cpu(rate_window)

def prometheus_get_node_memory() -> Dict[str, Any]:
    """Get current memory usage for all nodes."""
    tool = get_prometheus_tool()
    return tool.get_current_node_memory()

def prometheus_get_pod_cpu(namespace: Optional[str] = None, rate_window: str = "1m") -> Dict[str, Any]:
    """Get current CPU usage for pods in specified namespace or all namespaces."""
    tool = get_prometheus_tool()
    return tool.get_current_pod_cpu(namespace, rate_window)

def prometheus_get_pod_memory(namespace: Optional[str] = None) -> Dict[str, Any]:
    """Get current memory usage for pods in specified namespace or all namespaces."""
    tool = get_prometheus_tool()
    return tool.get_current_pod_memory(namespace)

def prometheus_get_istio_latency(namespace: Optional[str] = None, percentile: str = "0.95", rate_window: str = "1m") -> Dict[str, Any]:
    """Get current Istio latency metrics for services in specified namespace or all namespaces."""
    tool = get_prometheus_tool()
    return tool.get_current_istio_latency(namespace, percentile, rate_window)

def prometheus_get_metrics_summary(namespace: Optional[str] = None) -> Dict[str, Any]:
    """Get a summary of all current metrics for a namespace or all namespaces."""
    tool = get_prometheus_tool()
    return tool.get_metrics_summary(namespace) 