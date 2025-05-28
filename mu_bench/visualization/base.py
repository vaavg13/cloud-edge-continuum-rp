"""
Base classes for MuBench visualization components.

This module provides the foundational classes and utilities that are shared
across all visualization components.
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from pathlib import Path
import subprocess
import json
import warnings
from abc import ABC, abstractmethod
import pytz
from datetime import datetime
from dateutil.tz import tzlocal

warnings.filterwarnings('ignore')

# Set style for better visualizations
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")


class BaseVisualizer(ABC):
    """Abstract base class for all visualization components."""
    
    def __init__(self, data_loader, exclude_zones=None):
        """Initialize the visualizer with data loader and filtering options.
        
        Args:
            data_loader (DataLoader): The data loader instance
            exclude_zones (list, optional): List of zone names to exclude from analysis
        """
        self.data_loader = data_loader
        self.exclude_zones = exclude_zones or []
        self.node_ip_to_zone_map = data_loader.node_ip_to_zone_map
    
    def _generate_node_label(self, node_ip):
        """Generate a descriptive label for a node including zone information."""
        if node_ip in self.node_ip_to_zone_map:
            node_info = self.node_ip_to_zone_map[node_ip]
            return f"{node_info['name']} (Zone: {node_info['zone']})"
        else:
            return f"{node_ip} (Zone: Unknown)"
    
    def _filter_by_zones(self, df, zone_column='zone'):
        """Filter dataframe to exclude specified zones.
        
        Args:
            df (pandas.DataFrame): DataFrame to filter
            zone_column (str): Name of the zone column
            
        Returns:
            pandas.DataFrame: Filtered dataframe
        """
        if not self.exclude_zones or zone_column not in df.columns:
            return df
        
        filtered_df = df[~df[zone_column].isin(self.exclude_zones)].copy()
        
        # Log filtering information
        original_zones = set(df[zone_column].unique())
        remaining_zones = set(filtered_df[zone_column].unique())
        excluded_zones = original_zones - remaining_zones
        
        if excluded_zones:
            print(f"🚫 Excluded zones from analysis: {', '.join(sorted(excluded_zones))}")
            print(f"📊 Remaining zones: {', '.join(sorted(remaining_zones))}")
        
        return filtered_df
    
    def _prepare_zone_data(self, df, metric_column):
        """Prepare dataframe with zone information and apply filtering.
        
        Args:
            df (pandas.DataFrame): Input dataframe
            metric_column (str): Name of the metric column
            
        Returns:
            pandas.DataFrame: Dataframe with zone column and filtering applied
        """
        df_copy = df.copy()
        
        # Add zone information
        df_copy['zone'] = df_copy['node'].map(
            lambda x: self.node_ip_to_zone_map.get(x, {}).get('zone', 'Unknown')
        )
        
        # Apply zone filtering
        df_filtered = self._filter_by_zones(df_copy, 'zone')
        
        # Remove zones with no data
        zones_with_data = df_filtered.groupby('zone')[metric_column].count()
        zones_to_keep = zones_with_data[zones_with_data > 0].index.tolist()
        
        if len(zones_to_keep) < len(zones_with_data):
            zones_no_data = set(zones_with_data.index) - set(zones_to_keep)
            print(f"⚠ Zones with no data removed: {', '.join(sorted(zones_no_data))}")
        
        return df_filtered[df_filtered['zone'].isin(zones_to_keep)]
    
    @abstractmethod
    def plot_analysis(self, figsize=None):
        """Create and display analysis plots for this component.
        
        Args:
            figsize (tuple, optional): Figure size (width, height)
            
        Returns:
            matplotlib.figure.Figure: The created figure
        """
        pass
    
    @abstractmethod
    def get_summary_stats(self):
        """Get summary statistics for this component.
        
        Returns:
            dict: Summary statistics
        """
        pass


class DataLoader:
    """Handles loading and managing metrics data from CSV files."""
    
    def __init__(self, metrics_dir, experiment_start_time=None):
        """Initialize the data loader with the metrics directory path.
        
        Args:
            metrics_dir (str): Path to the metrics directory
            experiment_start_time (pd.Timestamp, optional): Experiment start time for filtering
        """
        self.metrics_dir = Path(metrics_dir)
        if not self.metrics_dir.exists():
            raise FileNotFoundError(f"Metrics directory not found: {metrics_dir}")
        
        self.data = {}
        self.node_ip_to_zone_map = {}
        self.experiment_start_time = experiment_start_time
        self.load_data()
        self.load_node_zone_mapping()
    
    def load_data(self):
        """Load all available CSV files from the metrics directory."""
        csv_files = {
            'node_cpu': 'node_cpu_usage.csv',
            'node_memory': 'node_memory_usage.csv',
            'pod_cpu': 'pod_cpu_usage.csv',
            'pod_memory': 'pod_memory_usage.csv',
            'istio_latency': 'istio_latency.csv'
        }
        
        # Get local timezone
        local_tz_obj = tzlocal()
        try:
            local_tz_display_name = local_tz_obj.tzname(datetime.now(local_tz_obj))
            if not local_tz_display_name:
                local_tz_display_name = str(local_tz_obj)
        except:
            local_tz_display_name = str(local_tz_obj)

        print(f"🕒 Plotting timestamps will be converted to local timezone: {local_tz_display_name}")

        for metric_type, filename in csv_files.items():
            file_path = self.metrics_dir / filename
            if file_path.exists():
                try:
                    df = pd.read_csv(file_path)
                    if len(df) > 1:  # Check if file has data beyond header
                        # Convert timestamps to datetime (UTC)
                        if 'timestamp' in df.columns:
                            df['datetime'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)
                        if 'collection_time' in df.columns:
                            df['collection_datetime'] = pd.to_datetime(df['collection_time'], unit='s', utc=True)
                        
                        # Filter by experiment_start_time (timestamps are UTC at this point)
                        if self.experiment_start_time:
                            datetime_col_to_filter = None
                            if 'datetime' in df.columns and not df.empty:
                                datetime_col_to_filter = 'datetime'
                            elif 'collection_datetime' in df.columns and not df.empty:
                                datetime_col_to_filter = 'collection_datetime'
                            
                            if datetime_col_to_filter:
                                records_before_filter = len(df)
                                df = df[df[datetime_col_to_filter] >= self.experiment_start_time].copy()
                        
                        # Convert to local timezone for plotting
                        if 'datetime' in df.columns and not df.empty:
                            df['datetime'] = df['datetime'].dt.tz_convert(local_tz_obj)
                        if 'collection_datetime' in df.columns and not df.empty:
                            df['collection_datetime'] = df['collection_datetime'].dt.tz_convert(local_tz_obj)
                        
                        self.data[metric_type] = df
                        print(f"✓ Loaded {metric_type}: {len(df)} records (filtered by start time if applicable, converted to {local_tz_display_name})")
                    else:
                        print(f"⚠ {metric_type}: File exists but contains no data")
                except Exception as e:
                    print(f"✗ Error loading {metric_type}: {e}")
            else:
                print(f"⚠ {metric_type}: File not found")
    
    def load_node_zone_mapping(self):
        """Load node IP to zone mapping using kubectl."""
        try:
            nodes_json_bytes = subprocess.check_output(
                ["kubectl", "get", "nodes", "-o", "json"],
                stderr=subprocess.DEVNULL
            )
            nodes_data = json.loads(nodes_json_bytes)

            for node in nodes_data["items"]:
                node_name = node["metadata"]["name"]
                labels = node["metadata"]["labels"]
                
                # Get zone information
                zone = labels.get("topology.kubernetes.io/zone")
                if not zone:
                    zone = next((v for k, v in labels.items() if "zone" in k.lower()), "Unknown")
                
                # Get node IP
                node_ip = None
                if "status" in node and "addresses" in node["status"]:
                    for address_info in node["status"]["addresses"]:
                        if address_info.get("type") == "InternalIP":
                            node_ip = address_info.get("address")
                            break
                    if not node_ip:  # If no InternalIP, take the first available IP
                        for address_info in node["status"]["addresses"]:
                            if address_info.get("address"):
                                node_ip = address_info.get("address")
                                break
                
                if node_ip:
                    self.node_ip_to_zone_map[node_ip] = {"zone": zone, "name": node_name}
            
            if self.node_ip_to_zone_map:
                print(f"✓ Loaded zone mapping for {len(self.node_ip_to_zone_map)} nodes")
            else:
                print("⚠ No node zone mapping could be loaded")
                
        except subprocess.CalledProcessError:
            print("⚠ kubectl not available or no access to cluster - zone mapping disabled")
        except json.JSONDecodeError:
            print("⚠ Error parsing kubectl output - zone mapping disabled")
        except Exception as e:
            print(f"⚠ Error loading node zone mapping: {e}")
    
    def get_data(self, metric_type):
        """Get data for a specific metric type.
        
        Args:
            metric_type (str): The metric type to retrieve
            
        Returns:
            pandas.DataFrame or None: The data if available, None otherwise
        """
        return self.data.get(metric_type)
    
    def has_data(self, metric_type):
        """Check if data is available for a specific metric type.
        
        Args:
            metric_type (str): The metric type to check
            
        Returns:
            bool: True if data is available, False otherwise
        """
        return metric_type in self.data and len(self.data[metric_type]) > 0 