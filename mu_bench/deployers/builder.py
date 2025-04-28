import os
import yaml
import json
from jinja2 import Environment, FileSystemLoader
from copy import deepcopy
from collections import defaultdict
from .expander import expand_workmodel


def indent_block(text, spaces=2):
    pad = ' ' * spaces
    return ''.join(pad + line if line.strip() else line for line in text.splitlines(True))

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
        nginx_node_port: int = 31114,
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
        self.nginx_node_port = nginx_node_port
        self.K8s_YAML_BUILDER_PATH = os.path.dirname(os.path.abspath(__file__))
        self.env = Environment(
            loader=FileSystemLoader(f"{self.K8s_YAML_BUILDER_PATH}/templates"),
            trim_blocks=True,
            lstrip_blocks=True
        )
        self.env.filters['indent'] = indent_block

    def _write_yaml(self, path, content):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)

    def _build_resource_block(self, service_conf, counter):
        resources = {}
        rank_string = str(counter).zfill(5)
        if "cpu-requests" in service_conf:
            cpu_req = service_conf["cpu-requests"]
            resources.setdefault('requests', {})['cpu'] = cpu_req
            if 'm' in cpu_req:
                rank_string = str(int(cpu_req.replace('m', ''))).zfill(5)
            else:
                rank_string = str(int(float(cpu_req) * 1000)).zfill(5)
        if "memory-requests" in service_conf:
            mem_req = service_conf["memory-requests"]
            resources.setdefault('requests', {})['memory'] = mem_req
        if "cpu-limits" in service_conf:
            resources.setdefault('limits', {})['cpu'] = service_conf['cpu-limits']
        if "memory-limits" in service_conf:
            resources.setdefault('limits', {})['memory'] = service_conf['memory-limits']
        return resources, rank_string

    def _build_node_affinity(self, values):
        if not values:
            return None
        return {
            'affinity': {
                'nodeAffinity': {
                    'requiredDuringSchedulingIgnoredDuringExecution': {
                        'nodeSelectorTerms': [{
                            'matchExpressions': [{
                                'key': 'kubernetes.io/hostname',
                                'operator': 'In',
                                'values': values
                            }]
                        }]
                    }
                }
            }
        }

    def _build_pod_antiaffinity(self, service):
        return {
            'affinity': {
                'podAntiAffinity': {
                    'requiredDuringSchedulingIgnoredDuringExecution': [{
                        'labelSelector': {
                            'matchExpressions': [{
                                'key': 'app',
                                'operator': 'In',
                                'values': [service]
                            }]
                        },
                        'topologyKey': 'kubernetes.io/hostname'
                    }]
                }
            }
        }

    def customize_workmodel(self, workmodel):
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

    def generate_all_yamls(self, workmodel, nfs_conf, output_path, internal_service_functions_path):
        # Expand workmodel expands individual deployments into separate services
        # For example, if the workmodel has a service "s0" with deployments
        # "s0-edge-site-1" and "s0-edge-site-2", the expanded workmodel will have
        # two services: "s0-edge-site-1" and "s0-edge-site-2", each with the same
        # configuration as "s0" but with the deployment name added to the service name.
        # The node_affinity will be set per deployment. This does not affect services 
        # without deployments.
        expanded_workmodel = expand_workmodel(workmodel)

        # Create deployment and service YAML files
        self.create_deployment_service_yaml_files(expanded_workmodel, nfs_conf, output_path)
        
        # Create workmodel configmap
        self.create_configmap_yaml_file(
            workmodel=expanded_workmodel,
            output_path=output_path,
            template_name="ConfigMapWorkmodelTemplate.yaml",
            context={
                "workmodel": '    ' + '    '.join(json.dumps(expanded_workmodel, indent=2).splitlines(True)),
                "namespace": self.namespace
            },
            output_suffix="ConfigMapWorkmodel.yaml"
        )

        # Create internal services configmap
        self.create_configmap_yaml_file(
            workmodel=None,
            output_path=output_path,
            template_name="ConfigMapInternalServicesTemplate.yaml",
            context={
                "data": self._get_internal_service_data(internal_service_functions_path),
                "namespace": self.namespace
            },
            output_suffix="ConfigMapInternalServices.yaml"
        )

        # Create nginx gateway files
        if self.nginx_gw:
            self.create_nginx_gateway_files(output_path)

    def create_deployment_service_yaml_files(self, workmodel, nfs, output_path):
        for counter, (service, conf) in enumerate(workmodel.items(), 1):
            # Deployment YAML
            resources, rank_string = self._build_resource_block(conf, counter)
            node_affinity = self._build_node_affinity(conf.get("node_affinity"))
            pod_antiaffinity = self._build_pod_antiaffinity(service) if conf.get('pod_antiaffinity') else None
            template = self.env.get_template("DeploymentTemplate.yaml")
            content = template.render(
                service_name=service,
                namespace=self.namespace,
                scheduler_name=self.scheduler_name,
                image=self.image,
                replicas=conf.get("replicas", 1),
                node_affinity=yaml.dump(node_affinity) if node_affinity else None,
                pod_antiaffinity=yaml.dump(pod_antiaffinity) if pod_antiaffinity else None,
                sidecar=conf.get("sidecar", None),
                pn=str(conf.get('workers', 1)),
                tn=str(conf.get('threads', 4)),
                resources=yaml.dump(resources) if resources else '{}'
            )
            deployment_filename = (
                f"{output_path}/yamls/"
                f"{self.prefix_yaml_file}-"
                f"{str(rank_string).zfill(3)}-"
                f"Deployment-{service}.yaml"
            )
            self._write_yaml(deployment_filename, content)
            
            # Service YAML
            service_template = self.env.get_template("ServiceTemplate.yaml")
            service_content = service_template.render(
                service_name=service,
                namespace=self.namespace
            )
            service_filename = (
                f"{output_path}/yamls/"
                f"{self.prefix_yaml_file}-"
                f"{str(rank_string).zfill(3)}-"
                f"Service-{service}.yaml"
            )
            self._write_yaml(service_filename, service_content)

    def create_configmap_yaml_file(self, workmodel, output_path, template_name, context, output_suffix):
        template = self.env.get_template(template_name)
        content = template.render(**context)
        output_file = (
            f"{output_path}/yamls/"
            f"{self.prefix_yaml_file}-{output_suffix}"
        )
        self._write_yaml(output_file, content)

    def _get_internal_service_data(self, internal_service_functions_path):
        data_dict = {}
        if internal_service_functions_path:
            for file_name in os.listdir(internal_service_functions_path):
                file_path = os.path.join(internal_service_functions_path, file_name)
                if os.path.isfile(file_path):
                    with open(file_path, 'r') as f:
                        data_dict[file_name] = f.read()
        return json.dumps(data_dict, indent=2)

    def create_nginx_gateway_files(self, output_path):
        configmap_template = self.env.get_template("ConfigMapNginxGwTemplate.yaml")
        config_content = configmap_template.render(
            namespace=self.namespace,
            path=self.path,
            resolver=self.dns_resolver
        )
        configmap_output = (
            f"{output_path}/yamls/"
            f"{self.prefix_yaml_file}-ConfigMapNginxGw.yaml"
        )
        self._write_yaml(configmap_output, config_content)
        deployment_template = self.env.get_template("DeploymentNginxGwTemplate.yaml")
        deploy_content = deployment_template.render(
            namespace=self.namespace,
            svc_type=self.nginx_svc_type,
            nginx_node_port=self.nginx_node_port,
            scheduler_name=self.scheduler_name
        )
        deployment_output = (
            f"{output_path}/yamls/"
            f"{self.prefix_yaml_file}-DeploymentNginxGw.yaml"
        )
        self._write_yaml(deployment_output, deploy_content)

    def customize_and_generate_yamls(self, workmodel, nfs_conf, output_path, internal_service_functions_path):
        self.customize_workmodel(workmodel)
        self.generate_all_yamls(
            workmodel=workmodel,
            nfs_conf=nfs_conf,
            output_path=output_path,
            internal_service_functions_path=internal_service_functions_path
        ) 