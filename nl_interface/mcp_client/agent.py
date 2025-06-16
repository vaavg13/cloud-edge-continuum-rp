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
from client import MCPClient
from kubernetes_tool_schemas import get_kubernetes_function_schemas, get_system_prompt
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
    
    async def call_mcp(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call MCP server with kubectl action.
        
        Args:
            args: Arguments containing function name and parameters
            
        Returns:
            Result from MCP server
        """
        if not self.is_initialized:
            raise RuntimeError("Agent not initialized. Call initialize() first.")
        
        function_name = args.get("function")
        parameters = args.get("parameters", {})
        
        print(f"🔧 Calling MCP: {function_name} with {json.dumps(parameters, indent=2)}")
        
        try:
            result = await self.mcp_client.call_tool(function_name, parameters)
            print(f"✅ MCP call completed")
            return result
        except Exception as e:
            error_result = {"error": f"MCP call failed: {str(e)}"}
            print(f"❌ MCP call failed: {e}")
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
            {"role": "user", "content": f"Based on the following context, what should I do next?\n\n{context_text}"}
        ]
        
        # Define available functions for the agent loop
        functions = [
            {
                "name": "kubectl_action",
                "description": "Execute a kubectl command through the MCP server. You must provide specific parameters for each kubectl function.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "function": {
                            "type": "string",
                            "description": "kubectl function to call",
                            "enum": ["kubectl_get", "kubectl_list", "kubectl_patch", "kubectl_apply", "kubectl_delete", "kubectl_scale"]
                        },
                        "parameters": {
                            "type": "object",
                            "description": "Parameters for the kubectl function - must include required fields like resourceType for kubectl_get",
                            "properties": {
                                "resourceType": {
                                    "type": "string",
                                    "description": "Type of Kubernetes resource (e.g., 'hpa', 'deployment', 'pod')"
                                },
                                "name": {
                                    "type": "string", 
                                    "description": "Name of the specific resource"
                                },
                                "namespace": {
                                    "type": "string",
                                    "description": "Namespace for the resource"
                                },
                                "output": {
                                    "type": "string",
                                    "description": "Output format (json, yaml, wide)"
                                },
                                "patchData": {
                                    "type": "object",
                                    "description": "Patch data for kubectl_patch operations"
                                },
                                "patchType": {
                                    "type": "string",
                                    "description": "Type of patch (merge, strategic, json)"
                                }
                            }
                        }
                    },
                    "required": ["function", "parameters"]
                }
            },
            {
                "name": "sleep_seconds",
                "description": "Wait for a specified number of seconds",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "duration": {
                            "type": "number",
                            "description": "Number of seconds to sleep"
                        }
                    },
                    "required": ["duration"]
                }
            }
        ]
        
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
                
                if func_name == "kubectl_action":
                    result = await self.call_mcp(args)
                    action = f"Executed: {args}"
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