"""
K8sDeploymentManager: Main API for managing K8s microservice deployments.
"""
from .yaml_based.builder import K8sYamlBuilder
from .deployer import K8sYamlDeployer
import os
import shutil
import datetime
from kubernetes import client, config
from kubernetes.client.rest import ApiException
import json
from mu_bench.utils.pretty_print import print_status, print_error, print_warning

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
        namespace: str = "test",
        image: str = "msvcbench/microservice:latest",
        cluster_domain: str = "cluster",
        path: str = "/api/v1",
        dns_resolver: str = "kube-dns.kube-system.svc.cluster.local",
        scheduler_name: str = "default-scheduler",
        sleep: int = 0,
        nginx_gw: bool = True,
        nginx_svc_type: str = "NodePort",
        no_apply: bool = False,
        output_dir: str = "SimulationWorkspace",
        nginx_node_port: int = 31114,
        istio_injection: bool = False
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
        self.output_dir = output_dir
        self.nginx_node_port = nginx_node_port
        self.istio_injection = istio_injection
        self.deployment_dir = None  # Will be set on deploy
        self.nfs_conf = dict()  # Placeholder for NFS config if needed

    def _prepare_deployment_dir(self):
        # Define the specific path for YAML files
        yamls_target_dir = os.path.join(self.output_dir, "yamls")

        # Clean up the entire yamls directory if it exists
        if os.path.exists(yamls_target_dir):
            print_status(f"Removing existing directory {yamls_target_dir} before YAML generation...")
            try:
                shutil.rmtree(yamls_target_dir)
                print_status(f"Successfully removed {yamls_target_dir}.")
            except OSError as e:
                print_error(f"Error removing directory {yamls_target_dir}: {e}. Proceeding to recreate.")
        
        # Ensure the directory exists for the YAML builder
        # This will create it if it was removed or didn't exist initially
        os.makedirs(yamls_target_dir, exist_ok=True)
        print_status(f"Ensured YAML directory {yamls_target_dir} exists.")
        
        self.deployment_dir = self.output_dir # This is the root for workmodel.json, k8parameters.json
        # Save deployment parameters for reproducibility
        # Note: output_dir is excluded as it should be determined by the deployment directory location
        params = {
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
            "nginx_node_port": self.nginx_node_port,
            "istio_injection": self.istio_injection
        }
        with open(os.path.join(self.output_dir, "k8parameters.json"), "w") as f:
            json.dump(params, f, indent=2)
        return self.output_dir

    @classmethod
    def from_deployment_dir(cls, deployment_dir):
        """
        Alternative constructor: initialize manager from a deployment directory containing k8parameters.json and workmodel.json
        """
        params_path = os.path.join(deployment_dir, "k8parameters.json")
        workmodel_path = os.path.join(deployment_dir, "workmodel.json")
        if not os.path.exists(params_path):
            raise RuntimeError(f"k8parameters.json not found in {deployment_dir}")
        if not os.path.exists(workmodel_path):
            raise RuntimeError(f"workmodel.json not found in {deployment_dir}")
        with open(params_path, "r") as f:
            params = json.load(f)
        with open(workmodel_path, "r") as f:
            workmodel = json.load(f)
        # Remove legacy parameters that shouldn't be in the config
        params.pop("deployment_dir", None)
        params.pop("internal_service_functions_path", None)
        params.pop("output_dir", None)  # output_dir should be the deployment_dir
        # Set output_dir to the deployment directory
        params["output_dir"] = deployment_dir
        instance = cls(workmodel=workmodel, **params)
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
            nginx_node_port=self.nginx_node_port
        )
        builder.customize_and_generate_yamls(
            workmodel=self.workmodel,
            nfs_conf=self.nfs_conf,
            output_path=self.deployment_dir
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
        # Istio injection label if requested
        if self.istio_injection:
            try:
                body = {"metadata": {"labels": {"istio-injection": "enabled"}}}
                k8s_core_api.patch_namespace(name=namespace, body=body)
                print_status(f"Labeled namespace '{namespace}' with istio-injection=enabled.")
            except Exception as e:
                print_warning(f"Failed to label namespace '{namespace}' for Istio injection: {e}")

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

    def _nginx_nodeport_is_available(self):
        """
        Checks if the desired nginx_node_port is available across all namespaces.
        Returns True if available, False if in use.
        """
        config.load_kube_config()
        k8s_core_api = client.CoreV1Api()
        desired_port = self.nginx_node_port
        # Only check if nginx_gw is True and NodePort is requested
        if not (self.nginx_gw and self.nginx_svc_type == "NodePort"):
            return True
        try:
            services = k8s_core_api.list_service_for_all_namespaces().items
            for svc in services:
                if svc.spec.type == "NodePort" and svc.spec.ports:
                    for port in svc.spec.ports:
                        if port.node_port == desired_port:
                            print_error(
                                f"NodePort {desired_port} is already in use by service '{svc.metadata.name}' in namespace '{svc.metadata.namespace}'."
                            )
                            return False
            return True
        except Exception as e:
            print_warning(f"Failed to check NodePort availability: {e}")
            return False

    def deploy(self):
        try:
            print_status(f"Ensuring namespace '{self.namespace}' exists...")
            self._ensure_namespace_exists()
            if self._namespace_is_occupied():
                print_error(
                    f"Namespace '{self.namespace}' is already occupied by existing resources. "
                    "No YAMLs will be generated or deployed."
                )
                return None
            # Check NodePort availability before proceeding
            if not self._nginx_nodeport_is_available():
                print_error(f"Aborting deployment due to NodePort conflict.")
                return None
            deployment_dir = self._prepare_deployment_dir()
            print_status(f"Generating YAMLs in '{deployment_dir}/yamls'...")
            self._generate_yamls()
            yamls_folder = os.path.join(deployment_dir, "yamls")
            if not self.no_apply:
                print_status(f"Deploying resources from '{yamls_folder}'...")
                deployer = K8sYamlDeployer()
                try:
                    deployer.deploy(yamls_folder, sleep=self.sleep)
                    print_status("Deployment completed successfully.")
                except Exception as e:
                    print_error(f"Deployment failed: {e}")
                    raise
            else:
                print_warning("YAMLs generated but not applied (no_apply=True).")
            return deployment_dir
        except Exception as e:
            print_error(f"Deployment process failed: {e}")
            raise

    def undeploy(self):
        if not self.deployment_dir:
            print_error(
                "No deployment_dir set. Deploy first or specify the directory to undeploy."
            )
            return
        yamls_folder = os.path.join(self.deployment_dir, "yamls")
        print_status(f"Undeploying resources from '{yamls_folder}'...")
        deployer = K8sYamlDeployer()
        deleted_any = False
        not_found_count = 0
        total_resources = 0
        for yaml_file in deployer._collect_yaml_files(yamls_folder):
            for resource in deployer._load_yaml(yaml_file):
                total_resources += 1
                try:
                    deployer._undeploy_resource(resource)
                    deleted_any = True
                except ApiException as e:
                    if e.status == 404:
                        not_found_count += 1
                    else:
                        print_error(f"Undeployment failed: {e}")
                        raise
        if not deleted_any and not_found_count == total_resources:
            print_status("Nothing to delete: all resources were already removed.")
        elif deleted_any:
            print_status("Undeployment completed successfully.")

    def cleanup(self):
        if self.deployment_dir:
            yamls_dir = os.path.join(self.deployment_dir, "yamls")
            if os.path.exists(yamls_dir):
                try:
                    shutil.rmtree(yamls_dir)
                    print_status(f"Cleaned up yamls directory: {yamls_dir}")
                except Exception as e:
                    print_warning(f"Failed to clean up yamls directory: {e}")