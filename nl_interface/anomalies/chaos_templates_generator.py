#!/usr/bin/env python3
"""
Simple Chaos Benchmark Generator
Creates static benchmark experiments with randomized intensities
"""

import os
import yaml
import random
import subprocess
import tempfile
from typing import Dict, Any, List


INTENSITY_PARAMS = {
    "cpu_stress": {
        "low": {"workers": 1, "load": 50},
        "medium": {"workers": 2, "load": 80},
        "high": {"workers": 4, "load": 95},
        "extreme": {"workers": 16, "load": 100}  # Much more aggressive: 16 workers at 100% load
    },
    "memory_stress": {
        "low": {"workers": 1, "size": "128MB"},
        "medium": {"workers": 1, "size": "512MB"},
        "high": {"workers": 2, "size": "1GB"},
        "extreme": {"workers": 4, "size": "2GB"}
    },
    "network_delay": {
        "low": {"latency": "50ms", "jitter": "10ms"},
        "medium": {"latency": "200ms", "jitter": "50ms"},
        "high": {"latency": "500ms", "jitter": "100ms"},
        "extreme": {"latency": "1000ms", "jitter": "200ms"}
    },
    "network_loss": {
        "low": {"loss": "5"}, "medium": {"loss": "25"},
        "high": {"loss": "50"}, "extreme": {"loss": "80"}
    },
    "network_duplicate": {
        "low": {"duplicate": "10"}, "medium": {"duplicate": "50"},
        "high": {"duplicate": "80"}, "extreme": {"duplicate": "100"}
    },
    "network_corrupt": {
        "low": {"corrupt": "10"}, "medium": {"corrupt": "30"},
        "high": {"corrupt": "60"}, "extreme": {"corrupt": "90"}
    },
    "network_bandwidth": {
        "low": {"rate": "10mbps", "limit": 102400, "buffer": 50000},
        "medium": {"rate": "1mbps", "limit": 20480, "buffer": 10000},
        "high": {"rate": "100kbps", "limit": 2048, "buffer": 1000},
        "extreme": {"rate": "10kbps", "limit": 512, "buffer": 100}
    }
}

FAULT_TYPES = ["cpu_stress", "memory_stress", "pod_failure", "network_delay", 
                           "network_loss", "network_partition", "network_duplicate", 
                           "network_corrupt", "network_bandwidth"]
INTENSITIES = ["low", "medium", "high", "extreme"]


