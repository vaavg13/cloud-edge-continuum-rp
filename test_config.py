"""
Configuration for comprehensive integration tests.
Update these settings based on your environment.
"""

import os

# Test configuration
TEST_CONFIG = {
    # Test namespace in Kubernetes
    "namespace": "app-edge",
    
    # Prometheus configuration
    "prometheus_url": "http://localhost:9090",
    
    # Agent configuration - API key will be auto-loaded from environment
    "agent_config": {
        "max_rounds": 50,
        "agent_timeout": 60,
        "openai_model": "gpt-4.1"
    },
    
    # Drift monitor configuration
    "monitor_config": {
        "prometheus_url": "http://localhost:9090",
        "check_interval": 30,
        "metrics": [
            {
                "name": "s0_edge_site_1_cpu",
                "type": "cpu_usage_percent",
                "query": "avg(rate(container_cpu_usage_seconds_total{namespace=\"app-edge\",pod=~\"s0-edge-site-1.*\"}[5m])) * 100",
                "threshold": 5.0,  # Very low threshold for testing
                "operator": "greater_than",
                "namespace": "app-edge",
                "deployment_name": "s0-edge-site-1"
            },
            {
                "name": "s0_edge_site_2_cpu",
                "type": "cpu_usage_percent", 
                "query": "avg(rate(container_cpu_usage_seconds_total{namespace=\"app-edge\",pod=~\"s0-edge-site-2.*\"}[5m])) * 100",
                "threshold": 5.0,  # Very low threshold for testing
                "operator": "greater_than",
                "namespace": "app-edge",
                "deployment_name": "s0-edge-site-2"
            },
            {
                "name": "s1_edge_site_1_memory",
                "type": "memory_usage_percent",
                "query": "avg(container_memory_working_set_bytes{namespace=\"app-edge\",pod=~\"s1-edge-site-1.*\"} / container_spec_memory_limit_bytes{namespace=\"app-edge\",pod=~\"s1-edge-site-1.*\"} * 100)",
                "threshold": 10.0,  # Low threshold for testing
                "operator": "greater_than",
                "namespace": "app-edge",
                "deployment_name": "s1-edge-site-1"
            },
            {
                "name": "s2_cloud_memory",
                "type": "memory_usage_percent",
                "query": "avg(container_memory_working_set_bytes{namespace=\"app-edge\",pod=~\"s2-cloud.*\"} / container_spec_memory_limit_bytes{namespace=\"app-edge\",pod=~\"s2-cloud.*\"} * 100)",
                "threshold": 10.0,  # Low threshold for testing
                "operator": "greater_than",
                "namespace": "app-edge",
                "deployment_name": "s2-cloud"
            },
            {
                "name": "app_edge_pod_restarts",
                "type": "pod_restart_count",
                "query": "increase(kube_pod_container_status_restarts_total{namespace=\"app-edge\"}[5m])",
                "threshold": 0,
                "operator": "greater_than",
                "namespace": "app-edge"
            }
        ]
    },
    
    # Orchestrator configuration  
    "orchestrator_config": {
        "check_interval_seconds": 30,
        "agent_cooldown_seconds": 60,  # Short cooldown for testing
        "agent_timeout_seconds": 120,
        "max_concurrent_agents": 1
    },
    
    # Test behavior settings
    "test_settings": {
        "create_test_workload": False,  # Don't create new workloads, use existing s0, s1, s2
        "create_stress_load": True,     # Create CPU stress pod to trigger violations
        "stress_duration": "90s",       # How long to run stress test
        "cleanup_after_test": True,     # Whether to cleanup test resources
        "wait_for_metrics": 45,         # Seconds to wait for metrics after creating load
        "target_services": ["s0-edge-site-1", "s0-edge-site-2", "s1-edge-site-1", "s2-cloud", "gw-nginx"],  # Existing services to monitor
        "target_deployments": ["s0-edge-site-1", "s0-edge-site-2", "s1-edge-site-1", "s2-cloud", "gw-nginx"]  # Existing deployments
    }
}

# CPU stress pod for triggering violations
STRESS_POD_MANIFEST = """
apiVersion: v1
kind: Pod
metadata:
  name: cpu-stress-test
  namespace: {namespace}
  labels:
    app: stress-test
    test: cpu-load
spec:
  containers:
  - name: stress
    image: polinux/stress
    command: ["stress"]
    args: ["--cpu", "2", "--timeout", "{duration}"]
    resources:
      requests:
        cpu: 100m
        memory: 64Mi
      limits:
        cpu: 500m  # Higher limit to allow CPU stress
        memory: 128Mi
  restartPolicy: Never
""" 