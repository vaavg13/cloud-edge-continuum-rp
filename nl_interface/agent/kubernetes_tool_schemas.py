#!/usr/bin/env python3
"""
Kubernetes Tool Schemas for OpenAI Function Calling
Defines all available Kubernetes operations that an AI agent can perform through MCP.
"""

from typing import List, Dict, Any

SYSTEM_PROMPT = """You are a Kubernetes administrator assistant working in an agent loop. You have access to specific kubectl operations as individual functions.

Available kubectl functions:
- kubectl_get: Get specific resources (requires: resourceType; optional: name, namespace, output)
- kubectl_list: List resources of a type (requires: resourceType; optional: namespace, allNamespaces)
- kubectl_patch: Modify existing resources (requires: resourceType, name, patchData; optional: namespace, patchType, dryRun)
- kubectl_apply: Apply manifests (requires: manifest; optional: namespace, dryRun)
- kubectl_delete: Remove resources (requires: resourceType, name; optional: namespace, force)
- kubectl_scale: Scale deployments (requires: name, replicas; optional: namespace, resourceType)

Example operations:

Checking pod status:
kubectl_get(resourceType="pod", name="my-pod", namespace="default")

Listing all services across namespaces:
kubectl_list(resourceType="service", allNamespaces=true)

Updating a deployment's image:
kubectl_patch(resourceType="deployment", name="my-app", patchData={"spec": {"template": {"spec": {"containers": [{"name": "app", "image": "nginx:1.21"}]}}}})

Applying a new resource:
kubectl_apply(manifest="apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: test")

You should analyze the situation, determine what information you need, and choose appropriate kubectl operations to accomplish your goals.
""" 

def get_kubernetes_function_schemas() -> List[Dict[str, Any]]:
    """
    Get all available Kubernetes function schemas for OpenAI function calling.
    These define what operations the AI agent can perform on the Kubernetes cluster.
    """
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
                        "description": "Type of resource (e.g., 'namespace', 'pod', 'deployment', 'hpa')"
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
                        "description": "Type of resource to delete (e.g., 'namespace', 'pod', 'hpa')"
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
                        "description": "Type of resource to list (e.g., 'namespaces', 'pods', 'hpa')"
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
        },
        {
            "name": "kubectl_scale",
            "description": "Scale a Kubernetes deployment to a specific number of replicas",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the deployment to scale"
                    },
                    "namespace": {
                        "type": "string",
                        "description": "Namespace of the deployment"
                    },
                    "replicas": {
                        "type": "number",
                        "description": "Number of replicas to scale to"
                    },
                    "resourceType": {
                        "type": "string",
                        "description": "Resource type to scale (deployment, replicaset, statefulset)"
                    }
                },
                "required": ["name", "replicas"]
            }
        },
        {
            "name": "kubectl_patch",
            "description": "Patch a Kubernetes resource with specific changes (useful for HPA modifications)",
            "parameters": {
                "type": "object",
                "properties": {
                    "resourceType": {
                        "type": "string",
                        "description": "Type of resource to patch (e.g., 'hpa', 'deployment')"
                    },
                    "name": {
                        "type": "string",
                        "description": "Name of the resource to patch"
                    },
                    "namespace": {
                        "type": "string",
                        "description": "Namespace of the resource"
                    },
                    "patchType": {
                        "type": "string",
                        "description": "Type of patch: 'strategic', 'merge', or 'json'"
                    },
                    "patchData": {
                        "type": "object",
                        "description": "The patch data as a JSON object"
                    },
                    "dryRun": {
                        "type": "boolean",
                        "description": "If true, only validate the patch without applying it"
                    }
                },
                "required": ["resourceType", "name", "patchData"]
            }
        }
    ]

def get_system_prompt() -> str:
    """
    Get the system prompt that describes the AI agent's capabilities.
    """
    return SYSTEM_PROMPT