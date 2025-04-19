from kubernetes import client, config
from kubernetes.client.rest import ApiException
import yaml
import json
import os
import time

class K8sYamlDeployer:
    """
    Utility class for deploying and undeploying Kubernetes YAML files.
    Refactored for readability and simplicity.
    """
    def __init__(self):
        config.load_kube_config()
        self.k8s_apps_api = client.AppsV1Api()
        self.k8s_core_api = client.CoreV1Api()

    def deploy(self, folder, sleep=0):
        for yaml_file in self._collect_yaml_files(folder):
            for resource in self._load_yaml(yaml_file):
                self._ensure_namespace(resource)
                self._deploy_resource(resource, sleep)

    def undeploy(self, folder):
        for yaml_file in self._collect_yaml_files(folder):
            for resource in self._load_yaml(yaml_file):
                self._undeploy_resource(resource)

    def _collect_yaml_files(self, folder):
        """Collect all YAML files from a folder or a single file."""
        items = []
        if os.path.isfile(folder):
            items.append(folder)
        else:
            for r, _, files in os.walk(folder):
                for file in sorted(files):
                    if file.endswith('.yaml'):
                        items.append(os.path.join(r, file))
        return items

    def _load_yaml(self, yaml_file):
        """Load all YAML documents from a file."""
        with open(yaml_file) as f:
            return list(yaml.load_all(f, Loader=yaml.FullLoader))

    def _ensure_namespace(self, resource):
        """Ensure the namespace exists for the resource."""
        namespace = resource.get("metadata", {}).get("namespace")
        if not namespace:
            return
        try:
            self.k8s_core_api.read_namespace(name=namespace)
        except ApiException as ns_err:
            if ns_err.status == 404:
                print(f"Namespace '{namespace}' does not exist. Creating...")
                ns_body = client.V1Namespace(metadata=client.V1ObjectMeta(name=namespace))
                self.k8s_core_api.create_namespace(ns_body)
            else:
                raise

    def _deploy_resource(self, resource, sleep=0):
        kind = resource.get("kind")
        metadata = resource.get("metadata", {})
        namespace = metadata.get("namespace")
        name = metadata.get("name")
        if kind == "Deployment":
            if self._resource_exists(self.k8s_apps_api.read_namespaced_deployment, name, namespace):
                raise Exception(f"Deployment '{name}' already exists in namespace '{namespace}'.")
            self.k8s_apps_api.create_namespaced_deployment(namespace=namespace, body=resource)
            self._wait_for_deployment_ready(name, namespace)
            time.sleep(sleep)
        elif kind == "Service":
            if self._resource_exists(self.k8s_core_api.read_namespaced_service, name, namespace):
                raise Exception(f"Service '{name}' already exists in namespace '{namespace}'.")
            self.k8s_core_api.create_namespaced_service(namespace=namespace, body=resource)
        elif kind == "ConfigMap":
            if self._resource_exists(self.k8s_core_api.read_namespaced_config_map, name, namespace):
                raise Exception(f"ConfigMap '{name}' already exists in namespace '{namespace}'.")
            self.k8s_core_api.create_namespaced_config_map(namespace=namespace, body=resource)

    def _undeploy_resource(self, resource):
        kind = resource.get("kind")
        metadata = resource.get("metadata", {})
        namespace = metadata.get("namespace")
        name = metadata.get("name")
        if kind == "Deployment":
            self.k8s_apps_api.delete_namespaced_deployment(name=name, namespace=namespace, grace_period_seconds=0)
        elif kind == "Service":
            self.k8s_core_api.delete_namespaced_service(name=name, namespace=namespace, grace_period_seconds=0)
        elif kind == "ConfigMap":
            self.k8s_core_api.delete_namespaced_config_map(name=name, namespace=namespace)

    def _resource_exists(self, read_func, name, namespace):
        try:
            read_func(name=name, namespace=namespace)
            return True
        except ApiException as e:
            if e.status == 404:
                return False
            raise

    def _wait_for_deployment_ready(self, name, namespace):
        while True:
            api_response = self.k8s_apps_api.read_namespaced_deployment_status(name=name, namespace=namespace, pretty=True)
            if api_response.status.ready_replicas == api_response.status.replicas:
                break
            time.sleep(1) 