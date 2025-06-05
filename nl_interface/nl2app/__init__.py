"""
NL2App: Natural Language to Application Generator

This package provides tools for generating microservice workmodel JSON 
using OpenAI function calling.
"""

from .openai_function_schemas import (
    get_microservice_function_schema,
    generate_service_prompt,
    call_openai_for_service,
    generate_all_services_with_openai
)

from .workmodel_prompt_template import (
    format_service_json,
    generate_workmodel_json
)

__all__ = [
    'get_microservice_function_schema',
    'generate_service_prompt', 
    'call_openai_for_service',
    'generate_all_services_with_openai',
    'format_service_json',
    'generate_workmodel_json'
] 