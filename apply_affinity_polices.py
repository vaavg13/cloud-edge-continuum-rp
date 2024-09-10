from kubernetes import client, config
from kubernetes.client.rest import ApiException
import json
import re
import sys

# Load Kubernetes configuration
config.load_kube_config()

# Kubernetes client for interacting with deployments
api_instance = client.AppsV1Api()

def patch_deployments(deployments, patch_file, affinity_type):
    # Load the patch data from JSON file
    with open(patch_file, 'r') as file:
        patch_data = json.load(file)

    for deployment in deployments:
        try:
            # Modify the patch to add the `zone` label based on affinity_type
            patch_data_with_label = {
                "metadata": {
                    "labels": {
                        "zone": affinity_type
                    }
                }
            }
            # Merge the patch_data and the label data
            patch_data_with_label.update(patch_data)

            # Apply the patch
            api_instance.patch_namespaced_deployment(
                name=deployment, 
                namespace="default",  # Use the appropriate namespace
                body=patch_data_with_label
            )
            print(f"-- Successfully patched {affinity_type} deployment {deployment} with label 'zone={affinity_type}'")
        except ApiException as e:
            print(f"-- Failed to patch {affinity_type} deployment {deployment}: {e}", file=sys.stderr)

def rollout_restart(deployments):
    for deployment in deployments:
        try:
            # Rollout restart by setting the annotation to trigger the restart
            api_instance.patch_namespaced_deployment(
                name=deployment, 
                namespace="default",  # Use the appropriate namespace
                body={
                    "spec": {
                        "template": {
                            "metadata": {
                                "annotations": {
                                    "kubectl.kubernetes.io/restartedAt": "now"
                                }
                            }
                        }
                    }
                }
            )
            print(f"-- Successfully rollout restarted deployment {deployment}")
        except ApiException as e:
            print(f"-- Failed to restart deployment {deployment}: {e}", file=sys.stderr)

def find_deployments():
    deployments = []
    try:
        print("Listing all deployments in the namespace...")
        # List all deployments in the default namespace
        all_deployments = api_instance.list_namespaced_deployment(namespace="default")

        # Define the pattern to match deployments with names like s0, s1, ..., s9
        pattern = re.compile(r'^s[0-9]+$')

        # Filter deployments whose names match the pattern
        for deployment in all_deployments.items:
            if pattern.match(deployment.metadata.name):
                deployments.append(deployment.metadata.name)
        
        print(f"Found deployments: {deployments}")
    except ApiException as e:
        print(f"Exception when listing deployments: {e}", file=sys.stderr)
    
    return deployments

def split_deployments(deployments, edge_deployment_ratio):
    split_index = int(len(deployments) * edge_deployment_ratio)
    edge_deployments = deployments[:split_index]
    cloud_deployments = deployments[split_index:]
    
    return cloud_deployments, edge_deployments

def set_affinity_policies(edge_deployment_ratio=0.5):
    """
    Apply affinity policies to cloud and edge deployments based 
    on the ratio of deployments to be assigned as edge deployments.

    :param edge_deployment_ratio: Proportion of deployments to be treated as 
                                  edge deployments. Must be a float between 
                                  0 and 1.
    """
    assert (0 <= edge_deployment_ratio <= 1), \
        "edge_deployment_ratio must be between 0 and 1"
    
    # Find deployments matching the pattern
    matching_deployments = find_deployments()

    if not matching_deployments:
        print("No deployments found matching the pattern.")
        return
    
    # Split deployments into cloud and edge based on the given ratio
    cloud_deployments, edge_deployments = split_deployments(
        matching_deployments, 
        edge_deployment_ratio
    )

    # Patch and restart cloud deployments
    if cloud_deployments:
        print(f"## Patching and restarting {len(cloud_deployments)} cloud deployments...")
        patch_deployments(
            cloud_deployments, 
            './affinity_policies/cloud-affinity.json', 
            'cloud'
        )
        rollout_restart(cloud_deployments)
    else:
        print("No cloud deployments found.")

    # Patch and restart edge deployments
    if edge_deployments:
        print(f"## Patching and restarting {len(edge_deployments)} edge deployments...")
        patch_deployments(
            edge_deployments, 
            './affinity_policies/edge-affinity.json', 
            'edge'
        )
        rollout_restart(edge_deployments)
    else:
        print("No edge deployments found.")

if __name__ == "__main__":
    set_affinity_policies()
