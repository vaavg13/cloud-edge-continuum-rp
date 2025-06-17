#!/usr/bin/env python3
"""
Main Agent Loop for Kubernetes Operations
Based on the template provided by the user, adapted for MCP Kubernetes operations.
"""

import asyncio
import json
import time
import openai
from typing import Dict, Any, List
from mcp_client import MCPClient
from tool_schemas import get_kubernetes_function_schemas, get_system_prompt
from prometheus_tool import (
    prometheus_get_node_cpu, prometheus_get_node_memory,
    prometheus_get_pod_cpu, prometheus_get_pod_memory,
    prometheus_get_istio_latency, prometheus_get_metrics_summary
)
from config import OPENAI_API_KEY, OPENAI_MODEL

class KubernetesAgent:
    """
    Main Kubernetes agent with a simple loop-based approach.
    """
    
    def __init__(self, openai_api_key: str = OPENAI_API_KEY):
        self.openai_api_key = openai_api_key
        self.mcp_client = None
        self.openai_client = None
        self.is_initialized = False
    
    async def initialize(self):
        """Initialize MCP and OpenAI clients."""
        if self.is_initialized:
            return
            
        print("🚀 Initializing Kubernetes Agent...")
        
        # Initialize MCP client
        self.mcp_client = MCPClient(["npx", "mcp-server-kubernetes"])
        await self.mcp_client.start()
        await self.mcp_client.initialize()
        print("✅ MCP Kubernetes client initialized")
        
        # Initialize OpenAI client
        self.openai_client = openai.AsyncOpenAI(api_key=self.openai_api_key)
        print("✅ OpenAI client initialized")
        
        self.is_initialized = True
    
    async def call_mcp(self, function_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call MCP server with kubectl function.
        
        Args:
            function_name: Name of the kubectl function to call
            parameters: Parameters for the function
            
        Returns:
            Result from MCP server
        """
        if not self.is_initialized:
            raise RuntimeError("Agent not initialized. Call initialize() first.")
        
        print(f"🔧 Calling MCP: {function_name} with {json.dumps(parameters, indent=2)}")
        
        try:
            result = await self.mcp_client.call_tool(function_name, parameters)
            print(f"✅ MCP call completed")
            # print(json.dumps(result, indent=2))
            return result
        except Exception as e:
            error_result = {"error": f"MCP call failed: {str(e)}"}
            print(f"❌ MCP call failed: {e}")
            # print(json.dumps(error_result, indent=2))
            return error_result
    
    async def call_prometheus_function(self, function_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call Prometheus metrics function.
        
        Args:
            function_name: Name of the prometheus function to call
            parameters: Parameters for the function
            
        Returns:
            Result from Prometheus query
        """
        print(f"📊 Calling Prometheus: {function_name} with {json.dumps(parameters, indent=2)}")
        
        try:
            # Map function names to actual functions
            function_map = {
                "prometheus_get_node_cpu": prometheus_get_node_cpu,
                "prometheus_get_node_memory": prometheus_get_node_memory,
                "prometheus_get_pod_cpu": prometheus_get_pod_cpu,
                "prometheus_get_pod_memory": prometheus_get_pod_memory,
                "prometheus_get_istio_latency": prometheus_get_istio_latency,
                "prometheus_get_metrics_summary": prometheus_get_metrics_summary
            }
            
            func = function_map.get(function_name)
            if not func:
                return {"error": f"Unknown Prometheus function: {function_name}"}
            
            # Call the function with parameters
            result = func(**parameters)
            print(f"✅ Prometheus call completed")
            return result
            
        except Exception as e:
            error_result = {"error": f"Prometheus call failed: {str(e)}"}
            print(f"❌ Prometheus call failed: {e}")
            return error_result
    
    async def ask_llm_step(self, context: List[str]) -> Dict[str, Any]:
        """
        Ask the LLM for the next step based on current context.
        
        Args:
            context: List of context strings from previous rounds
            
        Returns:
            LLM response with potential function call
        """
        if not self.is_initialized:
            raise RuntimeError("Agent not initialized. Call initialize() first.")
        
        # Build the context message
        context_text = "\n".join(context)
        
        messages = [
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": f"Based on the following context, what should you do next?\n\n{context_text}"}
        ]
        
        # Get all available functions from tool schemas
        functions = get_kubernetes_function_schemas()
        
        try:
            response = await self.openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                functions=functions,
                function_call="auto"
            )
            
            message = response.choices[0].message
            
            result = {
                "content": message.content,
                "function_call": None
            }
            
            if message.function_call:
                result["function_call"] = {
                    "name": message.function_call.name,
                    "arguments": json.loads(message.function_call.arguments)
                }
            
            return result
            
        except Exception as e:
            print(f"❌ OpenAI API error: {e}")
            return {"error": f"OpenAI API error: {str(e)}"}
    
    async def agent_loop(self, intent: str, snapshot: Dict[str, Any] = None) -> List[str]:
        """
        Main agent loop based on the user's template.
        
        Args:
            intent: What the agent should accomplish
            snapshot: Initial state information (optional)
            
        Returns:
            List of actions taken during the loop
        """
        if not self.is_initialized:
            await self.initialize()
        
        snapshot = snapshot or {}
        context = [
            f"Intent: {intent}",
            f"Snapshot: {json.dumps(snapshot, indent=2)}"
        ]
        
        actions_taken = []
        
        for round_num in range(10):
            print(f"\n🔄 Round {round_num + 1}")
            
            llm_msg = await self.ask_llm_step(context)
            
            if llm_msg.get("error"):
                print(f"❌ LLM error: {llm_msg['error']}")
                break
            
            if llm_msg.get("function_call"):
                func_name = llm_msg["function_call"]["name"]
                args = llm_msg["function_call"]["arguments"]
                
                if func_name in [
                    "kubectl_apply", "kubectl_get", "kubectl_delete", 
                    "kubectl_list", "kubectl_scale", "kubectl_patch",
                    "kubectl_describe", "kubectl_logs", "kubectl_rollout"
                ]:
                    result = await self.call_mcp(func_name, args)
                    action = f"Executed {func_name}: {args}"
                    context.append(action)
                    context.append(f"Result: {json.dumps(result, indent=2)}")
                    actions_taken.append(action)
                
                elif func_name in [
                    "prometheus_get_node_cpu", "prometheus_get_node_memory",
                    "prometheus_get_pod_cpu", "prometheus_get_pod_memory", 
                    "prometheus_get_istio_latency", "prometheus_get_metrics_summary"
                ]:
                    result = await self.call_prometheus_function(func_name, args)
                    action = f"Executed {func_name}: {args}"
                    context.append(action)
                    context.append(f"Result: {json.dumps(result, indent=2)}")
                    actions_taken.append(action)
                
                elif func_name == "sleep_seconds":
                    duration = args["duration"]
                    print(f"⏳ Sleeping for {duration} seconds")
                    await asyncio.sleep(duration)
                    action = f"Slept {duration} seconds"
                    context.append(action)
                    actions_taken.append(action)
                
                else:
                    print(f"❓ Unknown function: {func_name}")
            
            else:
                print(f"✅ Agent stopped: {llm_msg.get('content', '').strip()}")
                break
        
        return actions_taken
    
    async def cleanup(self):
        """Clean up resources."""
        print("\n🔌 Cleaning up agent...")
        if self.mcp_client:
            await self.mcp_client.stop()
        self.is_initialized = False
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()

# Convenience function for quick agent usage
async def run_agent(intent: str, snapshot: Dict[str, Any] = None) -> List[str]:
    """
    Run the agent with a specific intent.
    
    Args:
        intent: What the agent should accomplish
        snapshot: Initial state information (optional)
        
    Returns:
        List of actions taken
    """
    async with KubernetesAgent() as agent:
        return await agent.agent_loop(intent, snapshot) 