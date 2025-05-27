"""
MuBench Visualization Module
Cloud-Edge Continuum Research Project

This module provides comprehensive visualization and analysis capabilities
for MuBench experiment metrics with modular, extensible architecture.

Features:
- Modular visualization components per resource type
- Automatic node zone detection via kubectl
- Enhanced plot labels with node names and zones
- Comprehensive summary reports with zone mapping
- Time series analysis with zone-aware legends
- Resource utilization overview across zones
- Zone filtering to exclude specific zones from analysis

Usage:
    from mu_bench.visualization import MetricsVisualizer
    
    # Basic usage
    viz = MetricsVisualizer('DATA/edge_experiment_2025_05_27_10_03/metrics/')
    
    # With zone filtering (exclude Unknown and empty zones)
    viz = MetricsVisualizer(
        'DATA/edge_experiment_2025_05_27_10_03/metrics/',
        exclude_zones=['Unknown', 'edge-site-2']
    )
    
    viz.show_summary()  # Shows zone mapping and comprehensive stats
    viz.plot_all()      # Generate all available plots at once
    
    # Individual analysis components
    viz.plot_cpu_analysis()
    viz.plot_memory_analysis()
    viz.plot_pod_analysis()
    viz.plot_istio_analysis()

Requirements:
- kubectl access to cluster for zone detection (optional but recommended)
- pandas, matplotlib, seaborn, numpy
"""

from .interface import MetricsVisualizer
from .utils import quick_analysis, load_and_summarize

__all__ = [
    'MetricsVisualizer',
    'quick_analysis', 
    'load_and_summarize'
]

__version__ = '1.0.0' 