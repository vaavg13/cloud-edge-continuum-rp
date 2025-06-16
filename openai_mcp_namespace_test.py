#!/usr/bin/env python3
"""
OpenAI Function Calling script to interact with MCP Kubernetes server.
The LLM will use function calling to create and delete a namespace.
"""

import asyncio
import json
import sys
import os
import openai
from typing import Dict, Any, Optional

# Add the mcp_client directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'nl_interface', 'mcp_client'))

from client import MCPClient

# OpenAI API key from nl2app
OPENAI_API_KEY = ('sk-proj-DiA9-QUBGXsMxJGD4khuFmpH9bm7Ww-'
                  'D2hWzAPREKhsQaLf2bcBN1awr32g4kMT63LMmy5kmGeT3BlbkFJQUGUw-'
                  '40noCLugjh0hDoU94R0Iz6BLzAxwRcsybW7CjQS8bOKzhBS2EZp7-'
                  'B3ZmRHNk8znukoA')

# Global MCP client instance
mcp_client = None

def get_kubernetes_function_schemas():
    """Define the function schemas for Kubernetes operations that the LLM can call."""
    return [
        {
            "name": "kubectl_apply",
            "description": "Apply a Kubernetes YAML manifest to create or update resources",
            "parameters": {
                "type": "object",
                "properties": {
                    "manifest": {
                        "type": "string",
                        "description": "The YAML manifest content to apply"
                    },
                    "namespace": {
                        "type": "string",
                        "description": "Target namespace (optional, defaults to 'default')"
                    },
                    "dryRun": {
                        "type": "boolean",
                        "description": "If true, only validate the resource without applying it"
                    }
                },
                "required": ["manifest"]
            }
        },
        {
            "name": "kubectl_get",
            "description": "Get or list Kubernetes resources by type and name",
            "parameters": {
                "type": "object",
                "properties": {
                    "resourceType": {
                        "type": "string",
                        "description": "Type of resource (e.g., 'namespace', 'pod', 'deployment')"
                    },
                    "name": {
                        "type": "string",
                        "description": "Name of the specific resource (optional for listing all)"
                    },
                    "namespace": {
                        "type": "string",
                        "description": "Namespace to search in (optional)"
                    },
                    "output": {
                        "type": "string",
                        "description": "Output format: 'json', 'yaml', 'wide', 'name'"
                    }
                },
                "required": ["resourceType"]
            }
        },
        {
            "name": "kubectl_delete",
            "description": "Delete Kubernetes resources by type and name",
            "parameters": {
                "type": "object",
                "properties": {
                    "resourceType": {
                        "type": "string",
                        "description": "Type of resource to delete (e.g., 'namespace', 'pod')"
                    },
                    "name": {
                        "type": "string",
                        "description": "Name of the resource to delete"
                    },
                    "namespace": {
                        "type": "string",
                        "description": "Namespace of the resource (optional for cluster-scoped resources)"
                    },
                    "force": {
                        "type": "boolean",
                        "description": "Force immediate deletion without graceful shutdown"
                    }
                },
                "required": ["resourceType", "name"]
            }
        },
        {
            "name": "kubectl_list",
            "description": "List all resources of a specific type across namespaces",
            "parameters": {
                "type": "object",
                "properties": {
                    "resourceType": {
                        "type": "string",
                        "description": "Type of resource to list (e.g., 'namespaces', 'pods')"
                    },
                    "namespace": {
                        "type": "string",
                        "description": "Specific namespace to list from (optional)"
                    },
                    "allNamespaces": {
                        "type": "boolean",
                        "description": "List resources across all namespaces"
                    }
                },
                "required": ["resourceType"]
            }
        }
    ]

