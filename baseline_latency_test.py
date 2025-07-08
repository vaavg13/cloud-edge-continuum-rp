#!/usr/bin/env python3
"""
Simple Baseline Latency Test Script
Tests latency performance of a single deployed application.
"""

import asyncio
import time
import logging
import sys
import subprocess
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent
sys.path.append(str(project_root))

# CRITICAL: Import Locust FIRST to do SSL monkey-patching before Kubernetes client
try:
    import locust  # Import Locust first to ensure proper SSL monkey-patching
except ImportError:
    pass  # If Locust not available, continue without it

# Import required modules
from nl_interface.anomalies.traffic_generator import LocustTrafficGenerator
from nl_interface.anomalies.experiment_utils import smart_warmup_with_monitoring
from nl_interface.shared.prometheus_client import PrometheusMetricsTool
from mu_bench.deployers.manager import K8sDeploymentManager
from kubernetes import client, config

# ===============================================
# CONFIGURATION - EDIT THESE VALUES FOR YOUR APP
# ===============================================

# Target application settings
NAMESPACE = "app-smart-city"
PORT = 31117

# Application deployment settings
APP_DIRECTORY = "./APPS"  # Directory containing app deployments
DEPLOY_FRESH_APP = True   # Set to False to skip deployment

# Application endpoints to test
ENDPOINTS = [
    f"http://172.23.0.5:{PORT}/traffic-sensor-ingest-edge-site-1",
    f"http://172.23.0.5:{PORT}/traffic-sensor-ingest-edge-site-2"
]

# Traffic configuration
REQUESTS_PER_SECOND = 5  # Per endpoint
REQUEST_TIMEOUT = 10

# Test timing
POD_WARMUP_DURATION = 300  # Smart warmup with latency monitoring
BASELINE_DURATION = 60     # Measurement period

# ===============================================
# END CONFIGURATION
# ===============================================

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
for lib in ["httpx", "httpcore", "locust"]:
    logging.getLogger(lib).setLevel(logging.WARNING)

def wait_for_pods_ready(namespace: str, timeout: int = 300) -> bool:
    """Wait for all pods in namespace to be ready."""
    config.load_kube_config()
    k8s_core_api = client.CoreV1Api()
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            pods = k8s_core_api.list_namespaced_pod(namespace=namespace)
            if not pods.items:
                time.sleep(5)
                continue
                
            ready_count = 0
            for pod in pods.items:
                if pod.status.conditions:
                    for condition in pod.status.conditions:
                        if condition.type == 'Ready' and condition.status == 'True':
                            ready_count += 1
                            break
            
            if ready_count == len(pods.items):
                print(f"✅ All {ready_count} pods ready in {namespace}")
                return True
                
            print(f"⏳ Waiting... {ready_count}/{len(pods.items)} pods ready")
            time.sleep(5)
            
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)
    
    print(f"❌ Timeout waiting for pods in {namespace}")
    return False

def deploy_fresh_app() -> bool:
    """Deploy fresh application."""
    if not DEPLOY_FRESH_APP:
        print("Skipping fresh app deployment (disabled in config)")
        return True
        
    print(f"\n🚀 === DEPLOYING APPLICATION ===")
    
    # Use namespace as app name (e.g., "app-smart-manufacturing")
    app_name = NAMESPACE
    app_dir = f"{APP_DIRECTORY}/{app_name}"
    
    try:
        # Delete the namespace first to ensure completely clean state
        print(f"Deleting namespace to ensure clean state...")
        delete_cmd = f"kubectl delete namespace {NAMESPACE} --ignore-not-found=true"
        subprocess.run(delete_cmd.split(), capture_output=True, text=True)
        
        # Wait for namespace deletion to complete
        print(f"Waiting for namespace deletion to complete...")
        time.sleep(15)
        
        print(f"Undeploying existing {app_name}...")
        try:
            mgr = K8sDeploymentManager.from_deployment_dir(app_dir)
            mgr.undeploy()
            print(f"Undeployment completed")
        except Exception as e:
            print(f"Undeploy warning (may not exist): {e}")
        
        # Wait a bit for cleanup
        time.sleep(10)
        
        print(f"Deploying fresh {app_name}...")
        mgr = K8sDeploymentManager.from_deployment_dir(app_dir)
        mgr.deploy()
        
        print(f"Waiting for pods to be ready...")
        if not wait_for_pods_ready(mgr.namespace):
            print(f"Failed to wait for pods to be ready")
            return False
        
        print(f"✅ Fresh application deployed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Deployment error: {e}")
        return False

