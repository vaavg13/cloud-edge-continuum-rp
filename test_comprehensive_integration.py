#!/usr/bin/env python3
"""
Comprehensive Integration Test Script
Tests agent, drift monitor, and full pipeline integration.
"""

import asyncio
import json
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List
from test_config import TEST_CONFIG, STRESS_POD_MANIFEST

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Extract config values
TEST_NAMESPACE = TEST_CONFIG["namespace"]

class TestResults:
    """Track test results."""
    
    def __init__(self):
        self.results = {}
        self.start_time = time.time()
    
    def add_result(self, test_name: str, status: str, details: Any = None, error: str = None):
        """Add a test result."""
        self.results[test_name] = {
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "details": details,
            "error": error
        }
        
        # Print result
        emoji = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{emoji} {test_name}: {status}")
        if error:
            print(f"   Error: {error}")
        if details and isinstance(details, dict):
            for key, value in details.items():
                print(f"   {key}: {value}")
        print()
    
    def print_summary(self):
        """Print test summary."""
        total_time = time.time() - self.start_time
        
        passed = sum(1 for r in self.results.values() if r["status"] == "PASS")
        failed = sum(1 for r in self.results.values() if r["status"] == "FAIL")
        warnings = sum(1 for r in self.results.values() if r["status"] == "WARN")
        
        print("=" * 60)
        print("🧪 TEST SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {len(self.results)}")
        print(f"Passed: {passed} ✅")
        print(f"Failed: {failed} ❌")  
        print(f"Warnings: {warnings} ⚠️")
        print(f"Execution Time: {total_time:.2f}s")
        print("=" * 60)

