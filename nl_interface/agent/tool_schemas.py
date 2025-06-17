#!/usr/bin/env python3
"""
Tool Schemas for OpenAI Function Calling
Defines all available operations that an AI agent can perform through MCP and other utilities.
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
- kubectl_describe: Describe detailed resource information (requires: resourceType, name; optional: namespace, allNamespaces)
- kubectl_logs: Get logs from pods, deployments, jobs (requires: resourceType, name, namespace; optional: container, tail, since, timestamps, previous, follow)
- kubectl_rollout: Manage deployment rollouts (requires: subCommand, resourceType, name; optional: namespace, revision, timeout, watch)
- prometheus_get_node_cpu: Get current CPU usage for all nodes (optional: rate_window)
- prometheus_get_node_memory: Get current memory usage for all nodes
- prometheus_get_pod_cpu: Get current CPU usage for pods (optional: namespace, rate_window)
- prometheus_get_pod_memory: Get current memory usage for pods (optional: namespace)
- prometheus_get_istio_latency: Get current Istio latency metrics for services (optional: namespace, percentile, rate_window)
- prometheus_get_metrics_summary: Get a summary of all current metrics for a namespace or all namespaces (optional: namespace)
- sleep_seconds: Wait for a specified number of seconds (requires: duration)

Example operations:

Checking pod status:
kubectl_get(resourceType="pod", name="my-pod", namespace="default")

Getting detailed pod information:
kubectl_describe(resourceType="pod", name="my-pod", namespace="default")

Getting pod logs:
kubectl_logs(resourceType="pod", name="my-pod", namespace="default", tail=100)

Checking deployment rollout status:
kubectl_rollout(subCommand="status", resourceType="deployment", name="my-app", namespace="default")

Rolling back a deployment:
kubectl_rollout(subCommand="undo", resourceType="deployment", name="my-app", namespace="default")

Waiting between operations:
sleep_seconds(duration=5)

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
    Get all available function schemas for OpenAI function calling.
    These define what operations the AI agent can perform on the Kubernetes cluster and utilities.
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
        },
        {
            "name": "kubectl_describe",
            "description": "Describe Kubernetes resources by resource type, name, and optionally namespace",
            "parameters": {
                "type": "object",
                "properties": {
                    "resourceType": {
                        "type": "string",
                        "description": "Type of resource to describe (e.g., pods, deployments, services, hpa, nodes)"
                    },
                    "name": {
                        "type": "string",
                        "description": "Name of the resource to describe"
                    },
                    "namespace": {
                        "type": "string",
                        "description": "Namespace of the resource (optional - defaults to 'default' for namespaced resources)"
                    },
                    "allNamespaces": {
                        "type": "boolean",
                        "description": "If true, describe resources across all namespaces"
                    }
                },
                "required": ["resourceType", "name"]
            }
        },
        {
            "name": "kubectl_logs",
            "description": "Get logs from Kubernetes resources like pods, deployments, or jobs",
            "parameters": {
                "type": "object",
                "properties": {
                    "resourceType": {
                        "type": "string",
                        "description": "Type of resource to get logs from (pod, deployment, job, cronjob)"
                    },
                    "name": {
                        "type": "string",
                        "description": "Name of the resource"
                    },
                    "namespace": {
                        "type": "string",
                        "description": "Namespace of the resource"
                    },
                    "container": {
                        "type": "string",
                        "description": "Container name (required when pod has multiple containers)"
                    },
                    "tail": {
                        "type": "number",
                        "description": "Number of lines to show from end of logs"
                    },
                    "since": {
                        "type": "string",
                        "description": "Show logs since relative time (e.g. '5s', '2m', '3h')"
                    },
                    "sinceTime": {
                        "type": "string",
                        "description": "Show logs since absolute time (RFC3339)"
                    },
                    "timestamps": {
                        "type": "boolean",
                        "description": "Include timestamps in logs"
                    },
                    "previous": {
                        "type": "boolean",
                        "description": "Include logs from previously terminated containers"
                    },
                    "follow": {
                        "type": "boolean",
                        "description": "Follow logs output (not recommended, may cause timeouts)"
                    },
                    "labelSelector": {
                        "type": "string",
                        "description": "Filter resources by label selector"
                    }
                },
                "required": ["resourceType", "name", "namespace"]
            }
        },
        {
            "name": "kubectl_rollout",
            "description": "Manage the rollout of a resource (e.g., deployment, daemonset, statefulset)",
            "parameters": {
                "type": "object",
                "properties": {
                    "subCommand": {
                        "type": "string",
                        "description": "Rollout subcommand to execute",
                        "enum": ["history", "pause", "restart", "resume", "status", "undo"]
                    },
                    "resourceType": {
                        "type": "string",
                        "description": "Type of resource to manage rollout for",
                        "enum": ["deployment", "daemonset", "statefulset"]
                    },
                    "name": {
                        "type": "string",
                        "description": "Name of the resource"
                    },
                    "namespace": {
                        "type": "string",
                        "description": "Namespace of the resource"
                    },
                    "revision": {
                        "type": "number",
                        "description": "Revision to rollback to (for undo subcommand)"
                    },
                    "toRevision": {
                        "type": "number",
                        "description": "Revision to roll back to (for history subcommand)"
                    },
                    "timeout": {
                        "type": "string",
                        "description": "The length of time to wait before giving up (e.g., '30s', '1m', '2m30s')"
                    },
                    "watch": {
                        "type": "boolean",
                        "description": "Watch the rollout status in real-time until completion"
                    }
                },
                "required": ["subCommand", "resourceType", "name"]
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
        },
        {
            "name": "prometheus_get_node_cpu",
            "description": "Get current CPU usage for all nodes from Prometheus",
            "parameters": {
                "type": "object",
                "properties": {
                    "rate_window": {
                        "type": "string",
                        "description": "Time window for rate calculation (e.g., '1m', '5m', '30s')",
                        "default": "1m"
                    }
                },
                "required": []
            }
        },
        {
            "name": "prometheus_get_node_memory",
            "description": "Get current memory usage for all nodes from Prometheus",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "prometheus_get_pod_cpu",
            "description": "Get current CPU usage for pods from Prometheus",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {
                        "type": "string",
                        "description": "Specific namespace to filter pods (optional, defaults to all namespaces)"
                    },
                    "rate_window": {
                        "type": "string",
                        "description": "Time window for rate calculation (e.g., '1m', '5m', '30s')",
                        "default": "1m"
                    }
                },
                "required": []
            }
        },
        {
            "name": "prometheus_get_pod_memory",
            "description": "Get current memory usage for pods from Prometheus",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {
                        "type": "string",
                        "description": "Specific namespace to filter pods (optional, defaults to all namespaces)"
                    }
                },
                "required": []
            }
        },
        {
            "name": "prometheus_get_istio_latency",
            "description": "Get current Istio service latency metrics from Prometheus",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {
                        "type": "string",
                        "description": "Specific namespace to filter services (optional, defaults to all namespaces)"
                    },
                    "percentile": {
                        "type": "string",
                        "description": "Latency percentile to query (e.g., '0.95', '0.99', '0.50')",
                        "default": "0.95"
                    },
                    "rate_window": {
                        "type": "string",
                        "description": "Time window for rate calculation (e.g., '1m', '5m', '30s')",
                        "default": "1m"
                    }
                },
                "required": []
            }
        },
        {
            "name": "prometheus_get_metrics_summary",
            "description": "Get a comprehensive summary of all current metrics (CPU, memory, latency) from Prometheus",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {
                        "type": "string",
                        "description": "Specific namespace to filter metrics (optional, defaults to all namespaces)"
                    }
                },
                "required": []
            }
        }
    ]

def get_system_prompt() -> str:
    """Get the system prompt for the AI agent."""
    return SYSTEM_PROMPT