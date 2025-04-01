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
    yq eval ".$1" config.yaml
}

# Function to install MuBench
install_mubench() {
    print_status "Installing MuBench..."
    
    # Check if container already exists
    if docker ps -a --format '{{.Names}}' | grep -q "^mubench$"; then
        print_status "Removing existing MuBench container..."
        docker rm -f mubench
    fi
    
    # Run the MuBench container with kubectl config mounted
    docker run -d --name mubench \
        -v ~/.kube/config:/root/.kube/config \
        -v $(pwd)/mubench:/root/mubench_custom \
        $(get_config 'mubench.image')
    
    if [ $? -ne 0 ]; then
        print_error "Failed to start MuBench container"
        exit 1
    fi
    
    # Wait for Kubernetes API server to be ready
    print_status "Waiting for Kubernetes API server..."
    until kubectl get nodes &>/dev/null; do
        sleep 5
    done
    
    # Copy the MuBench configurations to the right location
    print_status "Deploying MuBench configuration..."
    docker exec mubench bash -c '
        cd /root/muBench && \
        cp -r /root/mubench_custom/Configs/* /root/muBench/Configs/ && \
        python3 Deployers/K8sDeployer/RunK8sDeployer.py -c Configs/K8sParameters.json
    '
    
    print_status "MuBench installed successfully"
}

# Function to run load test
run_load_test() {
    print_status "Running load test..."
    
    # Start metrics logging in background
    python3 -m src.monitoring.log &
    LOG_PID=$!
    
    # Run load test
    locust -f locustfile.py \
        --host $(get_config 'test.host') \
        --users $(get_config 'test.users') \
        --spawn-rate $(get_config 'test.spawn_rate') \
        --run-time $(get_config 'test.duration')
    
    # Kill metrics logging process
    kill $LOG_PID
    
    print_status "Load test completed"
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check required commands
    check_command "python3"
    check_command "docker"
    check_command "kubectl"
    check_command "yq"
    check_command "locust"
    
    # Check if K3D cluster exists
    if ! k3d cluster list | grep -q "$(get_config 'k3d.cluster_name')"; then
        print_error "K3D cluster '$(get_config 'k3d.cluster_name')' not found. Please run setup.sh first."
        exit 1
    fi
    
    # Check if MuBench directory exists
    if [ ! -d "./mubench" ] || [ ! -d "./mubench/Configs" ]; then
        print_error "MuBench configuration not found. Please run setup.sh first."
        exit 1
    fi
    
    # Check if mubench_config.yaml exists
    if [ ! -f "./mubench/Configs/mubench_config.yaml" ]; then
        print_error "MuBench configuration file not found. Please check mubench/Configs/mubench_config.yaml."
        exit 1
    fi
    
    print_status "Prerequisites check completed"
}

# Function to run the complete experiment
run_experiment() {
    print_status "Starting experiment..."
    print_status "The following steps will be performed:"
    print_status "1. Check prerequisites (K3D cluster, MuBench container)"
    print_status "2. Run load test with Locust"
    print_status "3. Collect metrics during the test"
    
    read -p "Do you want to proceed? (y/n): " confirm
    if [[ $confirm != [yY] ]]; then
        print_status "Experiment cancelled."
        exit 0
    fi
    
    # Check prerequisites
    check_prerequisites
    
    # Run load test
    run_load_test
    
    print_status "Experiment completed successfully"
}

# Function to analyze experiment results
analyze_results() {
    print_status "Analyzing experiment results..."
    
    # TODO: Implement results analysis
    
    print_status "Results analysis completed"
}

# Function to clean up experiment resources
cleanup() {
    print_status "Cleaning up experiment resources..."
    
    # Remove MuBench container
    if docker ps -a --format '{{.Names}}' | grep -q "^mubench$"; then
        docker rm -f mubench
    fi
    
    # Delete MuBench deployments from Kubernetes
    kubectl delete deployment -l app=mubench
    
    print_status "Cleanup completed"
}

# Function to display usage
show_usage() {
    echo "Usage: $0 [command]"
    echo "Commands:"
    echo "  (no arguments)  - Run the complete experiment with confirmation"
    echo "  run-test        - Run just the load test"
    echo "  cleanup         - Clean up experiment resources"
    echo "  help            - Show this help message"
}

# Main execution
main() {
    if [ $# -eq 0 ]; then
        run_experiment
        exit 0
    fi
    
    case "$1" in
        "run-test")
            check_prerequisites
            run_load_test
            ;;
        "cleanup")
            cleanup
            ;;
        "help"|"-h"|"--help")
            show_usage
            ;;
        *)
            print_error "Unknown command: $1"
            show_usage
            exit 1
            ;;
    esac
}

# Make the script executable
chmod +x "$0"

# Execute main function with all arguments
main "$@" 