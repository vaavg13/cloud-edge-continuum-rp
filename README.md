# Cloud-Edge Continuum Resource Prediction Experiment
RESOURCE PREDICTION FOR VOLATILITY NODES IN A CLOUD EDGE CONTINUUM

# experiment.sh script

This script helps you to manage a k3d cluster with specified cloud and edge nodes, including setting resource limits and displaying node information.

## Prerequisites

Ensure you have the following installed on your system:

- Docker
- k3d
- kubectl

## Usage

The script supports the following commands:

- `init`: Install k3d and other dependencies.
- `up`: Start the k3d cluster with the specified configurations.
- `info`: Display information about the cluster's agent nodes.
- `down`: Stop the cluster and remove related containers.

### Script Commands

- `init`: Use this command to install k3d and other dependencies.
- `up`: Use this command to start the k3d cluster.
- `info`: Use this command to display allocatable resources and labels of agent nodes.
- `down`: Use this command to stop the cluster and remove related containers.

### Example

```sh
./k3d_cluster.sh init  # Install k3d and dependencies
./k3d_cluster.sh up    # Start the k3d cluster
./k3d_cluster.sh info  # Display cluster agent nodes information
./k3d_cluster.sh down  # Stop the cluster and remove containers
```

### Parameters

- `CLOUD_NODES_NUM`: Number of cloud nodes.
- `EDGE_NODES_NUM`: Number of edge nodes.
- `CLOUD_NODES_CPU_CAPACITY`: CPU capacity for cloud nodes.
- `EDGE_NODES_CPU_CAPACITY`: CPU capacity for edge nodes.
- `CLOUD_NODES_MEMORY_CAPACITY_GB`: Memory capacity (in GB) for cloud nodes.
- `EDGE_NODES_MEMORY_CAPACITY_GB`: Memory capacity (in GB) for edge nodes.
- `CLOUD_NODES_LABELS`: Labels for cloud nodes.
- `EDGE_NODE_LABELS`: Labels for edge nodes.
-  `EDGE_NODES_NETWORK_RESTRICTIONS`:
    - `rate`: Rate of the network (e.g., 1mbps)
    - `delay`: Network delay (e.g., 100ms)
    - `loss`: Packet loss percentage (e.g., 50%)
    - `duplicate`: Packet duplication percentage (e.g., 50%)
    - `corrupt`: Packet corruption percentage (e.g., 10%)

### Requirements

- Docker
- k3d
- kubectl