async def execute_kubectl_function(function_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a kubectl function through the MCP client."""
    global mcp_client
    
    try:
        print(f"🔧 Executing {function_name} with args: {json.dumps(arguments, indent=2)}")
        
        # Map function names to MCP tool names
        tool_mapping = {
            "kubectl_apply": "kubectl_apply",
            "kubectl_get": "kubectl_get", 
            "kubectl_delete": "kubectl_delete",
            "kubectl_list": "kubectl_list"
        }
        
        if function_name not in tool_mapping:
            return {"error": f"Unknown function: {function_name}"}
        
        # Call the MCP tool
        result = await mcp_client.call_tool(tool_mapping[function_name], arguments)
        
        print(f"✅ {function_name} completed")
        return result
        
    except Exception as e:
        error_msg = f"Error executing {function_name}: {str(e)}"
        print(f"❌ {error_msg}")
        return {"error": error_msg}

async def run_openai_agent_workflow():
    """Run the complete workflow using OpenAI function calling."""
    global mcp_client
    
    # Initialize MCP client
    mcp_client = MCPClient(["npx", "mcp-server-kubernetes"])
    
    try:
        print("🚀 Starting MCP Kubernetes client...")
        await mcp_client.start()
        await mcp_client.initialize()
        print("✅ MCP client initialized")
        
        # Initialize OpenAI client
        openai_client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
        
        # Phase 1: Ask the LLM to create a namespace named "test"
        print("\n" + "="*60)
        print("🤖 PHASE 1: Asking LLM to create namespace 'test'")
        print("="*60)
        
        create_response = await openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": """You are a Kubernetes administrator assistant. You have access to kubectl functions through function calling.
                    
Available functions:
- kubectl_apply: Apply YAML manifests to create/update resources
- kubectl_get: Get specific resources by name and type  
- kubectl_delete: Delete resources by type and name
- kubectl_list: List all resources of a specific type

When creating namespaces, use a simple YAML manifest with apiVersion: v1, kind: Namespace, and appropriate metadata."""
                },
                {
                    "role": "user", 
                    "content": "Please create a namespace called 'test' in the Kubernetes cluster."
                }
            ],
            functions=get_kubernetes_function_schemas(),
            function_call="auto"
        )
        
        # Execute function calls from LLM
        message = create_response.choices[0].message
        if message.function_call:
            func_name = message.function_call.name
            func_args = json.loads(message.function_call.arguments)
            result = await execute_kubectl_function(func_name, func_args)
            
            print(f"\n🔍 LLM decided to call: {func_name}")
            print(f"📄 Function result: {json.dumps(result, indent=2)}")
        
        # Phase 2: Ask the LLM to verify the namespace was created
        print("\n" + "="*60)
        print("🤖 PHASE 2: Asking LLM to verify namespace creation")
        print("="*60)
        
        verify_response = await openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": """You are a Kubernetes administrator assistant. You have access to kubectl functions through function calling.
                    
Available functions:
- kubectl_apply: Apply YAML manifests to create/update resources
- kubectl_get: Get specific resources by name and type  
- kubectl_delete: Delete resources by type and name
- kubectl_list: List all resources of a specific type"""
                },
                {
                    "role": "user",
                    "content": "Please check if the namespace 'test' was successfully created in the Kubernetes cluster."
                }
            ],
            functions=get_kubernetes_function_schemas(),
            function_call="auto"
        )
        
        # Execute verification function call
        verify_message = verify_response.choices[0].message
        if verify_message.function_call:
            func_name = verify_message.function_call.name
            func_args = json.loads(verify_message.function_call.arguments)
            result = await execute_kubectl_function(func_name, func_args)
            
            print(f"\n🔍 LLM decided to call: {func_name}")
            print(f"📄 Verification result: {json.dumps(result, indent=2)}")
        
        # Phase 3: Ask the LLM to delete the namespace
        print("\n" + "="*60)
        print("🤖 PHASE 3: Asking LLM to delete namespace 'test'")
        print("="*60)
        
        delete_response = await openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": """You are a Kubernetes administrator assistant. You have access to kubectl functions through function calling.
                    
Available functions:
- kubectl_apply: Apply YAML manifests to create/update resources
- kubectl_get: Get specific resources by name and type  
- kubectl_delete: Delete resources by type and name
- kubectl_list: List all resources of a specific type"""
                },
                {
                    "role": "user",
                    "content": "Please delete the namespace 'test' from the Kubernetes cluster."
                }
            ],
            functions=get_kubernetes_function_schemas(),
            function_call="auto"
        )
        
        # Execute deletion function call
        delete_message = delete_response.choices[0].message
        if delete_message.function_call:
            func_name = delete_message.function_call.name
            func_args = json.loads(delete_message.function_call.arguments)
            result = await execute_kubectl_function(func_name, func_args)
            
            print(f"\n🔍 LLM decided to call: {func_name}")
            print(f"📄 Deletion result: {json.dumps(result, indent=2)}")
        
        # Phase 4: Final verification that namespace is deleted
        print("\n" + "="*60)
        print("🤖 PHASE 4: Final verification that namespace is deleted")
        print("="*60)
        
        final_verify_response = await openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": """You are a Kubernetes administrator assistant. You have access to kubectl functions through function calling.
                    
Available functions:
- kubectl_apply: Apply YAML manifests to create/update resources
- kubectl_get: Get specific resources by name and type  
- kubectl_delete: Delete resources by type and name
- kubectl_list: List all resources of a specific type"""
                },
                {
                    "role": "user",
                    "content": "Please verify that the namespace 'test' has been successfully deleted from the Kubernetes cluster."
                }
            ],
            functions=get_kubernetes_function_schemas(),
            function_call="auto"
        )
        
        # Execute final verification
        final_message = final_verify_response.choices[0].message
        if final_message.function_call:
            func_name = final_message.function_call.name
            func_args = json.loads(final_message.function_call.arguments)
            result = await execute_kubectl_function(func_name, func_args)
            
            print(f"\n🔍 LLM decided to call: {func_name}")
            print(f"📄 Final verification result: {json.dumps(result, indent=2)}")
        
        print("\n🎉 OpenAI + MCP Kubernetes workflow completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during workflow: {e}")
    finally:
        print("\n🔌 Stopping MCP client...")
        if mcp_client:
            await mcp_client.stop()

if __name__ == "__main__":
    print("🤖 Starting OpenAI Function Calling + MCP Kubernetes Test")
    print("=" * 70)
    asyncio.run(run_openai_agent_workflow()) 