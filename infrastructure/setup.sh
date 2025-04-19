#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to check if a command exists
check_command() {
    if ! command -v $1 &> /dev/null; then
        print_error "$1 is not installed. Please install it first."
        exit 1
    fi
}
# Function to get config value from YAML
get_config() {
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    yq eval ".$1" "$SCRIPT_DIR/default.yaml"
}

# Function to install required dependencies
install_dependencies() {
    print_status "Installing required dependencies..."
    
    # Check and install Python dependencies
    # pip3 install -q -r requirements.txt
    
    # Install yq if not available
    if ! command -v yq &> /dev/null; then
        print_status "Installing yq..."
        wget -qO /tmp/yq https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64
        chmod +x /tmp/yq
        sudo mv /tmp/yq /usr/local/bin/
    fi
    
    print_status "Dependencies installed successfully"
}

# Function to install K3D
install_k3d() {
    print_status "Installing K3D..."
    
    if ! command -v k3d &> /dev/null; then
        # Get K3D install script from config
        K3D_INSTALL_SCRIPT=$(get_config 'k3d.install_script')
        
        # Install K3D
        wget -q -O - $K3D_INSTALL_SCRIPT | bash
    else
        print_status "K3D is already installed"
    fi
    
    print_status "K3D installed successfully"
}

# Function to create K3D cluster with specified number of agents
create_k3d_cluster() {
    print_status "Creating K3D cluster..."

    # Get cluster name and node counts from config
    CLUSTER_NAME=$(get_config 'k3d.cluster_name')
    CLOUD_NODES=$(get_config 'nodes.cloud.num_nodes')
    EDGE_NODES=$(get_config 'nodes.edge.num_nodes')
    TOTAL_AGENTS=$((CLOUD_NODES + EDGE_NODES))

    # Check if cluster already exists
    if k3d cluster list | grep -q "^$CLUSTER_NAME"; then
        print_warning "Cluster '$CLUSTER_NAME' already exists"
        read -p "Do you want to delete the existing cluster and create a new one? (y/n): " confirm
        if [[ $confirm == [yY] ]]; then
            print_status "Deleting existing cluster..."
            k3d cluster delete "$CLUSTER_NAME"
        else
            print_status "Using existing cluster"
            return 0
        fi
    fi
    
    # Create the cluster with specified number of agents
    # Read host port configuration from config
    PROMETHEUS_HOST_PORT=$(get_config 'k3d.host_ports.prometheus')
    GRAFANA_HOST_PORT=$(get_config 'k3d.host_ports.grafana')
    MUBENCH_SERVICE_PORT=$(get_config 'k3d.host_ports.mubench_service')
    KIALI_HOST_PORT=$(get_config 'k3d.host_ports.kiali')
    
    k3d cluster create "$CLUSTER_NAME" \
        --agents "$TOTAL_AGENTS" \
        --k3s-arg "--disable=traefik@server:*" \
        -p "${PROMETHEUS_HOST_PORT}:30000" \
        -p "${GRAFANA_HOST_PORT}:30001" \
        -p "${MUBENCH_SERVICE_PORT}:31113" \
        -p "${KIALI_HOST_PORT}:30003" \
        --runtime-label "com.docker.compose.project=cec_emulator@all"

    if [ $? -ne 0 ]; then
        print_error "Failed to create K3D cluster"
        exit 1
    fi

    print_status "K3D cluster created successfully with $TOTAL_AGENTS agents"
}

# Function to apply resource limits to nodes
apply_node_resource_limits() {
    print_status "Applying resource limits to nodes..."

    CLUSTER_NAME=$(get_config 'k3d.cluster_name')
    CLOUD_NODES=$(get_config 'nodes.cloud.num_nodes')
    EDGE_NODES=$(get_config 'nodes.edge.num_nodes')
    CLOUD_CPU=$(get_config 'nodes.cloud.cpu_capacity')
    CLOUD_MEM=$(get_config 'nodes.cloud.memory_capacity_gb')
    EDGE_CPU=$(get_config 'nodes.edge.cpu_capacity')
    EDGE_MEM=$(get_config 'nodes.edge.memory_capacity_gb')

    # Convert GB to MB for smaller values
    CLOUD_MEM_MB=$((CLOUD_MEM * 1024))
    EDGE_MEM_MB=$((EDGE_MEM * 1024))

    # Apply limits to cloud nodes
    for i in $(seq 0 $((CLOUD_NODES-1))); do
        CONTAINER_NAME="k3d-${CLUSTER_NAME}-agent-$i"
        print_status "Applying resource limits to cloud node $i: ${CLOUD_CPU} CPU and ${CLOUD_MEM_MB}MB memory..."
        
        # Set memory and memory-swap together to avoid the error
        docker update --cpus="$CLOUD_CPU" \
                     --memory="${CLOUD_MEM_MB}m" \
                     --memory-swap="${CLOUD_MEM_MB}m" \
                     "$CONTAINER_NAME"
    done

    # Apply limits to edge nodes
    for i in $(seq 0 $((EDGE_NODES-1))); do
        NODE_INDEX=$((CLOUD_NODES + i))
        CONTAINER_NAME="k3d-${CLUSTER_NAME}-agent-$NODE_INDEX"
        print_status "Applying resource limits to edge node $NODE_INDEX: ${EDGE_CPU} CPU and ${EDGE_MEM_MB}MB memory..."
        
        # Set memory and memory-swap together to avoid the error
        docker update --cpus="$EDGE_CPU" \
                     --memory="${EDGE_MEM_MB}m" \
                     --memory-swap="${EDGE_MEM_MB}m" \
                     "$CONTAINER_NAME"
    done

    print_status "Resource limits applied successfully"
}

