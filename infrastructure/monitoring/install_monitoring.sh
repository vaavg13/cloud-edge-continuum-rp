#!/bin/bash

set -e

MANIFEST_DIR="$(dirname "$0")/manifests"
NODEPORT_DIR="$MANIFEST_DIR/nodeports"

# Helper to apply YAML
apply_yaml() {
    local filename=$1
    local namespace=$2
    local nodeport=$3
    local path
    if [[ "$nodeport" == "true" ]]; then
        path="$NODEPORT_DIR/$filename"
    else
        path="$MANIFEST_DIR/$filename"
    fi
    echo "→ Applying $filename"
    if [[ -n "$namespace" ]]; then
        kubectl apply -f "$path" -n "$namespace"
    else
        kubectl apply -f "$path"
    fi
}

# Secure kubeconfig file
secure_kubeconfig() {
    local kubeconfig="$HOME/.kube/config"
    if [[ -f "$kubeconfig" ]]; then
        echo "→ Securing kubeconfig file"
        chmod go-r "$kubeconfig" || echo "Warning: Could not modify kubeconfig permissions (not critical)"
    fi
}

# Install monitoring stack
install_monitoring_stack() {
    secure_kubeconfig

    # --- Prometheus & Grafana ---
    kubectl create namespace monitoring || true
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm repo update
    helm install prometheus prometheus-community/kube-prometheus-stack -n monitoring

    apply_yaml "prometheus-nodeport.yaml" "monitoring" true
    apply_yaml "grafana-nodeport.yaml" "monitoring" true

    # --- Istio ---
    kubectl create namespace istio-system || true
    helm repo add istio https://istio-release.storage.googleapis.com/charts
    helm repo update
    helm install istio-base istio/base -n istio-system
    helm install istiod istio/istiod -n istio-system --set global.proxy.tracer=zipkin --wait
    helm install istio-ingressgateway istio/gateway -n istio-system

    kubectl label namespace default istio-injection=enabled --overwrite

    apply_yaml "istio-prometheus-operator.yaml"

    # --- Jaeger ---
    apply_yaml "jaeger.yaml"
    apply_yaml "jaeger-nodeport.yaml" "" true

    # --- Kiali ---
    helm repo add kiali https://kiali.org/helm-charts
    helm repo update
    helm install -n istio-system -f "$MANIFEST_DIR/kiali-values.yaml" kiali-server kiali/kiali-server
    apply_yaml "kiali-nodeport.yaml" "" true
}

# Main
if [[ ! -d "$MANIFEST_DIR" ]]; then
    echo "Error: Manifests directory not found at $MANIFEST_DIR"
    echo "Please ensure all YAML files are in the manifests directory"
    exit 1
fi
if [[ ! -d "$NODEPORT_DIR" ]]; then
    echo "Error: Nodeports directory not found at $NODEPORT_DIR"
    echo "Please ensure all nodeport YAML files are in the manifests/nodeports directory"
    exit 1
fi

install_monitoring_stack

echo "Monitoring setup completed successfully!" 