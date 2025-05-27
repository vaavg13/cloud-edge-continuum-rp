"""
Utility functions for MuBench visualization module.

This module provides convenience functions for quick analysis and maintains
backward compatibility with the original script API.
"""

from .interface import MetricsVisualizer


def quick_analysis(metrics_dir, exclude_zones=None):
    """Perform a quick analysis of all metrics in the directory.
    
    Args:
        metrics_dir (str): Path to the metrics directory
        exclude_zones (list, optional): List of zone names to exclude from analysis
        
    Returns:
        MetricsVisualizer: The visualizer instance for further analysis
    """
    viz = MetricsVisualizer(metrics_dir, exclude_zones=exclude_zones)
    viz.plot_all()
    return viz


def load_and_summarize(metrics_dir, exclude_zones=None):
    """Load data and show summary only.
    
    Args:
        metrics_dir (str): Path to the metrics directory
        exclude_zones (list, optional): List of zone names to exclude from analysis
        
    Returns:
        MetricsVisualizer: The visualizer instance for further analysis
    """
    viz = MetricsVisualizer(metrics_dir, exclude_zones=exclude_zones)
    viz.show_summary()
    return viz


def create_visualizer(metrics_dir, exclude_zones=None):
    """Create a new MetricsVisualizer instance.
    
    Args:
        metrics_dir (str): Path to the metrics directory
        exclude_zones (list, optional): List of zone names to exclude from analysis
        
    Returns:
        MetricsVisualizer: The visualizer instance
    """
    return MetricsVisualizer(metrics_dir, exclude_zones=exclude_zones)


def analyze_cpu_only(metrics_dir, exclude_zones=None):
    """Perform CPU-only analysis.
    
    Args:
        metrics_dir (str): Path to the metrics directory
        exclude_zones (list, optional): List of zone names to exclude from analysis
        
    Returns:
        MetricsVisualizer: The visualizer instance
    """
    viz = MetricsVisualizer(metrics_dir, exclude_zones=exclude_zones)
    
    if viz.has_data('node_cpu'):
        print("📊 Node CPU Analysis:")
        viz.plot_cpu_analysis()
    
    if viz.has_data('pod_cpu'):
        print("\n📦 Pod CPU Analysis:")
        viz.plot_pod_cpu_analysis()
    
    return viz


def analyze_memory_only(metrics_dir, exclude_zones=None):
    """Perform memory-only analysis.
    
    Args:
        metrics_dir (str): Path to the metrics directory
        exclude_zones (list, optional): List of zone names to exclude from analysis
        
    Returns:
        MetricsVisualizer: The visualizer instance
    """
    viz = MetricsVisualizer(metrics_dir, exclude_zones=exclude_zones)
    
    if viz.has_data('node_memory'):
        print("💾 Node Memory Analysis:")
        viz.plot_memory_analysis()
    
    if viz.has_data('pod_memory'):
        print("\n📦 Pod Memory Analysis:")
        viz.plot_pod_memory_analysis()
    
    return viz


def analyze_network_only(metrics_dir, exclude_zones=None):
    """Perform network-only analysis.
    
    Args:
        metrics_dir (str): Path to the metrics directory
        exclude_zones (list, optional): List of zone names to exclude from analysis
        
    Returns:
        MetricsVisualizer: The visualizer instance
    """
    viz = MetricsVisualizer(metrics_dir, exclude_zones=exclude_zones)
    
    if viz.has_data('istio_latency'):
        print("🌐 Network Analysis:")
        viz.plot_istio_latency_analysis()
        
        print("\n🔬 Advanced Service Mesh Analysis:")
        viz.plot_service_mesh_analysis()
    else:
        print("❌ No network data available for analysis")
    
    return viz


def analyze_zones_only(metrics_dir, exclude_zones=None):
    """Perform zone-only analysis.
    
    Args:
        metrics_dir (str): Path to the metrics directory
        exclude_zones (list, optional): List of zone names to exclude from analysis
        
    Returns:
        MetricsVisualizer: The visualizer instance
    """
    viz = MetricsVisualizer(metrics_dir, exclude_zones=exclude_zones)
    
    if viz.has_data('node_cpu') and viz.has_data('node_memory'):
        print("🌍 Zone Analysis:")
        viz.plot_sites_analysis()
    else:
        print("❌ Insufficient data for zone analysis")
    
    return viz


def compare_experiments(metrics_dirs, exclude_zones=None):
    """Compare multiple experiments.
    
    Args:
        metrics_dirs (list): List of paths to metrics directories
        exclude_zones (list, optional): List of zone names to exclude from analysis
        
    Returns:
        list: List of MetricsVisualizer instances
    """
    visualizers = []
    
    for i, metrics_dir in enumerate(metrics_dirs):
        print(f"\n{'='*60}")
        print(f"EXPERIMENT {i+1}: {metrics_dir}")
        print(f"{'='*60}")
        
        viz = MetricsVisualizer(metrics_dir, exclude_zones=exclude_zones)
        viz.show_summary()
        visualizers.append(viz)
    
    return visualizers


def get_experiment_overview(metrics_dir, exclude_zones=None):
    """Get a comprehensive overview of an experiment.
    
    Args:
        metrics_dir (str): Path to the metrics directory
        exclude_zones (list, optional): List of zone names to exclude from analysis
        
    Returns:
        dict: Comprehensive experiment overview
    """
    viz = MetricsVisualizer(metrics_dir, exclude_zones=exclude_zones)
    
    overview = {
        'metrics_directory': str(viz.metrics_dir),
        'excluded_zones': viz.exclude_zones,
        'available_metrics': viz.get_available_metrics(),
        'zone_info': viz.get_zone_info(),
        'data_summary': viz.get_data_summary()
    }
    
    return overview


def validate_experiment_data(metrics_dir):
    """Validate experiment data integrity.
    
    Args:
        metrics_dir (str): Path to the metrics directory
        
    Returns:
        dict: Validation results
    """
    try:
        viz = MetricsVisualizer(metrics_dir)
        
        validation = {
            'valid': True,
            'metrics_directory': str(viz.metrics_dir),
            'available_metrics': viz.get_available_metrics(),
            'data_counts': {},
            'issues': []
        }
        
        # Check data counts
        for metric_type in ['node_cpu', 'node_memory', 'pod_cpu', 'pod_memory', 'istio_latency']:
            if viz.has_data(metric_type):
                data_count = len(viz.data_loader.get_data(metric_type))
                validation['data_counts'][metric_type] = data_count
                
                if data_count < 10:
                    validation['issues'].append(f"Low data count for {metric_type}: {data_count} records")
            else:
                validation['data_counts'][metric_type] = 0
        
        # Check for zone mapping
        if not viz.node_ip_to_zone_map:
            validation['issues'].append("No zone mapping available (kubectl access might be required)")
        
        # Check for minimum viable dataset
        if not any(viz.has_data(mt) for mt in ['node_cpu', 'node_memory']):
            validation['issues'].append("No node-level metrics available")
            validation['valid'] = False
        
        if validation['issues']:
            validation['valid'] = len(validation['issues']) <= 2  # Allow minor issues
        
        return validation
        
    except Exception as e:
        return {
            'valid': False,
            'error': str(e),
            'metrics_directory': metrics_dir
        }


# Backward compatibility aliases
MetricsVisualizerNotebook = MetricsVisualizer  # For direct replacement

# Legacy function names for backward compatibility
def create_metrics_visualizer_notebook(metrics_dir, exclude_zones=None):
    """Legacy function name for backward compatibility."""
    return MetricsVisualizer(metrics_dir, exclude_zones=exclude_zones) 