import os
import yaml
import json
from pprint import pprint

SIDECAR_TEMPLATE = """
- name: %s-sidecar
  image: %s
""".strip()

NODE_AFFINITY_TEMPLATE = {
    'affinity': {
        'nodeAffinity': {
            'requiredDuringSchedulingIgnoredDuringExecution': {
                'nodeSelectorTerms': [{
                    'matchExpressions': [{
                        'key': 'kubernetes.io/hostname',
                        'operator': 'In',
                        'values': ['']
                    }]
                }]
            }
        }
    }
}

POD_ANTIAFFINITI_TEMPLATE = {
    'affinity': {
        'podAntiAffinity': {
            'requiredDuringSchedulingIgnoredDuringExecution': [{
                'labelSelector': {
                    'matchExpressions': [{
                        'key': 'app',
                        'operator': 'In',
                        'values': ['']
                    }]
                },
                'topologyKey': 'kubernetes.io/hostname'
            }]
        }
    }
}

class K8sYamlBuilder:
    """
    Utility class for generating Kubernetes YAML files for microservice deployments.
    Accepts all configuration as explicit arguments.
    """
    def __init__(
        self,
        prefix_yaml_file: str = "mubench",
        namespace: str = "default",
        image: str = "msvcbench/microservice:latest",
        cluster_domain: str = "cluster",
        path: str = "/api/v1",
        dns_resolver: str = "kube-dns.kube-system.svc.cluster.local",
        scheduler_name: str = "default-scheduler",
        nginx_gw: bool = True,
        nginx_svc_type: str = "NodePort",
    ):
        self.prefix_yaml_file = prefix_yaml_file
        self.namespace = namespace
        self.image = image
        self.cluster_domain = cluster_domain
        self.path = path
        self.dns_resolver = dns_resolver
        self.scheduler_name = scheduler_name
        self.nginx_gw = nginx_gw
        self.nginx_svc_type = nginx_svc_type
        self.K8s_YAML_BUILDER_PATH = os.path.dirname(os.path.abspath(__file__))

    def customize_workmodel(self, workmodel):
        """
        Override work_model params with those in the builder's configuration.
        """
        for service in workmodel:
            base_url = (
                f"{service}.{self.namespace}"
                f".svc.{self.cluster_domain}.local"
            )
            workmodel[service].update({
                "url": base_url,
                "path": self.path,
                "image": self.image,
                "namespace": self.namespace
            })
            optional_params = [
                "scheduler-name", "replicas", "cpu-requests", "cpu-limits",
                "memory-requests", "memory-limits"
            ]
            for param in optional_params:
                if hasattr(self, param.replace('-', '_')):
                    workmodel[service].update({param: getattr(self, param.replace('-', '_'))})
        print("Work Model Updated!")

    def generate_all_yamls(self, workmodel, nfs_conf, output_path, internal_service_functions_path):
        self.create_deployment_service_yaml_files(workmodel, nfs_conf, output_path)
        self.create_workmodel_configmap_yaml_file(workmodel, nfs_conf, output_path)
        self.create_internalservice_configmap_yaml_file(nfs_conf, output_path, internal_service_functions_path)
        if self.nginx_gw:
            self.create_nginx_gateway_files(output_path)
        print("All YAMLs generated!")

    def create_deployment_service_yaml_files(self, workmodel, nfs, output_path):
        namespace = self.namespace
        counter = 0
        for service in workmodel:
            counter += 1
            with open(f"{self.K8s_YAML_BUILDER_PATH}/Templates/DeploymentTemplate.yaml", "r") as file:
                f = file.read()
                f = f.replace("{{SERVICE_NAME}}", service)
                f = f.replace("{{IMAGE}}", workmodel[service]["image"])
                f = f.replace("{{NAMESPACE}}", namespace)
                scheduler_name = workmodel[service].get("scheduler-name", self.scheduler_name)
                f = f.replace("{{SCHEDULER_NAME}}", str(scheduler_name))
                if "sidecar" in workmodel[service]:
                    sidecar = SIDECAR_TEMPLATE % (service, workmodel[service]["sidecar"])
                    f = f.replace("{{SIDECAR}}", sidecar)
                else:
                    f = f.replace("{{SIDECAR}}", "")
                replicas = workmodel[service].get("replicas", "1")
                f = f.replace("{{REPLICAS}}", str(replicas))
                if "node_affinity" in workmodel[service]:
                    node_affinity = NODE_AFFINITY_TEMPLATE.copy()
                    node_affinity['affinity']['nodeAffinity']['requiredDuringSchedulingIgnoredDuringExecution']['nodeSelectorTerms'][0]['matchExpressions'][0]['values'] = workmodel[service]["node_affinity"]
                    affinity_yaml = str(yaml.dump(node_affinity)).rstrip()
                    f = f.replace("{{NODE_AFFINITY}}", affinity_yaml.replace('\n', '\n   '))
                else:
                    f = f.replace("{{NODE_AFFINITY}}", "")
                if workmodel[service].get('pod_antiaffinity', False):
                    pod_antiaffinity = POD_ANTIAFFINITI_TEMPLATE.copy()
                    pod_antiaffinity['affinity']['podAntiAffinity']['requiredDuringSchedulingIgnoredDuringExecution'][0]['labelSelector']['matchExpressions'][0]['values'] = [service]
                    antiaffinity_yaml = str(yaml.dump(pod_antiaffinity))
                    antiaffinity_yaml = antiaffinity_yaml.replace('\n', '\n        ')
                    f = f.replace("{{POD_ANTIAFFINITY}}", antiaffinity_yaml.rstrip())
                else:
                    f = f.replace("{{POD_ANTIAFFINITY}}", "")
                workers = workmodel[service].get("workers", "1")
                threads = workmodel[service].get("threads", "4")
                f = f.replace("{{PN}}", f"'{workers}'")
                f = f.replace("{{TN}}", f"'{threads}'")
                resource_keys = {"cpu-limits", "memory-limits", "cpu-requests", "memory-requests"}
                if set(workmodel[service].keys()) & resource_keys:
                    resources = []
                    requests = []
                    if "cpu-requests" in workmodel[service]:
                        cpu_req = workmodel[service]["cpu-requests"]
                        requests.append(f"cpu: {cpu_req}")
                        if 'm' in cpu_req:
                            rank_string = str(int(cpu_req.replace('m', ''))).zfill(5)
                        else:
                            rank_string = str(int(float(cpu_req) * 1000)).zfill(5)
                    else:
                        rank_string = str(counter).zfill(5)
                    if "memory-requests" in workmodel[service]:
                        mem_req = workmodel[service]["memory-requests"]
                        requests.append(f"memory: {mem_req}")
                    if requests:
                        resources.append("requests:")
                        resources.extend(f"  {req}" for req in requests)
                    limits = []
                    if "cpu-limits" in workmodel[service]:
                        limits.append(f"cpu: {workmodel[service]['cpu-limits']}")
                    if "memory-limits" in workmodel[service]:
                        limits.append(f"memory: {workmodel[service]['memory-limits']}")
                    if limits:
                        resources.append("limits:")
                        resources.extend(f"  {limit}" for limit in limits)
                    resource_yaml = "\n            ".join(resources)
                    f = f.replace("{{RESOURCES}}", resource_yaml)
                else:
                    f = f.replace("{{RESOURCES}}", "{}")
                    rank_string = str(counter).zfill(5)
            os.makedirs(f"{output_path}/yamls", exist_ok=True)
            deployment_filename = (
                f"{output_path}/yamls/"
                f"{self.prefix_yaml_file}-"
                f"{str(rank_string).zfill(3)}-"
                f"Deployment-{service}.yaml"
            )
            with open(deployment_filename, "w") as file:
                file.write(f)
            service_template_path = (
                f"{self.K8s_YAML_BUILDER_PATH}/Templates/ServiceTemplate.yaml"
            )
            with open(service_template_path, "r") as file:
                f = file.read()
                f = f.replace("{{SERVICE_NAME}}", service)
                f = f.replace("{{NAMESPACE}}", namespace)
            service_filename = (
                f"{output_path}/yamls/"
                f"{self.prefix_yaml_file}-"
                f"{str(rank_string).zfill(3)}-"
                f"Service-{service}.yaml"
            )
            with open(service_filename, "w") as file:
                file.write(f)

    def create_workmodel_configmap_yaml_file(self, workmodel, nfs, output_path):
        namespace = self.namespace
        template_path = (
            f"{self.K8s_YAML_BUILDER_PATH}/Templates/ConfigMapWorkmodelTemplate.yaml"
        )
        with open(template_path, "r") as file:
            content = file.read()
            content = content.replace("{{NAMESPACE}}", namespace)
            workmodel_json = json.dumps(workmodel, indent=2)
            workmodel_json = '    '.join(workmodel_json.splitlines(True))
            content = content.replace("{{WORKMODEL}}", workmodel_json)
        output_file = (
            f"{output_path}/yamls/"
            f"{self.prefix_yaml_file}-ConfigMapWorkmodel.yaml"
        )
        with open(output_file, "w") as file:
            file.write(content)
        print("Workmodel Configmap Created!")

    def create_internalservice_configmap_yaml_file(self, nfs, output_path, internal_service_functions_path):
        namespace = self.namespace
        data_dict = {}
        if internal_service_functions_path:
            for file_name in os.listdir(internal_service_functions_path):
                file_path = os.path.join(internal_service_functions_path, file_name)
                if os.path.isfile(file_path):
                    with open(file_path, 'r') as f:
                        data_dict[file_name] = f.read()
        template_path = (
            f"{self.K8s_YAML_BUILDER_PATH}/Templates/ConfigMapInternalServicesTemplate.yaml"
        )
        with open(template_path, "r") as file:
            content = file.read()
            content = content.replace("{{NAMESPACE}}", namespace)
            data_json = json.dumps(data_dict, indent=2)
            data_json = '  '.join(data_json.splitlines(True))
            content = content.replace("{{DATA}}", data_json)
        output_file = (
            f"{output_path}/yamls/"
            f"{self.prefix_yaml_file}-ConfigMapInternalServices.yaml"
        )
        with open(output_file, "w") as file:
            file.write(content)
        print("Internal-Services Configmap Created!")

    def create_nginx_gateway_files(self, output_path):
        namespace = self.namespace
        configmap_template = (
            f"{self.K8s_YAML_BUILDER_PATH}/Templates/ConfigMapNginxGwTemplate.yaml"
        )
        with open(configmap_template, "r") as file:
            config_content = file.read()
            config_content = config_content.replace("{{NAMESPACE}}", namespace)
            config_content = config_content.replace("{{PATH}}", self.path)
            config_content = config_content.replace("{{RESOLVER}}", self.dns_resolver)
        configmap_output = (
            f"{output_path}/yamls/"
            f"{self.prefix_yaml_file}-ConfigMapNginxGw.yaml"
        )
        with open(configmap_output, "w") as file:
            file.write(config_content)
        deployment_template = (
            f"{self.K8s_YAML_BUILDER_PATH}/Templates/DeploymentNginxGwTemplate.yaml"
        )
        with open(deployment_template, "r") as file:
            deploy_content = file.read()
            deploy_content = deploy_content.replace("{{NAMESPACE}}", namespace)
            deploy_content = deploy_content.replace("{{SVCTYPE}}", self.nginx_svc_type)
            scheduler_name = self.scheduler_name
            deploy_content = deploy_content.replace("{{SCHEDULER_NAME}}", str(scheduler_name))
        deployment_output = (
            f"{output_path}/yamls/"
            f"{self.prefix_yaml_file}-DeploymentNginxGw.yaml"
        )
        with open(deployment_output, "w") as file:
            file.write(deploy_content) 