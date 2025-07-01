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
import subprocess

# CRITICAL: Import TrafficGenerator FIRST (contains Locust) before Kubernetes
# This ensures proper SSL monkey-patching order to prevent recursion errors
from .traffic_generator import LocustTrafficGenerator

# Import other project modules
from .chaos_templates_generator import ChaosBenchmarkGenerator
from nl_interface.agent.agent import KubernetesAgent
from nl_interface.shared.prometheus_client import PrometheusMetricsTool
from .prometheus_utils import (
    format_pod_cpu, format_pod_memory, format_istio_latency,
    extract_prometheus_latency, extract_prometheus_cpu
)
from .experiment_utils import smart_warmup_with_monitoring

logger = logging.getLogger(__name__)

class ChaosAndMitigationTest:
    """Orchestrates chaos injection and agent mitigation testing."""
    
    def __init__(self, 
        experiment_config: Dict[str, Any], 
        alert_config: Dict[str, Any],
        reasoning_in_context: bool = False
    ):
        self.config = experiment_config
        self.alert_config = alert_config
        self.reasoning_in_context = reasoning_in_context
        
        # Initialize components
        self.chaos_generator = None
        self.agent = None
        self.traffic_generator = None
        self.chaos_experiment = None
        
        # Initialize Prometheus metrics tool
        self.prometheus_tool = PrometheusMetricsTool()
        
        # Store metrics for alert context
        self.baseline_metrics = None
        self.baseline_prometheus_metrics = None
        self.current_metrics = None
        
    async def setup(self):
        """Setup chaos and mitigation components."""
        # Initialize traffic generator
        self.traffic_generator = LocustTrafficGenerator(self.config["traffic_config"])
        
        # Initialize chaos generator  
        self.chaos_generator = ChaosBenchmarkGenerator(
            namespace=self.config["namespace"],
            app_list=[self.config["target_app"]],
            seed=self.config["chaos_config"]["seed"]
        )
        
        # Initialize agent (will be created fresh each time)
        self.agent = None
        self.baseline_metrics = None
        self.baseline_prometheus_metrics = None

    async def inject_chaos(self) -> bool:
        """Inject chaos into the target application."""
        print(f"🎯 Target: {self.config['target_app']}")
        print(f"⚔️  Type: {self.config['chaos_config']['fault_type']} ({self.config['chaos_config']['intensity']})")
        print(f"🎲 Mode: {self.config['chaos_config'].get('target_mode', 'one')} replica(s)")
        print(f"⏰ Duration: Indefinite (cleaned up after agent completes)")
        
        # Create chaos experiment
        self.chaos_experiment = {
            "name": f"{self.config['chaos_config']['fault_type']}-{self.config['target_app']}-{self.config['chaos_config']['intensity']}",
            "app": self.config['target_app'],
            "config": self.config['chaos_config']
        }
        
        # Generate and deploy chaos experiment
        template = self.chaos_generator.create_experiment_template(
            self.chaos_experiment["config"]["fault_type"],
            self.chaos_experiment["app"],
            self.chaos_experiment["config"]["intensity"],
            self.chaos_experiment["config"]
        )
        
        # Set experiment duration to 1 hour (will be cleaned up by stop_chaos)
        if template and "spec" in template:
            template["spec"]["duration"] = "3600s"
        
        deployment_success = self.chaos_generator.deploy_experiment({
            "name": self.chaos_experiment["name"],
            "template": template,
            "fault_type": self.chaos_experiment["config"]["fault_type"],
            "app": self.chaos_experiment["app"],
            "intensity": self.chaos_experiment["config"]["intensity"]
        })
        
        if deployment_success:
            print(f"✅ Chaos experiment deployed (will run until manually stopped)")
            
            return True
        else:
            print(f"❌ Failed to deploy chaos experiment")
            return False
    
    async def deploy_mitigation_agent(self, 
        chaos_metrics: Dict[str, Any], 
        chaos_prometheus_metrics: Dict[str, Any],
        reasoning_in_context: bool = False
    ) -> list:
        """Deploy the agent to mitigate the issues."""
        print(f"🤖 Deploying mitigation agent...")
        print(f"⚙️  Max rounds: {self.config['agent_config']['max_rounds']}, timeout: {self.config['agent_config']['agent_timeout']}s")
        print(f"🔍  Reasoning in context: {self.config['agent_config']['reasoning_in_context']}")
        
        # Initialize agent fresh for this execution
        self.agent = KubernetesAgent(config=self.config["agent_config"])
        await self.agent.initialize()
        
        # Store metrics for context
        self.current_metrics = chaos_metrics
        self._current_prometheus_metrics = chaos_prometheus_metrics
        
        # Extract Prometheus metrics for alert context
        baseline_p95 = extract_prometheus_latency(
            self.baseline_prometheus_metrics, 
            self.config["namespace"]
        ) if self.baseline_prometheus_metrics else 'unknown'
        
        current_p95 = extract_prometheus_latency(
            chaos_prometheus_metrics, 
            self.config["namespace"]
        ) if chaos_prometheus_metrics else 'unknown'
        
        # Create alert intent
        intent = self.alert_config["alert_template"].format(
            namespace=self.config["namespace"],
            timestamp=datetime.now().isoformat(),
            baseline_latency_p95=f"{baseline_p95}ms",
            baseline_success_rate=f"{self.baseline_metrics.get('success_rate_percent', 'unknown')}",
            current_latency_p95=f"{current_p95}ms", 
            current_success_rate=f"{self.current_metrics.get('success_rate_percent', 'unknown')}"
        )
        
        # Create monitoring context
        snapshot = {
            field: self._get_context_value(field)
            for field in self.alert_config["context_fields"]
        }
        
        print(f"🚨 Alert: Critical performance degradation in namespace {self.config['namespace']}")
        if self.baseline_metrics and self.current_metrics:
            print(f"   📈 Success rate: {self.baseline_metrics['success_rate_percent']:.1f}% → {self.current_metrics['success_rate_percent']:.1f}%")
            print(f"   📈 Latency P95: {self.baseline_metrics['p95_latency_seconds']:.3f}s → {self.current_metrics['p95_latency_seconds']:.3f}s")
        
        try:
            # Run the agent
            actions_taken = await self.agent.agent_loop(intent, snapshot)
            print(f"\n✅ Agent execution completed - {len(actions_taken)} action(s) taken")
            return actions_taken
            
        except Exception as e:
            print(f"\n❌ Agent execution failed: {e}")
            return []
    
    def _get_context_value(self, field: str) -> str:
        """Get context value for alert fields."""
        context_map = {
            "namespace": self.config["namespace"],
            "alert_type": "performance_degradation", 
            "timestamp": datetime.now().isoformat(),
            "baseline_latency_p95": str(self.baseline_metrics.get('p95_latency_seconds', 'unknown')) if self.baseline_metrics else 'unknown',
            "baseline_success_rate": str(self.baseline_metrics.get('success_rate_percent', 'unknown')) if self.baseline_metrics else 'unknown',
            "current_latency_p95": str(self.current_metrics.get('p95_latency_seconds', 'unknown')) if self.current_metrics else 'unknown',
            "current_success_rate": str(self.current_metrics.get('success_rate_percent', 'unknown')) if self.current_metrics else 'unknown'
        }
        return context_map.get(field, "unknown")
    
    def _cleanup_chaos_sync(self) -> bool:
        """Synchronous chaos cleanup function to run in thread executor."""
        if self.chaos_experiment:
            return self.chaos_generator.undeploy_experiment(self.chaos_experiment)
        return True

    async def cleanup_chaos(self):
        """Clean up the chaos experiment after agent completion."""
        print(f"🧹 Manually stopping chaos experiment (after agent completion)...")
        
        if self.chaos_experiment:
            # Run chaos cleanup in thread executor for consistency
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(None, self._cleanup_chaos_sync)
            
            if success:
                print("✅ Chaos experiment manually stopped - agent had unlimited time to work")
            else:
                print("⚠️  Chaos experiment cleanup had issues")
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
                loop = asyncio.get_event_loop()
                success = await loop.run_in_executor(None, self._cleanup_chaos_sync)
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
        print(f"\n" + "=" * 50)
        print(f"🎯 EXPERIMENT SUMMARY")
        print("=" * 50)
        
        # Phase results
        phase_emojis = {"baseline": "✅", "chaos": "⚠️", "recovery": "🩹"}
        for phase_name, metrics in phase_metrics.items():
            emoji = phase_emojis.get(phase_name, "📈")
            print(f"{emoji} {phase_name.upper()}: {metrics['total_requests']} req | "
                  f"{metrics['success_rate_percent']:.1f}% success | "
                  f"P95: {metrics['p95_latency_seconds']:.3f}s")
        
        # Impact analysis
        if "baseline" in phase_metrics and "chaos" in phase_metrics:
            baseline_p95 = phase_metrics["baseline"]["p95_latency_seconds"]
            chaos_p95 = phase_metrics["chaos"]["p95_latency_seconds"]
            baseline_success = phase_metrics["baseline"]["success_rate_percent"]
            chaos_success = phase_metrics["chaos"]["success_rate_percent"]
            
            # Check if baseline is placeholder (from skipped mode)
            is_placeholder_baseline = (baseline_p95 == 0.1 and 
                                     phase_metrics["baseline"]["total_requests"] == 0)
            
            print(f"\n💥 IMPACT:")
            if baseline_p95 > 0 and not is_placeholder_baseline:
                degradation = (chaos_p95 / baseline_p95)
                print(f"📈 Latency: {degradation:.2f}x worse ({baseline_p95:.3f}s → {chaos_p95:.3f}s)")
                print(f"📉 Success rate: {baseline_success:.1f}% → {chaos_success:.1f}%")
            elif is_placeholder_baseline:
                print(f"📈 Chaos latency: {chaos_p95:.3f}s (baseline skipped)")
                print(f"📉 Chaos success rate: {chaos_success:.1f}% (baseline skipped)")
            else:
                print(f"📈 Latency comparison not available")
                print(f"📉 Success rate: {baseline_success:.1f}% → {chaos_success:.1f}%")
            
            # Recovery
            if "recovery" in phase_metrics:
                recovery_p95 = phase_metrics["recovery"]["p95_latency_seconds"]
                recovery_success = phase_metrics["recovery"]["success_rate_percent"]
                print(f"🔄 Recovery: P95 {recovery_p95:.3f}s, Success {recovery_success:.1f}%")
        
        # Agent actions
        print(f"\n🤖 AGENT ACTIONS ({len(agent_actions)}):")
        if agent_actions:
            for i, action in enumerate(agent_actions, 1):
                print(f"  {i}. {action}")
        else:
            print("  ❌ No actions taken")
        
        print("=" * 50)

    async def run_full_experiment(self, deployment_already_done: bool = False, deployment_namespace: str = "") -> Dict[str, Any]:
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
            
            # Application deployment handled before async context
            print(f"✅ Using already deployed application in namespace: {deployment_namespace}")
            results["phases_completed"].append("deployment")
            
            # Check if we should skip warmup and baseline phases
            skip_warmup_baseline = self.config.get("test_settings", {}).get("skip_warmup_baseline", False)
            
            if skip_warmup_baseline:
                print(f"\n⚡ === SKIPPING WARMUP & BASELINE (FAST MODE) ===")
                print(f"🚀 Starting traffic generation without warmup...")
                await self.traffic_generator.start_traffic()
                
                # Brief startup to ensure traffic is flowing
                await asyncio.sleep(10)
                
                # Create minimal baseline metrics for agent context
                print(f"📈 Collecting minimal Prometheus metrics for agent context...")
                self.baseline_prometheus_metrics = self.prometheus_tool.get_metrics_summary(self.config["namespace"])
                
                # Create placeholder baseline metrics
                self.baseline_metrics = {
                    "total_requests": 0,
                    "success_rate_percent": 100.0,
                    "p95_latency_seconds": 0.1,
                    "actual_duration_seconds": 0,
                    "current_rps": 0,
                    "expected_requests": 0
                }
                
                results["phase_metrics"]["baseline"] = self.baseline_metrics
                print(f"✅ Fast mode enabled - skipped warmup and baseline phases")
                results["phases_completed"].extend(["pod_warmup", "baseline"])
                
            else:
                # === PHASE 1: POD WARMUP ===
                print(f"\n🚀 === PHASE 1: POD WARMUP ===")
                await self.traffic_generator.start_traffic()
                print(f"Starting service warmup with latency monitoring...")
                
                # Smart warmup with latency stabilization detection
                await smart_warmup_with_monitoring(self.config, self.traffic_generator)
                
                results["phases_completed"].append("pod_warmup")
                
                # === PHASE 2: BASELINE METRICS ===
                print(f"\n📊 === PHASE 2: BASELINE METRICS ===")
                # Reset metrics at START of baseline measurement phase
                self.traffic_generator.reset_phase_metrics()
                print(f"Recording baseline metrics for {self.config['baseline_duration']}s...")
                await asyncio.sleep(self.config["baseline_duration"])
                
                # Collect both traffic generator and Prometheus baseline metrics
                baseline_metrics = self.traffic_generator.get_phase_metrics(self.config["baseline_duration"])
                self.baseline_metrics = baseline_metrics
                
                # Collect Prometheus baseline metrics for agent context
                print(f"📈 Collecting Prometheus baseline metrics...")
                self.baseline_prometheus_metrics = self.prometheus_tool.get_metrics_summary(self.config["namespace"])
                
                results["phase_metrics"]["baseline"] = baseline_metrics
                print(f"✅ Baseline: {baseline_metrics['total_requests']} req ({baseline_metrics['expected_requests']} expected)")
                print(f"    Success: {baseline_metrics['success_rate_percent']}%, P95: {baseline_metrics['p95_latency_seconds']}s, Duration: {baseline_metrics['actual_duration_seconds']}s, RPS: {baseline_metrics.get('current_rps', 0)}")
                print(f"✅ Prometheus baseline captured for agent reference")
                results["phases_completed"].append("baseline")
            
            # === CHAOS INJECTION ===
            print(f"\n💥 === CHAOS INJECTION ===")
            if await self.inject_chaos():
                results["phases_completed"].append("chaos_injection")
            else:
                raise Exception("Failed to inject chaos")
            
            # === PHASE 3: CHAOS WARMUP (record metrics during active chaos) ===
            print(f"\n🔥 === PHASE 3: CHAOS WARMUP (ACTIVE CHAOS) ===")
            # Reset metrics at START of chaos measurement phase
            self.traffic_generator.reset_phase_metrics()
            print(f"Recording metrics during chaos for {self.config['chaos_warmup_duration']}s...")
            await asyncio.sleep(self.config["chaos_warmup_duration"])
            chaos_metrics = self.traffic_generator.get_phase_metrics(self.config["chaos_warmup_duration"])
            results["phase_metrics"]["chaos"] = chaos_metrics
            print(f"⚠️  Chaos: {chaos_metrics['total_requests']} req ({chaos_metrics['expected_requests']} expected)")
            print(f"    Success: {chaos_metrics['success_rate_percent']}%, P95: {chaos_metrics['p95_latency_seconds']}s, Duration: {chaos_metrics['actual_duration_seconds']}s, RPS: {chaos_metrics.get('current_rps', 0)}")
            
            # Collect Prometheus chaos metrics for agent context
            print(f"📈 Collecting Prometheus chaos metrics for agent context...")
            chaos_prometheus_metrics = self.prometheus_tool.get_metrics_summary(self.config["namespace"])
            print(f"✅ Prometheus chaos metrics captured for agent reference")
            results["phases_completed"].append("chaos_warmup")
            
            # === AGENT EXECUTION (during active chaos) ===
            print(f"\n🤖 === AGENT EXECUTION (CHAOS STILL ACTIVE) ===")
            agent_actions = await self.deploy_mitigation_agent(chaos_metrics, chaos_prometheus_metrics)
            results["agent_actions"] = agent_actions
            results["phases_completed"].append("agent_execution")
            
            # === PHASE 4: RECOVERY METRICS ===
            print(f"\n🔄 === PHASE 4: RECOVERY METRICS ===")
            # Reset metrics at START of recovery measurement phase (after agent execution)
            self.traffic_generator.reset_phase_metrics()
            print(f"Recording recovery metrics for {self.config['recovery_duration']}s...")
            await asyncio.sleep(self.config["recovery_duration"])
            recovery_metrics = self.traffic_generator.get_phase_metrics(self.config["recovery_duration"])
            results["phase_metrics"]["recovery"] = recovery_metrics
            print(f"🩹 Recovery: {recovery_metrics['total_requests']} req ({recovery_metrics['expected_requests']} expected)")
            print(f"    Success: {recovery_metrics['success_rate_percent']}%, P95: {recovery_metrics['p95_latency_seconds']}s, Duration: {recovery_metrics['actual_duration_seconds']}s, RPS: {recovery_metrics.get('current_rps', 0)}")
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