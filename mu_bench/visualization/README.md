# MuBench Visualization Module

A modular, extensible visualization and analysis system for MuBench experiment metrics.

## Overview

The MuBench visualization module provides comprehensive analysis capabilities for cloud-edge continuum experiments. It has been refactored from a monolithic script into a modular architecture that separates concerns and makes the system more maintainable and extensible.

## Architecture

### Modular Design

The visualization system is organized into focused modules:

```
mu_bench/visualization/
├── __init__.py           # Main module exports
├── README.md            # This documentation
├── base.py              # Base classes and data loader
├── interface.py         # Main MetricsVisualizer interface
├── utils.py             # Utility functions
├── cpu_visualizer.py    # CPU metrics analysis
├── memory_visualizer.py # Memory metrics analysis
├── network_visualizer.py # Network/Istio metrics analysis
└── zone_visualizer.py   # Zone/site correlation analysis
```

### Components

#### Core Components

- **`DataLoader`**: Handles loading and managing CSV metrics data
- **`BaseVisualizer`**: Abstract base class with common functionality
- **`MetricsVisualizer`**: Main interface maintaining backward compatibility

#### Specialized Visualizers

- **`CPUVisualizer`**: Node-level CPU analysis with correlation matrices
- **`PodCPUVisualizer`**: Pod-level CPU analysis by namespace
- **`MemoryVisualizer`**: Node-level memory analysis
- **`PodMemoryVisualizer`**: Pod-level memory analysis with CPU correlation
- **`ResourceOverviewVisualizer`**: Combined CPU/memory resource analysis
- **`IstioLatencyVisualizer`**: Istio service mesh latency analysis
- **`ServiceMeshAnalyzer`**: Advanced service mesh analytics with anomaly detection
- **`ZoneAnalysisVisualizer`**: Inter-zone correlation analysis
- **`PodZoneAnalysisVisualizer`**: Pod-level zone analysis

## Usage

### Basic Usage (Maintains Original API)

```python
from mu_bench.visualization import MetricsVisualizer

# Basic usage
viz = MetricsVisualizer('DATA/edge_experiment_2025_05_27_10_03/metrics/')

# With zone filtering
viz = MetricsVisualizer(
    'DATA/edge_experiment_2025_05_27_10_03/metrics/',
    exclude_zones=['Unknown', 'edge-site-2']
)

# Show comprehensive summary
viz.show_summary()

# Generate all available plots
viz.plot_all()
```

### Individual Analysis Components

```python
# Node-level analysis
viz.plot_cpu_analysis()
viz.plot_memory_analysis()
viz.plot_resource_overview()
viz.plot_sites_analysis()

# Pod-level analysis
viz.plot_pod_cpu_analysis()
viz.plot_pod_memory_analysis()
viz.plot_pod_sites_analysis()

# Network analysis
viz.plot_istio_latency_analysis()
viz.plot_service_mesh_analysis()
```

### Advanced Analysis

```python
# Advanced CPU analysis (both node and pod level)
viz.plot_cpu_analysis_advanced()

# Advanced memory analysis
viz.plot_memory_analysis_advanced()

# Advanced network analysis with service mesh insights
viz.plot_network_analysis_advanced()
```

### Utility Functions

```python
from mu_bench.visualization import quick_analysis, load_and_summarize

# Quick analysis of all metrics
viz = quick_analysis('DATA/metrics/', exclude_zones=['Unknown'])

# Summary only
viz = load_and_summarize('DATA/metrics/')

# Specialized analysis
from mu_bench.visualization.utils import analyze_cpu_only, analyze_network_only

cpu_viz = analyze_cpu_only('DATA/metrics/')
net_viz = analyze_network_only('DATA/metrics/')
```

## Features

### Zone Filtering and Management

- Automatic node zone detection via kubectl
- Zone filtering to exclude specific zones from analysis
- Enhanced plot labels with node names and zones
- Inter-zone correlation analysis

### Comprehensive Metrics Support

#### Node-level Metrics
- CPU usage analysis with correlation matrices
- Memory usage analysis
- Resource utilization overview
- Cross-node correlation analysis

#### Pod-level Metrics
- CPU usage by namespace and individual pods
- Memory usage with CPU correlation
- Pod resource analysis by namespace

#### Network Metrics
- Istio service latency (P95) analysis
- Service mesh performance analysis
- Latency anomaly detection
- Service performance ranking

### Advanced Analytics

- **Correlation Analysis**: Cross-resource and cross-zone correlations
- **Anomaly Detection**: Statistical anomaly detection for latency
- **Performance Ranking**: Service performance scoring
- **Trend Analysis**: Resource utilization trends over time
- **Degradation Detection**: Automatic performance degradation detection