class ChaosBenchmarkGenerator:
    """Generate static benchmark chaos experiments with randomized intensities"""
    
    def __init__(self, namespace: str = "default", app_list: List[str] = None, seed: int = 42):
        self.namespace = namespace
        self.app_list = app_list
        self.seed = seed
        random.seed(seed)
        
        self.benchmark_experiments = []
    
    def create_experiment_template(self, fault_type: str, app: str, intensity: str, chaos_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create a chaos experiment template"""
        name = f"{fault_type}-{app}-{intensity}".replace("_", "-")
        
        # Get targeting configuration
        target_mode = "one"  # Default
        target_value = ""
        if chaos_config:
            target_mode = chaos_config.get("target_mode", "one")
            target_value = chaos_config.get("target_value", "")
        
        base_template = {
            "apiVersion": "chaos-mesh.org/v1alpha1",
            "metadata": {
                "name": name,
                "namespace": self.namespace
            },
            "spec": {
                "mode": target_mode,
                "selector": {
                    "namespaces": [self.namespace],
                    "labelSelectors": {"app": app}
                },
                "duration": "60s"
            }
        }
        
        # Add target value for specific modes
        if target_mode in ["fixed", "fixed-percent", "random-max-percent"] and target_value:
            base_template["spec"]["value"] = target_value
        
        if fault_type in ["cpu_stress", "memory_stress"]:
            base_template["kind"] = "StressChaos"
            stressor_type = fault_type.split("_")[0]
            base_template["spec"]["stressors"] = {
                stressor_type: INTENSITY_PARAMS[fault_type][intensity]
            }
        
        elif fault_type == "pod_failure":
            base_template["kind"] = "PodChaos"
            base_template["spec"]["action"] = "pod-kill"
            base_template["spec"]["duration"] = "30s"
        
        elif fault_type.startswith("network"):
            base_template["kind"] = "NetworkChaos"
            action = fault_type.replace("network_", "")
            base_template["spec"]["action"] = action
            
            if action == "partition":
                base_template["spec"]["direction"] = "both"
                base_template["spec"]["target"] = {
                    "mode": "all",
                    "selector": {"labelSelectors": {"app": "any-service"}}
                }
            elif action in INTENSITY_PARAMS:
                params = INTENSITY_PARAMS[fault_type][intensity]
                base_template["spec"][action] = params
                if action == "delay":
                    base_template["spec"][action]["correlation"] = "100"
                elif action in ["loss", "duplicate", "corrupt"]:
                    base_template["spec"][action]["correlation"] = "100"
        
        return base_template
    
    def generate_static_benchmark(self, max_per_type: int = 5) -> List[Dict[str, Any]]:
        """Generate static benchmark with randomized app-intensity combinations"""
        experiments = []
        
        for fault_type in FAULT_TYPES:
            count = 0
            for app in self.app_list:
                if count >= max_per_type:
                    break
                    
                # Random intensity for each app
                intensity = random.choice(INTENSITIES)
                
                experiment_config = {
                    "name": f"{fault_type}-{app}-{intensity}".replace("_", "-"),
                    "fault_type": fault_type,
                    "app": app,
                    "intensity": intensity,
                    "template": self.create_experiment_template(fault_type, app, intensity)
                }
                
                experiments.append(experiment_config)
                count += 1
        
        self.benchmark_experiments = experiments
        return experiments
    
    def deploy_experiment(self, experiment_config: Dict[str, Any]) -> bool:
        """Deploy a single chaos experiment"""
        try:
            template = experiment_config["template"]
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
                yaml.dump(template, temp_file, default_flow_style=False, sort_keys=False)
                temp_file_path = temp_file.name
            
            # Apply to cluster  
            cmd = f"kubectl apply -f {temp_file_path}"
            result = subprocess.run(cmd.split(), capture_output=True, text=True)
            
            # Clean up temp file
            os.unlink(temp_file_path)
            
            if result.returncode == 0:
                # Verify deployment and check target pods
                self._verify_chaos_deployment(experiment_config)
                return True
            else:
                print(f"❌ Failed to deploy chaos experiment: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Error deploying chaos experiment: {e}")
            return False
    
    def _verify_chaos_deployment(self, experiment_config: Dict[str, Any]):
        """Verify that chaos experiment was deployed and check target pods"""
        try:
            name = experiment_config["name"]
            fault_type = experiment_config["fault_type"]
            template = experiment_config["template"]
            
            # Determine chaos type for verification
            if fault_type in ["cpu_stress", "memory_stress"]:
                chaos_type = "stresschaos"
            elif fault_type == "pod_failure":
                chaos_type = "podchaos"
            else:
                chaos_type = "networkchaos"
            
            # Check if chaos resource exists
            cmd = f"kubectl get {chaos_type} {name} -n {self.namespace} -o yaml"
            result = subprocess.run(cmd.split(), capture_output=True, text=True)
            
            if result.returncode == 0:
                # Parse the status if available
                try:
                    import yaml
                    chaos_obj = yaml.safe_load(result.stdout)
                    status = chaos_obj.get('status', {})
                except Exception as e:
                    pass
            else:
                return
            
            # Check target pods
            target_app = template['spec']['selector']['labelSelectors']['app']
            
            pod_cmd = f"kubectl get pods -n {self.namespace} -l app={target_app} -o wide"
            pod_result = subprocess.run(pod_cmd.split(), capture_output=True, text=True)
            
            if pod_result.returncode == 0:
                # Count pods
                pod_lines = [line for line in pod_result.stdout.split('\n') if line.strip() and not line.startswith('NAME')]
                pod_count = len(pod_lines)
                
                if pod_count == 0:
                    all_pods_cmd = f"kubectl get pods -n {self.namespace} --show-labels"
                    all_pods_result = subprocess.run(all_pods_cmd.split(), capture_output=True, text=True)
                    if all_pods_result.returncode == 0:
                        pass
        except Exception as e:
            pass
    
    def undeploy_experiment(self, experiment_config: Dict[str, Any]) -> bool:
        """Undeploy/clean up a chaos experiment"""
        try:
            name = experiment_config["name"]
            fault_type = experiment_config["fault_type"]
            
            # Determine chaos type
            if fault_type in ["cpu_stress", "memory_stress"]:
                chaos_type = "stresschaos"
            elif fault_type == "pod_failure":
                chaos_type = "podchaos"
            else:
                chaos_type = "networkchaos"
            
            # Delete experiment
            cmd = f"kubectl delete {chaos_type} {name} -n {self.namespace} --ignore-not-found=true"
            result = subprocess.run(cmd.split(), capture_output=True, text=True)
            
            print(f"🧹 Cleaned up: {name}")
            return True
            
        except Exception as e:
            print(f"❌ Error cleaning up {experiment_config['name']}: {e}")
            return False