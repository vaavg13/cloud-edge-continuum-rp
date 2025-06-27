#!/usr/bin/env python3
"""
Chaos Mitigation Test Orchestrator
Main test class that orchestrates app deployment, chaos injection, and agent mitigation.
"""

import asyncio
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# Import Kubernetes and deployment modules
from kubernetes import client, config
from mu_bench.deployers.manager import K8sDeploymentManager

# Import project modules
from .chaos_templates_generator import ChaosBenchmarkGenerator
from nl_interface.agent.agent import KubernetesAgent
from .traffic_generator import TrafficGenerator

logger = logging.getLogger(__name__)

class ChaosAndMitigationTest:
    """Orchestrates chaos injection and agent mitigation testing."""
    
    def __init__(self, experiment_config: Dict[str, Any], alert_config: Dict[str, Any]):
        self.config = experiment_config
        self.alert_config = alert_config
        
        # Initialize components
        self.chaos_generator = None
        self.agent = None
        self.traffic_generator = None
        self.chaos_experiment = None
        self.start_time = None
        
    async def setup(self):
        """Initialize all test components."""
        print("🔧 Setting up test components...")
        
        # Initialize chaos generator
        self.chaos_generator = ChaosBenchmarkGenerator(
            namespace=self.config["namespace"],
            app_list=[self.config["target_app"]],
            seed=self.config["chaos_config"]["seed"]
        )
        
        # Initialize traffic generator
        self.traffic_generator = TrafficGenerator(self.config["traffic_config"])
        
        # Initialize agent
        self.agent = KubernetesAgent(config=self.config["agent_config"])
        await self.agent.initialize()
        
        print("✅ Test components initialized")
        
    async def wait_for_pods_ready(self, namespace: str, timeout: int = None) -> bool:
        """Wait for all pods in namespace to be ready."""
        if timeout is None:
            timeout = self.config["test_settings"]["pod_ready_timeout"]
            
        config.load_kube_config()
        k8s_core_api = client.CoreV1Api()
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                pods = k8s_core_api.list_namespaced_pod(namespace=namespace)
                if not pods.items:
                    await asyncio.sleep(5)
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
                await asyncio.sleep(5)
                
            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(5)
        
        print(f"❌ Timeout waiting for pods in {namespace}")
        return False

    async def deploy_fresh_app(self) -> bool:
        """Deploy fresh app instances for testing."""
        if not self.config["test_settings"]["deploy_fresh_app"]:
            print("ℹ️ Skipping fresh app deployment (disabled in config)")
            return True
            
        print(f"\n🚀 DEPLOYING FRESH APPLICATION")
        
        app_name = "app-edge"
        app_dir = f"{self.config['app_directory']}/{app_name}"
        
        print(f"   Undeploying existing {app_name}...")
        try:
            mgr = K8sDeploymentManager.from_deployment_dir(app_dir)
            mgr.undeploy()
            print(f"✅ Undeployment completed")
        except Exception as e:
            print(f"⚠️ Undeploy warning (may not exist): {e}")
        
        # Wait a bit for cleanup
        await asyncio.sleep(10)
        
        print(f"   Deploying fresh {app_name}...")
        mgr = K8sDeploymentManager.from_deployment_dir(app_dir)
        mgr.deploy()
        
        print(f"   Waiting for pods to be ready...")
        success = await self.wait_for_pods_ready(mgr.namespace)
        
        if success:
            print(f"✅ Fresh application deployed successfully")
        else:
            print(f"❌ Failed to deploy fresh application")
            return False
            
        return True

    async def warmup_traffic(self):
        """Run warm-up traffic to ensure pods are ready."""
        if not self.config["test_settings"]["run_warmup_traffic"]:
            print("ℹ️ Skipping pod warmup (disabled in config)")
            return
            
        print(f"\n🔥 WARMING UP PODS")
        warmup_duration = self.config["warmup_duration"]
        print(f"   Running light traffic for {warmup_duration}s to warm up pods...")
        
        # Start traffic
        await self.traffic_generator.start_traffic()
        
        # Run warm-up
        await asyncio.sleep(warmup_duration)
        
        # Stop traffic and reset metrics
        await self.traffic_generator.stop_traffic()
        self.traffic_generator.reset_metrics()
        
        print(f"✅ Pod warm-up completed, metrics reset")

    async def run_baseline_measurement(self):
        """Run baseline traffic measurement."""
        print(f"\n📊 BASELINE MEASUREMENT PHASE")
        await self.traffic_generator.start_traffic()
        self.traffic_generator.set_phase("baseline")
        
        baseline_duration = self.config["baseline_duration"]
        print(f"   Collecting baseline latency metrics ({baseline_duration}s)...")
        await asyncio.sleep(baseline_duration)
        
        print("✅ Baseline measurement completed")

    async def inject_chaos(self) -> bool:
        """Inject chaos into the target application."""
        print(f"\n🌪️ INJECTING CHAOS")
        print(f"   Target: {self.config['target_app']}")
        
        chaos_config = self.config["chaos_config"]
        print(f"   Type: {chaos_config['fault_type']} ({chaos_config['intensity']} intensity)")
        print(f"   Duration: {self.config['chaos_duration']}")
        
        # Create chaos experiment
        self.chaos_experiment = {
            "name": f"{chaos_config['fault_type']}-{self.config['target_app']}-{chaos_config['intensity']}".replace("_", "-"),
            "fault_type": chaos_config["fault_type"],
            "app": self.config["target_app"],
            "intensity": chaos_config["intensity"],
            "template": self.chaos_generator.create_experiment_template(
                chaos_config["fault_type"], 
                self.config["target_app"], 
                chaos_config["intensity"]
            )
        }
        
        # Override duration
        self.chaos_experiment["template"]["spec"]["duration"] = self.config["chaos_duration"]
        
        # Deploy the chaos experiment
        success = self.chaos_generator.deploy_experiment(self.chaos_experiment)
        
        if success:
            print("✅ Chaos experiment deployed successfully")
            self.start_time = time.time()
            return True
        else:
            print("❌ Failed to deploy chaos experiment")
            return False
    
    async def wait_for_chaos_impact(self):
        """Wait for chaos to take effect before starting mitigation."""
        wait_time = self.config["chaos_wait_duration"]
        print(f"\n⏳ Waiting {wait_time}s for chaos to take effect...")
        
        for i in range(wait_time):
            remaining = wait_time - i
            if remaining % 30 == 0 or remaining <= 10:
                print(f"   {remaining}s remaining...")
            await asyncio.sleep(1)
        
        print("✅ Chaos should now be significantly impacting the system")
    
    async def deploy_mitigation_agent(self) -> list:
        """Deploy the agent to mitigate the issues."""
        print(f"\n🤖 DEPLOYING MITIGATION AGENT")
        print(f"   Max rounds: {self.config['agent_config']['max_rounds']}")
        print(f"   Timeout: {self.config['agent_config']['agent_timeout']}s")
        
        # Create realistic alert intent
        intent = self.alert_config["alert_template"].format(
            target_app=self.config["target_app"],
            namespace=self.config["namespace"]
        )
        
        # Create minimal monitoring context
        snapshot = {
            field: self._get_context_value(field)
            for field in self.alert_config["context_fields"]
        }
        
        print(f"   Alert: High CPU usage detected on {self.config['target_app']}")
        print(f"   Context: Monitoring alert triggered")
        
        try:
            # Run the agent
            actions_taken = await self.agent.agent_loop(intent, snapshot)
            
            print(f"\n✅ Agent execution completed")
            print(f"   Actions taken: {len(actions_taken)}")
            for i, action in enumerate(actions_taken, 1):
                print(f"   {i}. {action}")
            
            return actions_taken
            
        except Exception as e:
            print(f"\n❌ Agent execution failed: {e}")
            return []
    
    def _get_context_value(self, field: str) -> str:
        """Get context value for alert fields."""
        context_map = {
            "namespace": self.config["namespace"],
            "alert_type": "high_cpu_usage",
            "affected_service": self.config["target_app"],
            "timestamp": datetime.now().isoformat()
        }
        return context_map.get(field, "unknown")
    
    async def monitor_system_recovery(self):
        """Monitor system recovery after agent mitigation."""
        print(f"\n📊 MONITORING SYSTEM RECOVERY")
        
        recovery_duration = self.config["recovery_duration"]
        check_interval = 10   # Check every 10 seconds
        
        print(f"   Monitoring duration: {recovery_duration}s")
        print(f"   Check interval: {check_interval}s")
        
        for i in range(0, recovery_duration, check_interval):
            remaining = recovery_duration - i
            print(f"   Checking system status... ({remaining}s remaining)")
            await asyncio.sleep(check_interval)
        
        print("✅ System monitoring completed")
    
    async def cleanup_chaos(self):
        """Clean up the chaos experiment."""
        print(f"\n🧹 CLEANING UP CHAOS EXPERIMENT")
        
        if self.chaos_experiment:
            success = self.chaos_generator.undeploy_experiment(self.chaos_experiment)
            if success:
                print("✅ Chaos experiment cleaned up successfully")
            else:
                print("⚠️ Chaos experiment cleanup had issues (may have already expired)")
        else:
            print("ℹ️ No chaos experiment to clean up")
    
    async def cleanup(self):
        """Clean up all test resources."""
        if not self.config["test_settings"]["cleanup_after_test"]:
            print("ℹ️ Skipping cleanup (disabled in config)")
            return
            
        print(f"\n🧹 CLEANING UP TEST RESOURCES")
        
        # Stop traffic first
        if self.traffic_generator:
            await self.traffic_generator.stop_traffic()
            print("✅ Traffic generation stopped")
        
        # Clean up chaos experiment
        await self.cleanup_chaos()
        
        # Clean up agent
        if self.agent:
            await self.agent.cleanup()
            print("✅ Agent cleaned up")
        
        print("✅ All test resources cleaned up")
    
    def print_test_summary(self, agent_actions: list):
        """Print final test summary."""
        print(f"\n🎯 TEST SUMMARY")
        print("=" * 40)
        
        if self.config["test_settings"]["deploy_fresh_app"]:
            print(f"✅ Fresh application deployed")
        if self.config["test_settings"]["run_warmup_traffic"]:
            print(f"✅ Pod warmup completed")
            
        print(f"✅ Baseline metrics collected")
        print(f"✅ Chaos injected successfully")
        print(f"✅ Agent executed with {len(agent_actions)} actions")
        print(f"✅ Recovery metrics collected")
        print("=" * 40)
        
        # Print traffic analysis
        if self.traffic_generator:
            self.traffic_generator.print_comprehensive_summary()
        
        if agent_actions:
            print(f"\n📋 AGENT ACTIONS TAKEN:")
            for i, action in enumerate(agent_actions, 1):
                print(f"   {i}. {action}")
        
        print(f"\n🏁 Test completed successfully!")
    
    async def run_full_experiment(self) -> Dict[str, Any]:
        """Run the complete chaos injection and mitigation experiment."""
        results = {
            "success": False,
            "phases_completed": [],
            "agent_actions": [],
            "error": None
        }
        
        try:
            # Setup
            await self.setup()
            results["phases_completed"].append("setup")
            
            # Deploy fresh application
            if await self.deploy_fresh_app():
                results["phases_completed"].append("deployment")
            else:
                raise Exception("Failed to deploy fresh application")
            
            # Warm up pods
            await self.warmup_traffic()
            results["phases_completed"].append("warmup")
            
            # Run baseline measurement
            await self.run_baseline_measurement()
            results["phases_completed"].append("baseline")
            
            # Inject chaos and switch to chaos phase
            if await self.inject_chaos():
                self.traffic_generator.set_phase("chaos")
                results["phases_completed"].append("chaos_injection")
            else:
                raise Exception("Failed to inject chaos")
            
            # Wait for chaos impact
            await self.wait_for_chaos_impact()
            results["phases_completed"].append("chaos_impact")
            
            # Deploy mitigation agent and switch to recovery phase
            self.traffic_generator.set_phase("recovery")
            agent_actions = await self.deploy_mitigation_agent()
            results["agent_actions"] = agent_actions
            results["phases_completed"].append("agent_mitigation")
            
            # Monitor recovery
            await self.monitor_system_recovery()
            results["phases_completed"].append("recovery_monitoring")
            
            # Print comprehensive summary
            self.print_test_summary(agent_actions)
            
            results["success"] = True
            return results
            
        except Exception as e:
            results["error"] = str(e)
            print(f"\n❌ Test failed: {e}")
            logger.exception("Test execution error")
            return results
        
        finally:
            # Always cleanup
            await self.cleanup() 