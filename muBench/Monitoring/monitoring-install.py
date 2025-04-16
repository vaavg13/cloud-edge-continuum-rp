#!/usr/bin/env python3
from pathlib import Path
import sh
import sys

MANIFEST_DIR = Path(__file__).parent / "manifests"
NODEPORT_DIR = MANIFEST_DIR / "nodeports"

# Helpers
def apply_yaml(filename, namespace=None, nodeport=False):
    path = NODEPORT_DIR / filename if nodeport else MANIFEST_DIR / filename
    print(f"→ Applying {filename}")
    if namespace:
        sh.kubectl("apply", "-f", path, "-n", namespace)
    else:
        sh.kubectl("apply", "-f", path)

def run_helm(*args):
    print(f"→ Helm {' '.join(args)}")
    sh.helm(*args)

def secure_kubeconfig():
    """Secure only the kubeconfig file, not the entire .kube directory"""
    kubeconfig = Path.home() / ".kube" / "config"
    if kubeconfig.exists():
        try:
            print("→ Securing kubeconfig file")
            sh.chmod("go-r", str(kubeconfig))
        except sh.ErrorReturnCode as e:
            print(f"Warning: Could not modify kubeconfig permissions (this is not critical): {e.stderr.decode()}")

def install_monitoring_stack():
    # Secure kubeconfig (optional)
    secure_kubeconfig()

    # --- Prometheus ---
    sh.kubectl("create", "namespace", "monitoring", _ok_code=[0, 1])  # 1 = already exists
    run_helm("repo", "add", "prometheus-community", "https://prometheus-community.github.io/helm-charts")
    run_helm("repo", "update")
    run_helm("install", "prometheus", "prometheus-community/kube-prometheus-stack", "-n", "monitoring")

    apply_yaml("prometheus-nodeport.yaml", namespace="monitoring", nodeport=True)
    apply_yaml("grafana-nodeport.yaml", namespace="monitoring", nodeport=True)

    # --- Istio ---
    sh.kubectl("create", "namespace", "istio-system", _ok_code=[0, 1])
    run_helm("repo", "add", "istio", "https://istio-release.storage.googleapis.com/charts")
    run_helm("repo", "update")
    run_helm("install", "istio-base", "istio/base", "-n", "istio-system")
    run_helm("install", "istiod", "istio/istiod", "-n", "istio-system", "--set", "global.proxy.tracer=zipkin", "--wait")
    run_helm("install", "istio-ingressgateway", "istio/gateway", "-n", "istio-system")

    sh.kubectl("label", "namespace", "default", "istio-injection=enabled", "--overwrite")

    apply_yaml("istio-prometheus-operator.yaml")

    # --- Jaeger ---
    apply_yaml("jaeger.yaml")
    apply_yaml("jaeger-nodeport.yaml", nodeport=True)

    # --- Kiali ---
    run_helm("repo", "add", "kiali", "https://kiali.org/helm-charts")
    run_helm("repo", "update")
    run_helm(
        "install", "-n", "istio-system",
        "-f", str(MANIFEST_DIR / "kiali-values.yaml"),
        "kiali-server", "kiali/kiali-server"
    )
    apply_yaml("kiali-nodeport.yaml", nodeport=True)

if __name__ == "__main__":
    try:
        if not MANIFEST_DIR.exists():
            print(f"Error: Manifests directory not found at {MANIFEST_DIR}")
            print("Please ensure all YAML files are in the manifests directory")
            sys.exit(1)
            
        if not NODEPORT_DIR.exists():
            print(f"Error: Nodeports directory not found at {NODEPORT_DIR}")
            print("Please ensure all nodeport YAML files are in the manifests/nodeports directory")
            sys.exit(1)
            
        install_monitoring_stack()
        print("Monitoring setup completed successfully!")
    except sh.ErrorReturnCode as e:
        print(f"Error during setup: {e.stderr.decode()}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1) 