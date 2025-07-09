import json
import openai
import time
import logging
from typing import List, Dict, Any, Optional
import asyncio
from promtpt_and_scemas import (
    generate_service_graph_prompt, 
    generate_service_prompt_with_graph, 
    get_microservice_function_schema,
    get_service_graph_function_schema
)

# Service Graph Generation
async def generate_service_graph(
    config: Dict[str, Any],
    client: openai.AsyncOpenAI,
    model: str = "gpt-4"
) -> Optional[Dict[str, Any]]:
    """Generate the overall service call graph structure."""
    prompt = generate_service_graph_prompt(config)
    
    try:
        start_time = time.time()
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            functions=[get_service_graph_function_schema()],
            function_call={"name": "define_service_graph"}
        )
        elapsed = time.time() - start_time
        logging.info(f"Service graph generation took {elapsed:.2f} seconds")
        
        message = response.choices[0].message
        
        if not message.function_call:
            print("No function call returned for service graph.")
            return None
            
        try:
            function_args = json.loads(message.function_call.arguments)
            services_count = len(function_args.get('services', []))
            print(f"Generated service graph with {services_count} services")
            
            # Validate that all expected services are present
            expected_services = {f"{config['service_prefix']}{i}" for i in range(config['num_services'])}
            actual_services = {s['service_name'] for s in function_args.get('services', [])}
            
            if actual_services != expected_services:
                missing = expected_services - actual_services
                extra = actual_services - expected_services
                print(f"Warning: Service mismatch. Missing: {missing}, Extra: {extra}")
            
            return function_args
            
        except json.JSONDecodeError as e:
            print(f"Failed to parse service graph function arguments: {e}")
            return None
            
    except Exception as e:
        print(f"Error generating service graph: {e}")
        return None

def validate_service_connectivity(services_graph_info: Dict[str, Dict], config: Dict[str, Any]):
    """Validate that all services are connected and reachable from ingress."""
    ingress_service = config['ingress_service_name']
    
    # Build adjacency list
    adjacency = {}
    for service_name, service_info in services_graph_info.items():
        adjacency[service_name] = []
        for ext_service in service_info.get('external_services', []):
            adjacency[service_name].extend(ext_service.get('services', []))
    
    # BFS to find reachable services from ingress
    visited = set()
    queue = [ingress_service]
    visited.add(ingress_service)
    
    while queue:
        current = queue.pop(0)
        for neighbor in adjacency.get(current, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    
    # Check for unreachable services
    all_services = set(services_graph_info.keys())
    unreachable = all_services - visited
    
    if unreachable:
        print(f"Warning: Services not reachable from ingress: {unreachable}")
    else:
        print("✓ All services are reachable from ingress") 

# Service configuration generation
async def call_openai_for_service_with_graph(
    service_index: int,
    config: Dict[str, Any],
    service_graph_info: Dict[str, Any],
    client: openai.AsyncOpenAI,
    model: str = "gpt-4"
) -> Optional[Dict[str, Any]]:
    """Call OpenAI to generate a single service definition using pre-defined graph."""
    service_name = f"{config['service_prefix']}{service_index}"
    prompt = generate_service_prompt_with_graph(service_index, config, service_graph_info)
    
    try:
        start_time = time.time()
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            functions=[get_microservice_function_schema()],
            function_call={"name": "define_microservice"}
        )
        elapsed = time.time() - start_time
        logging.info(f"OpenAI call for {service_name} took {elapsed:.2f} seconds")
        
        message = response.choices[0].message
        
        if not message.function_call:
            print(f"No function call returned for service {service_name}.")
            return None
            
        try:
            function_args = json.loads(message.function_call.arguments)
            print(f"Generated service: {service_name}")
            return function_args
            
        except json.JSONDecodeError as e:
            print(f"Failed to parse function arguments for {service_name}: {e}")
            return None
            
    except Exception as e:
        print(f"Error generating service {service_name}: {e}")
        return None

# Generate All Services
async def generate_all_services(
    config: Dict[str, Any],
    client: openai.AsyncOpenAI,
    model: str = "gpt-4",
    semaphore_limit: int = 10
) -> List[Dict[str, Any]]:
    """Generate all services using the optimized two-phase async approach."""
    # Phase 1: Generate the service graph structure
    print("Phase 1: Generating service call graph...")
    service_graph = await generate_service_graph(config, client, model)
    
    if not service_graph or 'services' not in service_graph:
        raise Exception("Failed to generate service graph")
    
    services_graph_info = {s['service_name']: s for s in service_graph['services']}
    
    # Validate connectivity
    validate_service_connectivity(services_graph_info, config)
    
    # Phase 2: Generate all services in parallel with semaphore
    print(f"Phase 2: Generating {len(service_graph['services'])} services in parallel...")
    
    semaphore = asyncio.Semaphore(semaphore_limit)
    
    async def generate_single_service_with_semaphore(service_index: int) -> Optional[tuple]:
        async with semaphore:
            service_name = f"{config['service_prefix']}{service_index}"
            if service_name not in services_graph_info:
                print(f"Warning: {service_name} not found in service graph")
                return None
            
            service_params = await call_openai_for_service_with_graph(
                service_index, 
                config, 
                services_graph_info[service_name], 
                client, 
                model
            )
            return (service_index, service_params) if service_params else None
    
    start_time = time.time()
    
    # Create all tasks
    tasks = [
        generate_single_service_with_semaphore(i) 
        for i in range(config['num_services'])
    ]
    
    # Execute all tasks concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    elapsed = time.time() - start_time
    print(f"Parallel service generation completed in {elapsed:.2f} seconds")
    
    # Process results
    all_services = []
    for result in results:
        if isinstance(result, Exception):
            print(f"Error in async task: {result}")
        elif result is not None:
            all_services.append(result)
    
    # Sort services by original index and return just the service params
    all_services.sort(key=lambda x: x[0])
    return [service_params for _, service_params in all_services]