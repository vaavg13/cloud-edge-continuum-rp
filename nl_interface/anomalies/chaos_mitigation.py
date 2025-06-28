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
        
        # Store metrics for alert context
        self.baseline_metrics = None
        self.current_metrics = None
        
    async def setup(self):
        """Initialize all test components."""
        print("Setting up test components...")
        
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
        
        print("Test components initialized")
        
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
                    print(f"All {ready_count} pods ready in {namespace}")
                    return True
                    
                print(f"Waiting... {ready_count}/{len(pods.items)} pods ready")
                await asyncio.sleep(5)
                
            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(5)
        
        print(f"Timeout waiting for pods in {namespace}")
        return False

    async def deploy_fresh_app(self) -> bool:
        """Deploy fresh app instances for testing."""
        if not self.config["test_settings"]["deploy_fresh_app"]:
            print("Skipping fresh app deployment (disabled in config)")
            return True
            
        print(f"\nDeploying fresh application...")
        
        app_name = "app-edge"
        app_dir = f"{self.config['app_directory']}/{app_name}"
        
        print(f"Undeploying existing {app_name}...")
        try:
            mgr = K8sDeploymentManager.from_deployment_dir(app_dir)
            mgr.undeploy()
            print(f"Undeployment completed")
        except Exception as e:
            print(f"Undeploy warning (may not exist): {e}")
        
        # Wait a bit for cleanup
        await asyncio.sleep(10)
        
        print(f"Deploying fresh {app_name}...")
        mgr = K8sDeploymentManager.from_deployment_dir(app_dir)
        mgr.deploy()
        
        print(f"Waiting for pods to be ready...")
        success = await self.wait_for_pods_ready(mgr.namespace)
        
        if success:
            print(f"Fresh application deployed successfully")
        else:
            print(f"Failed to deploy fresh application")
            return False
            
        return True

    async def inject_chaos(self) -> bool:
        """Inject chaos into the target application."""
        print(f"🎯 Target: {self.config['target_app']}")
        print(f"⚔️  Type: {self.config['chaos_config']['fault_type']} ({self.config['chaos_config']['intensity']}, {self.config['chaos_duration']})")
        print(f"🎲 Mode: {self.config['chaos_config'].get('target_mode', 'one')} replica(s)")
        
        # Create chaos experiment
        self.chaos_experiment = {
            "name": f"{self.config['chaos_config']['fault_type']}-{self.config['target_app']}-{self.config['chaos_config']['intensity']}".replace("_", "-"),
            "fault_type": self.config['chaos_config']["fault_type"],
            "app": self.config["target_app"],
            "intensity": self.config['chaos_config']["intensity"],
            "template": self.chaos_generator.create_experiment_template(
                self.config['chaos_config']["fault_type"], 
                self.config["target_app"], 
                self.config['chaos_config']["intensity"],
                self.config['chaos_config']  # Pass the full chaos config for targeting
            )
        }
        
        # Override duration
        self.chaos_experiment["template"]["spec"]["duration"] = self.config["chaos_duration"]
        
        # Deploy the chaos experiment
        success = self.chaos_generator.deploy_experiment(self.chaos_experiment)
        
        if success:
            print("✅ Chaos experiment deployed")
            self.start_time = time.time()
            return True
        else:
            print("❌ Failed to deploy chaos experiment")
            return False
    
    async def deploy_mitigation_agent(self) -> list:
        """Deploy the agent to mitigate the issues."""
        print(f"🤖 Deploying mitigation agent...")
        print(f"⚙️  Max rounds: {self.config['agent_config']['max_rounds']}, timeout: {self.config['agent_config']['agent_timeout']}s")
        print(f"⚠️  Note: Agent executing while chaos is still ACTIVE for real-time mitigation")
        
        # Capture current metrics for alert context
        self.current_metrics = self.traffic_generator.get_phase_metrics()
        
        # Create realistic alert intent with baseline comparison
        intent = self.alert_config["alert_template"].format(
            target_app=self.config["target_app"],
            namespace=self.config["namespace"],
            baseline_latency_p95=self.baseline_metrics.get('p95_latency_seconds', 'unknown') if self.baseline_metrics else 'unknown',
            baseline_success_rate=self.baseline_metrics.get('success_rate_percent', 'unknown') if self.baseline_metrics else 'unknown',
            current_latency_p95=self.current_metrics.get('p95_latency_seconds', 'unknown'),
            current_success_rate=self.current_metrics.get('success_rate_percent', 'unknown')
        )
        
        # Create minimal monitoring context
        snapshot = {
            field: self._get_context_value(field)
            for field in self.alert_config["context_fields"]
        }
        
        print(f"🚨 Alert: Performance degradation detected on {self.config['target_app']}")
        if self.baseline_metrics and self.current_metrics:
            print(f"   📊 Baseline: {self.baseline_metrics['success_rate_percent']:.1f}% success, {self.baseline_metrics['p95_latency_seconds']:.3f}s P95")
            print(f"   ⚠️  Current: {self.current_metrics['success_rate_percent']:.1f}% success, {self.current_metrics['p95_latency_seconds']:.3f}s P95")
        
        try:
            # Run the agent
            actions_taken = await self.agent.agent_loop(intent, snapshot)
            
            print(f"\n✅ Agent execution completed while chaos was active")
            print(f"📝 Agent took {len(actions_taken)} action(s)")
            
            return actions_taken
            
        except Exception as e:
            print(f"\n❌ Agent execution failed: {e}")
            return []
    
    def _get_context_value(self, field: str) -> str:
        """Get context value for alert fields."""
        context_map = {
            "namespace": self.config["namespace"],
            "alert_type": "performance_degradation",
            "affected_service": self.config["target_app"],
            "timestamp": datetime.now().isoformat(),
            "baseline_latency_p95": str(self.baseline_metrics.get('p95_latency_seconds', 'unknown')) if self.baseline_metrics else 'unknown',
            "baseline_success_rate": str(self.baseline_metrics.get('success_rate_percent', 'unknown')) if self.baseline_metrics else 'unknown',
            "current_latency_p95": str(self.current_metrics.get('p95_latency_seconds', 'unknown')) if self.current_metrics else 'unknown',
            "current_success_rate": str(self.current_metrics.get('success_rate_percent', 'unknown')) if self.current_metrics else 'unknown'
        }
        return context_map.get(field, "unknown")
    
    async def cleanup_chaos(self):
        """Clean up the chaos experiment."""
        print(f"🧹 Cleaning up chaos experiment...")
        
        if self.chaos_experiment:
            success = self.chaos_generator.undeploy_experiment(self.chaos_experiment)
            if success:
                print("✅ Chaos experiment cleaned up")
            else:
                print("⚠️  Chaos experiment cleanup had issues (may have already expired)")
        else:
            print("ℹ️  No chaos experiment to clean up")
    
    async def emergency_cleanup(self):
        """Emergency cleanup for when experiment is interrupted."""
        print(f"\nEMERGENCY CLEANUP - CTRL+C DETECTED")
        print("=" * 40)
        
        # Stop traffic generation immediately
        if self.traffic_generator:
            try:
                print("Stopping traffic generation...")
                await self.traffic_generator.stop_traffic()
                print("Traffic generation stopped")
            except Exception as e:
                print(f"Error stopping traffic: {e}")
        
        # Clean up chaos experiment with timeout
        if self.chaos_experiment:
            try:
                print("Cleaning up chaos experiment...")
                success = self.chaos_generator.undeploy_experiment(self.chaos_experiment)
                if success:
                    print("Chaos experiment cleaned up")
                else:
                    print("Chaos experiment cleanup had issues")
            except Exception as e:
                print(f"Error cleaning chaos experiment: {e}")
        
        # Clean up agent
        if self.agent:
            try:
                print("Cleaning up agent...")
                await self.agent.cleanup()
                print("Agent cleaned up")
            except Exception as e:
                print(f"Error cleaning agent: {e}")
        
        print("=" * 40)
        print("Emergency cleanup completed - safe to exit")

    async def cleanup(self):
        """Clean up all test resources."""
        if not self.config["test_settings"]["cleanup_after_test"]:
            print("Skipping cleanup (disabled in config)")
            return
            
        print(f"\nCleaning up test resources...")
        
        # Stop traffic first
        if self.traffic_generator:
            await self.traffic_generator.stop_traffic()
            print("Traffic generation stopped")
        
        # Clean up chaos experiment
        await self.cleanup_chaos()
        
        # Clean up agent
        if self.agent:
            await self.agent.cleanup()
            print("Agent cleaned up")
        
        print("All test resources cleaned up")

    async def cleanup_remaining_resources(self):
        """Clean up remaining resources (traffic, agent) after chaos is already cleaned."""
        if not self.config["test_settings"]["cleanup_after_test"]:
            print("Skipping cleanup (disabled in config)")
            return
            
        print(f"\nCleaning up remaining test resources...")
        
        # Stop traffic first
        if self.traffic_generator:
            await self.traffic_generator.stop_traffic()
            print("Traffic generation stopped")
        
        # Clean up agent
        if self.agent:
            await self.agent.cleanup()
            print("Agent cleaned up")
        
        print("Remaining test resources cleaned up")
    
    def print_experiment_summary(self, phase_metrics: Dict, agent_actions: list):
        """Print final experiment summary with phase comparisons."""
        print(f"\n" + "=" * 60)
        print(f"🎯 EXPERIMENT SUMMARY")
        print("=" * 60)
        
        # Phase-by-phase results
        print(f"\n📊 PHASE RESULTS:")
        print("-" * 60)
        phase_emojis = {
            "baseline": "✅",
            "chaos": "⚠️ ",
            "recovery": "🩹"
        }
        for phase_name, metrics in phase_metrics.items():
            emoji = phase_emojis.get(phase_name, "📈")
            print(f"{emoji} {phase_name.upper():>11}: {metrics['total_requests']:>5} req | "
                  f"{metrics['success_rate_percent']:>6.1f}% success | "
                  f"P95: {metrics['p95_latency_seconds']:>6.3f}s")
        
        # Impact analysis
        if "baseline" in phase_metrics and "chaos" in phase_metrics:
            baseline_p95 = phase_metrics["baseline"]["p95_latency_seconds"]
            chaos_p95 = phase_metrics["chaos"]["p95_latency_seconds"]
            
            print(f"\n💥 IMPACT ANALYSIS:")
            print("-" * 60)
            if baseline_p95 > 0:
                latency_degradation = (chaos_p95 / baseline_p95)
                print(f"📈 Latency degradation: {latency_degradation:.2f}x worse ({baseline_p95:.3f}s → {chaos_p95:.3f}s)")
            
            baseline_success = phase_metrics["baseline"]["success_rate_percent"]
            chaos_success = phase_metrics["chaos"]["success_rate_percent"]
            success_drop = baseline_success - chaos_success
            print(f"📉 Success rate drop: {success_drop:.1f}% ({baseline_success:.1f}% → {chaos_success:.1f}%)")
            
            # Recovery analysis
            if "recovery" in phase_metrics:
                recovery_p95 = phase_metrics["recovery"]["p95_latency_seconds"]
                recovery_success = phase_metrics["recovery"]["success_rate_percent"]
                
                if chaos_p95 > 0:
                    recovery_improvement = ((chaos_p95 - recovery_p95) / chaos_p95) * 100
                    print(f"🔄 Recovery improvement: {recovery_improvement:.1f}% (P95: {chaos_p95:.3f}s → {recovery_p95:.3f}s)")
                
                success_recovery = recovery_success - chaos_success
                print(f"🔄 Success rate recovery: {success_recovery:.1f}% ({chaos_success:.1f}% → {recovery_success:.1f}%)")
        
        # Agent actions
        print(f"\n🤖 AGENT ACTIONS ({len(agent_actions)}):")
        print("-" * 60)
        if agent_actions:
            for i, action in enumerate(agent_actions, 1):
                print(f"  {i}. {action}")
        else:
            print("  ❌ No actions taken")
        
        print("=" * 60)
        print("🎉 EXPERIMENT COMPLETED")
        print("=" * 60)

    async def run_full_experiment(self) -> Dict[str, Any]:
        """Run the simplified chaos injection and mitigation experiment."""
        results = {
            "success": False,
            "phases_completed": [],
            "agent_actions": [],
            "error": None,
            "interrupted": False,
            "phase_metrics": {}
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
            
            # === PHASE 1: POD WARMUP (no metrics recorded) ===
            print(f"\n🚀 === PHASE 1: POD WARMUP ===")
            await self.traffic_generator.start_traffic()
            print(f"Warming up pods for {self.config['pod_warmup_duration']}s...")
            await asyncio.sleep(self.config["pod_warmup_duration"])
            # No metrics recorded for warmup
            results["phases_completed"].append("pod_warmup")
            
            # === PHASE 2: BASELINE METRICS ===
            print(f"\n📊 === PHASE 2: BASELINE METRICS ===")
            print(f"Recording baseline metrics for {self.config['baseline_duration']}s...")
            await asyncio.sleep(self.config["baseline_duration"])
            baseline_metrics = self.traffic_generator.get_phase_metrics()
            
            # Store baseline metrics for agent alert context
            self.baseline_metrics = baseline_metrics
            
            results["phase_metrics"]["baseline"] = baseline_metrics
            print(f"✅ Baseline: {baseline_metrics['total_requests']} req, {baseline_metrics['success_rate_percent']}% success, P95: {baseline_metrics['p95_latency_seconds']}s")
            results["phases_completed"].append("baseline")
            
            # === CHAOS INJECTION ===
            print(f"\n💥 === CHAOS INJECTION ===")
            if await self.inject_chaos():
                results["phases_completed"].append("chaos_injection")
            else:
                raise Exception("Failed to inject chaos")
            
            # === PHASE 3: CHAOS WARMUP (record metrics during active chaos) ===
            print(f"\n🔥 === PHASE 3: CHAOS WARMUP (ACTIVE CHAOS) ===")
            print(f"Recording metrics during chaos for {self.config['chaos_warmup_duration']}s...")
            await asyncio.sleep(self.config["chaos_warmup_duration"])
            chaos_metrics = self.traffic_generator.get_phase_metrics()
            results["phase_metrics"]["chaos"] = chaos_metrics
            print(f"⚠️  Chaos: {chaos_metrics['total_requests']} req, {chaos_metrics['success_rate_percent']}% success, P95: {chaos_metrics['p95_latency_seconds']}s")
            results["phases_completed"].append("chaos_warmup")
            
            # === AGENT EXECUTION (during active chaos) ===
            print(f"\n🤖 === AGENT EXECUTION (CHAOS STILL ACTIVE) ===")
            agent_actions = await self.deploy_mitigation_agent()
            results["agent_actions"] = agent_actions
            results["phases_completed"].append("agent_execution")
            
            # === PHASE 4: RECOVERY METRICS ===
            print(f"\n🔄 === PHASE 4: RECOVERY METRICS ===")
            print(f"Recording recovery metrics for {self.config['recovery_duration']}s...")
            await asyncio.sleep(self.config["recovery_duration"])
            recovery_metrics = self.traffic_generator.get_phase_metrics()
            results["phase_metrics"]["recovery"] = recovery_metrics
            print(f"🩹 Recovery: {recovery_metrics['total_requests']} req, {recovery_metrics['success_rate_percent']}% success, P95: {recovery_metrics['p95_latency_seconds']}s")
            results["phases_completed"].append("recovery")
            
            # === CLEANUP AND FINAL METRICS ===
            print(f"\n🧹 === CLEANUP ===")
            await self.traffic_generator.stop_traffic()
            await self.cleanup_chaos()
            
            # Final metrics comparison
            self.print_experiment_summary(results["phase_metrics"], agent_actions)
            
            results["success"] = True
            return results
            
        except KeyboardInterrupt:
            results["interrupted"] = True
            results["error"] = "Experiment interrupted by user (Ctrl+C)"
            print(f"\nExperiment interrupted! Initiating cleanup...")
            return results
            
        except Exception as e:
            results["error"] = str(e)
            print(f"\nTest failed: {e}")
            logger.exception("Test execution error")
            return results
        
        finally:
            # Always cleanup
            if results.get("interrupted", False):
                await self.emergency_cleanup()
            else:
                await self.cleanup_remaining_resources() 