#!/bin/bash

# Source utility functions
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "${SCRIPT_DIR}/../scripts/utils.sh"

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

    docker run -d \
        --rm \
        --name mubench \
        -v ~/.kube/:/root/.kube \
        -v "${SCRIPT_DIR}/../mubench/Configs/:/root/muBench/Configs" \
        --network host \
        --label com.docker.compose.project=cec_emulator \
        $(get_config 'mubench.image')
    
    if [ $? -ne 0 ]; then
        print_error "Failed to start MuBench container"
        exit 1
    fi
    
    # Wait for Kubernetes API server to be ready
    print_status "Waiting for Kubernetes API server..."
    until docker exec mubench kubectl get nodes &>/dev/null; do
        sleep 5
    done
    
    print_status "MuBench installed successfully"
}

# Function to deploy MuBench monitoring
deploy_mubench() {
    print_status "Deploying MuBench monitoring. This may take a while..."
    
    # Run the monitoring installation script and suppress its output
    docker exec -it mubench bash -c "cd \$HOME/muBench/Monitoring/kubernetes-full-monitoring && sh ./monitoring-install.sh"
    
    # Check if the command completed successfully
    if [ $? -eq 0 ]; then
        print_status "MuBench monitoring deployed successfully"
    else
        print_error "Failed to deploy MuBench monitoring"
        exit 1
    fi
}

# Function to setup MuBench
setup() {
    print_status "Starting MuBench setup..."
    print_status "The following steps will be performed:"
    print_status "1. Prepare MuBench configuration"
    print_status "2. Install and deploy MuBench"
    print_status "3. Deploy MuBench monitoring"
    
    read -p "Do you want to proceed? (y/n): " confirm
    if [[ $confirm != [yY] ]]; then
        print_status "Setup cancelled."
        exit 0
    fi
    
    # Check required commands
    check_command "docker"
    
    # Prepare MuBench configuration
    prepare_mubench_config
    
    # Install MuBench
    install_mubench
    
    # Deploy MuBench monitoring
    deploy_mubench
    
    print_status "MuBench setup completed successfully"
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
            echo "  (no arguments)  - Run complete MuBench setup with confirmation"
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