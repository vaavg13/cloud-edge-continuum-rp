#!/usr/bin/env python3
import sys
import time
from typing import Optional

from kubernetes import client, config
from mu_bench.deployers.manager import K8sDeploymentManager


APP_DIR = "APPS"


def wait_for_pods_ready(namespace: str, timeout_seconds: int = 300) -> bool:
    config.load_kube_config()
    core = client.CoreV1Api()
    start = time.time()
    while time.time() - start < timeout_seconds:
        try:
            pods = core.list_namespaced_pod(namespace=namespace)
        except Exception:
            time.sleep(5)
            continue

        if not pods.items:
            time.sleep(5)
            continue

        ready = 0
        for pod in pods.items:
            if pod.status.conditions:
                for cond in pod.status.conditions:
                    if cond.type == "Ready" and cond.status == "True":
                        ready += 1
                        break
        if ready == len(pods.items):
            print(f"✅ All {ready} pods ready in {namespace}")
            return True
        print(f"⏳ Waiting... {ready}/{len(pods.items)} pods ready in {namespace}")
        time.sleep(5)
    print(f"❌ Timeout waiting for pods in {namespace}")
    return False


def cleanup_legacy_nginx(namespace: str) -> None:
    """Best-effort removal of old gw-nginx resources if they exist."""
    try:
        config.load_kube_config()
        apps = client.AppsV1Api()
        core = client.CoreV1Api()
        # Delete Deployment gw-nginx
        try:
            apps.delete_namespaced_deployment(name="gw-nginx", namespace=namespace)
            print(f"🗑️  Deleted legacy Deployment gw-nginx in {namespace}")
        except client.exceptions.ApiException as e:
            if e.status != 404:
                print(f"⚠️  Failed deleting gw-nginx Deployment in {namespace}: {e}")
        # Delete Service gw-nginx
        try:
            core.delete_namespaced_service(name="gw-nginx", namespace=namespace)
            print(f"🗑️  Deleted legacy Service gw-nginx in {namespace}")
        except client.exceptions.ApiException as e:
            if e.status != 404:
                print(f"⚠️  Failed deleting gw-nginx Service in {namespace}: {e}")
    except Exception as e:
        print(f"⚠️  Skipping legacy nginx cleanup: {e}")


def main(app_name: str) -> int:
    app_dir = f"{APP_DIR}/{app_name}"
    try:
        mgr = K8sDeploymentManager.from_deployment_dir(app_dir)
    except Exception as e:
        print(f"❌ Failed to load deployment manager for {app_name}: {e}")
        return 1

    # Undeploy current resources
    print(f"🗑️  Undeploying {app_name}...")
    try:
        mgr.undeploy()
    except Exception as e:
        print(f"⚠️  Undeploy encountered issues (continuing): {e}")

    # Best-effort cleanup of any legacy gw-nginx
    cleanup_legacy_nginx(mgr.namespace)

    # Deploy again
    print(f"🚀 Deploying {app_name}...")
    try:
        mgr.deploy()
    except Exception as e:
        print(f"❌ Deployment failed for {app_name}: {e}")
        return 1

    print(f"⏳ Waiting for pods in {mgr.namespace}...")
    ok = wait_for_pods_ready(mgr.namespace)
    return 0 if ok else 2


if __name__ == "__main__":
    app = sys.argv[1] if len(sys.argv) > 1 else "app-iot-gateway"
    raise SystemExit(main(app))


