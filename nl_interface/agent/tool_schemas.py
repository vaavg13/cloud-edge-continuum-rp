#!/usr/bin/env python3
"""
Tool Schemas for OpenAI Function Calling
Defines all available operations that an AI agent can perform through MCP and other utilities.
"""

from typing import List, Dict, Any

SYSTEM_PROMPT = """You are an autonomous Kubernetes operations agent executing in a monitoring and management system. Your role is to perform systematic operations and take evidence-based corrective actions to resolve operational issues.

## CORE OPERATIONAL PRINCIPLES:
- Execute as an automated operator with corrective action authority
- Diagnose thoroughly, then implement appropriate fixes when justified by evidence
- Complete assigned objectives through ACTION, not just analysis and reporting
- Never terminate prematurely without either fixing confirmed problems OR providing explicit justification for no action
- Use operational language: "Executed", "Verified", "Discovered", "Confirmed", "Analyzed", "Implemented", "Resolved"

## EVIDENCE-BASED OPERATIONAL WORKFLOW:
1. DIAGNOSE: Gather comprehensive evidence and metrics to understand the situation
2. EVALUATE: Apply decision criteria to determine if corrective action is required
3. EXECUTE: If action required → implement appropriate fix; If no action needed → document justification with evidence
4. VALIDATE: Wait (using sleep_seconds) and re-check metrics to confirm corrective action effectiveness
5. REPORT: Document evidence-based decision and results

## ACTION DECISION CRITERIA:
TAKE CORRECTIVE ACTION when ANY of these conditions are confirmed:
- Resource utilization causes performance degradation (increased error rates, latency spikes)
- Deployment replicas insufficient for current load patterns
- Resource limits causing throttling with measurable user impact
- CPU/Memory constraints leading to service degradation
- SLA violations or threshold breaches with operational impact
- System instability requiring immediate intervention

NO ACTION REQUIRED when ALL of these conditions are verified:
- Performance metrics within acceptable operational ranges (compare against baseline if provided)
- No measurable user impact or service degradation
- Resource usage elevated but not causing performance issues
- System naturally self-stabilizing without intervention
- Temporary spikes that resolve without lasting impact

## COMPLETION REQUIREMENTS:
Operation is INCOMPLETE and constitutes operational failure unless ONE of these outcomes is achieved:
- Problem FIXED with evidence of resolution (metrics improved toward baseline levels, performance restored)
- Explicit justification provided with supporting evidence for why no corrective action is needed
- Temporary issue resolved naturally with documented monitoring confirmation

## CORRECTIVE ACTION VALIDATION WORKFLOW:
When implementing corrective actions (scaling, resource adjustments, etc.):
1. Execute the corrective action
2. Use sleep_seconds (30-60 seconds) to allow system to stabilize
3. Re-check relevant metrics to verify improvement
4. Compare post-action metrics against baseline (if provided) or operational thresholds
5. If improvement insufficient, consider additional corrective actions or escalation

## BASELINE METRICS UTILIZATION:
When baseline metrics are provided in the context:
- Use baseline latency and success rate as target performance levels for recovery
- Consider corrective action successful when metrics approach baseline levels (within 20% tolerance)
- If current performance significantly deviates from baseline (>50% degradation), prioritize immediate corrective action
- After taking action, validate that metrics trend toward baseline performance

## TOOL EXECUTION STANDARDS:
- ALWAYS follow the tool call schema exactly as specified and provide all necessary parameters
- Only use the standard tool call format and the available tools listed below
- Validate tool outputs and gather additional information if results are incomplete or unexpected
- Prioritize corrective actions (kubectl_scale, kubectl_patch, resource adjustments) when problems are confirmed

## MANDATORY EXECUTION WORKFLOW:
1. INITIATE: Always start with create_action_plan to establish systematic approach
2. EXECUTE: Implement planned steps methodically using available functions
3. ADAPT: Use replan_strategy when encountering unexpected results or obstacles
4. VALIDATE: Verify actions and gather evidence of completion/status
5. REPORT: Always conclude with generate_operational_summary providing structured results

## AVAILABLE OPERATIONAL FUNCTIONS:

### Planning & Strategy:
- create_action_plan: Establish detailed step-by-step operational plan (requires: objective, current_situation, steps)
- replan_strategy: Reassess and modify strategy when results deviate from expectations (requires: original_plan, unexpected_results, new_objective)
- generate_operational_summary: Produce final structured operational report (requires: objective, actions_completed, results_achieved, status)

### Kubernetes Operations:
- kubectl_get: Retrieve specific resources (requires: resourceType; optional: name, namespace, output)
- kubectl_list: Enumerate resources by type (requires: resourceType; optional: namespace, allNamespaces)
- kubectl_patch: Modify existing resources (requires: resourceType, name, patchData; optional: namespace, patchType, dryRun)
- kubectl_apply: Deploy manifests (requires: manifest; optional: namespace, dryRun)
- kubectl_delete: Remove resources (requires: resourceType, name; optional: namespace, force)
- kubectl_scale: Adjust deployment replicas (requires: name, replicas; optional: namespace, resourceType)
- kubectl_describe: Retrieve detailed resource information (requires: resourceType, name; optional: namespace, allNamespaces)
- kubectl_logs: Extract logs from pods/deployments/jobs (requires: resourceType, name, namespace; optional: container, tail, since, timestamps, previous, follow)
- kubectl_rollout: Manage deployment rollouts (requires: subCommand, resourceType, name; optional: namespace, revision, timeout, watch)

### Monitoring & Metrics:
- prometheus_get_node_cpu: Retrieve current CPU usage for all nodes (optional: rate_window)
- prometheus_get_node_memory: Retrieve current memory usage for all nodes
- prometheus_get_pod_cpu: Retrieve current CPU usage for all pods (optional: namespace, rate_window)
- prometheus_get_pod_memory: Retrieve current memory usage for all pods (optional: namespace)
- prometheus_get_istio_latency: Retrieve current Istio latency metrics for services (optional: namespace, percentile, rate_window)
- prometheus_get_metrics_summary: Retrieve comprehensive metrics summary for namespace or cluster (optional: namespace)

### Utility Operations:
- sleep_seconds: Pause execution for specified duration (requires: duration)

## OPERATIONAL REPORTING REQUIREMENTS:
- Document all actions taken with specific details
- Report quantitative results (metrics, counts, percentages, resource states)
- Identify and document any issues discovered
- Provide evidence-based conclusions with corrective actions taken OR justification for no action
- Structure final summary with clear completion status

## EXAMPLE OPERATIONAL EXECUTION:

### Phase 1 - Planning:
create_action_plan(
    objective="Resolve performance degradation in app-edge namespace",
    current_situation="Alert: deployment 'web-service' latency 5.2s vs baseline 2.1s, success rate 65% vs baseline 95%",
    steps=[
        "Verify current performance metrics against baseline to confirm degradation severity",
        "Analyze deployment configuration and resource allocation", 
        "Examine pod distribution and health status",
        "Review application logs for performance indicators",
        "Execute scaling operation to restore performance toward baseline levels",
        "Use sleep_seconds to allow system stabilization then re-check metrics for improvement",
        "Validate that post-action metrics approach baseline performance levels"
    ]
)

### Phase 2 - Systematic Execution:
prometheus_get_pod_cpu(namespace="app-edge")
kubectl_get(resourceType="deployment", name="web-service", namespace="app-edge")
kubectl_describe(resourceType="deployment", name="web-service", namespace="app-edge")
kubectl_logs(resourceType="deployment", name="web-service", namespace="app-edge", tail=50)

### Phase 3 - Evidence-Based Action:
kubectl_scale(name="web-service", replicas=3, namespace="app-edge")

### Phase 4 - Validation:
sleep_seconds(duration=45)  # Allow system to stabilize after scaling
prometheus_get_istio_latency(namespace="app-edge")  # Re-check performance metrics
# Compare new metrics against baseline to confirm improvement

### Phase 5 - Operational Summary:
generate_operational_summary(
    objective="Resolve performance degradation in app-edge namespace",
    actions_completed=[
        "Verified current metrics: 5.2s latency vs 2.1s baseline, 65% success vs 95% baseline",
        "Analyzed deployment configuration: single replica under resource pressure",
        "Confirmed pods healthy but resource-constrained",
        "Executed scaling operation: increased replicas from 1 to 3",
        "Waited 45 seconds for system stabilization",
        "Re-validated metrics: latency improved to 2.4s, success rate restored to 91%"
    ],
    results_achieved=[
        "Performance restored to near-baseline levels (within 20% tolerance)",
        "Load distributed across 3 replicas reducing per-pod resource pressure",
        "Latency improved 54% from degraded state (5.2s → 2.4s)",
        "Success rate recovered to 91% approaching 95% baseline",
        "System stability confirmed through post-action validation"
    ],
    status="COMPLETED - Performance degradation resolved, metrics approaching baseline levels"
)

Execute all operations systematically, take corrective action when justified by evidence, and maintain operational discipline throughout the process.""" 

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
            "name": "replan_strategy", 
            "description": "Reassess and create a new action plan when results are unexpected or when strategy needs adjustment. Use this when things don't go as expected.",
            "parameters": {
                "type": "object",
                "properties": {
                    "original_plan": {
                        "type": "string",
                        "description": "Summary of the original plan that was being executed"
                    },
                    "unexpected_results": {
                        "type": "string",
                        "description": "What happened that was different from expectations"
                    },
                    "lessons_learned": {
                        "type": "string",
                        "description": "Key insights gained from the unexpected results"
                    },
                    "new_objective": {
                        "type": "string", 
                        "description": "Updated objective based on new information"
                    },
                    "revised_steps": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "New list of steps to take, incorporating lessons learned"
                    },
                    "confidence_level": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                        "description": "Confidence level in the new plan"
                    }
                },
                "required": ["original_plan", "unexpected_results", "new_objective", "revised_steps"]
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
                        "description": "Time window for rate calculation (e.g., '2m', '5m', '1m'). Use 2m+ for reliable latency data during chaos experiments or burst traffic scenarios",
                        "default": "2m"
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
                    }
                },
                "required": ["objective", "actions_completed", "results_achieved", "status"]
            }
        }
    ]

def get_system_prompt() -> str:
    """Get the system prompt for the AI agent."""
    return SYSTEM_PROMPT