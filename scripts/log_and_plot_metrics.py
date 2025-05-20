import os
import sys
from datetime import datetime, timedelta, timezone
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import subprocess
import json

# Adjust path to import PrometheusExporter from the parent directory
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)
from mu_bench.metrics_exporter.prometheus_exporter import PrometheusExporter

# --- Configuration ---
EXPERIMENT_NAME = "test_experiment"
TARGET_NAMESPACES = ["app-edge"] # Monitor a single namespace
PROMETHEUS_URL = "http://localhost:9090"
DURATION_MINUTES = 20  # How long to fetch data for, ending now
STEP = "15s"  # Prometheus query step
NODE_RATE_WINDOW = "1m"
POD_RATE_WINDOW = "1m"

# --- Setup Output Directory ---
current_date_str = datetime.now().strftime("%Y-%m-%d")
OUTPUT_DIR = os.path.join(project_root, "DATA", f"{EXPERIMENT_NAME}_{current_date_str}")
os.makedirs(OUTPUT_DIR, exist_ok=True)
print(f"Output directory: {OUTPUT_DIR}")

class DataSaver:
    def __init__(self, output_dir):
        self.output_dir = output_dir

    def save_to_csv(self, df, metric_name, filename_prefix):
        if df is None or df.empty:
            print(f"No data for {metric_name}. Skipping CSV save.")
            return None
        
        csv_path = os.path.join(self.output_dir, f"{filename_prefix}.csv")
        try:
            df.to_csv(csv_path)
            return csv_path
        except Exception as e:
            print(f"Error saving {metric_name} to CSV {csv_path}: {e}")
            return None

class DataPlotter:
    def __init__(self, output_dir, node_ip_to_zone_map=None):
        self.output_dir = output_dir
        self.node_ip_to_zone_map = node_ip_to_zone_map

    def _generate_plot_label(self, name, group_by_cols):
        label_str = ""
        if group_by_cols == ['node']:
            ip_from_group = name[0] if isinstance(name, tuple) and len(name) == 1 else str(name)
            
            if self.node_ip_to_zone_map and ip_from_group in self.node_ip_to_zone_map:
                node_info = self.node_ip_to_zone_map[ip_from_group]
                label_str = f"{node_info['name']} ({ip_from_group} - Zone: {node_info['zone']})"
            else:
                label_str = f"{ip_from_group} (Zone: Unknown)"
        elif isinstance(name, tuple):
            label_str = ", ".join(map(str, name))
        else:
            label_str = str(name)
        return label_str

    def _prepare_plot_df(self, df, metric_name, group_by_cols, value_col):
        plot_df = df.reset_index()
        
        required_cols_for_grouping = group_by_cols + ['timestamp']
        
        if 'timestamp' not in plot_df.columns and 'timestamp' in plot_df.index.names: # type: ignore
             plot_df = plot_df.reset_index(level='timestamp') # type: ignore

        actual_value_col = value_col
        if value_col not in plot_df.columns:
            potential_value_cols = [c for c in plot_df.columns if c not in required_cols_for_grouping]
            if len(potential_value_cols) == 1:
                actual_value_col = potential_value_cols[0]
                print(f"Inferred value column as '{actual_value_col}' for {metric_name}")
        
        if not all(col in plot_df.columns for col in required_cols_for_grouping + [actual_value_col]): # type: ignore
            print(f"Plotting error for {metric_name}: Missing required columns. Available: {plot_df.columns.tolist()}. Required: {group_by_cols} + ['timestamp'] + ['{actual_value_col}']. Skipping plot.")
            return None, None

        return plot_df, actual_value_col

    def plot_data(self, df, metric_name, filename_prefix, group_by_cols=None, value_col=None):
        if df is None or df.empty:
            print(f"No data for {metric_name}. Skipping plot.")
            return None

        plot_path = os.path.join(self.output_dir, f"{filename_prefix}.png")
        plt.figure(figsize=(12, 6))
        
        plot_value_col_name = value_col 

        if group_by_cols and value_col:
            prepared_df, actual_plot_value_col = self._prepare_plot_df(df, metric_name, group_by_cols, value_col)
            if prepared_df is None:
                plt.close()
                return None
            
            plot_value_col_name = actual_plot_value_col

            for name, group in prepared_df.groupby(group_by_cols):
                label_str = self._generate_plot_label(name, group_by_cols)
                plt.plot(group['timestamp'], group[actual_plot_value_col], marker='o', linestyle='-', label=label_str)
        
        else: # Single line plot if no grouping needed
            if 'timestamp' in df.columns:
                potential_value_cols = [c for c in df.columns if c != 'timestamp']
                if not potential_value_cols:
                    print(f"Cannot determine value column to plot for {metric_name} (single line, no non-timestamp columns). Skipping plot.")
                    plt.close()
                    return None
                
                col_to_plot = potential_value_cols[0]
                plot_value_col_name = col_to_plot
                plt.plot(df['timestamp'], df[col_to_plot], marker='o', linestyle='-')
                if len(potential_value_cols) > 1:
                    print(f"Warning: Multiple potential value columns for single line plot of {metric_name}. Plotted '{col_to_plot}'.")
            elif not df.index.empty and isinstance(df.index, pd.MultiIndex) and 'timestamp' in df.index.names: # type: ignore
                temp_df = df.reset_index()
                val_cols = [c for c in temp_df.columns if c != 'timestamp' and c not in (df.index.names if df.index.names else [])] # type: ignore
                if val_cols:
                    plot_value_col_name = val_cols[0]
                    plt.plot(temp_df['timestamp'], temp_df[val_cols[0]], marker='o', linestyle='-')
                else:
                    print(f"Cannot determine columns to plot for {metric_name} (MultiIndex case). Skipping plot.")
                    plt.close()
                    return None
            else:
                print(f"Cannot determine columns to plot for {metric_name} (unhandled single line case). Skipping plot.")
                plt.close()
                return None

        plt.title(f"{metric_name} Over Time")
        plt.xlabel("Time")
        plt.ylabel(plot_value_col_name.replace('_', ' ').title() if plot_value_col_name else "Value")
        plt.xticks(rotation=45)
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M:%S'))
        
        if any(line.get_label() and not line.get_label().startswith('_') for line in plt.gca().lines):
            plt.legend(loc='best')

        plt.tight_layout()
        plt.grid(True)
        
        try:
            plt.savefig(plot_path)
            return plot_path
        except Exception as e:
            print(f"Error saving {metric_name} plot to {plot_path}: {e}")
            return None
        finally:
            plt.close()

