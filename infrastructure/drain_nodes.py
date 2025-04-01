import random
import time
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from config import experiment_config

# Colors for output
RESET = '\033[0m'
RED = '\033[91m'
HEADER = '\033[95m'

class NodeDrainer:
    def __init__(self, config=experiment_config):
        self.config = config
        self.min_interval = 10  # minimum interval in seconds
        self.max_interval = 20  # maximum interval in seconds
        self.ignore_daemonsets = True
        self.cordoned_nodes = set()
        
        # Load the Kubernetes config
        config.load_kube_config()
        self.v1 = client.CoreV1Api()

    def get_nodes_by_label(self, label_key, label_value):
        """Get all nodes with a specific label."""
        try:
            nodes = self.v1.list_node().items
            matching_nodes = [
                node.metadata.name for node in nodes 
                if node.metadata.labels.get(label_key) == label_value
            ]
            return matching_nodes
        except ApiException as e:
            print(f"Error retrieving nodes: {e}")
            return []

    def get_cordoned_nodes(self, nodes):
        """Get list of currently cordoned nodes."""
        cordoned = set()
        try:
            for node in nodes:
                node_info = self.v1.read_node(node)
                if node_info.spec.unschedulable:
                    cordoned.add(node)
            return cordoned
        except ApiException as e:
            print(f"Error getting cordoned nodes: {e}")
            return set()

    def drain_node(self, node):
        """Drain a specific node."""
        print(f"Cordoning node: {node}")
        try:
            body = {"spec": {"unschedulable": True}}
            self.v1.patch_node(node, body)
            print(f"-- Node {node} cordoned successfully.")
            self.cordoned_nodes.add(node)
        except ApiException as e:
            print(f"-- Error cordoning node {node}: {e}")

    def uncordon_node(self, node):
        """Uncordon a specific node."""
        print(f"Uncordoning node: {node}")
        try:
            body = {"spec": {"unschedulable": False}}
            self.v1.patch_node(node, body)
            print(f"-- Node {node} uncordoned successfully.")
            self.cordoned_nodes.remove(node)
        except ApiException as e:
            print(f"-- Error uncordoning node {node}: {e}")

    def drain_random_nodes(self, nodes):
        """Drain random nodes from the provided list."""
        if not nodes:
            print("No nodes available to drain.")
            return

        # Ensure we don't try to sample more nodes than available
        num_nodes_to_drain = random.randint(1, len(nodes))
        print(f"{HEADER}# Draining {num_nodes_to_drain} random node(s)...{RESET}")

        # Convert the set to a list before using random.sample
        selected_nodes = random.sample(nodes, num_nodes_to_drain)

        for node in selected_nodes:
            self.drain_node(node)

    def uncordon_random_nodes(self):
        """Uncordon random nodes from the cordoned nodes."""
        if not self.cordoned_nodes:
            print("No nodes are cordoned. Skipping uncordon action.")
            return

        # Ensure we don't try to sample more nodes than available
        num_nodes_to_uncordon = random.randint(1, len(self.cordoned_nodes))
        print(f"{HEADER}# Making {num_nodes_to_uncordon} cordoned node(s) available again...{RESET}")

        # Convert the set to a list before using random.sample
        selected_nodes = random.sample(list(self.cordoned_nodes), num_nodes_to_uncordon)

        for node in selected_nodes:
            self.uncordon_node(node)

    def drainage_loop(self):
        """Main drainage loop."""
        # Get all nodes with the label 'zone=edge'
        nodes = self.get_nodes_by_label("zone", "edge")

        if not nodes:
            print(f"No nodes found with label zone=edge")
            return

        print(f"Found nodes with label zone=edge: {nodes}")

        # Initialize the cordoned_nodes set based on the current state of the cluster
        self.cordoned_nodes = self.get_cordoned_nodes(nodes)
        print(f"Initial cordoned nodes: {self.cordoned_nodes}")

        # Main loop
        while True:
            sleep_time = random.randint(self.min_interval, self.max_interval)

            # Randomly choose action: drain or uncordon
            action = random.randint(0, 1)

            if action == 0:
                self.drain_random_nodes(nodes)
            else:
                self.uncordon_random_nodes()

            print(f"{RED}Waiting for {sleep_time} seconds before next action...{RESET}")
            time.sleep(sleep_time)

def main():
    drainer = NodeDrainer()
    drainer.drainage_loop()

if __name__ == "__main__":
    main()
