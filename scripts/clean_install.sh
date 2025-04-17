#!/bin/bash

# Source utility functions
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "${SCRIPT_DIR}/utils.sh"

# Function to clean existing environment
clean_environment() {
    print_status "Cleaning existing environment..."
    
    # Get cluster name from config
    CLUSTER_NAME=$(get_config 'k3d.cluster_name')
    
    # Delete K3D cluster if it exists
    if k3d cluster list | grep -q "^$CLUSTER_NAME"; then
        print_status "Deleting existing K3D cluster..."
        k3d cluster delete "$CLUSTER_NAME"
    fi
    
    print_status "Environment cleaned successfully"
}

# Function to setup everything
setup() {  
    # Clean existing environment
    clean_environment
    
    # Install infrastructure
    print_status "Installing infrastructure..."
    "${SCRIPT_DIR}/../infrastructure/setup.sh"
    
    print_status "Clean installation completed successfully"
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
            echo "  (no arguments)  - Run complete clean installation with confirmation"
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