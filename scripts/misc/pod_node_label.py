import subprocess
import json
from tabulate import tabulate

namespace = "monitoring"

# Get all pods in the namespace
pods_json = subprocess.check_output(
    ["kubectl", "get", "pods", "-n", namespace, "-o", "json"]
)
pods = json.loads(pods_json)

# Get all nodes
nodes_json = subprocess.check_output(
    ["kubectl", "get", "nodes", "-o", "json"]
)
nodes = json.loads(nodes_json)

# Build node -> zone map using labels
node_zone_map = {}
for node in nodes["items"]:
    name = node["metadata"]["name"]
    labels = node["metadata"]["labels"]
    
    # Match any key that contains "zone"
    zone = next(
        (v for k, v in labels.items() if "zone" in k and "topology" in k),
        "Unknown"
    )
    node_zone_map[name] = zone

# Build final output table
rows = []
for pod in pods["items"]:
    pod_name = pod["metadata"]["name"]
    node_name = pod["spec"].get("nodeName", "NotScheduled")
    zone = node_zone_map.get(node_name, "Unknown")
    rows.append([pod_name, node_name, zone])

# Display table
print(tabulate(rows, headers=["POD", "NODE", "ZONE"], tablefmt="grid"))
