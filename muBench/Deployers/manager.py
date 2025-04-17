"""
K8sDeploymentManager: Main API for managing K8s microservice deployments.
"""
from .builder import K8sYamlBuilder
from .deployer import K8sYamlDeployer
import os
import shutil
import datetime
from kubernetes import client, config
from kubernetes.client.rest import ApiException
import json

class K8sDeploymentManager:
    """
    Manages the lifecycle of a K8s microservice deployment from a workmodel and configuration options.
    All configuration options are explicit arguments, with defaults from Configs/K8sParameters.json.
    """
    RESERVED_NAMESPACES = {"kube-system", "monitoring", "default", "kube-public", "kube-node-lease"}

    def __init__(
        self,
        workmodel: dict,
        prefix_yaml_file: str = "mubench",
        namespace: str = "default",
        image: str = "msvcbench/microservice:latest",
        cluster_domain: str = "cluster",
        path: str = "/api/v1",
        dns_resolver: str = "kube-dns.kube-system.svc.cluster.local",
        scheduler_name: str = "default-scheduler",
        sleep: int = 0,
        nginx_gw: bool = True,
        nginx_svc_type: str = "NodePort",
        no_apply: bool = False,
        internal_service_functions_path: str = "CustomFunctions",
        output_dir: str = "SimulationWorkspace"
    ):
        self.workmodel = workmodel
        self.prefix_yaml_file = prefix_yaml_file
        self.namespace = namespace
        self.image = image
        self.cluster_domain = cluster_domain
        self.path = path
        self.dns_resolver = dns_resolver
        self.scheduler_name = scheduler_name
        self.sleep = sleep
        self.nginx_gw = nginx_gw
        self.nginx_svc_type = nginx_svc_type
        self.no_apply = no_apply
        self.internal_service_functions_path = internal_service_functions_path
        self.output_dir = output_dir
        self.deployment_dir = None  # Will be set on deploy
        self.nfs_conf = dict()  # Placeholder for NFS config if needed

    def _create_unique_deployment_dir(self):
        os.makedirs(self.output_dir, exist_ok=True)
        ns_dir = os.path.join(self.output_dir, self.namespace)
        os.makedirs(os.path.join(ns_dir, "yamls"), exist_ok=True)
        self.deployment_dir = ns_dir
        # Save deployment parameters for reproducibility
        params = {
            "workmodel": self.workmodel,
            "prefix_yaml_file": self.prefix_yaml_file,
            "namespace": self.namespace,
            "image": self.image,
            "cluster_domain": self.cluster_domain,
            "path": self.path,
            "dns_resolver": self.dns_resolver,
            "scheduler_name": self.scheduler_name,
            "sleep": self.sleep,
            "nginx_gw": self.nginx_gw,
            "nginx_svc_type": self.nginx_svc_type,
            "no_apply": self.no_apply,
            "internal_service_functions_path": self.internal_service_functions_path,
            "output_dir": self.output_dir
        }
        with open(os.path.join(ns_dir, "k8parameters.json"), "w") as f:
            json.dump(params, f, indent=2)
        return ns_dir

    @classmethod
    def from_deployment_dir(cls, deployment_dir):
        """
        Alternative constructor: initialize manager from a deployment directory containing k8parameters.json
        """
        params_path = os.path.join(deployment_dir, "k8parameters.json")
        if not os.path.exists(params_path):
            raise RuntimeError(f"k8parameters.json not found in {deployment_dir}")
        with open(params_path, "r") as f:
            params = json.load(f)
        # Remove deployment_dir from params to avoid passing it twice
        params.pop("deployment_dir", None)
        instance = cls(**params)
        instance.deployment_dir = deployment_dir
        return instance

    def _generate_yamls(self):
        builder = K8sYamlBuilder(
            prefix_yaml_file=self.prefix_yaml_file,
            namespace=self.namespace,
            image=self.image,
            cluster_domain=self.cluster_domain,
            path=self.path,
            dns_resolver=self.dns_resolver,
            scheduler_name=self.scheduler_name,
            nginx_gw=self.nginx_gw,
            nginx_svc_type=self.nginx_svc_type,
        )
        builder.customize_workmodel(self.workmodel)
        builder.generate_all_yamls(
            workmodel=self.workmodel,
            nfs_conf=self.nfs_conf,
            output_path=self.deployment_dir,
            internal_service_functions_path=self.internal_service_functions_path
        )
        return os.listdir(os.path.join(self.deployment_dir, "yamls"))

    def _ensure_namespace_exists(self):
        config.load_kube_config()
        k8s_core_api = client.CoreV1Api()
        namespace = self.namespace
        if namespace in self.RESERVED_NAMESPACES:
            raise RuntimeError(
                f"Deployment to reserved namespace '{namespace}' is not allowed. "
                "Please choose a different namespace."
            )
        try:
            k8s_core_api.read_namespace(name=namespace)
        except ApiException as ns_err:
            if ns_err.status == 404:
                ns_body = client.V1Namespace(metadata=client.V1ObjectMeta(name=namespace))
                k8s_core_api.create_namespace(ns_body)
            else:
                raise RuntimeError(f"Failed to ensure namespace '{namespace}': {ns_err}")

    def _namespace_is_occupied(self):
        config.load_kube_config()
        k8s_apps_api = client.AppsV1Api()
        k8s_core_api = client.CoreV1Api()
        namespace = self.namespace
        # Exclude resources with 'istio' or 'kube' in their names (case-insensitive)
        def is_relevant(name):
            lname = name.lower()
            return ('istio' not in lname) and ('kube' not in lname)
        try:
            dep_list = k8s_apps_api.list_namespaced_deployment(namespace=namespace)
            if any(is_relevant(dep.metadata.name) for dep in dep_list.items):
                return True
        except Exception:
            pass
        try:
            svc_list = k8s_core_api.list_namespaced_service(namespace=namespace)
            if any(is_relevant(svc.metadata.name) for svc in svc_list.items):
                return True
        except Exception:
            pass
        try:
            cm_list = k8s_core_api.list_namespaced_config_map(namespace=namespace)
            if any(is_relevant(cm.metadata.name) for cm in cm_list.items):
                return True
        except Exception:
            pass
        return False

    def deploy(self):
        self._ensure_namespace_exists()
        if self._namespace_is_occupied():
            raise RuntimeError(
                f"Namespace '{self.namespace}' is already occupied by existing resources. "
                "No YAMLs will be generated or deployed."
            )
        deployment_dir = self._create_unique_deployment_dir()
        self._generate_yamls()
        yamls_folder = os.path.join(deployment_dir, "yamls")
        if not self.no_apply:
            deployer = K8sYamlDeployer()
            deployer.deploy(yamls_folder, sleep=self.sleep)
        return deployment_dir

    def undeploy(self):
        if not self.deployment_dir:
            raise RuntimeError(
                "No deployment_dir set. "  
                "Deploy first or specify the directory to undeploy."
            )
        yamls_folder = os.path.join(self.deployment_dir, "yamls")
        deployer = K8sYamlDeployer()
        deployer.undeploy(yamls_folder)

    def cleanup(self):
        if self.deployment_dir and os.path.exists(self.deployment_dir):
            shutil.rmtree(self.deployment_dir)
            self.deployment_dir = None
            folder = os.path.dirname(self.deployment_dir)
            if os.path.exists(folder):
                shutil.rmtree(folder)