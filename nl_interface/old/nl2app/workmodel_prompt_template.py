# workmodel_prompt_template.py

# This file defines JSON templates for generating microservice workmodel JSON.

import json
from typing import List, Dict, Any
from openai_function_schemas import generate_all_services
import logging
import openai

SERVICE_JSON_TEMPLATE = '''
  "{service_name}": {{
    "external_services": [
      {external_services_json_list}
    ],
    "internal_service": {{
      "loader": {{
        "cpu_stress": {{ "run": {cpu_stress_run}, "range_complexity": {cpu_range_complexity_json_list}, "thread_pool_size": {cpu_thread_pool_size}, "trials": {cpu_trials} }},
        "memory_stress": {{ "run": {memory_stress_run}, "memory_size": {memory_size}, "memory_io": {memory_io} }},
        "disk_stress": {{ "run": {disk_stress_run}, "tmp_file_name": "{disk_tmp_file_name}", "disk_write_block_count": {disk_write_block_count}, "disk_write_block_size": {disk_write_block_size} }},
        "sleep_stress": {{ "run": {sleep_stress_run}, "sleep_time": {sleep_time} }},
        "mean_response_size": {mean_response_size},
        "function_id": "{function_id}"
      }}
    }},
    "request_method": "{request_method}",
    "workers": {workers},
    "threads": {threads},
    "url": "{service_name}.{namespace}.svc.cluster.local",
    "path": "{path}",
    "image": "{image}",
    "namespace": "{namespace}",
    "deployments": [
      {deployments_json_list}
    ]
  }}
'''

EXTERNAL_SERVICE_TEMPLATE = '''{{ "seq_len": {seq_len}, "services": {services_json_list}{probabilities_json_str} }}'''

DEPLOYMENT_ENTRY_TEMPLATE = '''
      {{
        "name": "{deployment_name}",
        "node_affinity": "topology.kubernetes.io/zone={node_affinity_zone}",
        "cpu-requests": "{cpu_requests}",
        "memory-requests": "{memory_requests}",
        "cpu-limits": "{cpu_limits}",
        "memory-limits": "{memory_limits}",
        "autoscaling": {{
          "enabled": {autoscaling_enabled},
          "min": {autoscaling_min},
          "max": {autoscaling_max},
          "metric": "{autoscaling_metric}",
          "target": {autoscaling_target}
        }}
      }}
'''

def format_service_json(params: Dict[str, Any], config: Dict[str, Any]) -> str:
    """Format service parameters into JSON template."""
    params_copy = params.copy()
    
    # Infer fields from config
    params_copy["image"] = config.get("default_image", "msvcbench/microservice_v6-screen:1.0")
    params_copy["namespace"] = config.get("default_namespace", "default")
    params_copy["path"] = config.get("default_api_path", "/api/v1")

    # Helper for safe get with warning
    def safe_get(key, default):
        if key not in params_copy:
            logging.warning(f"Key '{key}' missing in service '{params_copy.get('service_name', '?')}', using default: {default}")
        return params_copy.get(key, default)

    # Format external services with probabilities
    external_services_json = []
    for ext_service in params_copy.get("external_services", []):
        services_list = ext_service.get("services", [])
        seq_len = ext_service.get("seq_len", 1)
        services_json_list = json.dumps(services_list)
        probabilities = ext_service.get("probabilities", {})
        if probabilities and services_list:
            probabilities_json_str = f', "probabilities": {json.dumps(probabilities)}'
        else:
            probabilities_json_str = ""
        external_service_json = EXTERNAL_SERVICE_TEMPLATE.format(
            seq_len=seq_len,
            services_json_list=services_json_list,
            probabilities_json_str=probabilities_json_str
        )
        external_services_json.append(external_service_json)
    if not external_services_json:
        external_services_json = ['{ "seq_len": 1, "services": [] }']
    params_copy["external_services_json_list"] = ",\n      ".join(external_services_json)

    # Format deployments
    deployments_json = []
    for dep_param in params_copy.get("deployments", []):
        dep_param_copy = dep_param.copy()
        dep_param_copy["deployment_name"] = f"{params_copy['service_name']}-{dep_param_copy.get('deployment_name_suffix', 'default')}"
        dep_param_copy["autoscaling_enabled"] = str(dep_param_copy.get("autoscaling_enabled", True)).lower()
        deployments_json.append(DEPLOYMENT_ENTRY_TEMPLATE.format(**dep_param_copy))
    params_copy["deployments_json_list"] = ",\n      ".join(deployments_json)

    # Format boolean values and lists
    for key in ["cpu_stress_run", "memory_stress_run", "disk_stress_run", "sleep_stress_run"]:
        params_copy[key] = str(params_copy.get(key, False)).lower()

    # Use safe_get for all required keys in the template
    template_args = dict(
        service_name=safe_get("service_name", "unknown"),
        downstream_services_json_list=json.dumps(params_copy.get("downstream_services", [])),
        cpu_stress_run=safe_get("cpu_stress_run", False),
        cpu_range_complexity_json_list=json.dumps(params_copy.get("cpu_range_complexity", [0, 0])),
        cpu_thread_pool_size=safe_get("cpu_thread_pool_size", 1),
        cpu_trials=safe_get("cpu_trials", 1),
        memory_stress_run=safe_get("memory_stress_run", False),
        memory_size=safe_get("memory_size", 0),
        memory_io=safe_get("memory_io", 0),
        disk_stress_run=safe_get("disk_stress_run", False),
        disk_tmp_file_name=safe_get("disk_tmp_file_name", ""),
        disk_write_block_count=safe_get("disk_write_block_count", 0),
        disk_write_block_size=safe_get("disk_write_block_size", 0),
        sleep_stress_run=safe_get("sleep_stress_run", False),
        sleep_time=safe_get("sleep_time", 0),
        mean_response_size=safe_get("mean_response_size", 0),
        function_id=safe_get("function_id", "f0"),
        request_method=safe_get("request_method", "rest"),
        workers=safe_get("workers", 4),
        threads=safe_get("threads", 16),
        url=f"{params_copy.get('service_name', 'unknown')}.{params_copy['namespace']}.svc.cluster.local",
        path=params_copy["path"],
        image=params_copy["image"],
        namespace=params_copy["namespace"],
        deployments_json_list=params_copy["deployments_json_list"],
        external_services_json_list=params_copy["external_services_json_list"]
    )

    return SERVICE_JSON_TEMPLATE.format(**template_args)

async def generate_workmodel_json(
    config: Dict[str, Any],
    client: openai.AsyncOpenAI,
    model: str = "gpt-4",
    semaphore_limit: int = 10
) -> str:
    """Generate complete workmodel JSON using async OpenAI function calling."""
    
    # Get all service parameters from OpenAI using the optimized async approach
    all_services = await generate_all_services(config, client, model, semaphore_limit)
    
    if not all_services:
        return json.dumps({"error": "No services generated"})
    
    # Convert to JSON format
    all_services_json = []
    for service_params in all_services:
        service_json = format_service_json(service_params, config)
        all_services_json.append(service_json)
    
    full_json_string = "{\n" + ",\n".join(all_services_json) + "\n}"
    
    # Validate JSON
    try:
        json.loads(full_json_string)
        return full_json_string
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Generated invalid JSON: {e}", "output": full_json_string})