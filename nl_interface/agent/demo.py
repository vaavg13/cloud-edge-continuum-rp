#!/usr/bin/env python3
"""
HPA Demo using the new agent loop approach.
The agent decides how to check and modify HPA settings autonomously.
"""

import asyncio
from agent import run_agent
from utils import format_action_summary
from config import DEFAULT_DEPLOYMENT_NAME

async def main():
    """
    Main demo function that uses the agent loop to handle HPA scaling.
    """
    deployment_name = DEFAULT_DEPLOYMENT_NAME
    
    print("🚀 HPA Scaling Demo - Agent Loop Approach")
    print("=" * 60)
    print(f"Target deployment: {deployment_name}")
    print("=" * 60)
    
    # Define the intent for the agent
    intent = (
        f"I want to increase the maxReplicas of the HPA for deployment '{deployment_name}' by 1. "
        f"First check the current maxReplicas value, then increase it by 1, then verify the change was successful."
    )
    
    # Initial snapshot (empty - let the agent discover the current state)
    snapshot = {
        "target_deployment": deployment_name,
        "operation": "increase_hpa_max_replicas",
        "increment": 1
    }
    
    try:
        print(f"\n🤖 Starting agent with intent: {intent}")
        print("\n" + "="*60)
        
        actions = await run_agent(intent, snapshot)
        
        print("\n" + "="*60)
        print("📋 FINAL SUMMARY")
        print("="*60)
        print(format_action_summary(actions))
        print("\n🎉 HPA Demo completed!")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 