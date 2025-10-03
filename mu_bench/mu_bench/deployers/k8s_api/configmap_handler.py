import json
import os
from typing import Dict, Any, Optional
from kubernetes import client
from kubernetes.client.rest import ApiException


class ConfigMapHandler:
    """
    Handles creation and management of Kubernetes ConfigMaps
    """
    
    def __init__(self, core_v1_api: client.CoreV1Api, namespace: str, dry_run: bool = False):
        self.core_v1 = core_v1_api
        self.namespace = namespace
        self.dry_run = dry_run
        self.created_configmaps = []

    def create_configmap(self, name: str, data: Dict[str, str]) -> Optional[client.V1ConfigMap]:
        """Create a Kubernetes ConfigMap"""
        try:
            configmap = client.V1ConfigMap(
                api_version="v1",
                kind="ConfigMap",
                metadata=client.V1ObjectMeta(
                    name=name,
                    namespace=self.namespace
                ),
                data=data
            )
            
            dry_run_param = "All" if self.dry_run else None
            
            result = self.core_v1.create_namespaced_config_map(
                namespace=self.namespace,
                body=configmap,
                dry_run=dry_run_param
            )
            
            if not self.dry_run:
                self.created_configmaps.append(name)
                print(f"✅ Created ConfigMap: {name}")
            else:
                print(f"🧪 Dry run - ConfigMap would be created: {name}")
            
            return result
            
        except ApiException as e:
            print(f"❌ Failed to create ConfigMap {name}: {e}")
            if not self.dry_run:
                raise
            return None

    def create_workmodel_configmap(self, workmodel: Dict[str, Any]) -> Optional[client.V1ConfigMap]:
        """Create ConfigMap containing the workmodel configuration"""
        workmodel_data = {
            "workmodel.json": json.dumps(workmodel, indent=2)
        }
        return self.create_configmap("workmodel", workmodel_data)

    def create_internal_services_configmap(self, internal_service_functions_path: Optional[str]) -> Optional[client.V1ConfigMap]:
        """Create ConfigMap containing internal service functions"""
        internal_service_data = self._get_internal_service_data(internal_service_functions_path)
        if internal_service_data:
            parsed_data = json.loads(internal_service_data)
            return self.create_configmap("internal-services", parsed_data)
        return None

    def _get_internal_service_data(self, internal_service_functions_path: Optional[str]) -> str:
        """Get internal service function data"""
        data_dict = {}
        if internal_service_functions_path and os.path.exists(internal_service_functions_path):
            for file_name in os.listdir(internal_service_functions_path):
                file_path = os.path.join(internal_service_functions_path, file_name)
                if os.path.isfile(file_path):
                    with open(file_path, 'r') as f:
                        data_dict[file_name] = f.read()
        return json.dumps(data_dict, indent=2)

    def get_created_resources(self):
        """Return list of created ConfigMaps"""
        return self.created_configmaps 