### Visualization Types

- Time series plots
- Box plots and distributions
- Correlation heatmaps
- Scatter plots
- Performance rankings
- Anomaly detection plots

## Data Requirements

### Supported CSV Files

The module expects the following CSV files in the metrics directory:

- `node_cpu_usage.csv`: Node-level CPU metrics
- `node_memory_usage.csv`: Node-level memory metrics
- `pod_cpu_usage.csv`: Pod-level CPU metrics
- `pod_memory_usage.csv`: Pod-level memory metrics
- `istio_latency.csv`: Istio service mesh latency metrics

### Required Columns

#### Node Metrics
- `timestamp`: Unix timestamp
- `node`: Node IP address
- `cpu_cores_used`: CPU cores used
- `memory_working_set_bytes`: Memory usage in bytes

#### Pod Metrics
- `timestamp`: Unix timestamp
- `namespace`: Kubernetes namespace
- `pod`: Pod name
- `cpu_cores_used`: CPU cores used
- `memory_usage_bytes`: Memory usage in bytes

#### Istio Metrics
- `timestamp`: Unix timestamp
- `namespace`: Kubernetes namespace
- `pod`: Service/pod name
- `p95_latency_ms`: P95 latency in milliseconds

## Dependencies

### Required Packages
- `pandas`: Data manipulation and analysis
- `matplotlib`: Plotting library
- `seaborn`: Statistical data visualization
- `numpy`: Numerical computing

### Optional Dependencies
- `kubectl`: For automatic zone detection (recommended)

## Configuration

### Zone Filtering

```python
# Exclude specific zones from analysis
viz = MetricsVisualizer(
    'DATA/metrics/',
    exclude_zones=['Unknown', 'edge-site-2', 'maintenance-zone']
)
```

### Visualization Settings

The module uses seaborn styling by default:
- Style: `seaborn-v0_8`
- Color palette: `husl`
- Figure sizes are configurable for each plot type

## Backward Compatibility

The new modular system maintains full backward compatibility with the original `MetricsVisualizerNotebook` interface:

```python
# Old import still works
from scripts.metrics_visualizer_notebook import MetricsVisualizerNotebook

# New import (recommended)
from mu_bench.visualization import MetricsVisualizer

# Both provide the same API
viz1 = MetricsVisualizerNotebook('DATA/metrics/')
viz2 = MetricsVisualizer('DATA/metrics/')  # Same functionality
```

## Extending the System

### Adding New Visualizers

1. Create a new visualizer class inheriting from `BaseVisualizer`
2. Implement the required abstract methods
3. Add the visualizer to the main interface
4. Update the module exports

Example:

```python
from .base import BaseVisualizer

class CustomVisualizer(BaseVisualizer):
    def plot_analysis(self, figsize=None):
        # Implementation here
        pass
    
    def get_summary_stats(self):
        # Implementation here
        pass
```

### Adding New Metrics

1. Update the `DataLoader` to handle new CSV files
2. Create appropriate visualizer methods
3. Update the interface to expose new functionality

## Performance Considerations

- Large datasets are automatically sampled for visualization
- Extreme outliers are filtered for better plot readability
- Memory usage is optimized through lazy loading
- Zone filtering reduces processing overhead

## Troubleshooting

### Common Issues

1. **No zone mapping available**: Ensure kubectl access to the cluster
2. **Empty plots**: Check if data files exist and contain data beyond headers
3. **Memory errors**: Use zone filtering to reduce dataset size
4. **Import errors**: Ensure all dependencies are installed

### Debugging

Enable detailed logging by checking data availability:

```python
viz = MetricsVisualizer('DATA/metrics/')
print("Available metrics:", viz.get_available_metrics())
print("Zone info:", viz.get_zone_info())
```

## Migration Guide

### From Original Script

If you're migrating from the original monolithic script:

1. Replace import:
   ```python
   # Old
   from scripts.metrics_visualizer_notebook import MetricsVisualizerNotebook
   
   # New
   from mu_bench.visualization import MetricsVisualizer
   ```

2. Update class name (optional):
   ```python
   # Old
   viz = MetricsVisualizerNotebook('DATA/metrics/')
   
   # New
   viz = MetricsVisualizer('DATA/metrics/')
   ```

3. All existing method calls remain the same
4. New methods are available for advanced analysis

### Benefits of Migration

- **Modularity**: Easier to maintain and extend
- **Performance**: Better memory management and faster loading
- **Features**: New advanced analysis capabilities
- **Testing**: Individual components can be tested separately
- **Documentation**: Better organized and documented code 