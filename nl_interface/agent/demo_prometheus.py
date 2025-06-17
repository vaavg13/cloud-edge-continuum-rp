#!/usr/bin/env python3
"""
Demo script for Prometheus metrics integration with the agent.
"""

import asyncio
import json
from agent import KubernetesAgent
from config import DEFAULT_NAMESPACE

async def demo_prometheus_agent():
    """Demo the Prometheus metrics functionality in the agent."""
    
    print("🚀 Starting Prometheus Agent Demo")
    
    async with KubernetesAgent() as agent:
        print("\n🔍 Demo 1: Get current node CPU usage")
        actions = await agent.agent_loop(
            intent="Get the current CPU usage for all nodes in the cluster using Prometheus metrics",
            snapshot={"cluster_analysis": True, "focus": "node_performance"}
        )
        print(f"Actions taken: {actions}")
        
        print(f"\n🔍 Demo 2: Get pod metrics for namespace '{DEFAULT_NAMESPACE}'")
        actions = await agent.agent_loop(
            intent=f"Get the current CPU and memory usage for all pods in the '{DEFAULT_NAMESPACE}' namespace",
            snapshot={"cluster_analysis": True, "target_namespace": DEFAULT_NAMESPACE, "focus": "pod_resources"}
        )
        print(f"Actions taken: {actions}")
        
        print(f"\n🔍 Demo 3: Get Istio latency metrics for namespace '{DEFAULT_NAMESPACE}'")
        actions = await agent.agent_loop(
            intent=f"Check the current p95 latency metrics for services in namespace '{DEFAULT_NAMESPACE}'. If no service mesh metrics are found, report that and stop.",
            snapshot={"cluster_analysis": True, "target_namespace": DEFAULT_NAMESPACE, "focus": "service_performance"}
        )
        print(f"Actions taken: {actions}")
        
        print(f"\n🔍 Demo 4: Get comprehensive metrics summary for namespace '{DEFAULT_NAMESPACE}'")
        actions = await agent.agent_loop(
            intent=f"Get a comprehensive overview of all current metrics for namespace '{DEFAULT_NAMESPACE}' including CPU, memory, and any latency data available.",
            snapshot={"cluster_analysis": True, "target_namespace": DEFAULT_NAMESPACE, "focus": "comprehensive_health"}
        )
        print(f"Actions taken: {actions}")
        
        print(f"\n🔍 Demo 5: Quick Istio check - just get raw data")
        actions = await agent.agent_loop(
            intent="Check if any service mesh latency data is available in the cluster. Report what you find.",
            snapshot={"cluster_analysis": True, "focus": "service_mesh_availability"}
        )
        print(f"Actions taken: {actions}")

if __name__ == "__main__":
    asyncio.run(demo_prometheus_agent()) 