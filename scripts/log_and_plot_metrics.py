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
            zone = next(
                (v for k, v in labels.items() if "topology.kubernetes.io/zone" == k), None
            )
            if zone is None:
                zone = next(
                    (v for k, v in labels.items() if "zone" in k.lower()), "Unknown"
                )
            
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

        if node_ip_to_zone:
            print(f"Successfully fetched node IP to zone/name map: {node_ip_to_zone}")
        else:
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

def save_and_plot_df(df, metric_name, filename_prefix, group_by_cols=None, value_col=None, node_ip_to_zone_map=None):
    """Saves DataFrame to CSV and generates a plot."""
    if df.empty:
        print(f"No data for {metric_name}. Skipping CSV and plot.")
        return

    csv_path = os.path.join(OUTPUT_DIR, f"{filename_prefix}.csv")
    df.to_csv(csv_path)
    print(f"Saved {metric_name} to {csv_path}")

    plot_path = os.path.join(OUTPUT_DIR, f"{filename_prefix}.png")
    
    plt.figure(figsize=(12, 6))
    
    if group_by_cols and value_col:
        # Reset index if it's a multi-index to access columns for grouping
        plot_df = df.reset_index()
        if not all(col in plot_df.columns for col in group_by_cols + ['timestamp', value_col]):
            print(f"Plotting error for {metric_name}: Missing required columns. Available: {plot_df.columns.tolist()}")
            # Try to infer columns if index names are standard
            if 'timestamp' not in plot_df.columns and 'timestamp' in plot_df.index.names:
                 plot_df = plot_df.reset_index(level='timestamp')

            # Attempt to find the value column if not explicitly named value_col
            potential_value_cols = [c for c in plot_df.columns if c not in group_by_cols + ['timestamp']]
            if len(potential_value_cols) == 1 and value_col not in plot_df.columns:
                actual_value_col = potential_value_cols[0]
                print(f"Inferred value column as '{actual_value_col}' for {metric_name}")
            else:
                actual_value_col = value_col # Stick to original if inference is ambiguous
            
            # Check again after potential fixes
            if not all(col in plot_df.columns for col in group_by_cols + ['timestamp', actual_value_col]):
                print(f"Still missing columns for {metric_name} after trying to fix. Skipping plot.")
                plt.close()
                return
            value_col = actual_value_col


        for name, group in plot_df.groupby(group_by_cols):
            # ---- START PRE-CONDITION DEBUG ----
            # print(f"[PRE-COND DEBUG] For metric '{metric_name}': group_by_cols is {group_by_cols} (expected ['node'] for node metrics), actual name from group is '{name}' (type: {type(name)}), node_ip_to_zone_map is populated: {bool(node_ip_to_zone_map)}")
            # ---- END PRE-CONDITION DEBUG ----

            label_str = ""
            ip_from_group = ""

            if group_by_cols == ['node']:
                if isinstance(name, tuple) and len(name) == 1:
                    ip_from_group = name[0] # Extract IP from single-element tuple
                elif isinstance(name, str): # Should not happen with current groupby but good for robustness
                    ip_from_group = name
                else:
                    # Fallback if name is not a tuple or string as expected
                    label_str = str(name) 
            elif isinstance(name, tuple):
                label_str = ", ".join(map(str, name))
            else:
                label_str = str(name)

            # Augment label for node plots if zone map is available and it's a node metric
            if node_ip_to_zone_map and group_by_cols == ['node'] and isinstance(ip_from_group, str) and ip_from_group:
                # 'ip_from_group' here is the node IP from Prometheus data (e.g., from df['node'])
                node_info = node_ip_to_zone_map.get(ip_from_group)
                
                # ---- START DETAILED DEBUG ----
                # print(f"[NODE PLOT DEBUG] Metric Node IP: '{ip_from_group}' (type: {type(ip_from_group)})")
                # if ip_from_group in node_ip_to_zone_map:
                #     print(f"[NODE PLOT DEBUG]   Found in map. Mapped info: {node_ip_to_zone_map[ip_from_group]}")
                # else:
                #     print(f"[NODE PLOT DEBUG]   NOT found in map. Map keys: {list(node_ip_to_zone_map.keys())}")
                # ---- END DETAILED DEBUG ----
                
                if node_info:
                    label_str = f"{node_info['name']} ({ip_from_group} - Zone: {node_info['zone']})"
                else:
                    label_str = f"{ip_from_group} (Zone: Unknown)" # Show IP if node name/zone not found
            elif not label_str: # Ensure label_str is set if not a node plot or if ip_from_group was not set
                if group_by_cols == ['node'] and ip_from_group: # if it was a node group but mapping failed before this block
                    label_str = ip_from_group
                # else label_str would have been set by the tuple/string conversion above

            plt.plot(group['timestamp'], group[value_col], marker='o', linestyle='-', label=label_str)
    else: # Single line plot if no grouping needed (e.g. simple df from exporter before set_index)
        # This case might not be hit if dataframes are always indexed as planned
        if 'timestamp' in df.columns and len(df.columns) > 1:
             # Assuming the first column after timestamp is the value
            value_col_plot = df.columns[1]
            plt.plot(df['timestamp'], df[value_col_plot], marker='o', linestyle='-')
        elif not df.index.empty and isinstance(df.index, pd.MultiIndex) and 'timestamp' in df.index.names:
            # Handle cases where timestamp is part of MultiIndex and we need to plot one of the value columns
            # This is a simplified case, might need adjustment based on actual df structure
            temp_df = df.reset_index()
            val_cols = [c for c in temp_df.columns if c not in temp_df.index.names]
            if val_cols:
                plt.plot(temp_df['timestamp'], temp_df[val_cols[0]], marker='o', linestyle='-')
            else:
                print(f"Cannot determine columns to plot for {metric_name}. Skipping plot.")
                plt.close()
                return

        else:
            print(f"Cannot determine columns to plot for {metric_name}. Skipping plot.")
            plt.close()
            return


    plt.title(f"{metric_name} Over Time")
    plt.xlabel("Time")
    plt.ylabel(value_col.replace('_', ' ').title() if value_col else "Value")
    plt.xticks(rotation=45)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M:%S'))
    plt.legend(loc='best')
    plt.tight_layout()
    plt.grid(True)
    plt.savefig(plot_path)
    print(f"Saved {metric_name} plot to {plot_path}")
    plt.close()

