import requests
import csv
import time
import os
import yaml
from pathlib import Path

class MetricsLogger:
    def __init__(self):
        # Load configuration from YAML
        self.config = self.load_config()
        self.prometheus_url = self.config['monitoring']['prometheus_url']
        self.metrics = self.config['monitoring']['metrics']
        self.logging = self.config['monitoring']['logging']
        self.filepaths = None

    def load_config(self):
        """Load configuration from YAML file."""
        config_path = Path(__file__).parent.parent.parent / "config.yaml"
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    def setup_experiment_directory(self):
        """Set up the directory for the experiment and create the necessary files with headers."""
        timestr = time.strftime("%Y%m%d-%H%M%S")
        experiment_folder = 'experiment_' + timestr
        folder = os.path.join(self.logging['base_folder'], experiment_folder)
        
        if not os.path.exists(folder):
            os.makedirs(folder)

        # Create the files with headers
        self.filepaths = {
            'node_cpu': os.path.join(folder, self.metrics['node_cpu_file']),
            'node_memory': os.path.join(folder, self.metrics['node_memory_file']),
            'pod_cpu': os.path.join(folder, self.metrics['pod_cpu_file']),
            'pod_memory': os.path.join(folder, self.metrics['pod_memory_file'])
        }

        # Create files with headers
        for key, filepath in self.filepaths.items():
            if not os.path.isfile(filepath):
                with open(filepath, mode='w', newline='') as file:
                    writer = csv.writer(file)
                    if 'pod' in key:
                        writer.writerow(self.logging['headers']['pod'])
                    else:
                        writer.writerow(self.logging['headers']['node'])

        return self.filepaths

    def get_metrics(self):
        """Fetch metrics from Prometheus."""
        metrics = {}
        for metric_name, query in self.metrics['queries'].items():
            response = requests.get(
                f"{self.prometheus_url}/api/v1/query",
                params={'query': query}
            )
            if response.status_code == 200:
                metrics[metric_name] = response.json()
            else:
                print(f"Error fetching {metric_name}: {response.status_code}")
        return metrics

    def log_metrics(self):
        """Log metrics to CSV files."""
        filepaths = self.setup_experiment_directory()
        start_time = time.time()

        while True:
            if not self.logging['run_indefinitely'] and time.time() - start_time > self.logging['duration']:
                break

            metrics = self.get_metrics()
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

            # Log node metrics
            for metric_name, data in metrics.items():
                if metric_name.startswith('node_'):
                    with open(filepaths[metric_name], mode='a', newline='') as file:
                        writer = csv.writer(file)
                        for result in data['data']['result']:
                            node_name = result['metric']['instance']
                            value = result['value'][1]
                            writer.writerow([timestamp, node_name, value])

            # Log pod metrics
            for metric_name, data in metrics.items():
                if metric_name.startswith('pod_'):
                    with open(filepaths[metric_name], mode='a', newline='') as file:
                        writer = csv.writer(file)
                        for result in data['data']['result']:
                            pod_name = result['metric']['pod']
                            node_name = result['metric'].get('node', 'unknown')
                            value = result['value'][1]
                            writer.writerow([timestamp, node_name, pod_name, value])

            time.sleep(self.logging['log_interval'])

if __name__ == "__main__":
    logger = MetricsLogger()
    logger.log_metrics()