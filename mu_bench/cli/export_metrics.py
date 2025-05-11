'''
CLI script to export metrics using PrometheusExporter.

This script provides a command-line interface to fetch metrics 
(node/pod CPU/memory, Istio latency) for a defined period (default last 10 minutes) 
and prints averages.
'''
import argparse
from datetime import datetime, timedelta, timezone
import os

# Adjust the import path based on the new location of PrometheusExporter
from mu_bench.metrics_exporter.prometheus_exporter import PrometheusExporter

def main():
    parser = argparse.ArgumentParser(description="Prometheus Metrics Exporter CLI")
    parser.add_argument(
        "--prometheus-url", 
        default=os.environ.get("PROMETHEUS_URL", "http://localhost:9090"),
        help="Prometheus server URL (default: http://localhost:9090 or PROMETHEUS_URL env var)"
    )
    parser.add_argument(
        "--namespaces", 
        nargs='*', 
        help="Target namespace(s) for pod and Istio metrics. If not provided, fetches from all."
    )
    parser.add_argument(
        "--minutes", 
        type=int, 
        default=10, 
        help="How many minutes of metrics to fetch from the past (default: 10)"
    )
    parser.add_argument(
        "--step", 
        type=str, 
        default="1m", 
        help="Step for range queries (e.g., '1m', '30s') (default: 1m)"
    )
    parser.add_argument(
        "--node-rate-window", 
        type=str, 
        default="1m", 
        help="Rate window for node metrics (default: 1m)"
    )
    parser.add_argument(
        "--pod-rate-window", 
        type=str, 
        default="1m", 
        help="Rate window for pod metrics (default: 1m)"
    )
    parser.add_argument(
        "--istio-rate-window", 
        type=str, 
        default="1m", 
        help="Rate window for Istio metrics (default: 1m)"
    )

    args = parser.parse_args()

    print("--- Prometheus Metrics Exporter CLI ---")
    
    # Determine target_namespaces: could be None, a single string, or a list
    target_namespaces_arg = args.namespaces
    if args.namespaces and len(args.namespaces) == 1:
        target_namespaces_arg = args.namespaces[0] # Pass as string if only one

    exporter = PrometheusExporter(
        prometheus_url=args.prometheus_url, 
        target_namespaces=target_namespaces_arg
    )

    end_time_dt = datetime.now(timezone.utc)
    start_time_dt = end_time_dt - timedelta(minutes=args.minutes)
    
    all_dfs = exporter.fetch_metrics_as_dataframes(
        start_time=start_time_dt, 
        end_time=end_time_dt, 
        step=args.step,
        node_rate_window=args.node_rate_window,
        pod_rate_window=args.pod_rate_window,
        istio_rate_window=args.istio_rate_window
    )

    print("\n--- Exported Metrics (Averages) ---")
    for name, df in all_dfs.items():
        if not df.empty:
            print(f"\n--- {name} (Average Consumption over {args.minutes} min) ---")
            # The DataFrame already has a MultiIndex. We need to reset it for groupby on those index levels.
            df_reset = df.reset_index()
            if name == 'node_cpu_usage':
                avg_df = df_reset.groupby('node')['cpu_usage_percent'].mean().reset_index()
                print(avg_df.to_string())
            elif name == 'node_memory_usage':
                avg_df = df_reset.groupby('node')['memory_usage_percent'].mean().reset_index()
                print(avg_df.to_string())
            elif name == 'pod_cpu_usage':
                avg_df = df_reset.groupby(['namespace', 'pod'])['cpu_cores_used'].mean().reset_index()
                print(avg_df.to_string())
            elif name == 'pod_memory_usage':
                avg_df = df_reset.groupby(['namespace', 'pod'])['memory_usage_bytes'].mean().reset_index()
                avg_df['memory_usage_mib'] = (avg_df['memory_usage_bytes'] / (1024*1024)).round(2)
                print(avg_df.to_string())
            elif name == 'istio_pod_latency':
                latency_col = df_reset.columns[-1] # Last column is the PXX_latency_ms
                avg_df = df_reset.groupby(['namespace', 'pod'])[latency_col].mean().reset_index()
                print(avg_df.to_string())
        else:
            print(f"\n--- {name} ---")
            print("DataFrame is empty.")
            
    print("\n--- Metrics Export Complete ---")

if __name__ == "__main__":
    main() 