def main():
    # --- Initialize Exporter ---
    exporter = PrometheusExporter(prometheus_url=PROMETHEUS_URL, target_namespaces=TARGET_NAMESPACES)

    # --- Define Time Range ---
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=DURATION_MINUTES)
    print(f"Fetching data from {start_time.isoformat()} to {end_time.isoformat()} (step: {STEP})")

    # --- Fetch Node-IP-Zone Mapping ---
    node_ip_zone_map = get_node_ip_to_zone_map()

    # --- Fetch, Save, and Plot Metrics ---

    # 1. Node CPU Usage
    print("\nFetching Node CPU Usage...")
    df_node_cpu = exporter.get_node_cpu_usage_range(start_time, end_time, step=STEP, rate_window=NODE_RATE_WINDOW)
    save_and_plot_df(df_node_cpu, "Node CPU Usage", "node_cpu_usage", 
                     group_by_cols=['node'], value_col='cpu_cores_used', node_ip_to_zone_map=node_ip_zone_map)

    # 2. Node Memory Usage
    print("\nFetching Node Memory Usage...")
    df_node_mem = exporter.get_node_memory_usage_range(start_time, end_time, step=STEP)
    save_and_plot_df(df_node_mem, "Node Memory Usage", "node_memory_usage", 
                     group_by_cols=['node'], value_col='memory_working_set_bytes', node_ip_to_zone_map=node_ip_zone_map)

    # 3. Pod CPU Usage
    print("\nFetching Pod CPU Usage...")
    df_pod_cpu = exporter.get_pod_cpu_usage_range(start_time, end_time, step=STEP, rate_window=POD_RATE_WINDOW)
    save_and_plot_df(df_pod_cpu, f"Pod CPU Usage (Namespaces: {', '.join(TARGET_NAMESPACES)})", "pod_cpu_usage",
                     group_by_cols=['namespace', 'pod'], value_col='cpu_cores_used', node_ip_to_zone_map=node_ip_zone_map)

    # 4. Pod Memory Usage
    print("\nFetching Pod Memory Usage...")
    df_pod_mem = exporter.get_pod_memory_usage_range(start_time, end_time, step=STEP)
    save_and_plot_df(df_pod_mem, f"Pod Memory Usage (Namespaces: {', '.join(TARGET_NAMESPACES)})", "pod_memory_usage",
                     group_by_cols=['namespace', 'pod'], value_col='memory_usage_bytes', node_ip_to_zone_map=node_ip_zone_map)
    
    print("\n--- Script Finished ---")

if __name__ == "__main__":
    # Ensure matplotlib uses a non-interactive backend if no GUI is available
    # or if running in a headless environment.
    if "DISPLAY" not in os.environ:
        plt.switch_backend('Agg')
    main() 