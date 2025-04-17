from kubernetes import client, config
from kubernetes.client.rest import ApiException
import yaml
import json
import os
import time

class K8sYamlDeployer:
    """
    Utility class for deploying and undeploying Kubernetes YAML files.
    """
    def __init__(self):
        pass

    def deploy(self, folder, sleep=0):
        """
        Deploy all YAML files in the given folder to Kubernetes.
        Waits for deployments to be ready. Sleeps between deployments if specified.
        """
        print("######################")
        print(f"We are going to DEPLOY the yaml files in the following folder: {folder}")
        print("######################")
        config.load_kube_config()
        k8s_apps_api = client.AppsV1Api()
        k8s_core_api = client.CoreV1Api()
        items = []
        for r, d, f in os.walk(folder):
            f.sort(reverse=True)
            for file in f:
                if '.yaml' in file:
                    items.append(os.path.join(r, file))
        if os.path.isfile(folder):
            items.append(folder)
        for yaml_to_apply in items:
            with open(yaml_to_apply) as f:
                complete_yaml = yaml.load_all(f, Loader=yaml.FullLoader)
                for partial_yaml in complete_yaml:
                    try:
                        namespace = partial_yaml["metadata"]["namespace"]
                        # Check if namespace exists, create if not
                        try:
                            k8s_core_api.read_namespace(name=namespace)
                        except ApiException as ns_err:
                            if ns_err.status == 404:
                                print(f"Namespace '{namespace}' does not exist. Creating...")
                                ns_body = client.V1Namespace(metadata=client.V1ObjectMeta(name=namespace))
                                k8s_core_api.create_namespace(ns_body)
                            else:
                                raise
                        if partial_yaml["kind"] == "Deployment":
                            dep_name = partial_yaml["metadata"]["name"]
                            # Check if deployment exists
                            try:
                                k8s_apps_api.read_namespaced_deployment(name=dep_name, namespace=namespace)
                                print(f"[SKIP] Deployment '{dep_name}' already exists in namespace '{namespace}'.")
                                continue
                            except ApiException as e:
                                if e.status != 404:
                                    raise
                            k8s_apps_api.create_namespaced_deployment(namespace=namespace, body=partial_yaml)
                            dn = dep_name
                            api_response = k8s_apps_api.read_namespaced_deployment_status(name=dep_name, namespace=namespace, pretty=True)
                            while (api_response.status.ready_replicas != api_response.status.replicas):
                                print(f"\n *** Waiting deployment {dn} ready ...*** \n")
                                time.sleep(1)
                                api_response = k8s_apps_api.read_namespaced_deployment_status(name=dep_name, namespace=namespace, pretty=True)
                            time.sleep(sleep)
                            print(f"Deployment {dn} created.")
                        elif partial_yaml["kind"] == "Service":
                            svc_name = partial_yaml["metadata"]["name"]
                            # Check if service exists
                            try:
                                k8s_core_api.read_namespaced_service(name=svc_name, namespace=namespace)
                                print(f"[SKIP] Service '{svc_name}' already exists in namespace '{namespace}'.")
                                continue
                            except ApiException as e:
                                if e.status != 404:
                                    raise
                            k8s_core_api.create_namespaced_service(namespace=namespace, body=partial_yaml)
                            print(f"Service '{svc_name}' created.")
                            print("---")
                        elif partial_yaml["kind"] == "ConfigMap":
                            map_name = partial_yaml["metadata"]["name"]
                            # Check if configmap exists
                            try:
                                k8s_core_api.read_namespaced_config_map(name=map_name, namespace=namespace)
                                print(f"[SKIP] ConfigMap '{map_name}' already exists in namespace '{namespace}'.")
                                continue
                            except ApiException as e:
                                if e.status != 404:
                                    raise
                            k8s_core_api.create_namespaced_config_map(namespace=namespace, body=partial_yaml)
                            print(f"ConfigMap '{map_name}' created.")
                            print("---")
                    except ApiException as err:
                        api_exception_body = json.loads(err.body)
                        print("######################")
                        print(f"Exception raised deploying a {partial_yaml['kind']}: {api_exception_body['details']} -> {api_exception_body['reason']}")
                        print("######################")

    def undeploy(self, folder):
        """
        Undeploy all YAML files in the given folder from Kubernetes.
        """
        print("######################")
        print(f"We are going to UNDEPLOY the yaml files in the following folder: {folder}")
        print("######################")
        config.load_kube_config()
        k8s_apps_api = client.AppsV1Api()
        k8s_core_api = client.CoreV1Api()
        items = []
        for r, d, f in os.walk(folder):
            for file in f:
                if '.yaml' in file:
                    items.append(os.path.join(r, file))
        if os.path.isfile(folder):
            items.append(folder)
        for yaml_to_create in items:
            with open(yaml_to_create) as f:
                complete_yaml = yaml.load_all(f, Loader=yaml.FullLoader)
                for partial_yaml in complete_yaml:
                    try:
                        if partial_yaml["kind"] == "Deployment":
                            dep_name = partial_yaml["metadata"]["name"]
                            k8s_apps_api.delete_namespaced_deployment(name=dep_name, namespace=partial_yaml["metadata"]["namespace"], grace_period_seconds=0)
                            print(f"Deployment '{dep_name}' deleted.")
                        elif partial_yaml["kind"] == "Service":
                            svc_name = partial_yaml["metadata"]["name"]
                            k8s_core_api.delete_namespaced_service(name=svc_name, namespace=partial_yaml["metadata"]["namespace"], grace_period_seconds=0)
                            print(f"Service '{svc_name}' deleted.")
                            print("---")
                        elif partial_yaml["kind"] == "ConfigMap":
                            map_name = partial_yaml["metadata"]["name"]
                            k8s_core_api.delete_namespaced_config_map(name=map_name, namespace=partial_yaml["metadata"]["namespace"])
                            print(f"ConfigMap '{map_name}' deleted.")
                            print("---")
                    except ApiException as err:
                        api_exception_body = json.loads(err.body)
                        print("######################")
                        print(f"Exception raised trying to delete {partial_yaml['kind']} '{api_exception_body['details']['name']}': {api_exception_body['reason']}")
                        print("######################") 