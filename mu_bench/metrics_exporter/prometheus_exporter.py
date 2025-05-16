'''
Script to export metrics from Prometheus as Pandas DataFrames.

This script defines a class PrometheusExporter that queries a Prometheus server 
for specific metrics related to node and pod resource usage (CPU, RAM), 
and Istio service latencies over a specified time range, 
optionally filtered by namespace(s) for pod and Istio metrics.
'''
import requests
import json
import time
from datetime import datetime, timedelta, timezone
import os
import pandas as pd

class PrometheusExporter:
    def __init__(self, prometheus_url="http://localhost:9090", target_namespaces=None):
        """
        Initializes the PrometheusExporter.

        Args:
            prometheus_url (str): The base URL of the Prometheus server.
            target_namespaces (str or list/tuple, optional): A single namespace string 
                                  or a list/tuple of namespace strings to filter pod and Istio metrics. 
                                  If None, these metrics are fetched from all relevant namespaces.
        """
        self.prometheus_url = os.environ.get("PROMETHEUS_URL", prometheus_url)
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

    def _build_namespace_filter_string(self, filter_key="namespace"):
        """Builds the namespace filter string for PromQL queries based on self.target_namespaces."""
        if not self.target_namespaces:
            return ""
        
        if len(self.target_namespaces) == 1:
            return f'{filter_key}="{self.target_namespaces[0]}"'
        else:
            regex_namespaces = "|".join(self.target_namespaces)
            return f'{filter_key}=~"{regex_namespaces}"'

    def _query_prometheus(self, query, is_range_query=False, start_time=None, end_time=None, step='1m'):
        """ Internal helper to send a query to Prometheus. """
        if is_range_query:
            if not all([start_time, end_time]):
                print("Error: start_time and end_time are required for range queries.")
                return None
            api_endpoint = "/api/v1/query_range"
            params = {
                'query': query,
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
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
            print(f"Error querying Prometheus ({full_url}): {e}")
            if hasattr(e, 'response') and e.response is not None:
                 print(f"Response body: {e.response.text}")
            return None

    def get_node_cpu_usage_range(self, start_time, end_time, step="1m", rate_window="1m", instance_label_name='node'):
        """ Fetches time-series of average CPU usage percentage per node. """
        query = f'sum by (instance) (rate(container_cpu_usage_seconds_total{{image!="", container!="POD"}}[{rate_window}]))'
        data = self._query_prometheus(query, is_range_query=True, start_time=start_time, end_time=end_time, step=step)
        flat_data = []
        if data and data.get('status') == 'success' and data['data']['result']:
            for item in data['data']['result']:
                node_id = item['metric'].get('instance', 'unknown_instance').split(':')[0]
                for ts, val_str in item['values']:
                    flat_data.append({
                        'timestamp': datetime.fromtimestamp(float(ts)),
                        instance_label_name: node_id,
                        'cpu_cores_used': round(float(val_str), 3)
                    })
        elif data:
             print(f"Node CPU usage query failed or returned no data: Status {data.get('status')}, Error {data.get('errorType')}, {data.get('error')}")
        return pd.DataFrame(flat_data) if flat_data else pd.DataFrame(columns=['timestamp', instance_label_name, 'cpu_cores_used'])

    def get_node_memory_usage_range(self, start_time, end_time, step="1m", instance_label_name='node'):
        """ Fetches time-series of memory working set in bytes per node. """
        query = f'sum by (instance) (container_memory_working_set_bytes{{image!="", container!="POD"}})'
        
        flat_data = []
        data = self._query_prometheus(query, is_range_query=True, start_time=start_time, end_time=end_time, step=step)
        
        if data and data.get('status') == 'success' and data['data']['result']:
            for item in data['data']['result']:
                node_id = item['metric'].get('instance', 'unknown_instance').split(':')[0]
                for ts, val_str in item['values']:
                    flat_data.append({
                        'timestamp': datetime.fromtimestamp(float(ts)),
                        instance_label_name: node_id,
                        'memory_working_set_bytes': int(float(val_str))
                    })
        elif data:
            print(f"Node Memory usage query failed or returned no data: Status {data.get('status')}, Error {data.get('errorType')}, {data.get('error')}")
            
        return pd.DataFrame(flat_data) if flat_data else pd.DataFrame(columns=['timestamp', instance_label_name, 'memory_working_set_bytes'])

    def get_pod_cpu_usage_range(self, start_time, end_time, step="1m", rate_window="1m", 
                                namespace_label_name='namespace', pod_label_name='pod'):
        """ Fetches time-series of CPU usage in cores per pod, optionally filtered by target_namespaces. """
        namespace_filter = self._build_namespace_filter_string(filter_key="namespace")
        base_selector = 'image!="", container!="POD"'
        full_selector = f'{base_selector}, {namespace_filter}' if namespace_filter else base_selector
        query = f'sum by (namespace, pod) (rate(container_cpu_usage_seconds_total{{{full_selector}}}[{rate_window}]))'
        data = self._query_prometheus(query, is_range_query=True, start_time=start_time, end_time=end_time, step=step)
        flat_data = []
        if data and data.get('status') == 'success' and data['data']['result']:
            for item in data['data']['result']:
                namespace_val = item['metric'].get('namespace', 'unknown_namespace')
                pod_val = item['metric'].get('pod', 'unknown_pod')
                for ts, val_str in item['values']:
                    flat_data.append({
                        'timestamp': datetime.fromtimestamp(float(ts)),
                        namespace_label_name: namespace_val,
                        pod_label_name: pod_val,
                        'cpu_cores_used': round(float(val_str), 3)
                    })
        elif data:
            print(f"Pod CPU usage query failed or returned no data: Status {data.get('status')}, Error {data.get('errorType')}, {data.get('error')}")
        return pd.DataFrame(flat_data) if flat_data else pd.DataFrame(columns=['timestamp', namespace_label_name, pod_label_name, 'cpu_cores_used'])

    def get_pod_memory_usage_range(self, start_time, end_time, step="1m", 
                                   namespace_label_name='namespace', pod_label_name='pod'):
        """ Fetches time-series of memory usage in bytes per pod, optionally filtered by target_namespaces. """
        namespace_filter = self._build_namespace_filter_string(filter_key="namespace")
        base_selector = 'image!="", container!="POD"'
        full_selector = f'{base_selector}, {namespace_filter}' if namespace_filter else base_selector
        query = f'sum by (namespace, pod) (container_memory_usage_bytes{{{full_selector}}})'
        data = self._query_prometheus(query, is_range_query=True, start_time=start_time, end_time=end_time, step=step)
        flat_data = []
        if data and data.get('status') == 'success' and data['data']['result']:
            for item in data['data']['result']:
                namespace_val = item['metric'].get('namespace', 'unknown_namespace')
                pod_val = item['metric'].get('pod', 'unknown_pod')
                for ts, val_str in item['values']:
                    flat_data.append({
                        'timestamp': datetime.fromtimestamp(float(ts)),
                        namespace_label_name: namespace_val,
                        pod_label_name: pod_val,
                        'memory_usage_bytes': int(float(val_str))
                    })
        elif data:
            print(f"Pod Memory usage query failed or returned no data: Status {data.get('status')}, Error {data.get('errorType')}, {data.get('error')}")
        return pd.DataFrame(flat_data) if flat_data else pd.DataFrame(columns=['timestamp', namespace_label_name, pod_label_name, 'memory_usage_bytes'])

    def get_istio_pod_latency_range(self, start_time, end_time, percentile="0.95", step="1m", rate_window="1m", 
                                    workload_label_name='pod', namespace_label_name='namespace'):
        """ Fetches Istio request latency (e.g., P95) per pod, optionally filtered by target_namespaces. """
        # For Istio, the namespace label is typically 'destination_workload_namespace'
        namespace_filter = self._build_namespace_filter_string(filter_key="destination_workload_namespace")
        base_selector = 'reporter="destination"'
        full_selector = f'{base_selector}, {namespace_filter}' if namespace_filter else base_selector
        
        query = f'''histogram_quantile({percentile},
            sum(rate(istio_request_duration_milliseconds_bucket{{{full_selector}}}[{rate_window}]))
            by (le, destination_workload, destination_workload_namespace)
        )'''
        data = self._query_prometheus(query, is_range_query=True, start_time=start_time, end_time=end_time, step=step)
        flat_data = []
        if data and data.get('status') == 'success' and data['data']['result']:
            if not data['data']['result']:
                ns_info = f" for namespace(s) {self.target_namespaces}" if self.target_namespaces else ""
                print(f"Warning: Istio latency query{ns_info} returned no data. Check traffic and metric labels.")
            for item in data['data']['result']:
                # Istio uses destination_workload for pod and destination_workload_namespace for namespace by default
                pod_name_val = item['metric'].get('destination_workload', 'unknown_pod')
                namespace_val = item['metric'].get('destination_workload_namespace', 'unknown_namespace')
                for ts, val_str in item['values']:
                    latency_ms = float(val_str)
                    if latency_ms != float('inf'): # Filter out +Inf values
                        flat_data.append({
                            'timestamp': datetime.fromtimestamp(float(ts)),
                            namespace_label_name: namespace_val,
                            workload_label_name: pod_name_val,
                            f'p{float(percentile)*100:.0f}_latency_ms': round(latency_ms, 2)
                        })
        elif data:
            print(f"Istio latency query failed or returned no data: Status {data.get('status')}, Error {data.get('errorType')}, {data.get('error')}")
        return pd.DataFrame(flat_data) if flat_data else pd.DataFrame(columns=['timestamp', namespace_label_name, workload_label_name, f'p{float(percentile)*100:.0f}_latency_ms'])

    def fetch_metrics_as_dataframes(self, start_time, end_time, step="1m", node_rate_window="1m", pod_rate_window="1m", istio_rate_window="1m"):
        """ Fetches all defined metrics for the given time range and returns them as a dictionary of Pandas DataFrames. """
        metrics_dataframes = {}
        print(f"Fetching metrics from {start_time.isoformat()} to {end_time.isoformat()} with step {step}")
        if self.target_namespaces:
            print(f"Pod and Istio metrics will be filtered for namespace(s): {self.target_namespaces}")

        df_node_cpu = self.get_node_cpu_usage_range(start_time, end_time, step=step, rate_window=node_rate_window)
        metrics_dataframes['node_cpu_usage'] = df_node_cpu.set_index(['timestamp', 'node']) if not df_node_cpu.empty else df_node_cpu
        if df_node_cpu.empty: print("No data returned for Node CPU usage.")

        df_node_mem = self.get_node_memory_usage_range(start_time, end_time, step=step)
        metrics_dataframes['node_memory_usage'] = df_node_mem.set_index(['timestamp', 'node']) if not df_node_mem.empty else df_node_mem
        if df_node_mem.empty: print("No data returned for Node Memory usage.")

        df_pod_cpu = self.get_pod_cpu_usage_range(start_time, end_time, step=step, rate_window=pod_rate_window)
        metrics_dataframes['pod_cpu_usage'] = df_pod_cpu.set_index(['timestamp', 'namespace', 'pod']) if not df_pod_cpu.empty else df_pod_cpu
        if df_pod_cpu.empty: print("No data returned for Pod CPU usage.")

        df_pod_mem = self.get_pod_memory_usage_range(start_time, end_time, step=step)
        metrics_dataframes['pod_memory_usage'] = df_pod_mem.set_index(['timestamp', 'namespace', 'pod']) if not df_pod_mem.empty else df_pod_mem
        if df_pod_mem.empty: print("No data returned for Pod Memory usage.")
        
        df_istio_latency = self.get_istio_pod_latency_range(start_time, end_time, step=step, rate_window=istio_rate_window)
        metrics_dataframes['istio_pod_latency'] = df_istio_latency.set_index(['timestamp', 'namespace', 'pod']) if not df_istio_latency.empty else df_istio_latency
        if df_istio_latency.empty: print("No data returned for Istio Pod Latency.")
            
        return metrics_dataframes 