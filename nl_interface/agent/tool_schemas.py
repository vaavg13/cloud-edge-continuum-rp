#!/usr/bin/env python3
"""
Tool Schemas for OpenAI Function Calling
Defines all available operations that an AI agent can perform through MCP and other utilities.
"""

from typing import List, Dict, Any



def get_kubernetes_function_schemas() -> List[Dict[str, Any]]:
    """
    Get all available function schemas for OpenAI function calling.
    These define what operations the AI agent can perform on the Kubernetes cluster and utilities.
    """
    return [
        {
            "name": "create_action_plan",
            "description": "Create a detailed step-by-step action plan before executing operations. Use this FIRST to establish a systematic approach.",
            "parameters": {
                "type": "object",
                "properties": {
                    "objective": {
                        "type": "string",
                        "description": "Clear description of what you want to accomplish"
                    },
                    "current_situation": {
                        "type": "string", 
                        "description": "Current state/context that triggered this planning session"
                    },
                    "steps": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of specific steps to take, in order"
                    },
                    "expected_outcome": {
                        "type": "string",
                        "description": "What you expect to achieve after completing all steps"
                    },
                    "risks_considerations": {
                        "type": "array",
                        "items": {"type": "string"}, 
                        "description": "Potential risks or important considerations to keep in mind"
                    }
                },
                "required": ["objective", "current_situation", "steps"]
            }
        },
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
            "description": "Patch a Kubernetes resource with specific changes. CRITICAL: patchData must be a JSON object, never a string.",
            "parameters": {
                "type": "object",
                "properties": {
                    "resourceType": {
                        "type": "string",
                        "description": "Type of resource to patch (e.g., 'deployment', 'hpa', 'service')"
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
                        "description": "Type of patch: 'strategic' (default, best for deployments), 'merge' (JSON merge), or 'json' (JSON patch operations)"
                    },
                    "patchData": {
                        "type": "object",
                        "description": "CRITICAL: Must be a JSON object (not string). For deployment resource updates, use: {\"spec\": {\"template\": {\"spec\": {\"containers\": [{\"name\": \"container-name\", \"resources\": {\"requests\": {\"cpu\": \"500m\"}, \"limits\": {\"cpu\": \"1000m\"}}}]}}}}. For HPA updates, use: {\"spec\": {\"maxReplicas\": 10}}. Always verify container names match the deployment spec."
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
            "name": "kubectl_drain",
            "description": "Drain a Kubernetes node by safely evicting all pods and marking the node as unschedulable",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_name": {
                        "type": "string",
                        "description": "Name of the node to drain"
                    },
                    "ignore_daemonsets": {
                        "type": "boolean",
                        "description": "Ignore DaemonSet-managed pods (usually required for successful drain)",
                        "default": True
                    },
                    "delete_emptydir_data": {
                        "type": "boolean",
                        "description": "Continue even if there are pods using emptyDir volumes",
                        "default": False
                    },
                    "force": {
                        "type": "boolean",
                        "description": "Continue even if there are pods not managed by a controller",
                        "default": False
                    },
                    "grace_period": {
                        "type": "integer",
                        "description": "Period of time in seconds given to each pod to terminate gracefully (default: 30)",
                        "default": 30
                    },
                    "timeout": {
                        "type": "string",
                        "description": "The length of time to wait before giving up (e.g., '5m', '10m')",
                        "default": "0s"
                    },
                    "disable_eviction": {
                        "type": "boolean",
                        "description": "Force drain to use delete instead of evict API",
                        "default": False
                    }
                },
                "required": ["node_name"]
            }
        },
        {
            "name": "kubectl_cordon",
            "description": "Mark a Kubernetes node as unschedulable (prevents new pods from being scheduled)",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_name": {
                        "type": "string",
                        "description": "Name of the node to cordon"
                    }
                },
                "required": ["node_name"]
            }
        },
        {
            "name": "kubectl_uncordon",
            "description": "Mark a Kubernetes node as schedulable (allows new pods to be scheduled)",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_name": {
                        "type": "string",
                        "description": "Name of the node to uncordon"
                    }
                },
                "required": ["node_name"]
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
            "name": "prometheus_get_timeseries",
            "description": "Get historical time series for pods/services with optimized settings (5s intervals, 2m max duration). Returns concise, human-readable format to minimize token usage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric_type": {
                        "type": "string",
                        "description": "Type of metric to retrieve",
                        "enum": ["cpu", "memory", "latency"]
                    },
                    "namespace": {
                        "type": "string",
                        "description": "Target namespace to filter metrics (required for focused analysis)"
                    },
                    "duration": {
                        "type": "string",
                        "description": "Time range to query backwards from now (e.g., '2m', '1m', '30s'). Maximum: 2m.",
                        "default": "2m"
                    }
                },
                "required": ["metric_type", "namespace"]
            }
        },
        {
            "name": "prometheus_get_node_timeseries",
            "description": "Get historical node-level metrics with optimized settings (5s intervals, 2m max duration). Returns concise, human-readable format to minimize token usage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric_type": {
                        "type": "string",
                        "description": "Type of node metric to retrieve",
                        "enum": ["cpu", "memory"]
                    },
                    "duration": {
                        "type": "string",
                        "description": "Time range to query backwards from now (e.g., '2m', '1m', '30s'). Maximum: 2m.",
                        "default": "2m"
                    }
                },
                "required": ["metric_type"]
            }
        },
        {
            "name": "prometheus_get_service_topology",
            "description": "Get service topology and communication patterns from Istio metrics. Shows which services communicate with each other, request volumes, critical dependencies, and service criticality analysis to help understand impact of failures and guide remediation priorities.",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {
                        "type": "string",
                        "description": "Target namespace to analyze topology for (optional - defaults to all namespaces)"
                    },
                    "time_window": {
                        "type": "string",
                        "description": "Time window for analyzing request patterns (e.g., '5m', '10m'). Default: 5m",
                        "default": "5m"
                    }
                },
                "required": []
            }
        },
        {
            "name": "generate_operational_summary",
            "description": "Generate final structured operational report",
            "parameters": {
                "type": "object",
                "properties": {
                    "objective": {
                        "type": "string",
                        "description": "Objective of the operation"
                    },
                    "actions_completed": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of actions completed"
                    },
                    "results_achieved": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of results achieved"
                    },
                    "status": {
                        "type": "string",
                        "description": "Status of the operation"
                    },
                    "problem_location": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "description": "Name of the resource where the problem occurred"
                                },
                                "type": {
                                    "type": "string",
                                    "description": "Type of Kubernetes resource",
                                    "enum": ["deployment", "pod", "node", "service"]
                                }
                            },
                            "required": ["name", "type"]
                        },
                        "description": "List of resources where problems occurred. If empty, indicates no fault was detected."
                    },
                    "success": {
                        "type": "boolean",
                        "description": "Whether the problem was successfully resolved (true) or not (false)"
                    }
                },
                "required": ["objective", "actions_completed", "results_achieved", "status", "success"]
            }
        }
    ]
