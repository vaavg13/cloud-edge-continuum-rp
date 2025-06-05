from typing import Dict, Any
import json


def get_service_graph_function_schema() -> Dict[str, Any]:
    """Return the OpenAI function schema for generating the overall service graph structure."""
    return {
        "name": "define_service_graph",
        "description": "Define the overall service call graph structure for all microservices",
        "parameters": {
            "type": "object",
            "properties": {
                "services": {
                    "type": "array",
                    "description": "List of all services with their call relationships",
                    "items": {
                        "type": "object",
                        "properties": {
                            "service_name": {"type": "string", "description": "Name of the service"},
                            "type_or_role": {"type": "string", "description": "Type of service"},
                            "deployment_zones": {
                                "type": "array", 
                                "items": {"type": "string"}, 
                                "description": "List of zones where this service should be deployed. If the service is an ingress, it should be deployed to all edge sites."
                            },
                            "external_services": {
                                "type": "array",
                                "description": "List of external service call patterns. Propability distributions for different services should sum to 1.0",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "seq_len": {"type": "integer", "description": "Depth of service calls"},
                                        "services": {"type": "array", "items": {"type": "string"}, "description": "List of downstream services to call. If the service is terminal list should be empty"},
                                        "probabilities": {
                                            "type": "object",
                                            "properties": {
                                                "service_name": {"type": "string", "description": "Name of the service"},
                                                "probability": {"type": "number", "minimum": 0, "maximum": 1, "description": "Probability of the service call"}
                                            },
                                            "description": "probability distribution for service calls (service_name: probability).",
                                            "required": ["service_name", "probability"]
                                        }
                                    },
                                    "required": ["seq_len", "services", "probabilities"]
                                }
                            }
                        },
                        "required": ["service_name", "service_type", "deployment_zones", "external_services"]
                    }
                }
            },
            "required": ["services"]
        }
    }

def generate_service_graph_prompt(config: Dict[str, Any]) -> str:
    """Generate prompt for creating the overall service call graph structure."""
    service_names = [f"{config['service_prefix']}{i}" for i in range(config['num_services'])]
    
    prompt = f"""Generate service call graph for microservice emulator.
        
        **Rules:**
        - Create DAG (no cycles)
        - ALL services must be reachable from {config['ingress_service_name']}
        - Ingress must call other services
        - Terminal services have empty external_services list. '[]'

        **Service Types & Deployment:**
        Unless otherwise specified do the following:
        - **ingress**: {config['ingress_service_name']} → deploy to all edge sites
        - **edge**: lightweight services → deploy to specific edge sites  
        - **cloud**: moderate services → deploy to cloud
        - **backend**: heavy services → deploy to cloud (terminal nodes)

        **Deployment zones must be:**
        - Edge sites: {config['edge_sites_list']}
        - Cloud: ["{config['cloud_site_name']}"]

        Generate connected graph for all {config['num_services']} services.
    """
    return prompt


def generate_service_prompt_with_graph(
    service_index: int, 
    config: Dict[str, Any], 
    service_graph_info: Dict[str, Any]
) -> str:
    service_name = f"{config['service_prefix']}{service_index}"
    service_names = [f"{config['service_prefix']}{i}" for i in range(config['num_services'])]
    
    

    prompt = f"""Generate configuration for {service_name} in microservice emulator.
        **All services:** {', '.join(service_names)}
        **Service type:** {service_graph_info.get('service_type', 'unknown')}
        **Deploy to zones:** {service_graph_info.get('deployment_zones', [])}
        **External calls:** {service_graph_info.get('external_services', [])}
        **Service Configuration:**
        {json.dumps(service_graph_info, indent=2)}
        
        **Instructions:**
        - For external_services, always include 'probabilities' and ensure they sum to 1.0.
        - For s0, set seq_len to 100
        - This configuration is for a microservice emulator. Try to make realistic configurations of microservices
        according to the description of the application the service type and the stressors that are available.
        - If the service is a terminal service, set the external_services list to empty. '[]'
        - If the service is an ingress, set the deployment_zones list to all edge sites.
        - If the service is an edge service, set the deployment_zones list to the edge sites that are available. ['edge-site-1', 'edge-site-2', 'edge-site-3']
        - If the service is a cloud service, set the deployment_zones list to the cloud site. ['cloud']
        - If the service is a backend service, set the deployment_zones list to the cloud site. ['cloud']
        - If the service is a backend service, set the external_services list to empty. '[]'
    """
    return prompt

