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
    yq eval ".$1" config/default.yaml
}

# Function to install required dependencies
install_dependencies() {
    print_status "Installing required dependencies..."
    
    # Check and install Python dependencies
    pip3 install -q -r requirements.txt
    
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

# Function to create K3D cluster
create_k3d_cluster() {
    print_status "Creating K3D cluster..."
    
    # Get cluster name from config
    CLUSTER_NAME=$(get_config 'k3d.cluster_name')
    
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
    
    # Get cluster arguments from config
    CLUSTER_ARGS="--k3s-arg --disable=traefik@server:*"
    CLUSTER_ARGS+=" -p $(get_config 'k3d.loadbalancer_port_map'):80@loadbalancer"
    CLUSTER_ARGS+=" -a $(($(get_config 'nodes.cloud.num_nodes') + $(get_config 'nodes.edge.num_nodes')))"
    CLUSTER_ARGS+=" --image $(get_config 'k3d.image')"
    # CLUSTER_ARGS+=" --runtime-label com.docker.compose.project=cec_emulator@all"
    
    # Create cluster with arguments from config
    k3d cluster create "$CLUSTER_NAME" $CLUSTER_ARGS
    
    if [ $? -ne 0 ]; then
        print_error "Failed to create K3D cluster"
        exit 1
    fi
    
    print_status "K3D cluster created successfully"
}

# Function to label nodes
label_nodes() {
    print_status "Labeling nodes..."
    
    # Get node counts
    CLOUD_NODES=$(get_config 'nodes.cloud.num_nodes')
    EDGE_NODES=$(get_config 'nodes.edge.num_nodes')
    
    # Label cloud nodes
    for i in $(seq 0 $((CLOUD_NODES-1))); do
        kubectl label node k3d-$(get_config 'k3d.cluster_name')-agent-$i zone=cloud --overwrite
    done
    
    # Label edge nodes
    for i in $(seq 0 $((EDGE_NODES-1))); do
        kubectl label node k3d-$(get_config 'k3d.cluster_name')-agent-$((CLOUD_NODES+i)) zone=edge --overwrite
    done
    
    print_status "Nodes labeled successfully"
}

# Function to prepare MuBench configuration
prepare_mubench_config() {
    print_status "Preparing MuBench configuration..."
    
    # Make sure the mubench directory exists
    if [ ! -d "./config/mubench" ]; then
        print_error "MuBench directory not found"
        exit 1
    fi
    
    print_status "MuBench configuration prepared successfully"
}

# Function to install MuBench
install_mubench() {
    print_status "Installing MuBench..."
    
    # Check if container already exists
    if docker ps -a --format '{{.Names}}' | grep -q "^mubench$"; then
        print_status "Removing existing MuBench container..."
        docker rm -f mubench
    fi
    
    # Run the MuBench container
    docker run -d --name mubench \
        -v $(pwd)/config/mubench:/root/mubench_custom \
        --label com.docker.compose.project=cec_emulator \
        $(get_config 'mubench.image')
    
    if [ $? -ne 0 ]; then
        print_error "Failed to start MuBench container"
        exit 1
    fi
    
    # Update the kubeconfig in the container
    print_status "Updating kubeconfig for MuBench..."
    if ! ./scripts/update_kubeconfig.sh; then
        print_error "Failed to update kubeconfig in MuBench container"
        docker rm -f mubench
        exit 1
    fi
    
    # Wait for Kubernetes API server to be ready
    print_status "Waiting for Kubernetes API server..."
    until docker exec mubench kubectl get nodes &>/dev/null; do
        sleep 5
    done
    
    print_status "MuBench installed successfully"
}

# Function to setup the environment
setup() {
    print_status "Starting environment setup..."
    print_status "The following steps will be performed:"
    print_status "1. Install dependencies (Python packages, yq)"
    print_status "2. Install K3D if not already installed"
    print_status "3. Create K3D cluster"
    print_status "4. Label nodes as cloud and edge"
    print_status "5. Prepare MuBench configuration"
    print_status "6. Install and deploy MuBench"
    
    read -p "Do you want to proceed? (y/n): " confirm
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
    
    # Label nodes
    label_nodes
    
    # Prepare MuBench configuration
    prepare_mubench_config
    
    # Install MuBench
    install_mubench
    
    print_status "Environment setup completed successfully"
}

# Main execution
main() {
    if [ $# -eq 0 ]; then
        setup
        exit 0
    fi
    
    case "$1" in
        "help"|"-h"|"--help")
            echo "Usage: $0 [command]"
            echo "Commands:"
            echo "  (no arguments)  - Run complete setup with confirmation"
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

# Make the script executable
chmod +x "$0"

# Execute main function with all arguments
main "$@" 