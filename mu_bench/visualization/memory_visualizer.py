"""
Memory Visualization Module for MuBench.

This module provides comprehensive memory usage analysis and visualization
capabilities for both node-level and pod-level memory metrics.
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from .base import BaseVisualizer


class MemoryVisualizer(BaseVisualizer):
    """Handles node-level memory usage visualization and analysis."""
    
    def plot_analysis(self, figsize=(16, 12)):
        """Create and display memory usage analysis plots."""
        if not self.data_loader.has_data('node_memory'):
            print("❌ No node memory data available for visualization")
            return None
        
        # Prepare data with memory conversion and zone filtering
        print("🔄 Preparing memory data with zone filtering...")
        df_temp = self.data_loader.get_data('node_memory').copy()
        df_temp['memory_gb'] = df_temp['memory_working_set_bytes'] / (1024**3)
        df = self._prepare_zone_data(df_temp, 'memory_gb')
        
        if len(df) == 0:
            print("❌ No memory data remaining after zone filtering")
            return None
        
        # Create subplots
        fig, axes = plt.subplots(2, 2, figsize=figsize)
        fig.suptitle('Node Memory Usage Analysis', fontsize=16, fontweight='bold')
        
        # 1. Time series plot for each node
        self._plot_time_series(axes[0, 0], df)
        
        # 2. Box plot of memory usage by node
        self._plot_distribution_boxplot(axes[0, 1], df)
        
        # 3. Memory usage correlation heatmap between nodes
        self._plot_correlation_matrix(axes[1, 0], df)
        
        # 4. Memory trend analysis
        self._plot_summary_statistics(axes[1, 1], df)
        
        plt.tight_layout()
        plt.close('all')  # Prevent duplicate plots in VS Code notebooks
        plt.show()
        
        return fig
    
    def _plot_time_series(self, ax, df):
        """Plot memory usage time series for each node."""
        for node in df['node'].unique():
            node_data = df[df['node'] == node]
            node_label = self._generate_node_label(node)
            ax.plot(node_data['datetime'], node_data['memory_gb'], 
                   label=node_label, marker='o', markersize=1, alpha=0.7)
        
        ax.set_title('Memory Usage Over Time by Node')
        ax.set_xlabel('Time')
        ax.set_ylabel('Memory Usage (GB)')
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis='x', rotation=45)
    
    def _plot_distribution_boxplot(self, ax, df):
        """Plot memory usage distribution by node."""
        df.boxplot(column='memory_gb', by='node', ax=ax)
        ax.set_title('Memory Usage Distribution by Node')
        ax.set_xlabel('Node')
        ax.set_ylabel('Memory Usage (GB)')
        plt.suptitle('')  # Remove auto-generated title
    
    def _plot_correlation_matrix(self, ax, df):
        """Plot memory usage correlation matrix between nodes."""
        pivot_memory = df.pivot_table(values='memory_gb', 
                                     index='datetime', 
                                     columns='node', 
                                     aggfunc='mean')
        
        if len(pivot_memory.columns) > 1:
            correlation_matrix = pivot_memory.corr()
            sns.heatmap(correlation_matrix, ax=ax, annot=True, cmap='coolwarm', center=0,
                       cbar_kws={'label': 'Correlation'})
            ax.set_title('Memory Usage Correlation Between Nodes')
        else:
            ax.text(0.5, 0.5, 'Single Node\nNo Correlation\nAnalysis', 
                   ha='center', va='center', transform=ax.transAxes, fontsize=12)
            ax.set_title('Memory Usage Correlation Between Nodes')
    
    def _plot_summary_statistics(self, ax, df):
        """Plot memory usage statistics by node."""
        stats = df.groupby('node')['memory_gb'].agg(['mean', 'std', 'min', 'max'])
        stats.plot(kind='bar', ax=ax)
        ax.set_title('Memory Usage Statistics by Node')
        ax.set_xlabel('Node')
        ax.set_ylabel('Memory Usage (GB)')
        ax.legend(['Mean', 'Std Dev', 'Min', 'Max'])
        ax.tick_params(axis='x', rotation=45)
    
    def get_summary_stats(self):
        """Get memory usage summary statistics."""
        if not self.data_loader.has_data('node_memory'):
            return {}
        
        mem_df = self.data_loader.get_data('node_memory').copy()
        mem_df['memory_gb'] = mem_df['memory_working_set_bytes'] / (1024**3)
        
        stats = {
            'total_records': len(mem_df),
            'nodes': mem_df['node'].nunique(),
            'avg_usage_gb': mem_df['memory_gb'].mean(),
            'peak_usage_gb': mem_df['memory_gb'].max(),
            'per_node_stats': mem_df.groupby('node')['memory_gb'].agg(['mean', 'max', 'std']).to_dict()
        }
        
        return stats
    
    def print_summary(self):
        """Print detailed memory usage summary."""
        if not self.data_loader.has_data('node_memory'):
            print("❌ No node memory data available")
            return
        
        mem_df = self.data_loader.get_data('node_memory').copy()
        mem_df['memory_gb'] = mem_df['memory_working_set_bytes'] / (1024**3)
        
        print(f"\n💾 NODE MEMORY USAGE:")
        print(f"   • Total data points: {len(mem_df)}")
        print(f"   • Nodes monitored: {mem_df['node'].nunique()}")
        print(f"   • Average memory usage: {mem_df['memory_gb'].mean():.2f} GB")
        print(f"   • Peak memory usage: {mem_df['memory_gb'].max():.2f} GB")
        
        # Per-node stats
        node_stats = mem_df.groupby('node')['memory_gb'].agg(['mean', 'max', 'std']).round(2)
        print(f"   • Per-node statistics:")
        for node, stats in node_stats.iterrows():
            node_label = self._generate_node_label(node)
            print(f"     - {node_label}: avg={stats['mean']} GB, max={stats['max']} GB, std={stats['std']} GB")


class PodMemoryVisualizer(BaseVisualizer):
    """Handles pod-level memory usage visualization and analysis."""
    
    def plot_analysis(self, figsize=(18, 14)):
        """Create and display pod memory usage analysis plots."""
        if not self.data_loader.has_data('pod_memory'):
            print("❌ No pod memory data available for visualization")
            return None
        
        df = self.data_loader.get_data('pod_memory').copy()
        
        if len(df) == 0:
            print("❌ Pod memory data is empty")
            return None
        
        # Convert bytes to MB for better readability
        df['memory_mb'] = df['memory_usage_bytes'] / (1024**2)
        
        # Create subplots
        fig, axes = plt.subplots(2, 2, figsize=figsize)
        fig.suptitle('Pod Memory Usage Analysis', fontsize=16, fontweight='bold')
        
        # 1. Time series plot by namespace
        self._plot_namespace_time_series(axes[0, 0], df)
        
        # 2. Box plot by namespace
        self._plot_namespace_distribution(axes[0, 1], df)
        
        # 3. Top pods by average memory usage
        self._plot_top_pods(axes[1, 0], df)
        
        # 4. Memory efficiency analysis (memory vs CPU correlation if available)
        self._plot_memory_cpu_correlation(axes[1, 1], df)
        
        plt.tight_layout()
        plt.close('all')
        plt.show()
        
        return fig
    
    def _plot_namespace_time_series(self, ax, df):
        """Plot memory usage time series by namespace."""
        namespaces = df['namespace'].unique()
        colors = plt.cm.Set3(np.linspace(0, 1, len(namespaces)))
        
        for i, namespace in enumerate(namespaces):
            ns_data = df[df['namespace'] == namespace]
            # Aggregate by namespace and time
            ns_agg = ns_data.groupby('datetime')['memory_mb'].sum().reset_index()
            ax.plot(ns_agg['datetime'], ns_agg['memory_mb'], 
                   label=f'Namespace: {namespace}', color=colors[i], linewidth=2, alpha=0.8)
        
        ax.set_title('Memory Usage Over Time by Namespace')
        ax.set_xlabel('Time')
        ax.set_ylabel('Total Memory Usage (MB)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis='x', rotation=45)
    
    def _plot_namespace_distribution(self, ax, df):
        """Plot memory usage distribution by namespace."""
        namespaces = df['namespace'].unique()
        colors = plt.cm.Set3(np.linspace(0, 1, len(namespaces)))
        
        namespace_data = [df[df['namespace'] == ns]['memory_mb'].values for ns in namespaces]
        bp = ax.boxplot(namespace_data, labels=namespaces, patch_artist=True)
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
        
        ax.set_title('Memory Usage Distribution by Namespace')
        ax.set_xlabel('Namespace')
        ax.set_ylabel('Memory Usage (MB)')
        ax.tick_params(axis='x', rotation=45)
        ax.grid(True, alpha=0.3)
    
    def _plot_top_pods(self, ax, df):
        """Plot top pods by average memory usage."""
        pod_stats = df.groupby(['namespace', 'pod'])['memory_mb'].agg(['mean', 'max']).reset_index()
        pod_stats['pod_label'] = pod_stats['namespace'] + '/' + pod_stats['pod']
        top_pods = pod_stats.nlargest(10, 'mean')
        
        bars = ax.barh(range(len(top_pods)), top_pods['mean'], color='lightcoral', alpha=0.7)
        ax.set_yticks(range(len(top_pods)))
        ax.set_yticklabels(top_pods['pod_label'], fontsize=8)
        ax.set_xlabel('Average Memory Usage (MB)')
        ax.set_title('Top 10 Pods by Average Memory Usage')
        ax.grid(True, alpha=0.3, axis='x')
        
        # Add value labels on bars
        for i, (bar, value) in enumerate(zip(bars, top_pods['mean'])):
            ax.text(value + max(top_pods['mean']) * 0.01, bar.get_y() + bar.get_height()/2, 
                   f'{value:.1f}', va='center', fontsize=8)
    
    def _plot_memory_cpu_correlation(self, ax, df):
        """Plot memory vs CPU correlation if CPU data is available."""
        if self.data_loader.has_data('pod_cpu') and len(self.data_loader.get_data('pod_cpu')) > 0:
            # Merge CPU and memory data
            cpu_df = self.data_loader.get_data('pod_cpu')
            merged_df = pd.merge(df, cpu_df[['timestamp', 'namespace', 'pod', 'cpu_cores_used']], 
                               on=['timestamp', 'namespace', 'pod'], how='inner')
            
            if len(merged_df) > 0:
                # Sample data for scatter plot
                sample_size = min(1000, len(merged_df))
                sample_df = merged_df.sample(n=sample_size)
                
                scatter = ax.scatter(sample_df['cpu_cores_used'], sample_df['memory_mb'], 
                                   alpha=0.6, c=range(len(sample_df)), cmap='viridis', s=20)
                ax.set_xlabel('CPU Cores Used')
                ax.set_ylabel('Memory Usage (MB)')
                ax.set_title('Memory vs CPU Usage Correlation')
                ax.grid(True, alpha=0.3)
                
                # Add correlation coefficient
                corr = sample_df['cpu_cores_used'].corr(sample_df['memory_mb'])
                ax.text(0.05, 0.95, f'Correlation: {corr:.3f}', 
                       transform=ax.transAxes, fontsize=10, 
                       bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
            else:
                ax.text(0.5, 0.5, 'No matching\nCPU/Memory data', 
                       ha='center', va='center', transform=ax.transAxes, fontsize=12)
                ax.set_title('Memory vs CPU Usage Correlation')
        else:
            ax.text(0.5, 0.5, 'No CPU data available\nfor correlation analysis', 
                   ha='center', va='center', transform=ax.transAxes, fontsize=12)
            ax.set_title('Memory vs CPU Usage Correlation')
    
    def get_summary_stats(self):
        """Get pod memory usage summary statistics."""
        if not self.data_loader.has_data('pod_memory'):
            return {}
        
        pod_mem_df = self.data_loader.get_data('pod_memory').copy()
        pod_mem_df['memory_mb'] = pod_mem_df['memory_usage_bytes'] / (1024**2)
        
        stats = {
            'total_records': len(pod_mem_df),
            'namespaces': pod_mem_df['namespace'].nunique(),
            'pods': pod_mem_df['pod'].nunique(),
            'avg_usage_mb': pod_mem_df['memory_mb'].mean(),
            'peak_usage_mb': pod_mem_df['memory_mb'].max(),
            'per_namespace_stats': pod_mem_df.groupby('namespace')['memory_mb'].agg(['mean', 'max', 'count']).to_dict()
        }
        
        return stats
    
    def print_summary(self):
        """Print detailed pod memory usage summary."""
        if not self.data_loader.has_data('pod_memory'):
            print("❌ No pod memory data available")
            return
        
        pod_mem_df = self.data_loader.get_data('pod_memory').copy()
        pod_mem_df['memory_mb'] = pod_mem_df['memory_usage_bytes'] / (1024**2)
        
        print(f"\n💾 POD MEMORY USAGE:")
        print(f"   • Total data points: {len(pod_mem_df)}")
        print(f"   • Namespaces monitored: {pod_mem_df['namespace'].nunique()}")
        print(f"   • Pods monitored: {pod_mem_df['pod'].nunique()}")
        print(f"   • Average memory usage: {pod_mem_df['memory_mb'].mean():.2f} MB")
        print(f"   • Peak memory usage: {pod_mem_df['memory_mb'].max():.2f} MB")
        
        # Per-namespace stats
        ns_stats = pod_mem_df.groupby('namespace')['memory_mb'].agg(['mean', 'max', 'count']).round(2)
        print(f"   • Per-namespace statistics:")
        for namespace, stats in ns_stats.iterrows():
            print(f"     - {namespace}: avg={stats['mean']} MB, max={stats['max']} MB, data_points={stats['count']}")


class ResourceOverviewVisualizer(BaseVisualizer):
    """Handles combined CPU and memory resource analysis."""
    
    def plot_analysis(self, figsize=(18, 12)):
        """Create and display resource utilization overview plots."""
        if not (self.data_loader.has_data('node_cpu') and self.data_loader.has_data('node_memory')):
            print("❌ Insufficient data for resource utilization overview")
            return None
        
        # Apply zone filtering to both datasets
        print("🔄 Preparing resource data with zone filtering...")
        cpu_df = self._prepare_zone_data(self.data_loader.get_data('node_cpu'), 'cpu_cores_used')
        
        mem_df_temp = self.data_loader.get_data('node_memory').copy()
        mem_df_temp['memory_gb'] = mem_df_temp['memory_working_set_bytes'] / (1024**3)
        mem_df = self._prepare_zone_data(mem_df_temp, 'memory_gb')
        
        if len(cpu_df) == 0 or len(mem_df) == 0:
            print("❌ No data remaining after zone filtering")
            return None
        
        # Merge datasets on timestamp and node
        merged_df = pd.merge(cpu_df[['timestamp', 'node', 'datetime', 'cpu_cores_used']], 
                           mem_df[['timestamp', 'node', 'memory_gb']], 
                           on=['timestamp', 'node'], how='inner')
        
        # Create subplots
        fig, axes = plt.subplots(2, 2, figsize=figsize)
        fig.suptitle('Resource Utilization Overview', fontsize=16, fontweight='bold')
        
        # 1. CPU vs Memory scatter plot
        self._plot_cpu_memory_scatter(axes[0, 0], merged_df)
        
        # 2. Resource utilization over time (normalized)
        self._plot_normalized_utilization(axes[0, 1], merged_df)
        
        # 3. Resource efficiency (CPU/Memory ratio)
        self._plot_resource_efficiency(axes[1, 0], merged_df)
        
        # 4. Total resource consumption over time
        self._plot_total_consumption(axes[1, 1], merged_df)
        
        plt.tight_layout()
        plt.close('all')  # Prevent duplicate plots in VS Code notebooks
        plt.show()
        
        return fig
    
    def _plot_cpu_memory_scatter(self, ax, merged_df):
        """Plot CPU vs Memory scatter plot."""
        for node in merged_df['node'].unique():
            node_data = merged_df[merged_df['node'] == node]
            node_label = self._generate_node_label(node)
            ax.scatter(node_data['cpu_cores_used'], node_data['memory_gb'], 
                      label=node_label, alpha=0.6, s=30)
        
        ax.set_title('CPU vs Memory Usage')
        ax.set_xlabel('CPU Cores Used')
        ax.set_ylabel('Memory Usage (GB)')
        ax.legend()
        ax.grid(True, alpha=0.3)
    
    def _plot_normalized_utilization(self, ax, merged_df):
        """Plot normalized resource utilization over time."""
        for node in merged_df['node'].unique():
            node_data = merged_df[merged_df['node'] == node]
            if len(node_data) > 1:  # Ensure we have enough data for normalization
                # Generate short label for legend (just node name or zone)
                if node in self.node_ip_to_zone_map:
                    short_label = self.node_ip_to_zone_map[node]['name']
                else:
                    short_label = node
                
                # Normalize to 0-1 scale for comparison
                cpu_range = node_data['cpu_cores_used'].max() - node_data['cpu_cores_used'].min()
                mem_range = node_data['memory_gb'].max() - node_data['memory_gb'].min()
                
                if cpu_range > 0:
                    cpu_norm = (node_data['cpu_cores_used'] - node_data['cpu_cores_used'].min()) / cpu_range
                else:
                    cpu_norm = node_data['cpu_cores_used'] * 0  # All zeros if no variation
                
                if mem_range > 0:
                    mem_norm = (node_data['memory_gb'] - node_data['memory_gb'].min()) / mem_range
                else:
                    mem_norm = node_data['memory_gb'] * 0  # All zeros if no variation
                
                ax.plot(node_data['datetime'], cpu_norm, label=f'{short_label} CPU', linestyle='-', alpha=0.7)
                ax.plot(node_data['datetime'], mem_norm, label=f'{short_label} Mem', linestyle='--', alpha=0.7)
        
        ax.set_title('Normalized Resource Utilization Over Time')
        ax.set_xlabel('Time')
        ax.set_ylabel('Normalized Usage (0-1)')
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis='x', rotation=45)
    
    def _plot_resource_efficiency(self, ax, merged_df):
        """Plot resource efficiency (CPU/Memory ratio)."""
        # Avoid division by zero
        merged_df['cpu_mem_ratio'] = merged_df['cpu_cores_used'] / (merged_df['memory_gb'] + 1e-9)
        merged_df.boxplot(column='cpu_mem_ratio', by='node', ax=ax)
        ax.set_title('CPU/Memory Efficiency Ratio by Node')
        ax.set_xlabel('Node')
        ax.set_ylabel('CPU Cores per GB Memory')
        plt.suptitle('')
    
    def _plot_total_consumption(self, ax, merged_df):
        """Plot total resource consumption over time."""
        total_cpu = merged_df.groupby('datetime')['cpu_cores_used'].sum()
        total_mem = merged_df.groupby('datetime')['memory_gb'].sum()
        
        ax_twin = ax.twinx()
        line1 = ax.plot(total_cpu.index, total_cpu.values, 'b-', label='Total CPU Cores', linewidth=2)
        line2 = ax_twin.plot(total_mem.index, total_mem.values, 'r-', label='Total Memory (GB)', linewidth=2)
        
        ax.set_title('Total Resource Consumption Over Time')
        ax.set_xlabel('Time')
        ax.set_ylabel('Total CPU Cores', color='b')
        ax_twin.set_ylabel('Total Memory (GB)', color='r')
        
        # Combine legends
        lines = line1 + line2
        labels = [l.get_label() for l in lines]
        ax.legend(lines, labels, loc='upper left')
        
        ax.tick_params(axis='x', rotation=45)
        ax.grid(True, alpha=0.3)
    
    def get_summary_stats(self):
        """Get combined resource usage summary statistics."""
        stats = {}
        
        if self.data_loader.has_data('node_cpu') and self.data_loader.has_data('node_memory'):
            cpu_df = self.data_loader.get_data('node_cpu')
            mem_df = self.data_loader.get_data('node_memory').copy()
            mem_df['memory_gb'] = mem_df['memory_working_set_bytes'] / (1024**3)
            
            # Merge datasets
            merged_df = pd.merge(cpu_df[['timestamp', 'node', 'cpu_cores_used']], 
                               mem_df[['timestamp', 'node', 'memory_gb']], 
                               on=['timestamp', 'node'], how='inner')
            
            if len(merged_df) > 0:
                merged_df['cpu_mem_ratio'] = merged_df['cpu_cores_used'] / (merged_df['memory_gb'] + 1e-9)
                
                stats = {
                    'total_records': len(merged_df),
                    'nodes': merged_df['node'].nunique(),
                    'avg_cpu_cores': merged_df['cpu_cores_used'].mean(),
                    'avg_memory_gb': merged_df['memory_gb'].mean(),
                    'avg_cpu_mem_ratio': merged_df['cpu_mem_ratio'].mean(),
                    'correlation_cpu_memory': merged_df['cpu_cores_used'].corr(merged_df['memory_gb'])
                }
        
        return stats 