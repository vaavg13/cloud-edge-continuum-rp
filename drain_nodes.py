import random
import time
from kubernetes import client, config
from kubernetes.client.rest import ApiException

# Global settings
MIN_INTERVAL = 10  # minimum interval in seconds
MAX_INTERVAL = 20  # maximum interval in seconds
ZONE_LABEL_KEY = "zone"
ZONE_LABEL_VALUE = "edge"
IGNORE_DAEMONSETS = True  # whether to ignore DaemonSet pods during eviction

# Colors for output
RESET = '\033[0m'
RED = '\033[91m'
HEADER = '\033[95m'


# Keep track of cordoned nodes
cordoned_nodes = set()

# Load the Kubernetes config
config.load_kube_config()

# Create a CoreV1Api client
v1 = client.CoreV1Api()

# Function to get all nodes with a specific label
def get_nodes_by_label(label_key, label_value):
    try:
        # Retrieve all nodes
        nodes = v1.list_node().items
        # Filter nodes by label
        matching_nodes = [
            node.metadata.name for node in nodes 
            if node.metadata.labels.get(label_key) == label_value
        ]
        return matching_nodes
    except ApiException as e:
        print(f"Error retrieving nodes: {e}")
        return []

# Function to get the list of cordoned (unschedulable) nodes
def get_cordoned_nodes(nodes):
    try:
        cordoned = set()
        for node_name in nodes:
            node = v1.read_node(node_name)
            if node.spec.unschedulable:
                cordoned.add(node_name)
        return cordoned
    except ApiException as e:
        print(f"Error retrieving node status: {e}")
        return set()

# Function to cordon a node (mark it as unschedulable)
def cordon_node(node_name):
    print(f"Cordoning node: {node_name}")
    body = {"spec": {"unschedulable": True}}
    try:
        v1.patch_node(node_name, body)
        cordoned_nodes.add(node_name)
        print(f"-- Node {node_name} cordoned successfully.")
        
    except ApiException as e:
        print(f"-- Error cordoning node {node_name}: {e}")

# Function to evict all non-DaemonSet pods on a node
def evict_pods_on_node(node_name):
    print(f"Evicting pods on node: {node_name}")
    try:
        pods = v1.list_pod_for_all_namespaces(field_selector=f"spec.nodeName={node_name}").items
        for pod in pods:
            # Skip DaemonSet pods if IGNORE_DAEMONSETS is True
            if IGNORE_DAEMONSETS and pod.metadata.owner_references and pod.metadata.owner_references[0].kind == "DaemonSet":
                print(f"-- Skipping DaemonSet pod {pod.metadata.name}")
                continue
            eviction = client.V1Eviction(
                metadata=client.V1ObjectMeta(name=pod.metadata.name, namespace=pod.metadata.namespace)
            )
            try:
                v1.create_namespaced_pod_eviction(name=pod.metadata.name, namespace=pod.metadata.namespace, body=eviction)
                print(f"-- Evicted pod {pod.metadata.name} from node {node_name}.")
            except ApiException as e:
                print(f"-- Error evicting pod {pod.metadata.name}: {e}")
                print(f"Error evicting pod {pod.metadata.name}: {e.reason}")
    except ApiException as e:
        print(f"-- Error listing pods for node {node_name}: {e}")

# Function to drain nodes (cordon + evict pods)
def drain_random_nodes(nodes):
    num_nodes_to_drain = random.randint(1, len(nodes))
    print(f"{HEADER}# Draining {num_nodes_to_drain} node(s)... {RESET}")

    selected_nodes = random.sample(nodes, num_nodes_to_drain)

    for node in selected_nodes:
        cordon_node(node)
        evict_pods_on_node(node)

# Function to uncordon nodes only from the cordoned nodes
# Function to uncordon nodes only from the cordoned nodes
def uncordon_random_nodes():
    if not cordoned_nodes:
        print("No nodes are cordoned. Skipping uncordon action.")
        return

    # Ensure we don't try to sample more nodes than available
    num_nodes_to_uncordon = random.randint(1, len(cordoned_nodes))
    print(f"{HEADER}# Making {num_nodes_to_uncordon} cordoned node(s) available again...{RESET}")

    # Convert the set to a list before using random.sample
    selected_nodes = random.sample(list(cordoned_nodes), num_nodes_to_uncordon)

    for node in selected_nodes:
        print(f"Uncordoning node: {node}")
        try:
            body = {"spec": {"unschedulable": False}}
            v1.patch_node(node, body)
            print(f"-- Node {node} uncordoned successfully.")
            # Remove node from the set of cordoned nodes
            cordoned_nodes.remove(node)
        except ApiException as e:
            print(f"-- Error uncordoning node {node}: {e}")


# Main function
def drainage_loop():
    # Get all nodes with the label 'zone=edge'
    nodes = get_nodes_by_label(ZONE_LABEL_KEY, ZONE_LABEL_VALUE)

    if not nodes:
        print(f"No nodes found with label {ZONE_LABEL_KEY}={ZONE_LABEL_VALUE}")
        return

    print(f"Found nodes with label {ZONE_LABEL_KEY}={ZONE_LABEL_VALUE}: {nodes}")

    # Initialize the cordoned_nodes set based on the current state of the cluster
    global cordoned_nodes
    cordoned_nodes = get_cordoned_nodes(nodes)

    print(f"Initial cordoned nodes: {cordoned_nodes}")

    # Main loop
    while True:
        sleep_time = random.randint(MIN_INTERVAL, MAX_INTERVAL)

        # Randomly choose action: drain or uncordon
        action = random.randint(0, 1)

        if action == 0:
            drain_random_nodes(nodes)
        else:
            uncordon_random_nodes()

        print(f"{RED}Waiting for {sleep_time} seconds before next action...{RESET}")
        time.sleep(sleep_time)

# Run the script
if __name__ == "__main__":
    drainage_loop()
