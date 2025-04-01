#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Hardcoded project name
PROJECT_NAME="cec-emulator"
print_status "Using project: $PROJECT_NAME"

# Use the container name as hostname instead of IP
SERVER_NAME=$(docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' k3d-cec-emulator-server-0)
print_status "Using server: $SERVER_NAME"

# Path to kubeconfig
KUBECONFIG="$HOME/.kube/config"

if [ ! -f "$KUBECONFIG" ]; then
    print_error "Kubeconfig file not found at $KUBECONFIG"
    exit 1
fi

# Create a temporary file for the new config
TMP_CONFIG=$(mktemp)

# Use port 6443 for internal container-to-container communication
PORT="6443"
print_status "Using internal k3s API port: $PORT"

# Replace the server address in the kubeconfig using the container name
sed "s|server: https://[0-9.]*:[0-9]*|server: https://$SERVER_NAME:$PORT|g" "$KUBECONFIG" > "$TMP_CONFIG"

# Check if sed command was successful
if [ $? -ne 0 ]; then
    print_error "Failed to update kubeconfig"
    rm "$TMP_CONFIG"
    exit 1
fi

# Check if target container exists
TARGET_CONTAINER="mubench"
if ! docker ps -a --format '{{.Names}}' | grep -q "^$TARGET_CONTAINER$"; then
    print_error "Target container '$TARGET_CONTAINER' not found"
    rm "$TMP_CONFIG"
    exit 1
fi

# Copy the config into the container
if ! docker cp "$TMP_CONFIG" "$TARGET_CONTAINER:/root/.kube/config"; then
    print_error "Failed to copy kubeconfig to container"
    rm "$TMP_CONFIG"
    exit 1
fi

print_status "Successfully updated kubeconfig in container $TARGET_CONTAINER"

# Clean up
rm "$TMP_CONFIG" 