class SimpleBaselineTester:
    """Simple baseline latency tester."""
    
    def __init__(self):
        self.traffic_config = {
            "endpoints": ENDPOINTS,
            "requests_per_second": REQUESTS_PER_SECOND,
            "request_timeout": REQUEST_TIMEOUT,
            "collect_metrics": True
        }
        
        self.config = {
            "namespace": NAMESPACE,
            "baseline_duration": BASELINE_DURATION,
            "pod_warmup_duration": POD_WARMUP_DURATION,
            "traffic_config": self.traffic_config
        }
        
        self.traffic_generator = LocustTrafficGenerator(self.traffic_config)
        self.prometheus_tool = PrometheusMetricsTool()
        
    async def run_test(self):
        """Run the baseline test."""
        print(f"🎯 BASELINE LATENCY TEST")
        print(f"=" * 50)
        print(f"Target: {NAMESPACE} namespace")
        print(f"Endpoints: {ENDPOINTS}")
        print(f"Traffic Rate: {REQUESTS_PER_SECOND} req/s per endpoint")
        print(f"=" * 50)
        
        try:
            # === PHASE 1: POD WARMUP ===
            print(f"\n🚀 === PHASE 1: POD WARMUP ===")
            await self.traffic_generator.start_traffic()
            print(f"Starting service warmup with latency monitoring...")
            
            # Smart warmup with latency stabilization detection
            await smart_warmup_with_monitoring(self.config, self.traffic_generator)
            
            # === PHASE 2: BASELINE MEASUREMENT ===
            print(f"\n📊 === PHASE 2: BASELINE MEASUREMENT ===")
            # Reset metrics at START of baseline measurement phase
            self.traffic_generator.reset_phase_metrics()
            print(f"Recording baseline metrics for {BASELINE_DURATION}s...")
            await asyncio.sleep(BASELINE_DURATION)
            
            # Collect metrics
            metrics = self.traffic_generator.get_phase_metrics(BASELINE_DURATION)
            
            print(f"📈 Collecting Prometheus metrics...")
            prometheus_metrics = self.prometheus_tool.get_metrics_summary(NAMESPACE)
            
            # Print results
            self.print_results(metrics, prometheus_metrics)
            
        except KeyboardInterrupt:
            print(f"\nTest interrupted! Cleaning up...")
        except Exception as e:
            print(f"\nTest failed: {e}")
            logging.exception("Test error")
        finally:
            # Cleanup
            await self.traffic_generator.stop_traffic()
            print("🧹 Traffic generation stopped")
    
    def print_results(self, metrics, prometheus_metrics):
        """Print test results."""
        print(f"\n" + "=" * 50)
        print(f"🎯 BASELINE TEST RESULTS")
        print("=" * 50)
        
        # Traffic metrics
        print(f"📊 TRAFFIC METRICS:")
        print(f"   Total Requests: {metrics['total_requests']} (expected: {metrics['expected_requests']})")
        print(f"   Success Rate: {metrics['success_rate_percent']}%")
        print(f"   P95 Latency: {metrics['p95_latency_seconds']:.3f}s")
        print(f"   Max Latency: {metrics['max_latency_seconds']:.3f}s")
        print(f"   Current RPS: {metrics['current_rps']}")
        print(f"   Test Duration: {metrics['actual_duration_seconds']}s")
        
        # Performance assessment
        print(f"\n🏆 PERFORMANCE ASSESSMENT:")
        if metrics['success_rate_percent'] >= 95:
            print(f"   ✅ Excellent success rate ({metrics['success_rate_percent']}%)")
        elif metrics['success_rate_percent'] >= 90:
            print(f"   ⚠️  Good success rate ({metrics['success_rate_percent']}%)")
        else:
            print(f"   ❌ Poor success rate ({metrics['success_rate_percent']}%)")
            
        if metrics['p95_latency_seconds'] <= 1.0:
            print(f"   ✅ Excellent latency (P95: {metrics['p95_latency_seconds']:.3f}s)")
        elif metrics['p95_latency_seconds'] <= 5.0:
            print(f"   ⚠️  Acceptable latency (P95: {metrics['p95_latency_seconds']:.3f}s)")
        else:
            print(f"   ❌ High latency (P95: {metrics['p95_latency_seconds']:.3f}s)")
        
        print("=" * 50)

async def main():
    """Main function."""
    print("Simple Baseline Latency Tester")
    print("=" * 40)
    
    # Deploy application first
    if not deploy_fresh_app():
        print("❌ Failed to deploy application")
        return 1
    
    # Run baseline test
    tester = SimpleBaselineTester()
    await tester.run_test()
    
    return 0

if __name__ == "__main__":
    print("Simple Baseline Latency Tester")
    print("Edit the configuration variables at the top of this script for your app")
    print()
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 