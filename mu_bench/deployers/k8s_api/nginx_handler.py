from typing import Dict, Any, Optional, List
from kubernetes import client
from kubernetes.client.rest import ApiException


class NginxGatewayHandler:
    """
    Handles creation and management of Nginx Gateway resources
    """
    
    def __init__(
        self, 
        core_v1_api: client.CoreV1Api, 
        apps_v1_api: client.AppsV1Api,
        namespace: str,
        dns_resolver: str = "kube-dns.kube-system.svc.cluster.local",
        path: str = "/api/v1",
        nginx_svc_type: str = "NodePort",
        nginx_node_port: int = 31114,
        scheduler_name: str = "default-scheduler",
        dry_run: bool = False
    ):
        self.core_v1 = core_v1_api
        self.apps_v1 = apps_v1_api
        self.namespace = namespace
        self.dns_resolver = dns_resolver
        self.path = path
        self.nginx_svc_type = nginx_svc_type
        self.nginx_node_port = nginx_node_port
        self.scheduler_name = scheduler_name
        self.dry_run = dry_run
        self.created_resources = []

    def _generate_nginx_config(self) -> str:
        """Generate nginx.conf content for the gateway"""
        nginx_config = f"""user nginx;
worker_processes  1;
error_log  /etc/nginx/error.log;
events {{
  worker_connections  10240;
}}
http {{
    log_format  main
    '[GATEWAY] - '
    '$remote_addr - - '
    '[$time_local] '
    '"$request_method '
    '$request_uri" '
    '$status -'
    ' http:/$request_uri.{self.namespace}.svc.cluster.local';

    access_log  /etc/nginx/access.log main;
    access_log on;

    server {{
            listen       80;
            server_name  _;
            location / {{
                proxy_read_timeout 5m;
                proxy_connect_timeout 5m;
                proxy_send_timeout 5m;
                resolver {self.dns_resolver};
                proxy_pass http:/$request_uri.{self.namespace}.svc.cluster.local{self.path};
                proxy_http_version 1.1;
            }}
            location ~* /update$ {{
                resolver {self.dns_resolver};
                rewrite ^(/.*)/update$ /update break;
                proxy_pass http:/$1.{self.namespace}.svc.cluster.local;
                proxy_http_version 1.1;
            }}
    }}
}}"""
        return nginx_config

    def create_nginx_configmap(self) -> Optional[client.V1ConfigMap]:
        """Create ConfigMap for nginx gateway configuration"""
        try:
            nginx_config = self._generate_nginx_config()
            
            configmap = client.V1ConfigMap(
                api_version="v1",
                kind="ConfigMap",
                metadata=client.V1ObjectMeta(
                    name="gw-nginx",
                    namespace=self.namespace
                ),
                data={"nginx.conf": nginx_config}
            )
            
            dry_run_param = "All" if self.dry_run else None
            
            result = self.core_v1.create_namespaced_config_map(
                namespace=self.namespace,
                body=configmap,
                dry_run=dry_run_param
            )
            
            if not self.dry_run:
                self.created_resources.append("gw-nginx-configmap")
                print(f"✅ Created Nginx ConfigMap: gw-nginx")
            else:
                print(f"🧪 Dry run - Nginx ConfigMap would be created: gw-nginx")
            
            return result
            
        except ApiException as e:
            print(f"❌ Failed to create Nginx ConfigMap: {e}")
            if not self.dry_run:
                raise
            return None

    def create_nginx_deployment(self) -> Optional[client.V1Deployment]:
        """Create Deployment for nginx gateway"""
        try:
            # Container specification
            container = client.V1Container(
                name="gw-nginx",
                image="nginx",
                ports=[
                    client.V1ContainerPort(
                        name="http-nginx",
                        container_port=80
                    )
                ],
                volume_mounts=[
                    client.V1VolumeMount(
                        name="config-volume",
                        mount_path="/etc/nginx/nginx.conf",
                        sub_path="nginx.conf",
                        read_only=True
                    ),
                    client.V1VolumeMount(
                        name="log",
                        mount_path="/var/log/nginx"
                    )
                ]
            )

            # Volumes
            volumes = [
                client.V1Volume(
                    name="config-volume",
                    config_map=client.V1ConfigMapVolumeSource(
                        name="gw-nginx"
                    )
                ),
                client.V1Volume(
                    name="log",
                    empty_dir=client.V1EmptyDirVolumeSource()
                )
            ]

            # Pod template spec
            pod_spec = client.V1PodSpec(
                containers=[container],
                volumes=volumes,
                scheduler_name=self.scheduler_name
            )

            # Pod template
            pod_template = client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(
                    labels={
                        "app": "gw-nginx",
                        "version": "1.0"
                    }
                ),
                spec=pod_spec
            )

            # Deployment spec
            deployment_spec = client.V1DeploymentSpec(
                replicas=1,
                selector=client.V1LabelSelector(
                    match_labels={"app": "gw-nginx"}
                ),
                template=pod_template
            )

            # Deployment
            deployment = client.V1Deployment(
                api_version="apps/v1",
                kind="Deployment",
                metadata=client.V1ObjectMeta(
                    name="gw-nginx",
                    namespace=self.namespace,
                    labels={
                        "app": "gw-nginx",
                        "version": "1.0"
                    }
                ),
                spec=deployment_spec
            )

            dry_run_param = "All" if self.dry_run else None
            
            result = self.apps_v1.create_namespaced_deployment(
                namespace=self.namespace,
                body=deployment,
                dry_run=dry_run_param
            )
            
            if not self.dry_run:
                self.created_resources.append("gw-nginx-deployment")
                print(f"✅ Created Nginx Deployment: gw-nginx")
            else:
                print(f"🧪 Dry run - Nginx Deployment would be created: gw-nginx")
            
            return result
            
        except ApiException as e:
            print(f"❌ Failed to create Nginx Deployment: {e}")
            if not self.dry_run:
                raise
            return None

    def create_nginx_service(self) -> Optional[client.V1Service]:
        """Create Service for nginx gateway"""
        try:
            # Service ports
            if self.nginx_svc_type == "NodePort":
                ports = [
                    client.V1ServicePort(
                        name="http-nginx",
                        port=80,
                        protocol="TCP",
                        target_port=80,
                        node_port=self.nginx_node_port
                    )
                ]
            else:
                ports = [
                    client.V1ServicePort(
                        name="http-nginx",
                        port=80,
                        protocol="TCP",
                        target_port=80
                    )
                ]

            # Service
            service = client.V1Service(
                api_version="v1",
                kind="Service",
                metadata=client.V1ObjectMeta(
                    name="gw-nginx",
                    namespace=self.namespace
                ),
                spec=client.V1ServiceSpec(
                    type=self.nginx_svc_type,
                    ports=ports,
                    selector={"app": "gw-nginx"}
                )
            )

            dry_run_param = "All" if self.dry_run else None
            
            result = self.core_v1.create_namespaced_service(
                namespace=self.namespace,
                body=service,
                dry_run=dry_run_param
            )
            
            if not self.dry_run:
                self.created_resources.append("gw-nginx-service")
                print(f"✅ Created Nginx Service: gw-nginx")
            else:
                print(f"🧪 Dry run - Nginx Service would be created: gw-nginx")
            
            return result
            
        except ApiException as e:
            print(f"❌ Failed to create Nginx Service: {e}")
            if not self.dry_run:
                raise
            return None

    def create_all_nginx_resources(self) -> Dict[str, Any]:
        """Create all nginx gateway resources"""
        results = {}
        
        # Create ConfigMap first (required by deployment)
        results['configmap'] = self.create_nginx_configmap()
        
        # Create Deployment
        results['deployment'] = self.create_nginx_deployment()
        
        # Create Service
        results['service'] = self.create_nginx_service()
        
        return results

    def get_created_resources(self) -> List[str]:
        """Return list of created nginx resources"""
        return self.created_resources 