#!/usr/bin/env python3
"""
Script to generate a workmodel using both ServiceGraphGenerator and WorkModelGenerator.
"""

import json
import os
from ServiceGraphGenerator import ServiceGraphGenerator
from WorkModelGenerator import WorkModelGenerator

# Read configurations
with open("../Configs/ServiceGraphParameters.json") as f:
    service_graph_config = json.load(f)

with open("../Configs/WorkModelParameters.json") as f:
    workmodel_config = json.load(f)

# Extract parameters
graph_params = service_graph_config["ServiceGraphParameters"]
output_path = workmodel_config["WorkModelParameters"].get("OutputPath", {}).get("value", "SimulationWorkspace")
output_file = workmodel_config["WorkModelParameters"].get("OutputFile", {}).get("value", "workmodel.json")

# Create output directory if it doesn't exist
os.makedirs(output_path, exist_ok=True)

# Generate service graph
graph_generator = ServiceGraphGenerator()
service_graph = graph_generator.generate_service_graph(graph_params)

# Generate work model
workmodel_generator = WorkModelGenerator(
    request_method=workmodel_config["WorkModelParameters"].get("request_method", {}).get("value", "rest"),
    databases_prefix=workmodel_config["WorkModelParameters"].get("databases_prefix", {}).get("value", "sdb")
)
work_model = workmodel_generator.generate_work_model(service_graph, workmodel_config["WorkModelParameters"])

# Save the final workmodel
with open(f"{output_path}/{output_file}", "w") as f:
    json.dump(work_model, f, indent=2)

print(f"Work model generated successfully!")
print(f"File saved as: {output_path}/{output_file}") 