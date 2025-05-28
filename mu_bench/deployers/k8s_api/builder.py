import json
import os
from copy import deepcopy
from typing import Dict, Any, Optional, List
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from ..expander import expand_workmodel
from .configmap_handler import ConfigMapHandler
from .nginx_handler import NginxGatewayHandler


class K8sApiBuilder:
    """
    Kubernetes API-based deployment builder.
    Creates Kubernetes resources directly via API calls instead of generating YAML files.
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
        dry_run: bool = False
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
        self.dry_run = dry_run
        
        # Initialize Kubernetes API clients
        self._init_k8s_clients()
        
        # Initialize handlers
        self.configmap_handler = ConfigMapHandler(self.core_v1, self.namespace, self.dry_run)
        self.nginx_handler = NginxGatewayHandler(
            self.core_v1, 
            self.apps_v1,
            self.namespace,
            self.dns_resolver,
            self.path,
            self.nginx_svc_type,
            self.nginx_node_port,
            self.scheduler_name,
            self.dry_run
        )
        
        # Track created resources for cleanup
        self.created_resources = {
            'deployments': [],
            'services': [],
            'configmaps': [],
            'hpas': [],
            'nginx_resources': []
        }

    def _init_k8s_clients(self):
        """Initialize Kubernetes API clients"""
        try:
            config.load_kube_config()
        except Exception:
            try:
                config.load_incluster_config()
            except Exception as e:
                raise RuntimeError(f"Failed to load Kubernetes config: {e}")
        
        self.apps_v1 = client.AppsV1Api()
        self.core_v1 = client.CoreV1Api()
        self.autoscaling_v2 = client.AutoscalingV2Api()

    def _build_resource_block(self, service_conf: Dict[str, Any], counter: int) -> tuple[Dict[str, Any], str]:
        """Build resource requests and limits specification"""
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

    def _build_node_affinity(self, affinity_string: Optional[str]) -> Optional[client.V1Affinity]:
        """Build node affinity specification from affinity string"""
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

        return client.V1Affinity(
            node_affinity=client.V1NodeAffinity(
                required_during_scheduling_ignored_during_execution=client.V1NodeSelector(
                    node_selector_terms=[
                        client.V1NodeSelectorTerm(
                            match_expressions=[
                                client.V1NodeSelectorRequirement(
                                    key=key,
                                    operator="In",
                                    values=[value]
                                )
                            ]
                        )
                    ]
                )
            )
        )

    def _build_deployment_spec(self, service_name: str, service_conf: Dict[str, Any], resources: Dict[str, Any]) -> client.V1Deployment:
        """Build Kubernetes Deployment specification"""
        
        # Container environment variables
        env_vars = [
            client.V1EnvVar(name="APP", value=service_name),
            client.V1EnvVar(
                name="ZONE",
                value_from=client.V1EnvVarSource(
                    field_ref=client.V1ObjectFieldSelector(field_path="metadata.labels['zone']")
                )
            ),
            client.V1EnvVar(
                name="K8S_APP",
                value_from=client.V1EnvVarSource(
                    field_ref=client.V1ObjectFieldSelector(field_path="metadata.labels['app']")
                )
            ),
            client.V1EnvVar(name="PN", value=str(service_conf.get('workers', 1))),
            client.V1EnvVar(name="TN", value=str(service_conf.get('threads', 4)))
        ]

        # Volume mounts
        volume_mounts = [
            client.V1VolumeMount(name="podinfo", mount_path="/etc/podinfo"),
            client.V1VolumeMount(name="microservice-workmodel", mount_path="/app/MSConfig"),
            client.V1VolumeMount(name="microservice-internal-services", mount_path="/app/MSConfig/InternalServiceFunctions")
        ]

        # Container ports
        ports = [
            client.V1ContainerPort(name="http-mubpodport", container_port=8080)
        ]

        # Main container
        containers = [
            client.V1Container(
                name=service_name,
                image=self.image,
                ports=ports,
                volume_mounts=volume_mounts,
                env=env_vars,
                resources=client.V1ResourceRequirements(
                    requests=resources.get('requests'),
                    limits=resources.get('limits')
                ) if resources else None
            )
        ]

        # Add sidecar container if specified
        if service_conf.get("sidecar"):
            sidecar_container = client.V1Container(
                name=f"{service_name}-sidecar",
                image=service_conf["sidecar"]
            )
            containers.append(sidecar_container)

        # Volumes
        volumes = [
            client.V1Volume(
                name="podinfo",
                downward_api=client.V1DownwardAPIVolumeSource(
                    items=[
                        client.V1DownwardAPIVolumeFile(
                            path="labels",
                            field_ref=client.V1ObjectFieldSelector(field_path="metadata.labels")
                        ),
                        client.V1DownwardAPIVolumeFile(
                            path="annotations",
                            field_ref=client.V1ObjectFieldSelector(field_path="metadata.annotations")
                        )
                    ]
                )
            ),
            client.V1Volume(
                name="microservice-workmodel",
                config_map=client.V1ConfigMapVolumeSource(name="workmodel")
            ),
            client.V1Volume(
                name="microservice-internal-services",
                config_map=client.V1ConfigMapVolumeSource(name="internal-services")
            )
        ]

        # Pod template spec
        pod_spec = client.V1PodSpec(
            containers=containers,
            volumes=volumes,
            termination_grace_period_seconds=3,
            scheduler_name=self.scheduler_name,
            affinity=self._build_node_affinity(service_conf.get("node_affinity"))
        )

        # Pod template
        pod_template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(
                labels={
                    "zone": "default",
                    "app": service_name,
                    "version": "1.0",
                    "prometheus.io/scrape": "true"
                },
                annotations={
                    "prometheus.io/scrape": "true",
                    "prometheus.io/port": "8080"
                }
            ),
            spec=pod_spec
        )

        # Deployment spec
        deployment_spec = client.V1DeploymentSpec(
            replicas=service_conf.get("replicas", 1),
            selector=client.V1LabelSelector(
                match_labels={"app": service_name}
            ),
            template=pod_template
        )

        # Deployment
        deployment = client.V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=client.V1ObjectMeta(
                name=service_name,
                namespace=self.namespace,
                labels={
                    "zone": "default",
                    "app": service_name,
                    "version": "1.0"
                },
                annotations={"something": "something"}
            ),
            spec=deployment_spec
        )

        return deployment

    def _build_service_spec(self, service_name: str) -> client.V1Service:
        """Build Kubernetes Service specification"""
        
        ports = [
            client.V1ServicePort(
                name="http-mubserviceport",
                port=80,
                target_port=8080
            ),
            client.V1ServicePort(
                name="grpc-mubserviceport",
                port=51313,
                target_port=51313
            )
        ]

        service = client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=client.V1ObjectMeta(
                name=service_name,
                namespace=self.namespace,
                labels={"app": service_name}
            ),
            spec=client.V1ServiceSpec(
                type="ClusterIP",
                ports=ports,
                selector={"app": service_name}
            )
        )

        return service

    def _build_hpa_spec(self, service_name: str, autoscaling_config: Dict[str, Any]) -> client.V2HorizontalPodAutoscaler:
        """Build Horizontal Pod Autoscaler specification"""
        
        # Metrics configuration
        metrics = [
            client.V2MetricSpec(
                type="Resource",
                resource=client.V2ResourceMetricSource(
                    name=autoscaling_config.get("metric", "cpu"),
                    target=client.V2MetricTarget(
                        type="Utilization",
                        average_utilization=autoscaling_config.get("target", 70)
                    )
                )
            )
        ]

        hpa = client.V2HorizontalPodAutoscaler(
            api_version="autoscaling/v2",
            kind="HorizontalPodAutoscaler",
            metadata=client.V1ObjectMeta(
                name=f"{service_name}-autoscaler",
                namespace=self.namespace
            ),
            spec=client.V2HorizontalPodAutoscalerSpec(
                scale_target_ref=client.V2CrossVersionObjectReference(
                    api_version="apps/v1",
                    kind="Deployment",
                    name=service_name
                ),
                min_replicas=autoscaling_config.get("min", 1),
                max_replicas=autoscaling_config.get("max", 10),
                metrics=metrics
            )
        )

        return hpa

    def customize_workmodel(self, workmodel: Dict[str, Any]):
        """Customize workmodel with URL and other service-specific settings"""
        for service in workmodel:
            base_url = f"{service}.{self.namespace}.svc.{self.cluster_domain}.local"
            workmodel[service].update({
                "url": base_url,
                "path": self.path,
                "image": self.image,
                "namespace": self.namespace
            })

    def create_deployment(self, service_name: str, service_conf: Dict[str, Any], counter: int) -> Optional[client.V1Deployment]:
        """Create a Kubernetes deployment"""
        try:
            resources, rank_string = self._build_resource_block(service_conf, counter)
            deployment = self._build_deployment_spec(service_name, service_conf, resources)
            
            dry_run_param = "All" if self.dry_run else None
            
            result = self.apps_v1.create_namespaced_deployment(
                namespace=self.namespace,
                body=deployment,
                dry_run=dry_run_param
            )
            
            if not self.dry_run:
                self.created_resources['deployments'].append(service_name)
                print(f"✅ Created deployment: {service_name}")
            else:
                print(f"🧪 Dry run - deployment would be created: {service_name}")
            
            return result
            
        except ApiException as e:
            print(f"❌ Failed to create deployment {service_name}: {e}")
            if not self.dry_run:
                raise
            return None

    def create_service(self, service_name: str, service_conf: Dict[str, Any]) -> Optional[client.V1Service]:
        """Create a Kubernetes service"""
        try:
            service = self._build_service_spec(service_name)
            
            dry_run_param = "All" if self.dry_run else None
            
            result = self.core_v1.create_namespaced_service(
                namespace=self.namespace,
                body=service,
                dry_run=dry_run_param
            )
            
            if not self.dry_run:
                self.created_resources['services'].append(service_name)
                print(f"✅ Created service: {service_name}")
            else:
                print(f"🧪 Dry run - service would be created: {service_name}")
            
            return result
            
        except ApiException as e:
            print(f"❌ Failed to create service {service_name}: {e}")
            if not self.dry_run:
                raise
            return None

    def create_hpa(self, service_name: str, autoscaling_config: Dict[str, Any]) -> Optional[client.V2HorizontalPodAutoscaler]:
        """Create a Horizontal Pod Autoscaler"""
        try:
            hpa = self._build_hpa_spec(service_name, autoscaling_config)
            
            dry_run_param = "All" if self.dry_run else None
            
            result = self.autoscaling_v2.create_namespaced_horizontal_pod_autoscaler(
                namespace=self.namespace,
                body=hpa,
                dry_run=dry_run_param
            )
            
            if not self.dry_run:
                self.created_resources['hpas'].append(service_name)
                print(f"✅ Created HPA: {service_name}-autoscaler")
            else:
                print(f"🧪 Dry run - HPA would be created: {service_name}-autoscaler")
            
            return result
            
        except ApiException as e:
            print(f"❌ Failed to create HPA {service_name}: {e}")
            if not self.dry_run:
                raise
            return None

    def generate_all_resources(
        self, 
        workmodel: Dict[str, Any], 
        nfs_conf: Dict[str, Any]
    ) -> Dict[str, List]:
        """
        Generate all Kubernetes resources.
        This is the main method that replaces generate_all_yamls.
        """
        # Expand workmodel
        expanded_workmodel = expand_workmodel(workmodel)
        
        # Create deployment and service resources
        self.create_deployment_service_resources(expanded_workmodel)
        
        # Create ConfigMaps using the handler - use absolute path
        custom_functions_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "custom_functions")
        self.configmap_handler.create_workmodel_configmap(expanded_workmodel)
        self.configmap_handler.create_internal_services_configmap(custom_functions_path)
        
        # Update our tracking with ConfigMap results
        self.created_resources['configmaps'].extend(self.configmap_handler.get_created_resources())
        
        # Create nginx gateway resources
        if self.nginx_gw:
            nginx_results = self.nginx_handler.create_all_nginx_resources()
            self.created_resources['nginx_resources'].extend(self.nginx_handler.get_created_resources())
        
        return self.created_resources

    def create_deployment_service_resources(self, workmodel: Dict[str, Any]):
        """Create deployments and services for all microservices"""
        for counter, (service_name, service_conf) in enumerate(workmodel.items(), 1):
            
            # Create deployment
            self.create_deployment(service_name, service_conf, counter)
            
            # Create service
            self.create_service(service_name, service_conf)
            
            # Create HPA if autoscaling is enabled
            autoscaling = service_conf.get("autoscaling", {})
            if autoscaling.get("enabled"):
                self.create_hpa(service_name, autoscaling)

    def customize_and_generate_resources(
        self, 
        workmodel: Dict[str, Any], 
        nfs_conf: Dict[str, Any]
    ) -> Dict[str, List]:
        """
        Main entry point that mirrors the YAML builder's customize_and_generate_yamls method
        """
        self.customize_workmodel(workmodel)
        return self.generate_all_resources(
            workmodel=workmodel,
            nfs_conf=nfs_conf
        )

    def cleanup_resources(self):
        """Clean up all created resources"""
        # This would delete all resources that were created
        # Useful for testing and cleanup
        print("🚧 Resource cleanup not yet implemented")
        pass 