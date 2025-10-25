import os
import yaml
import json
from jinja2 import Environment, FileSystemLoader
from copy import deepcopy
from collections import defaultdict
from ..expander import expand_workmodel


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

    def _build_node_affinity(self, affinity_string: str | None):
        if not affinity_string or not isinstance(affinity_string, str):
            return None
        
        parts = affinity_string.split('=')
        if len(parts) != 2:
            print(f"Warning: Malformed node_affinity string: '{affinity_string}'. Expected format 'key=value'.")
            return None
        
        key = parts[0].strip()
        value = parts[1].strip()

        if not key or not value:
            print(f"Warning: Malformed node_affinity string: '{affinity_string}'. Key or value is empty.")
            return None

        return {
            'affinity': {
                'nodeAffinity': {
                    'requiredDuringSchedulingIgnoredDuringExecution': {
                        'nodeSelectorTerms': [{
                            'matchExpressions': [{
                                'key': key,
                                'operator': 'In',
                                'values': [value]
                            }]
                        }]
                    }
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

    def generate_all_yamls(self, workmodel, nfs_conf, output_path):
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
        
        # Create Istio ingress (Gateway + VirtualService) YAML files
        self.create_istio_ingress_files(expanded_workmodel, output_path)
        
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

        # Create internal services configmap - use absolute path
        custom_functions_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "custom_functions")
        self.create_configmap_yaml_file(
            workmodel=None,
            output_path=output_path,
            template_name="ConfigMapInternalServicesTemplate.yaml",
            context={
                "data": self._get_internal_service_data(custom_functions_path),
                "namespace": self.namespace
            },
            output_suffix="ConfigMapInternalServices.yaml"
        )

        # Create nginx gateway files
        if self.nginx_gw:
            self.create_nginx_gateway_files(output_path)

    def create_istio_ingress_files(self, expanded_workmodel, output_path):
        """Create Istio Gateway and VirtualService YAMLs covering all services."""
        gateway_tmpl = self.env.get_template("IstioGatewayTemplate.yaml")
        vs_tmpl = self.env.get_template("IstioVirtualServiceTemplate.yaml")

        context = {
            "namespace": self.namespace,
            "gateway_name": "mub-gateway",
            "vs_name": "mub-vs",
            "services": list(expanded_workmodel.keys()),
            "path": self.path,
        }

        gw_content = gateway_tmpl.render(**context)
        vs_content = vs_tmpl.render(**context)

        gw_output = f"{output_path}/yamls/{self.prefix_yaml_file}-IstioGateway.yaml"
        vs_output = f"{output_path}/yamls/{self.prefix_yaml_file}-IstioVirtualService.yaml"
        self._write_yaml(gw_output, gw_content)
        self._write_yaml(vs_output, vs_content)

    def create_deployment_service_yaml_files(self, workmodel, nfs, output_path):
        for counter, (service, conf) in enumerate(workmodel.items(), 1):
            # Resource requests and limits YAML
            resources_dict, rank_string = self._build_resource_block(conf, counter)
            if not resources_dict: 
                resources_content = "{}" 
            else: 
                resources_content = yaml.dump(
                    resources_dict, indent=2, default_flow_style=False
                ).strip()


            # Node affinity YAML
            node_affinity = self._build_node_affinity(conf.get("node_affinity"))

            # Autoscaler YAML (if autoscaling is enabled)
            autoscaling = conf.get("autoscaling", {})
            if autoscaling.get("enabled"):
                self.create_autoscaler_yaml_file(service, autoscaling, output_path, rank_string)

            # Deployment YAML
            template = self.env.get_template("DeploymentTemplate.yaml")
            content = template.render(
                service_name=service,
                namespace=self.namespace,
                scheduler_name=self.scheduler_name,
                image=self.image,
                replicas=conf.get("replicas", 1),
                node_affinity=yaml.dump(node_affinity) if node_affinity else None,
                pod_antiaffinity= None,
                sidecar=conf.get("sidecar", None),
                pn=str(conf.get('workers', 1)),
                tn=str(conf.get('threads', 4)),
                resources_content=resources_content # Pass the fully prepared content string
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


    def create_autoscaler_yaml_file(self, service, autoscaling, output_path, rank_string):
        """
        Generate and write the autoscaler YAML file for a service if autoscaling is enabled.
        """
        autoscaler_template = self.env.get_template("AutoscalerTemplate.yaml")
        autoscaler_content = autoscaler_template.render(
            service_name=service,
            namespace=self.namespace,
            min=autoscaling.get("min", 1),
            max=autoscaling.get("max", 10),
            metric=autoscaling.get("metric", "cpu"),
            target=autoscaling.get("target", 70)
        )
        autoscaler_filename = (
            f"{output_path}/yamls/"
            f"{self.prefix_yaml_file}-"
            f"{str(rank_string).zfill(3)}-"
            f"Autoscaler-{service}.yaml"
        )
        self._write_yaml(autoscaler_filename, autoscaler_content)

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

    def customize_and_generate_yamls(self, workmodel, nfs_conf, output_path):
        self.customize_workmodel(workmodel)
        self.generate_all_yamls(
            workmodel=workmodel,
            nfs_conf=nfs_conf,
            output_path=output_path
        ) 