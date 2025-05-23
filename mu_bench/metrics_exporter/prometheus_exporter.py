import requests
import json
import time
import threading
import csv
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path

class PrometheusExporter:
    def __init__(self, prometheus_url="http://localhost:9090", target_namespaces=None, 
                 collection_interval_minutes=10, metrics_step="30s", output_dir="metrics_data", verbose=True):
        """
        Initializes the PrometheusExporter with interval-based collection.

        Args:
            prometheus_url (str): The base URL of the Prometheus server.
            target_namespaces (str or list/tuple, optional): A single namespace string 
                                  or a list/tuple of namespace strings to filter pod and Istio metrics. 
                                  If None, these metrics are fetched from all relevant namespaces.
            collection_interval_minutes (int): Interval in minutes for triggering metric collections.
            metrics_step (str): Step interval for Prometheus queries (e.g., "30s", "1m").
            output_dir (str): Directory to store CSV files.
            verbose (bool): Whether to print status messages and progress information.
        """
        self.prometheus_url = prometheus_url
        if not self.prometheus_url.startswith(("http://", "https://")):
            self.prometheus_url = "http://" + self.prometheus_url
        
        if target_namespaces:
            if isinstance(target_namespaces, str):
                self.target_namespaces = [target_namespaces]
            elif isinstance(target_namespaces, (list, tuple)):
                self.target_namespaces = list(target_namespaces)
            else:
                raise ValueError("target_namespaces must be a string, list, or tuple of strings")
        else:
            self.target_namespaces = None

        self.collection_interval_minutes = collection_interval_minutes
        self.metrics_step = metrics_step
        self.verbose = verbose
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Threading control
        self._collection_thread = None
        self._stop_event = threading.Event()
        self._is_running = False
        
        # CSV file paths
        self.csv_files = {
            'node_cpu': self.output_dir / 'node_cpu_usage.csv',
            'node_memory': self.output_dir / 'node_memory_usage.csv',
            'pod_cpu': self.output_dir / 'pod_cpu_usage.csv',
            'pod_memory': self.output_dir / 'pod_memory_usage.csv',
            'istio_latency': self.output_dir / 'istio_latency.csv'
        }
        
        # Initialize CSV files with headers
        self._initialize_csv_files()

    def _initialize_csv_files(self):
        """Initialize CSV files with appropriate headers."""
        headers = {
            'node_cpu': ['collection_time', 'timestamp', 'node', 'cpu_cores_used'],
            'node_memory': ['collection_time', 'timestamp', 'node', 'memory_working_set_bytes'],
            'pod_cpu': ['collection_time', 'timestamp', 'namespace', 'pod', 'cpu_cores_used'],
            'pod_memory': ['collection_time', 'timestamp', 'namespace', 'pod', 'memory_usage_bytes'],
            'istio_latency': ['collection_time', 'timestamp', 'namespace', 'pod', 'p95_latency_ms']
        }
        
        for metric_type, filepath in self.csv_files.items():
            if not filepath.exists():
                with open(filepath, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(headers[metric_type])

    def _build_namespace_filter_string(self, filter_key="namespace"):
        """Builds the namespace filter string for PromQL queries based on self.target_namespaces."""
        if not self.target_namespaces:
            return ""
        
        if len(self.target_namespaces) == 1:
            return f'{filter_key}="{self.target_namespaces[0]}"'
        else:
            regex_namespaces = "|".join(self.target_namespaces)
            return f'{filter_key}=~"{regex_namespaces}"'

    def _log(self, message):
        """Print message only if verbose mode is enabled."""
        if self.verbose:
            print(message)

    def _query_prometheus(self, query, is_range_query=False, start_time=None, end_time=None, step='1m'):
        """Internal helper to send a query to Prometheus."""
        if is_range_query:
            if not all([start_time, end_time]):
                self._log("Error: start_time and end_time are required for range queries.")
                return None
            api_endpoint = "/api/v1/query_range"
            
            # Handle both Unix timestamps and datetime objects
            if isinstance(start_time, (int, float)):
                start_time_str = datetime.fromtimestamp(start_time, tz=timezone.utc).isoformat()
            else:
                start_time_str = start_time.isoformat()
                
            if isinstance(end_time, (int, float)):
                end_time_str = datetime.fromtimestamp(end_time, tz=timezone.utc).isoformat()
            else:
                end_time_str = end_time.isoformat()
            
            params = {
                'query': query,
                'start': start_time_str,
                'end': end_time_str,
                'step': step
            }
            timeout = 60
        else:
            api_endpoint = "/api/v1/query"
            params = {'query': query}
            timeout = 30

        try:
            full_url = f"{self.prometheus_url}{api_endpoint}"
            response = requests.get(full_url, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self._log(f"Error querying Prometheus ({full_url}): {e}")
            if hasattr(e, 'response') and e.response is not None:
                self._log(f"Response body: {e.response.text}")
            return None

    def _collect_node_cpu_metrics(self, start_time, end_time, collection_time, rate_window="1m"):
        """Collect node CPU metrics and append to CSV."""
        query = f'sum by (instance) (rate(container_cpu_usage_seconds_total{{image!="", container!="POD"}}[{rate_window}]))'
        data = self._query_prometheus(query, is_range_query=True, start_time=start_time, end_time=end_time, step=self.metrics_step)
        
        if data and data.get('status') == 'success' and data['data']['result']:
            try:
                with open(self.csv_files['node_cpu'], 'a', newline='') as f:
                    writer = csv.writer(f)
                    for item in data['data']['result']:
                        node_id = item['metric'].get('instance', 'unknown_instance').split(':')[0]
                        for ts, val_str in item['values']:
                            writer.writerow([
                                collection_time,
                                int(float(ts)),
                                node_id,
                                round(float(val_str), 3)
                            ])
            except IOError as e:
                self._log(f"Error writing node CPU metrics to CSV: {e}")

    def _collect_node_memory_metrics(self, start_time, end_time, collection_time):
        """Collect node memory metrics and append to CSV."""
        query = f'sum by (instance) (container_memory_working_set_bytes{{image!="", container!="POD"}})'
        data = self._query_prometheus(query, is_range_query=True, start_time=start_time, end_time=end_time, step=self.metrics_step)
        
        if data and data.get('status') == 'success' and data['data']['result']:
            try:
                with open(self.csv_files['node_memory'], 'a', newline='') as f:
                    writer = csv.writer(f)
                    for item in data['data']['result']:
                        node_id = item['metric'].get('instance', 'unknown_instance').split(':')[0]
                        for ts, val_str in item['values']:
                            writer.writerow([
                                collection_time,
                                int(float(ts)),
                                node_id,
                                int(float(val_str))
                            ])
            except IOError as e:
                self._log(f"Error writing node memory metrics to CSV: {e}")

    def _collect_pod_cpu_metrics(self, start_time, end_time, collection_time, rate_window="1m"):
        """Collect pod CPU metrics and append to CSV."""
        namespace_filter = self._build_namespace_filter_string(filter_key="namespace")
        base_selector = 'image!="", container!="POD"'
        full_selector = f'{base_selector}, {namespace_filter}' if namespace_filter else base_selector
        query = f'sum by (namespace, pod) (rate(container_cpu_usage_seconds_total{{{full_selector}}}[{rate_window}]))'
        data = self._query_prometheus(query, is_range_query=True, start_time=start_time, end_time=end_time, step=self.metrics_step)
        
        if data and data.get('status') == 'success' and data['data']['result']:
            try:
                with open(self.csv_files['pod_cpu'], 'a', newline='') as f:
                    writer = csv.writer(f)
                    for item in data['data']['result']:
                        namespace_val = item['metric'].get('namespace', 'unknown_namespace')
                        pod_val = item['metric'].get('pod', 'unknown_pod')
                        for ts, val_str in item['values']:
                            writer.writerow([
                                collection_time,
                                int(float(ts)),
                                namespace_val,
                                pod_val,
                                round(float(val_str), 3)
                            ])
            except IOError as e:
                self._log(f"Error writing pod CPU metrics to CSV: {e}")

    def _collect_pod_memory_metrics(self, start_time, end_time, collection_time):
        """Collect pod memory metrics and append to CSV."""
        namespace_filter = self._build_namespace_filter_string(filter_key="namespace")
        base_selector = 'image!="", container!="POD"'
        full_selector = f'{base_selector}, {namespace_filter}' if namespace_filter else base_selector
        query = f'sum by (namespace, pod) (container_memory_usage_bytes{{{full_selector}}})'
        data = self._query_prometheus(query, is_range_query=True, start_time=start_time, end_time=end_time, step=self.metrics_step)
        
        if data and data.get('status') == 'success' and data['data']['result']:
            try:
                with open(self.csv_files['pod_memory'], 'a', newline='') as f:
                    writer = csv.writer(f)
                    for item in data['data']['result']:
                        namespace_val = item['metric'].get('namespace', 'unknown_namespace')
                        pod_val = item['metric'].get('pod', 'unknown_pod')
                        for ts, val_str in item['values']:
                            writer.writerow([
                                collection_time,
                                int(float(ts)),
                                namespace_val,
                                pod_val,
                                int(float(val_str))
                            ])
            except IOError as e:
                self._log(f"Error writing pod memory metrics to CSV: {e}")

    def _collect_istio_latency_metrics(self, start_time, end_time, collection_time, percentile="0.95", rate_window="1m"):
        """Collect Istio latency metrics and append to CSV."""
        namespace_filter = self._build_namespace_filter_string(filter_key="destination_workload_namespace")
        base_selector = 'reporter="destination"'
        full_selector = f'{base_selector}, {namespace_filter}' if namespace_filter else base_selector
        
        query = f'''histogram_quantile({percentile},
            sum(rate(istio_request_duration_milliseconds_bucket{{{full_selector}}}[{rate_window}]))
            by (le, destination_workload, destination_workload_namespace)
        )'''
        data = self._query_prometheus(query, is_range_query=True, start_time=start_time, end_time=end_time, step=self.metrics_step)
        
        if data and data.get('status') == 'success' and data['data']['result']:
            try:
                with open(self.csv_files['istio_latency'], 'a', newline='') as f:
                    writer = csv.writer(f)
                    for item in data['data']['result']:
                        pod_name_val = item['metric'].get('destination_workload', 'unknown_pod')
                        namespace_val = item['metric'].get('destination_workload_namespace', 'unknown_namespace')
                        for ts, val_str in item['values']:
                            latency_ms = float(val_str)
                            if latency_ms != float('inf'):  # Filter out +Inf values
                                writer.writerow([
                                    collection_time,
                                    int(float(ts)),
                                    namespace_val,
                                    pod_name_val,
                                    round(latency_ms, 2)
                                ])
            except IOError as e:
                self._log(f"Error writing Istio latency metrics to CSV: {e}")

    def _collection_worker(self):
        """Worker thread that collects metrics at specified intervals."""
        self._log(f"Starting metrics collection every {self.collection_interval_minutes} minutes")
        self._log(f"Metrics step interval: {self.metrics_step}")
        self._log(f"Output directory: {self.output_dir}")
        
        while not self._stop_event.is_set():
            try:
                # Calculate time range for this collection
                end_time = datetime.now(timezone.utc)
                start_time = end_time - timedelta(minutes=self.collection_interval_minutes)
                collection_time = int(end_time.timestamp())  # Use Unix timestamp
                
                self._log(f"Collecting metrics from {start_time.isoformat()} to {end_time.isoformat()}")
                self._log(f"Using {self.metrics_step} step intervals for the past {self.collection_interval_minutes} minutes")
                
                # Collect all metrics
                self._collect_node_cpu_metrics(start_time, end_time, collection_time)
                self._collect_node_memory_metrics(start_time, end_time, collection_time)
                self._collect_pod_cpu_metrics(start_time, end_time, collection_time)
                self._collect_pod_memory_metrics(start_time, end_time, collection_time)
                self._collect_istio_latency_metrics(start_time, end_time, collection_time)
                
                self._log(f"Metrics collection completed at {end_time.isoformat()}")
                
                # Wait for next collection interval
                self._stop_event.wait(self.collection_interval_minutes * 60)
                
            except Exception as e:
                self._log(f"Error during metrics collection: {e}")
                # Continue collecting even if one iteration fails
                self._stop_event.wait(60)  # Wait 1 minute before retrying

    def start_collection(self):
        """Start the metrics collection in a background thread."""
        if self._is_running:
            self._log("Metrics collection is already running")
            return
        
        self._stop_event.clear()
        self._collection_thread = threading.Thread(target=self._collection_worker, daemon=True)
        self._collection_thread.start()
        self._is_running = True
        self._log("Metrics collection started")

    def stop_collection(self):
        """Stop the metrics collection."""
        if not self._is_running:
            self._log("Metrics collection is not running")
            return
        
        self._log("Stopping metrics collection...")
        self._stop_event.set()
        if self._collection_thread and self._collection_thread.is_alive():
            self._collection_thread.join(timeout=10)
        self._is_running = False
        self._log("Metrics collection stopped")

    def is_running(self):
        """Check if metrics collection is currently running."""
        return self._is_running

    def collect_once(self, duration_minutes=None):
        """Collect metrics once for a specified duration or the default interval."""
        if duration_minutes is None:
            duration_minutes = self.collection_interval_minutes
        
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=duration_minutes)
        collection_time = int(end_time.timestamp())  # Use Unix timestamp
        
        self._log(f"Collecting metrics once from {start_time.isoformat()} to {end_time.isoformat()}")
        
        self._collect_node_cpu_metrics(start_time, end_time, collection_time)
        self._collect_node_memory_metrics(start_time, end_time, collection_time)
        self._collect_pod_cpu_metrics(start_time, end_time, collection_time)
        self._collect_pod_memory_metrics(start_time, end_time, collection_time)
        self._collect_istio_latency_metrics(start_time, end_time, collection_time)
        
        self._log(f"One-time metrics collection completed at {end_time.isoformat()}")

    def get_csv_files(self):
        """Return the paths to all CSV files."""
        return dict(self.csv_files)

    def set_collection_interval(self, minutes):
        """Update the collection interval. Requires restart if currently running."""
        was_running = self._is_running
        if was_running:
            self.stop_collection()
        
        self.collection_interval_minutes = minutes
        self._log(f"Collection interval updated to {minutes} minutes")
        
        if was_running:
            self.start_collection()

    def set_metrics_step(self, step):
        """Update the metrics step interval. Requires restart if currently running."""
        was_running = self._is_running
        if was_running:
            self.stop_collection()
        
        self.metrics_step = step
        self._log(f"Metrics step updated to {step}")
        
        if was_running:
            self.start_collection()

    def set_verbose(self, verbose):
        """Update the verbosity setting."""
        self.verbose = verbose
        self._log(f"Verbose mode {'enabled' if verbose else 'disabled'}") 