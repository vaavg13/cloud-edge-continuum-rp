import argparse
import sys
import os
from mu_bench.deployers.manager import K8sDeploymentManager
from mu_bench.utils.pretty_print import print_status, print_error

def main():
    parser = argparse.ArgumentParser(description="Undeploy a MuBench app from an app directory.")
    parser.add_argument('--app-dir', type=str, required=True, help='Path to the app directory (must contain workmodel.json or k8parameters.json)')
    args = parser.parse_args()

    app_dir = args.app_dir

    try:
        mgr = K8sDeploymentManager.from_deployment_dir(app_dir)
        mgr.undeploy()
        print_status(f"Undeployment completed for app directory: {app_dir}")
    except Exception as e:
        print_error(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 