# Function to apply labels to nodes
apply_node_labels() {
    print_status "Applying labels to nodes..."

    CLOUD_NODES=$(get_config 'nodes.cloud.num_nodes')
    EDGE_NODES=$(get_config 'nodes.edge.num_nodes')

    # Apply labels to cloud nodes
    for i in $(seq 0 $((CLOUD_NODES-1))); do
        NODE_NAME="k3d-${CLUSTER_NAME}-agent-$i"
        print_status "Applying labels to cloud node: $NODE_NAME..."
        kubectl label node "$NODE_NAME" zone=cloud
    done

    # Apply labels to edge nodes
    for i in $(seq 0 $((EDGE_NODES-1))); do
        NODE_NAME="k3d-${CLUSTER_NAME}-agent-$((CLOUD_NODES + i))"
        print_status "Applying labels to edge node: $NODE_NAME..."
        kubectl label node "$NODE_NAME" zone=edge
    done

    print_status "Labels applied successfully"
}

# Function to install monitoring if enabled in config
install_monitoring_if_enabled() {
    MONITORING_ENABLED=$(get_config 'monitoring.install')
    if [[ "$MONITORING_ENABLED" == "true" ]]; then
        print_status "Monitoring installation enabled in config. Installing monitoring..."
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        bash "$SCRIPT_DIR/monitoring/install_monitoring.sh"
        if [ $? -ne 0 ]; then
            print_error "Failed to install monitoring."
            exit 1
        fi
        print_status "Monitoring installed successfully."
    else
        print_status "Monitoring installation is disabled in config. Skipping monitoring setup."
    fi
}

# Function to clean existing environment (migrated from clean_install.sh)
clean_environment() {
    print_status "Cleaning existing environment..."
    CLUSTER_NAME=$(get_config 'k3d.cluster_name')
    # Delete K3D cluster if it exists
    if k3d cluster list | grep -q "^$CLUSTER_NAME"; then
        print_status "Deleting existing K3D cluster..."
        k3d cluster delete "$CLUSTER_NAME"
    fi
    print_status "Environment cleaned successfully"
}

# Function to setup the environment
setup() {
    print_status "Starting environment setup..."
    print_status "The following steps will be performed:"
    print_status "1. Clean existing environment (if requested)"
    print_status "2. Install dependencies (Python packages, yq)"
    print_status "3. Install K3D if not already installed"
    print_status "4. Create K3D cluster with specified number of agents"
    print_status "5. Apply resource limits to nodes"
    print_status "6. Apply labels to nodes"
    
    # Ask if user wants to clean existing environment if cluster exists
    CLUSTER_NAME=$(get_config 'k3d.cluster_name')
    if k3d cluster list | grep -q "^$CLUSTER_NAME"; then
        print_warning "Cluster '$CLUSTER_NAME' already exists."
        read -p "Do you want to clean the existing environment before setup? (y/n): " clean_confirm
        if [[ $clean_confirm == [yY] ]]; then
            clean_environment
        else
            print_status "Skipping environment cleaning. Proceeding with setup."
        fi
    fi
    
    read -p "Do you want to proceed with the setup? (y/n): " confirm
    if [[ $confirm != [yY] ]]; then
        print_status "Setup cancelled."
        exit 0
    fi
    
    # Check required commands
    check_command "python3"
    check_command "pip3"
    check_command "docker"
    
    # Install dependencies
    install_dependencies
    
    # Check dependencies installed successfully
    check_command "kubectl"
    check_command "yq"
    
    # Install K3D
    install_k3d
    
    # Create K3D cluster
    create_k3d_cluster
    
    # Apply resource limits to nodes
    apply_node_resource_limits
    
    # Apply labels to nodes
    apply_node_labels
    
    # Install monitoring if enabled
    install_monitoring_if_enabled
    
    print_status "Environment setup completed successfully"
    # print_status "To set up MuBench, run: ./workloads/setup_mubench.sh"
}

# Main execution
main() {
    if [ $# -eq 0 ]; then
        setup
        exit 0
    fi
    
    case "$1" in
        "clean")
            clean_environment
            ;;
        "help"|"-h"|"--help")
            echo "Usage: $0 [command]"
            echo "Commands:"
            echo "  (no arguments)  - Run complete setup with confirmation (asks before cleaning if infra exists)"
            echo "  clean           - Clean existing environment (delete cluster)"
            echo "  help            - Show this help message"
            ;;
        *)
            print_error "Unknown command: $1"
            echo "Usage: $0 [command]"
            echo "Use '$0 help' for more information"
            exit 1
            ;;
    esac
}

# Execute main function with all arguments
main "$@" 