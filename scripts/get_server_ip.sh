#!/bin/bash

# Source utility functions if script is not being sourced
if [ "${BASH_SOURCE[0]}" -ef "$0" ]; then
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    source "${SCRIPT_DIR}/utils.sh"
fi

# Function to get K3D server IP address
get_server_ip() {
    local SERVER_IP=$(docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' k3d-cec-emulator-server-0)
    
    if [ -z "$SERVER_IP" ]; then
        print_error "Failed to get server IP address. Is the K3D cluster running?"
        return 1
    fi
    
    echo "$SERVER_IP"
    return 0
}

# If script is run directly (not sourced), execute get_server_ip
if [ "${BASH_SOURCE[0]}" -ef "$0" ]; then
    print_status "Getting K3D server IP address..."
    IP=$(get_server_ip)
    if [ $? -eq 0 ]; then
        print_status "K3D Server IP: $IP"
    fi
fi 