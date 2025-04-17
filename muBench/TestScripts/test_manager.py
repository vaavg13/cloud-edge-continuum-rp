import json
import os
import time
from muBench.Deployers import K8sDeploymentManager

def test_k8s_deployment_manager():
    # Load a sample workmodel
    workmodel_path = os.path.join(os.path.dirname(__file__), '../Examples/workmodel-serial-3services.json')
    with open(workmodel_path, 'r') as f:
        workmodel = json.load(f)

    # Instantiate the manager with no_apply=True (dry run)
    manager = K8sDeploymentManager(
        workmodel=workmodel,
        no_apply=False,  # Do not actually deploy to K8s
        output_dir="test-deployments",
        internal_service_functions_path="muBench/CustomFunctions",
        namespace="test2"
    )
    try:
        deployment_dir = manager.deploy()
        print(f"YAMLs generated in: {deployment_dir}")
    except RuntimeError as e:
        print(f"Caught RuntimeError: {e}")
        exit(1)
    # Optionally, clean up
    time.sleep(100)
    manager.undeploy()
    manager.cleanup()
    print("Test completed and cleaned up.")

if __name__ == "__main__":
    test_k8s_deployment_manager() 