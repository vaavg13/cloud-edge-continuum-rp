#!/usr/bin/env python3
"""
Agent Core Logic
Handles the interaction between OpenAI function calling and MCP Kubernetes server.
"""

import asyncio
import json
import openai
from typing import Dict, Any, Optional, List
from client import MCPClient
from kubernetes_tool_schemas import get_kubernetes_function_schemas, get_system_prompt

class KubernetesAgent:
    """
    A reusable Kubernetes agent that can perform operations through OpenAI function calling.
    """
    
    def __init__(self, openai_api_key: str, mcp_server_command: List[str] = None):
        """
        Initialize the Kubernetes agent.
        
        Args:
            openai_api_key: OpenAI API key for GPT models
            mcp_server_command: Command to start MCP server (defaults to kubernetes server)
        """
        self.openai_api_key = openai_api_key
        self.mcp_server_command = mcp_server_command or ["npx", "mcp-server-kubernetes"]
        self.mcp_client = None
        self.openai_client = None
        self.is_initialized = False
    
    async def initialize(self):
        """Initialize both MCP and OpenAI clients."""
        if self.is_initialized:
            return
            
        print("🚀 Initializing Kubernetes Agent...")
        
        # Initialize MCP client
        self.mcp_client = MCPClient(self.mcp_server_command)
        await self.mcp_client.start()
        await self.mcp_client.initialize()
        print("✅ MCP Kubernetes client initialized")
        
        # Initialize OpenAI client
        self.openai_client = openai.AsyncOpenAI(api_key=self.openai_api_key)
        print("✅ OpenAI client initialized")
        
        self.is_initialized = True
    
    async def execute_kubectl_function(self, function_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a kubectl function through the MCP client.
        
        Args:
            function_name: Name of the function to execute
            arguments: Arguments for the function
            
        Returns:
            Result from the MCP server
        """
        if not self.is_initialized:
            raise RuntimeError("Agent not initialized. Call initialize() first.")
        
        try:
            print(f"🔧 Executing {function_name} with args: {json.dumps(arguments, indent=2)}")
            
            # Map function names to MCP tool names (they should be the same)
            tool_mapping = {
                "kubectl_apply": "kubectl_apply",
                "kubectl_get": "kubectl_get", 
                "kubectl_delete": "kubectl_delete",
                "kubectl_list": "kubectl_list",
                "kubectl_scale": "kubectl_scale",
                "kubectl_patch": "kubectl_patch"
            }
            
            if function_name not in tool_mapping:
                return {"error": f"Unknown function: {function_name}"}
            
            # Call the MCP tool
            result = await self.mcp_client.call_tool(tool_mapping[function_name], arguments)
            
            print(f"✅ {function_name} completed")
            return result
            
        except Exception as e:
            error_msg = f"Error executing {function_name}: {str(e)}"
            print(f"❌ {error_msg}")
            return {"error": error_msg}
    
    async def ask_agent(self, user_message: str, context_messages: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Ask the AI agent to perform a task using function calling.
        
        Args:
            user_message: The task to ask the agent to perform
            context_messages: Optional previous conversation context
            
        Returns:
            Dict containing the agent's response and any function call results
        """
        if not self.is_initialized:
            raise RuntimeError("Agent not initialized. Call initialize() first.")
        
        # Build message history
        messages = [{"role": "system", "content": get_system_prompt()}]
        
        if context_messages:
            messages.extend(context_messages)
        
        messages.append({"role": "user", "content": user_message})
        
        try:
            # Call OpenAI with function calling enabled
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                functions=get_kubernetes_function_schemas(),
                function_call="auto"
            )
            
            message = response.choices[0].message
            result = {
                "response_text": message.content,
                "function_call": None,
                "function_result": None
            }
            
            # Execute function call if present
            if message.function_call:
                func_name = message.function_call.name
                func_args = json.loads(message.function_call.arguments)
                
                result["function_call"] = {
                    "name": func_name,
                    "arguments": func_args
                }
                
                # Execute the function
                func_result = await self.execute_kubectl_function(func_name, func_args)
                result["function_result"] = func_result
                
                print(f"\n🔍 Agent decided to call: {func_name}")
                print(f"📄 Function result: {json.dumps(func_result, indent=2)}")
            
            return result
            
        except Exception as e:
            print(f"❌ Error calling OpenAI: {e}")
            return {"error": f"OpenAI API error: {str(e)}"}
    
    async def run_workflow(self, workflow_steps: List[str]) -> List[Dict[str, Any]]:
        """
        Run a multi-step workflow where each step is a separate agent interaction.
        
        Args:
            workflow_steps: List of user messages for each step
            
        Returns:
            List of results from each step
        """
        if not self.is_initialized:
            raise RuntimeError("Agent not initialized. Call initialize() first.")
        
        results = []
        context_messages = []
        
        for i, step in enumerate(workflow_steps):
            print(f"\n{'='*60}")
            print(f"🤖 STEP {i+1}: {step}")
            print("="*60)
            
            result = await self.ask_agent(step, context_messages)
            results.append(result)
            
            # Add to context for next step (if we want continuity)
            context_messages.append({"role": "user", "content": step})
            if result.get("response_text"):
                context_messages.append({"role": "assistant", "content": result["response_text"]})
        
        return results
    
    async def cleanup(self):
        """Clean up resources."""
        print("\n🔌 Cleaning up Kubernetes Agent...")
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