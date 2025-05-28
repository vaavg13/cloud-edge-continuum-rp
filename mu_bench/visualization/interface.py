"""
Main Interface for MuBench Visualization Module.

This module provides the main MetricsVisualizer interface that maintains
the same API as the original monolithic script while using the new
modular architecture underneath.
"""

from pathlib import Path
import pandas as pd
import re
from datetime import datetime
import pytz
from dateutil.tz import tzlocal
from .base import DataLoader
from .cpu_visualizer import CPUVisualizer, PodCPUVisualizer
from .memory_visualizer import MemoryVisualizer, PodMemoryVisualizer, ResourceOverviewVisualizer
from .network_visualizer import IstioLatencyVisualizer, NetworkAnalysisVisualizer, ServiceMeshAnalyzer
from .zone_visualizer import ZoneAnalysisVisualizer, PodZoneAnalysisVisualizer
from .edge_requests_visualizer import EdgeRequestsVisualizer


class MetricsVisualizer:
    """
    Main interface for MuBench metrics visualization and analysis.
    
    This class provides the same API as the original MetricsVisualizerNotebook
    but uses a modular architecture underneath for better maintainability
    and extensibility.
    """
    
    def __init__(self, experiment_dir, exclude_zones=None):
        """Initialize the metrics visualizer with the main experiment directory path.
        
        Args:
            experiment_dir (str): Path to the main experiment directory 
                                  (e.g., '../DATA/edge_experiment_YYYY_MM_DD_HH_MM/')
            exclude_zones (list, optional): List of zone names to exclude from analysis
                                          (e.g., ['Unknown', 'edge-site-2'])
        """
        self.experiment_dir = Path(experiment_dir)
        self.metrics_dir = self.experiment_dir / 'metrics'
        
        if not self.metrics_dir.exists():
            raise FileNotFoundError(f"Metrics directory not found at: {self.metrics_dir}")
        
        self.exclude_zones = exclude_zones or []
        
        # Extract experiment start time from experiment_dir name
        experiment_start_time = None
        try:
            dir_name = self.experiment_dir.name
            match = re.search(r'(\d{4}_\d{2}_\d{2}_\d{2}_\d{2})', dir_name)
            if match:
                time_str = match.group(1)
                # Parse as naive datetime first
                dt_obj_naive = datetime.strptime(time_str, '%Y_%m_%d_%H_%M')
                
                # Convert to pandas Timestamp, then localize and convert to UTC
                ts_naive = pd.Timestamp(dt_obj_naive)
                local_tz_info = tzlocal() # Get local tzinfo object
                ts_local = ts_naive.tz_localize(local_tz_info) # Localize to system's timezone
                experiment_start_time = ts_local.tz_convert('UTC') # Convert to UTC
                
                print(f"🕒 Parsed time_str '{time_str}' from {dir_name}. Assumed local time: {ts_local}. Converted to UTC for filtering: {experiment_start_time}")
            else:
                print(f"⚠️ Could not parse experiment start time from directory name: {dir_name}. Visualizations will not be filtered by start time.")
        except Exception as e:
            print(f"⚠️ Error parsing experiment start time from {dir_name}: {e}. Visualizations will not be filtered by start time.")

        # Initialize data loader with the actual metrics directory path
        self.data_loader = DataLoader(str(self.metrics_dir), experiment_start_time=experiment_start_time)
        
        # Initialize visualization components
        self.cpu_viz = CPUVisualizer(self.data_loader, exclude_zones)
        self.pod_cpu_viz = PodCPUVisualizer(self.data_loader, exclude_zones)
        self.memory_viz = MemoryVisualizer(self.data_loader, exclude_zones)
        self.pod_memory_viz = PodMemoryVisualizer(self.data_loader, exclude_zones)
        self.resource_overview_viz = ResourceOverviewVisualizer(self.data_loader, exclude_zones)
        self.istio_viz = IstioLatencyVisualizer(self.data_loader, exclude_zones)
        self.network_viz = NetworkAnalysisVisualizer(self.data_loader, exclude_zones)
        self.service_mesh_viz = ServiceMeshAnalyzer(self.data_loader, exclude_zones)
        self.zone_viz = ZoneAnalysisVisualizer(self.data_loader, exclude_zones)
        self.pod_zone_viz = PodZoneAnalysisVisualizer(self.data_loader, exclude_zones)
        self.edge_requests_viz = EdgeRequestsVisualizer(self.data_loader, exclude_zones)
    
    # Data access properties (for backward compatibility)
    @property
    def data(self):
        """Access to the underlying data dictionary."""
        return self.data_loader.data
    
    @property
    def node_ip_to_zone_map(self):
        """Access to the node IP to zone mapping."""
        return self.data_loader.node_ip_to_zone_map
    
    # Main analysis methods
    def show_summary(self):
        """Display a comprehensive summary of the loaded data."""
        print("=" * 60)
        print("METRICS SUMMARY REPORT")
        print("=" * 60)
        
        # Zone filtering information
        if self.exclude_zones:
            print(f"\n🚫 ZONE FILTERING ENABLED:")
            print(f"   • Excluded zones: {', '.join(self.exclude_zones)}")
        
        # Node Zone Information
        if self.node_ip_to_zone_map:
            print(f"\n🌍 NODE ZONE MAPPING:")
            zones = {}
            for node_ip, info in self.node_ip_to_zone_map.items():
                zone = info['zone']
                if zone not in zones:
                    zones[zone] = []
                zones[zone].append(f"{info['name']} ({node_ip})")
            
            for zone, nodes in zones.items():
                if zone in self.exclude_zones:
                    print(f"   • Zone {zone}: {', '.join(nodes)} [EXCLUDED]")
                else:
                    print(f"   • Zone {zone}: {', '.join(nodes)}")
        else:
            print(f"\n🌍 NODE ZONE MAPPING: Not available (kubectl access required)")
        
        # Print summaries from each component
        self.cpu_viz.print_summary()
        self.memory_viz.print_summary()
        self.pod_cpu_viz.print_summary()
        self.pod_memory_viz.print_summary()
        self.istio_viz.print_summary()
        
        # Edge requests summary
        if self.edge_requests_viz.requests_data is not None:
            self.edge_requests_viz.print_summary()
        
        # Data availability
        print(f"\n📈 DATA AVAILABILITY:")
        for metric_type in ['node_cpu', 'node_memory', 'pod_cpu', 'pod_memory', 'istio_latency']:
            if self.data_loader.has_data(metric_type):
                data_len = len(self.data_loader.get_data(metric_type))
                print(f"   • {metric_type}: ✓ Available ({data_len} records)")
            else:
                print(f"   • {metric_type}: ✗ Not available")
        
        # Edge requests availability
        if self.edge_requests_viz.requests_data is not None:
            print(f"   • edge_requests: ✓ Available ({len(self.edge_requests_viz.requests_data)} records)")
        else:
            print(f"   • edge_requests: ✗ Not available")
        
        print("\n" + "=" * 60)
    
    # Node-level analysis methods
    def plot_cpu_analysis(self, figsize=(18, 16)):
        """Create and display CPU usage analysis plots."""
        return self.cpu_viz.plot_analysis(figsize)
    
    def plot_memory_analysis(self, figsize=(16, 12)):
        """Create and display memory usage analysis plots."""
        return self.memory_viz.plot_analysis(figsize)
    
    def plot_resource_overview(self, figsize=(18, 12)):
        """Create and display resource utilization overview plots."""
        return self.resource_overview_viz.plot_analysis(figsize)
    
    def plot_sites_analysis(self, figsize=(16, 12)):
        """Create and display inter-site correlation and comparison analysis."""
        return self.zone_viz.plot_analysis(figsize)
    
    # Pod-level analysis methods
    def plot_pod_cpu_analysis(self, figsize=(18, 14)):
        """Create and display pod CPU usage analysis plots."""
        return self.pod_cpu_viz.plot_analysis(figsize)
    
    def plot_pod_memory_analysis(self, figsize=(18, 14)):
        """Create and display pod memory usage analysis plots."""
        return self.pod_memory_viz.plot_analysis(figsize)
    
    def plot_pod_sites_analysis(self, figsize=(16, 12)):
        """Create and display pod-level inter-site analysis."""
        return self.pod_zone_viz.plot_analysis(figsize)
    
    # Network/Service analysis methods
    def plot_istio_latency_analysis(self, figsize=(18, 14)):
        """Create and display Istio latency analysis plots."""
        return self.istio_viz.plot_analysis(figsize)
    
    def plot_network_analysis(self, figsize=(18, 14)):
        """Create and display comprehensive network analysis plots."""
        return self.network_viz.plot_analysis(figsize)
    
    def plot_service_mesh_analysis(self, figsize=(20, 16)):
        """Create and display advanced service mesh analysis plots."""
        return self.service_mesh_viz.plot_analysis(figsize)
    
    # Edge requests analysis methods
    def plot_edge_requests_analysis(self, figsize=(20, 16)):
        """Create and display edge requests analysis plots."""
        return self.edge_requests_viz.plot_analysis(figsize)
    
    # Summary methods
    def get_data_summary(self):
        """Return a summary of the loaded data as a dictionary."""
        summary = {}
        
        # Collect summaries from all components
        if self.data_loader.has_data('node_cpu'):
            summary['cpu'] = self.cpu_viz.get_summary_stats()
        
        if self.data_loader.has_data('node_memory'):
            summary['memory'] = self.memory_viz.get_summary_stats()
        
        if self.data_loader.has_data('pod_cpu'):
            summary['pod_cpu'] = self.pod_cpu_viz.get_summary_stats()
        
        if self.data_loader.has_data('pod_memory'):
            summary['pod_memory'] = self.pod_memory_viz.get_summary_stats()
        
        if self.data_loader.has_data('istio_latency'):
            summary['istio_latency'] = self.istio_viz.get_summary_stats()
            summary['service_mesh'] = self.service_mesh_viz.get_summary_stats()
        
        if (self.data_loader.has_data('node_cpu') and 
            self.data_loader.has_data('node_memory')):
            summary['resource_overview'] = self.resource_overview_viz.get_summary_stats()
            summary['zone_analysis'] = self.zone_viz.get_summary_stats()
        
        if (self.data_loader.has_data('pod_cpu') and 
            self.data_loader.has_data('pod_memory')):
            summary['pod_zone_analysis'] = self.pod_zone_viz.get_summary_stats()
        
        # Edge requests summary
        if self.edge_requests_viz.requests_data is not None:
            summary['edge_requests'] = self.edge_requests_viz.get_summary_stats()
        
        return summary
    
    # Utility methods
    def has_data(self, metric_type):
        """Check if data is available for a specific metric type."""
        return self.data_loader.has_data(metric_type)
    
    def get_available_metrics(self):
        """Get a list of available metric types."""
        return [metric_type for metric_type in ['node_cpu', 'node_memory', 'pod_cpu', 'pod_memory', 'istio_latency'] 
                if self.data_loader.has_data(metric_type)]
    
    def get_zone_info(self):
        """Get zone mapping information."""
        return {
            'zone_mapping': self.node_ip_to_zone_map,
            'excluded_zones': self.exclude_zones,
            'available_zones': list(set(info['zone'] for info in self.node_ip_to_zone_map.values()))
        }
    
    def export_edge_requests_analysis(self, output_dir="edge_requests_analysis"):
        """Export edge requests analysis to files."""
        return self.edge_requests_viz.export_analysis(output_dir) 