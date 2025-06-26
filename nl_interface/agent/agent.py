#!/usr/bin/env python3
"""
Main Agent Loop for Kubernetes Operations
Based on the template provided by the user, adapted for MCP Kubernetes operations.
"""

import asyncio
import json
import time
import openai
from typing import Dict, Any, List, Optional
from .mcp_client import MCPClient
from .tool_schemas import get_kubernetes_function_schemas, get_system_prompt
from ..shared.prometheus_client import (
    prometheus_get_node_cpu, prometheus_get_node_memory,
    prometheus_get_pod_cpu, prometheus_get_pod_memory,
    prometheus_get_istio_latency, prometheus_get_metrics_summary
)
from ..shared.types import MetricViolation
from .config_schema import create_agent_config, validate_agent_config
import logging

logger = logging.getLogger(__name__)

class KubernetesAgent:
    """
    Main Kubernetes agent with a simple loop-based approach.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, **kwargs):
        # Create config from dict, supporting both direct config and kwargs
        if config is not None:
            # Update config with any additional kwargs
            config = config.copy()
            config.update(kwargs)
        else:
            # Create config from kwargs
            config = kwargs
        
        # Merge with defaults and validate
        self.config = validate_agent_config(create_agent_config(**config))
        
        self.mcp_client = None
        self.openai_client = None
        self.is_initialized = False
    
    async def initialize(self):
        """Initialize the Kubernetes Agent with all required clients."""
        print("🔧 Initializing Kubernetes Agent...")
        print(f"   📋 Agent Config: max_rounds={self.config['max_rounds']}, timeout={self.config['agent_timeout']}s")
        
        # Initialize MCP client with the required server command
        # The server command should point to the MCP server for Kubernetes
        server_command = ["node", "./mcp-server-kubernetes/dist/index.js"]
        self.mcp_client = MCPClient(server_command)
        await self.mcp_client.start()
        await self.mcp_client.initialize()
        print("   ✅ MCP Kubernetes client ready")
        
        # Initialize OpenAI client  
        self.openai_client = openai.AsyncOpenAI(api_key=self.config["openai_api_key"])
        print("   ✅ OpenAI client ready")
        
        self.is_initialized = True
        print("✅ Agent initialization complete")
    
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
        
        try:
            result = await self.mcp_client.call_tool(function_name, parameters)
            return result
        except Exception as e:
            error_result = {"error": f"MCP call failed: {str(e)}"}
            print(f"❌ MCP Error: {str(e)}")
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
            return result
            
        except Exception as e:
            error_result = {"error": f"Prometheus call failed: {str(e)}"}
            print(f"❌ Prometheus Error: {str(e)}")
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
                model=self.config["openai_model"],
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
            logger.error(f"OpenAI API error: {e}")
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
        
        print(f"🤖 AGENT STARTED")
        print(f"   Intent: {intent}")
        print(f"   Max rounds: {self.config['max_rounds']}")
        print(f"   Context snapshot keys: {list(snapshot.keys()) if snapshot else 'None'}")
        
        for round_num in range(self.config['max_rounds']):
            print(f"\n🔄 Round {round_num + 1}/{self.config['max_rounds']}")
            
            llm_msg = await self.ask_llm_step(context)
            
            if llm_msg.get("error"):
                print(f"❌ LLM Error: {llm_msg['error']}")
                break
            
            if llm_msg.get("function_call"):
                func_name = llm_msg["function_call"]["name"]
                args = llm_msg["function_call"]["arguments"]
                
                print(f"⚡ Executing: {func_name}")
                if args:
                    print(f"   Parameters: {json.dumps(args, indent=2)}")
                
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
                    print(f"✅ MCP call completed")
                
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
                    print(f"✅ Prometheus call completed")
                
                elif func_name == "sleep_seconds":
                    duration = args["duration"]
                    print(f"💤 Sleeping for {duration} seconds...")
                    await asyncio.sleep(duration)
                    action = f"Slept {duration} seconds"
                    context.append(action)
                    actions_taken.append(action)
                    print(f"✅ Sleep completed")
                
                else:
                    print(f"⚠️ Unknown function: {func_name}")
            
            else:
                completion_msg = llm_msg.get('content', '').strip()
                if completion_msg:
                    print(f"💭 Agent says: {completion_msg}")
                print(f"🏁 Agent completed normally")
                break
        
        print(f"\n🎯 AGENT FINISHED")
        print(f"   Actions taken: {len(actions_taken)}")
        
        return actions_taken
    
    async def cleanup(self):
        """Clean up resources."""
        print("🧹 Cleaning up agent...")
        if self.mcp_client:
            await self.mcp_client.stop()
        self.is_initialized = False
        print("✅ Agent cleanup complete")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()