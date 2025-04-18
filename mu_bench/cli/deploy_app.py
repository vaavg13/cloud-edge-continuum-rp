import argparse
import sys
import os
from mu_bench.deployers.manager import K8sDeploymentManager

def main():
    parser = argparse.ArgumentParser(description="Deploy a MuBench app from an app directory.")
    parser.add_argument('--app-dir', type=str, required=True, help='Path to the app directory (must contain workmodel.json)')
    args = parser.parse_args()

    app_dir = args.app_dir
    k8params_path = os.path.join(app_dir, 'k8parameters.json')
    workmodel_path = os.path.join(app_dir, 'workmodel.json')

    try:
        if os.path.exists(k8params_path):
            print(f"Using existing k8parameters.json in {app_dir}...")
            mgr = K8sDeploymentManager.from_deployment_dir(app_dir)
        elif os.path.exists(workmodel_path):
            print(f"No k8parameters.json found, using workmodel.json in {app_dir}...")
            import json
            with open(workmodel_path) as f:
                workmodel = json.load(f)
            mgr = K8sDeploymentManager(workmodel=workmodel, output_dir=app_dir)
        else:
            print(f"Error: Neither k8parameters.json nor workmodel.json found in {app_dir}.")
            sys.exit(1)
        deployment_dir = mgr.deploy()
        print(f"Deployment completed. Deployment directory: {deployment_dir}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 