async def test_cluster_connectivity(results: TestResults):
    """Test basic cluster connectivity."""
    print("🔍 Testing Cluster Connectivity...")
    
    try:
        # Test kubectl access
        import subprocess
        result = subprocess.run(
            ["kubectl", "get", "nodes"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            node_count = len([line for line in result.stdout.split('\n') if line.strip() and not line.startswith('NAME')])
            results.add_result(
                "cluster_connectivity",
                "PASS",
                {"nodes_found": node_count, "kubectl_access": "working"}
            )
        else:
            results.add_result(
                "cluster_connectivity", 
                "FAIL",
                error=f"kubectl failed: {result.stderr}"
            )
            
    except Exception as e:
        results.add_result("cluster_connectivity", "FAIL", error=str(e))

async def test_existing_infrastructure(results: TestResults):
    """Test existing infrastructure (services s0, s1, s2 and deployments)."""
    print(f"🏗️ Testing Existing Infrastructure ({TEST_NAMESPACE})...")
    
    try:
        import subprocess
        
        # Check if namespace exists
        ns_result = subprocess.run(
            ["kubectl", "get", "namespace", TEST_NAMESPACE],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if ns_result.returncode != 0:
            results.add_result(
                "existing_infrastructure",
                "FAIL", 
                error=f"Namespace {TEST_NAMESPACE} does not exist"
            )
            return
        
        # Check for existing services
        services_result = subprocess.run(
            ["kubectl", "get", "services", "-n", TEST_NAMESPACE, "-o", "json"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Check for existing deployments
        deployments_result = subprocess.run(
            ["kubectl", "get", "deployments", "-n", TEST_NAMESPACE, "-o", "json"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Check for existing pods
        pods_result = subprocess.run(
            ["kubectl", "get", "pods", "-n", TEST_NAMESPACE, "-o", "json"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if all(r.returncode == 0 for r in [services_result, deployments_result, pods_result]):
            services_data = json.loads(services_result.stdout)
            deployments_data = json.loads(deployments_result.stdout)
            pods_data = json.loads(pods_result.stdout)
            
            service_names = [svc["metadata"]["name"] for svc in services_data.get("items", [])]
            deployment_names = [dep["metadata"]["name"] for dep in deployments_data.get("items", [])]
            pod_count = len(pods_data.get("items", []))
            
            target_services = TEST_CONFIG["test_settings"]["target_services"]
            target_deployments = TEST_CONFIG["test_settings"]["target_deployments"]
            
            found_services = [svc for svc in target_services if svc in service_names]
            found_deployments = [dep for dep in target_deployments if dep in deployment_names]
            
            results.add_result(
                "existing_infrastructure",
                "PASS",
                {
                    "namespace": TEST_NAMESPACE,
                    "total_services": len(service_names),
                    "target_services_found": found_services,
                    "total_deployments": len(deployment_names), 
                    "target_deployments_found": found_deployments,
                    "total_pods": pod_count
                }
            )
        else:
            results.add_result("existing_infrastructure", "FAIL", error="Failed to query infrastructure")
            
    except Exception as e:
        results.add_result("existing_infrastructure", "FAIL", error=str(e))

async def test_prometheus_connectivity(results: TestResults):
    """Test Prometheus connectivity and basic queries."""
    print("📊 Testing Prometheus Connectivity...")
    
    try:
        from nl_interface.shared.prometheus_client import prometheus_get_metrics_summary
        
        # Test basic metrics query
        metrics_result = prometheus_get_metrics_summary()
        
        if metrics_result.get("error"):
            results.add_result(
                "prometheus_connectivity",
                "FAIL", 
                error=metrics_result["error"]
            )
        else:
            results.add_result(
                "prometheus_connectivity",
                "PASS",
                {
                    "metrics_available": len(metrics_result.get("metrics", [])),
                    "prometheus_url": TEST_CONFIG["prometheus_url"]
                }
            )
            
    except Exception as e:
        results.add_result("prometheus_connectivity", "FAIL", error=str(e))

async def test_agent_independently(results: TestResults):
    """Test the agent independently with simple tasks."""
    print("🤖 Testing Agent Independently...")
    
    try:
        from nl_interface.agent.agent import KubernetesAgent
        
        # Test with simple kubectl commands
        agent = KubernetesAgent(config=TEST_CONFIG["agent_config"])
        
        await agent.initialize()
        
        # Test simple intent: check existing services
        intent = f"Check the status of services s0, s1, and s2 in the {TEST_NAMESPACE} namespace and list their pods"
        
        actions = await agent.agent_loop(intent)
        
        await agent.cleanup()
        
        if actions:
            results.add_result(
                "agent_independent_test",
                "PASS",
                {
                    "actions_taken": len(actions),
                    "intent": intent,
                    "first_action": actions[0] if actions else None
                }
            )
        else:
            results.add_result(
                "agent_independent_test",
                "WARN",
                {"actions_taken": 0, "intent": intent}
            )
            
    except Exception as e:
        results.add_result("agent_independent_test", "FAIL", error=str(e))

async def test_agent_prometheus_queries(results: TestResults):
    """Test agent with Prometheus queries."""
    print("📈 Testing Agent Prometheus Integration...")
    
    try:
        from nl_interface.agent.agent import KubernetesAgent
        
        agent = KubernetesAgent(config=TEST_CONFIG["agent_config"])
        await agent.initialize()
        
        # Test intent: get metrics for specific services  
        intent = f"Get CPU and memory metrics for services s0, s1, and s2 in {TEST_NAMESPACE} namespace using Prometheus, focusing on s0 deployments in edge-site-1 and edge-site-2"
        
        actions = await agent.agent_loop(intent)
        
        await agent.cleanup()
        
        if actions:
            has_prometheus_action = any("prometheus" in action.lower() for action in actions)
            results.add_result(
                "agent_prometheus_test",
                "PASS" if has_prometheus_action else "WARN",
                {
                    "actions_taken": len(actions),
                    "prometheus_actions": has_prometheus_action,
                    "intent": intent
                }
            )
        else:
            results.add_result("agent_prometheus_test", "WARN", {"actions_taken": 0})
            
    except Exception as e:
        results.add_result("agent_prometheus_test", "FAIL", error=str(e))

async def test_drift_monitor_metrics(results: TestResults):
    """Test drift monitor metrics fetching."""
    print("📊 Testing Drift Monitor Metrics...")
    
    try:
        from nl_interface.drift_monitor.monitor_manager import DriftMonitor
        from nl_interface.drift_monitor.config_schema import DriftMonitorConfig
        
        # Create proper config object
        monitor_config = DriftMonitorConfig(
            loop_id="test-monitor",
            namespace=TEST_NAMESPACE,
            prometheus_url=TEST_CONFIG["monitor_config"]["prometheus_url"],
            check_interval=TEST_CONFIG["monitor_config"]["check_interval"],
            thresholds=[],  # Required field
            metrics=TEST_CONFIG["monitor_config"]["metrics"]
        )
        
        # Create monitor with test config
        monitor = DriftMonitor(monitor_config)
        
        # Test metrics fetching
        check_result = await monitor.check_once()
        
        if check_result.get("error"):
            results.add_result(
                "drift_monitor_metrics",
                "FAIL",
                error=check_result["error"]
            )
        else:
            violations = check_result.get("violations", [])
            metrics_evaluated = check_result.get("metrics_evaluated", 0)
            
            results.add_result(
                "drift_monitor_metrics",
                "PASS",
                {
                    "metrics_evaluated": metrics_evaluated,
                    "violations_found": len(violations),
                    "check_duration": check_result.get("check_duration_seconds", 0)
                }
            )
            
    except Exception as e:
        results.add_result("drift_monitor_metrics", "FAIL", error=str(e))

async def test_violation_handler(results: TestResults):
    """Test violation handler independently."""
    print("⚡ Testing Violation Handler...")
    
    try:
        from nl_interface.agent.violation_handler import ViolationHandler
        from nl_interface.shared.types import MetricViolation, MetricType, ComparisonOperator
        
        # Create a test violation
        test_violation = MetricViolation(
            loop_id="test-monitor",
            namespace=TEST_NAMESPACE,
            deployment_name="s0-edge-site-1",
            metric_type=MetricType.POD_CPU,
            actual_value=85.5,
            threshold_value=80.0,
            operator=ComparisonOperator.GREATER_THAN,
            unit="percent",
            description="Test CPU violation",
            timestamp=datetime.now(timezone.utc)
        )
        
        handler = ViolationHandler(agent_config=TEST_CONFIG["agent_config"])
        
        result = await handler.handle_violation(test_violation)
        
        await handler.cleanup()
        
        if result.get("status") == "success":
            results.add_result(
                "violation_handler_test",
                "PASS",
                {
                    "status": result["status"],
                    "actions_taken": len(result.get("actions_taken", [])),
                    "intent": result.get("intent", "")[:100] + "..."
                }
            )
        else:
            results.add_result(
                "violation_handler_test",
                "FAIL",
                error=result.get("error", "Unknown error")
            )
            
    except Exception as e:
        results.add_result("violation_handler_test", "FAIL", error=str(e))

async def test_full_integration(results: TestResults):
    """Test full integration pipeline."""
    print("🔄 Testing Full Integration Pipeline...")
    
    try:
        from nl_interface.orchestrator.monitoring_orchestrator import create_monitoring_orchestrator
        from nl_interface.orchestrator.monitoring_orchestrator import OrchestratorConfig
        
        # Create orchestrator with test config
        from nl_interface.drift_monitor.config_schema import DriftMonitorConfig
        
        # Create proper monitor config object
        monitor_config = DriftMonitorConfig(
            loop_id="integration-test",
            namespace=TEST_NAMESPACE,
            prometheus_url=TEST_CONFIG["monitor_config"]["prometheus_url"],
            check_interval=TEST_CONFIG["monitor_config"]["check_interval"],
            thresholds=[],  # Required field
            metrics=TEST_CONFIG["monitor_config"]["metrics"]
        )
        
        orchestrator_config = OrchestratorConfig(
            check_interval_seconds=30,
            agent_cooldown_seconds=60,  # Shorter cooldown for testing
            agent_timeout_seconds=120
        )
        
        orchestrator = create_monitoring_orchestrator(
            monitor_config=monitor_config,
            agent_config=TEST_CONFIG["agent_config"],
            orchestrator_config=orchestrator_config
        )
        
        # Test single check and handle
        result = await orchestrator.check_and_handle_violations_once()
        
        if result.get("error"):
            results.add_result(
                "full_integration_test",
                "FAIL",
                error=result["error"]
            )
        else:
            status = result.get("status", "unknown")
            violations_found = result.get("violations_found", 0)
            violations_handled = result.get("violations_handled", 0)
            
            # Any status except error is considered a pass for this test
            test_status = "PASS" if status != "error" else "FAIL"
            
            results.add_result(
                "full_integration_test",
                test_status,
                {
                    "pipeline_status": status,
                    "violations_found": violations_found,
                    "violations_handled": violations_handled,
                    "cooldown_working": "cooldown_remaining_seconds" in result
                }
            )
            
    except Exception as e:
        results.add_result("full_integration_test", "FAIL", error=str(e))

async def verify_existing_services(results: TestResults):
    """Verify existing services are accessible and healthy."""
    print("🔍 Verifying Existing Services...")
    
    try:
        import subprocess
        
        target_services = TEST_CONFIG["test_settings"]["target_services"]
        target_deployments = TEST_CONFIG["test_settings"]["target_deployments"]
        
        service_status = {}
        deployment_status = {}
        
        # Check service endpoints
        for service in target_services:
            svc_result = subprocess.run(
                ["kubectl", "get", "service", service, "-n", TEST_NAMESPACE, "-o", "json"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if svc_result.returncode == 0:
                svc_data = json.loads(svc_result.stdout)
                service_status[service] = {
                    "exists": True,
                    "type": svc_data.get("spec", {}).get("type", "Unknown"),
                    "ports": len(svc_data.get("spec", {}).get("ports", []))
                }
            else:
                service_status[service] = {"exists": False}
        
        # Check deployment readiness
        for deployment in target_deployments:
            dep_result = subprocess.run(
                ["kubectl", "get", "deployment", deployment, "-n", TEST_NAMESPACE, "-o", "json"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if dep_result.returncode == 0:
                dep_data = json.loads(dep_result.stdout)
                status = dep_data.get("status", {})
                deployment_status[deployment] = {
                    "exists": True,
                    "replicas": status.get("replicas", 0),
                    "ready_replicas": status.get("readyReplicas", 0),
                    "available_replicas": status.get("availableReplicas", 0)
                }
            else:
                deployment_status[deployment] = {"exists": False}
        
        existing_services = [svc for svc, status in service_status.items() if status.get("exists")]
        existing_deployments = [dep for dep, status in deployment_status.items() if status.get("exists")]
        
        results.add_result(
            "verify_existing_services",
            "PASS" if existing_services and existing_deployments else "WARN",
            {
                "services_found": existing_services,
                "deployments_found": existing_deployments,
                "service_details": service_status,
                "deployment_details": deployment_status
            }
        )
        
    except Exception as e:
        results.add_result("verify_existing_services", "FAIL", error=str(e))

async def create_test_load(results: TestResults):
    """Create CPU stress load to trigger violations."""
    print("🔥 Creating Test Load (CPU Stress)...")
    
    try:
        import subprocess
        
        if not TEST_CONFIG["test_settings"]["create_stress_load"]:
            results.add_result("test_load_creation", "SKIP", {"reason": "disabled in config"})
            return
        
        # Create stress pod
        stress_duration = TEST_CONFIG["test_settings"]["stress_duration"]
        stress_yaml = STRESS_POD_MANIFEST.format(
            namespace=TEST_NAMESPACE,
            duration=stress_duration
        )
        
        apply_result = subprocess.run(
            ["kubectl", "apply", "-f", "-"],
            input=stress_yaml,
            text=True,
            capture_output=True,
            timeout=30
        )
        
        if apply_result.returncode == 0:
            results.add_result(
                "test_load_creation",
                "PASS",
                {
                    "stress_pod": "cpu-stress-test",
                    "duration": stress_duration,
                    "namespace": TEST_NAMESPACE
                }
            )
            
            # Wait for metrics to appear
            wait_time = TEST_CONFIG["test_settings"]["wait_for_metrics"]
            print(f"   Waiting {wait_time}s for metrics to update...")
            await asyncio.sleep(wait_time)
            
        else:
            results.add_result(
                "test_load_creation",
                "WARN",
                error=f"Failed to create stress pod: {apply_result.stderr}"
            )
            
    except Exception as e:
        results.add_result("test_load_creation", "FAIL", error=str(e))

async def cleanup_test_resources(results: TestResults):
    """Clean up test resources (only stress test pod, preserve existing infrastructure)."""
    print("🧹 Cleaning Up Test Resources...")
    
    try:
        import subprocess
        
        if not TEST_CONFIG["test_settings"]["cleanup_after_test"]:
            results.add_result("cleanup", "SKIP", {"reason": "cleanup disabled in config"})
            return
        
        resources_cleaned = []
        
        # Delete stress test pod if it exists
        stress_result = subprocess.run(
            ["kubectl", "delete", "pod", "cpu-stress-test", "-n", TEST_NAMESPACE, "--ignore-not-found=true", "--wait=false"],
            capture_output=True,
            timeout=10
        )
        
        if stress_result.returncode == 0:
            resources_cleaned.append("cpu-stress-test pod")
        
        # Note: We do NOT clean up s0, s1, s2 services/deployments as they're existing infrastructure
        
        results.add_result(
            "cleanup", 
            "PASS", 
            {
                "resources_cleaned": resources_cleaned,
                "preserved_services": TEST_CONFIG["test_settings"]["target_services"],
                "preserved_deployments": TEST_CONFIG["test_settings"]["target_deployments"]
            }
        )
        
    except Exception as e:
        results.add_result("cleanup", "WARN", error=str(e))

async def main():
    """Run comprehensive tests."""
    print("🧪 COMPREHENSIVE INTEGRATION TEST SUITE")
    print("=" * 60)
    print(f"Target Namespace: {TEST_NAMESPACE}")
    print(f"Prometheus URL: {TEST_CONFIG['prometheus_url']}")
    print("=" * 60)
    print()
    
    results = TestResults()
    
    # Run tests in order
    test_functions = [
        test_cluster_connectivity,
        test_existing_infrastructure,
        verify_existing_services,
        test_prometheus_connectivity,
        test_agent_independently,
        test_agent_prometheus_queries,
        test_drift_monitor_metrics,
        test_violation_handler,
        create_test_load,
        test_full_integration,
        cleanup_test_resources
    ]
    
    for test_func in test_functions:
        try:
            await test_func(results)
        except Exception as e:
            test_name = test_func.__name__
            results.add_result(test_name, "FAIL", error=f"Unexpected error: {str(e)}")
        
        # Small delay between tests
        await asyncio.sleep(1)
    
    # Print final summary
    results.print_summary()
    
    # Return exit code based on results
    failed_tests = [name for name, result in results.results.items() if result["status"] == "FAIL"]
    if failed_tests:
        print(f"\n❌ Failed tests: {', '.join(failed_tests)}")
        return 1
    else:
        print("\n✅ All tests passed or completed with warnings!")
        return 0

if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 