def get_node_ip_to_zone_map():
    """Fetches a map of node IPs to their zone using kubectl."""
    node_ip_to_zone = {}
    try:
        nodes_json_bytes = subprocess.check_output(
            ["kubectl", "get", "nodes", "-o", "json"]
        )
        nodes_data = json.loads(nodes_json_bytes)

        for node in nodes_data["items"]:
            node_name = node["metadata"]["name"]
            labels = node["metadata"]["labels"]
            # Simplified zone fetching
            zone = labels.get("topology.kubernetes.io/zone")
            if not zone:
                zone = next((v for k, v in labels.items() if "zone" in k.lower()), "Unknown")
            
            node_ip = None
            if "status" in node and "addresses" in node["status"]:
                for address_info in node["status"]["addresses"]:
                    if address_info.get("type") == "InternalIP":
                        node_ip = address_info.get("address")
                        break # Prefer InternalIP
                if not node_ip: # If no InternalIP, take the first available IP
                    for address_info in node["status"]["addresses"]:
                        if address_info.get("address"):
                            node_ip = address_info.get("address")
                            break
            
            if node_ip:
                node_ip_to_zone[node_ip] = {"zone": zone, "name": node_name}
            else:
                print(f"Warning: Could not determine IP for node {node_name}. It will not be mapped to a zone by IP.")

        if not node_ip_to_zone:
            print("Warning: Node IP to zone map is empty. Check kubectl output and node addresses.")
            
    except subprocess.CalledProcessError as e:
        print(f"Error calling kubectl to get nodes: {e}")
        print("Node zone information will be unavailable for plots.")
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from kubectl output: {e}")
        print("Node zone information will be unavailable for plots.")
    except Exception as e:
        print(f"An unexpected error occurred while fetching node IP-zone map: {e}")
        print("Node zone information will be unavailable for plots.")
    
    return node_ip_to_zone

def main():
    # --- Initialize Exporter ---
    exporter = PrometheusExporter(prometheus_url=PROMETHEUS_URL, target_namespaces=TARGET_NAMESPACES)

    # --- Define Time Range ---
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=DURATION_MINUTES)
    print(f"Fetching data from {start_time.isoformat()} to {end_time.isoformat()} (step: {STEP})")

    # --- Fetch Node-IP-Zone Mapping ---
    node_ip_zone_map = get_node_ip_to_zone_map()

    # --- Initialize Saver and Plotter ---
    saver = DataSaver(OUTPUT_DIR)
    plotter = DataPlotter(OUTPUT_DIR, node_ip_to_zone_map=node_ip_zone_map)

    def process_metric(
        df_fetch_func, 
        fetch_args, 
        metric_name_template, 
        filename_prefix, 
        group_by_cols, 
        value_col
    ):
        # If metric_name_template contains placeholders for namespaces, format it
        if "{namespaces}" in metric_name_template:
            metric_name = metric_name_template.format(namespaces=', '.join(TARGET_NAMESPACES))
        else:
            metric_name = metric_name_template

        print(f"Fetching {metric_name}...")
        df = df_fetch_func(*fetch_args)

        saver.save_to_csv(df, metric_name, filename_prefix)
        plotter.plot_data(
            df, 
            metric_name, 
            filename_prefix, 
            group_by_cols=group_by_cols, 
            value_col=value_col
        )

    # --- Fetch, Save, and Plot Metrics ---

    # 1. Node CPU Usage
    process_metric(
        exporter.get_node_cpu_usage_range,
        (start_time, end_time, STEP, NODE_RATE_WINDOW),
        "Node CPU Usage", 
        "node_cpu_usage",
        group_by_cols=['node'], 
        value_col='cpu_cores_used'
    )

    # 2. Node Memory Usage
    process_metric(
        exporter.get_node_memory_usage_range,
        (start_time, end_time, STEP),
        "Node Memory Usage", 
        "node_memory_usage",
        group_by_cols=['node'], 
        value_col='memory_working_set_bytes'
    )

    # 3. Pod CPU Usage
    process_metric(
        exporter.get_pod_cpu_usage_range,
        (start_time, end_time, STEP, POD_RATE_WINDOW),
        "Pod CPU Usage (Namespaces: {namespaces})", 
        "pod_cpu_usage",
        group_by_cols=['namespace', 'pod'], 
        value_col='cpu_cores_used'
    )

    # 4. Pod Memory Usage
    process_metric(
        exporter.get_pod_memory_usage_range,
        (start_time, end_time, STEP),
        "Pod Memory Usage (Namespaces: {namespaces})", 
        "pod_memory_usage",
        group_by_cols=['namespace', 'pod'], 
        value_col='memory_usage_bytes'
    )
    
if __name__ == "__main__":
    # Ensure matplotlib uses a non-interactive backend if no GUI is available
    # or if running in a headless environment.
    if "DISPLAY" not in os.environ:
        plt.switch_backend('Agg')
    main() 