def get_microservice_function_schema() -> Dict[str, Any]:
    """Return the OpenAI function schema for defining microservices. Updated to match human-generated workmodel.json."""
    # All properties and required fields
    properties = {
        "service_name": {"type": "string", "description": "Name of the service (e.g., s0, s1)"},
        "function_id": {"type": "string", "description": "Function identifier (always 'f1')"},
        "external_services": {
            "type": "array",
            "description": "List of external service call patterns (must always include 'probabilities')",
            "items": {
                "type": "object",
                "properties": {
                    "seq_len": {"type": "integer", "description": "Depth of service calls (100 for s0, 1 for others)"},
                    "services": {"type": "array", "items": {"type": "string"}, "description": "List of downstream services to call"},
                    "probabilities": {
                        "type": "object",
                        "properties": {
                            "service_name": {"type": "string", "description": "Name of the service"},
                            "probability": {"type": "number", "minimum": 0, "maximum": 1, "description": "Probability of the service call"}
                        },
                        "description": "probability distribution for service calls (service_name: probability).",
                        "required": ["service_name", "probability"]
                    }
                },
                "required": ["seq_len", "services", "probabilities"]
            }
        },
        "cpu_stress_run": {"type": "boolean", "description": "Whether to run CPU stress"},
        "cpu_range_complexity": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2, "description": "[min, max] ditits of Pi to compute (core logic) always between 10 and 1500"},
        "cpu_thread_pool_size": {"type": "integer", "description": "CPU thread pool size, duplicates core computing logic to a number of threads. It dos not make faster the core logic."},
        "cpu_trials": {"type": "integer", "description": "Number of CPU trials. It is the number of times the core logic is executed."},
        "memory_stress_run": {"type": "boolean", "description": "Whether to run memory stress"},
        "memory_size": {"type": "integer", "description": "write random memory_size mbs memory_io times to RAM"},
        "memory_io": {"type": "integer", "description": "Memory I/O operations. It is the number of times the memory is written to."},
        "disk_stress_run": {"type": "boolean", "description": "Whether to run disk stress"},
        "disk_tmp_file_name": {"type": "string", "description": "Temporary file name for disk stress"},
        "disk_write_block_count": {"type": "integer", "description": "Number of blocks to write"},
        "disk_write_block_size": {"type": "integer", "description": "Block size in bytes"},
        "sleep_stress_run": {"type": "boolean", "description": "Whether to run sleep stress, should be used only if asked by the user"},
        "sleep_time": {"type": "number", "description": "Sleep time in seconds, if asked by the user set to amounts between 0.001 and 0.1"},
        "mean_response_size": {"type": "integer", "description": "Mean response size in bytes (30, 40, 50, 100 etc.) not more than 300"},
        "request_method": {"type": "string", "description": "Request method (always 'rest')"},
        "workers": {"type": "integer", "description": "Number of workers (always 4)"},
        "threads": {"type": "integer", "description": "Number of threads (always 16)"},
        "deployments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "deployment_name_suffix": {"type": "string", "description": "Deployment name suffix (e.g., edge-site-1, cloud)"},
                    "node_affinity_zone": {"type": "string", "description": "Node affinity zone"},
                    "cpu_requests": {"type": "string", "description": "CPU requests (100m or 150m)"},
                    "memory_requests": {"type": "string", "description": "Memory requests (128Mi or 160Mi)"},
                    "cpu_limits": {"type": "string", "description": "CPU limits (200m or 300m)"},
                    "memory_limits": {"type": "string", "description": "Memory limits (256Mi)"},
                    "autoscaling_enabled": {"type": "boolean", "description": "Whether autoscaling is enabled (always true)"},
                    "autoscaling_min": {"type": "integer", "description": "Minimum replicas (2 for s0, 1 for others) unless otherwise specified"},
                    "autoscaling_max": {"type": "integer", "description": "Maximum replicas depends on the service type and the stressors specified"},
                    "autoscaling_metric": {"type": "string", "description": "Autoscaling metric (always 'cpu') unless otherwise specified"},
                    "autoscaling_target": {"type": "integer", "description": "Autoscaling target value (always 60) unless otherwise specified"}
                },
                "required": ["deployment_name_suffix", "node_affinity_zone", "cpu_requests", "memory_requests", "cpu_limits", "memory_limits", "autoscaling_enabled", "autoscaling_min", "autoscaling_max", "autoscaling_metric", "autoscaling_target"]
            }
        }
    }
    required = list(properties.keys())
    return {
        "name": "define_microservice",
        "description": "Define parameters for a microservice in the mesh. All fields are required and must match the following values unless otherwise specified:",
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required
        }
    }