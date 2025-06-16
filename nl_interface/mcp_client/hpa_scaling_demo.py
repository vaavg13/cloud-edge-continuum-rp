#!/usr/bin/env python3
"""
HPA Scaling Demo Script
Demonstrates how to use the Kubernetes agent to check and modify HPA settings for deployment s0-edge-site-1.
"""

import asyncio
import json
from agent_core import KubernetesAgent
from utils import extract_hpa_info, format_workflow_summary
from config import OPENAI_API_KEY, DEFAULT_DEPLOYMENT_NAME

async def demo_hpa_scaling():
    """
    Demonstrate HPA scaling workflow for deployment s0-edge-site-1.
    """
    deployment_name = DEFAULT_DEPLOYMENT_NAME
    
    # Define the workflow steps
    workflow_steps = [
        f"Please check if there is an HPA (Horizontal Pod Autoscaler) for deployment '{deployment_name}' in any namespace. If found, show me the current maxReplicas value.",
        
        f"Now please increase the maxReplicas value of the HPA for deployment '{deployment_name}' by 1. Use kubectl patch to modify the HPA resource.",
        
        f"Please verify that the HPA for deployment '{deployment_name}' has been updated by checking the maxReplicas value again. Show me the new value to confirm the change.",
        
        f"Finally, let's also check the current status of the deployment '{deployment_name}' itself to see how many replicas are currently running."
    ]
    
    print("🚀 Starting HPA Scaling Demo")
    print("="*70)
    print(f"Target deployment: {deployment_name}")
    print(f"Operation: Increase HPA maxReplicas by 1")
    print("="*70)
    
    # Use the agent as a context manager for automatic cleanup
    async with KubernetesAgent(OPENAI_API_KEY) as agent:
        
        # Run the workflow
        results = await agent.run_workflow(workflow_steps)
        
        # Print detailed results
        print("\n" + "="*60)
        print("📊 DETAILED RESULTS")
        print("="*60)
        
        for i, result in enumerate(results):
            print(f"\n🔍 Step {i+1} Details:")
            
            if result.get("function_call"):
                func_call = result["function_call"]
                print(f"  AI chose function: {func_call['name']}")
                print(f"  With arguments: {json.dumps(func_call['arguments'], indent=4)}")
            
            if result.get("function_result"):
                func_result = result["function_result"]
                print(f"  Function result:")
                print(f"    Raw response: {json.dumps(func_result, indent=4)}")
                
                # Try to extract HPA info if this was an HPA-related call
                if (result.get("function_call", {}).get("name") == "kubectl_get" and 
                    "hpa" in result.get("function_call", {}).get("arguments", {}).get("resourceType", "")):
                    
                    hpa_info = extract_hpa_info(func_result)
                    if hpa_info:
                        print(f"    Extracted HPA info:")
                        print(f"      Name: {hpa_info['name']}")
                        print(f"      Namespace: {hpa_info['namespace']}")
                        print(f"      Min Replicas: {hpa_info['min_replicas']}")
                        print(f"      Max Replicas: {hpa_info['max_replicas']}")
                        print(f"      Current Replicas: {hpa_info['current_replicas']}")
            
            if result.get("error"):
                print(f"  ❌ Error: {result['error']}")
        
        # Print summary
        summary = format_workflow_summary(results)
        print(summary)
        
        print("🎉 HPA Scaling Demo completed!")

async def main():
    """Main entry point."""
    try:
        await demo_hpa_scaling()
    except Exception as e:
        print(f"❌ Demo failed with error: {e}")
        raise

if __name__ == "__main__":
    print("🤖 HPA Scaling Demo - OpenAI + MCP Kubernetes Agent")
    print("=" * 70)
    asyncio.run(main()) 