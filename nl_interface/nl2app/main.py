#!/usr/bin/env python3
"""
Main entry point for generating microservice workmodel JSON using OpenAI function calling.
"""

import json
import openai
import asyncio
from typing import Dict, Any
from workmodel_prompt_template import generate_workmodel_json
import logging

# logging.basicConfig(level=logging.INFO)
# logging.getLogger("openai").setLevel(logging.INFO)

openai_key = ()

def create_sample_config() -> Dict[str, Any]:
    """Create a sample configuration for testing."""
    return {
        "num_services": 7,
        "service_prefix": "s",
        "edge_sites_list": ["edge-site-1", "edge-site-2"],
        "cloud_site_name": "cloud",
        "app_profile": "iot_data_processing",  # or "real_time_gaming", "cdn_delivery"
        "ingress_service_name": "s0",
        "default_request_method": "rest",
        "default_image": "msvcbench/microservice_v6-screen:1.0",
        "default_namespace": "default",
        "default_api_path": "/api/v1"
    }

async def main_async():
    """Async main function to generate workmodel JSON."""
    # Configuration
    config = create_sample_config()
    
    try:
        client = openai.AsyncOpenAI(api_key=openai_key)
    except Exception as e:
        print(f"Error initializing OpenAI client: {e}")
        print("Make sure to set your OPENAI_API_KEY environment variable")
        return
    
    print(f"Generating workmodel for {config['num_services']} services...")
    print(f"Application profile: {config['app_profile']}")
    print(f"Edge sites: {config['edge_sites_list']}")
    print(f"Cloud site: {config['cloud_site_name']}")
    print()
    
    # Generate the workmodel JSON using async function
    workmodel_json = await generate_workmodel_json(
        config, 
        client, 
        model="gpt-4.1", 
        semaphore_limit=10
    )
    
    # Parse and pretty print the result
    try:
        workmodel_dict = json.loads(workmodel_json)
        
        if "error" in workmodel_dict:
            print(f"Error generating workmodel: {workmodel_dict['error']}")
        else:
            output_file = f"workmodel.json"
            with open(output_file, 'w') as f:
                json.dump(workmodel_dict, f, indent=2)
            print(f"\nSaved to: {output_file}")
            
    except json.JSONDecodeError as e:
        print(f"Failed to parse generated JSON: {e}")
        print("Raw output:")
        print(workmodel_json)

def main():
    """Synchronous wrapper for the async main function."""
    asyncio.run(main_async())

if __name__ == "__main__":
    main() 