"""
CPU Visualization Module for MuBench.

This module provides comprehensive CPU usage analysis and visualization
capabilities for both node-level and pod-level CPU metrics.
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from .base import BaseVisualizer


class CPUVisualizer(BaseVisualizer):
    """Handles CPU usage visualization and analysis."""
    
    def plot_analysis(self, figsize=(18, 16)):
        """Create and display CPU usage analysis plots with correlation matrix and utilization rate analysis."""
        if not self.data_loader.has_data('node_cpu'):
            print("❌ No node CPU data available for visualization")
            return None
        
        # Apply zone filtering
        print("🔄 Preparing CPU data with zone filtering...")
        df = self._prepare_zone_data(self.data_loader.get_data('node_cpu'), 'cpu_cores_used')
        
        if len(df) == 0:
            print("❌ No CPU data remaining after zone filtering")
            return None
        
        # Create subplots - 3x2 grid
        fig, axes = plt.subplots(3, 2, figsize=figsize)
        fig.suptitle('Node CPU Usage Analysis', fontsize=16, fontweight='bold')
        
        # 1. Time series plot for each node
        self._plot_time_series(axes[0, 0], df)
        
        # 2. Box plot of CPU usage by node
        self._plot_distribution_boxplot(axes[0, 1], df)
        
        # 3. CPU usage correlation matrix between nodes
        self._plot_correlation_matrix(axes[1, 0], df)
        
        # 4. Heatmap of CPU usage over time
        self._plot_usage_heatmap(axes[1, 1], df)
        
        # 5. Summary statistics
        self._plot_summary_statistics(axes[2, 0], df)
        
        # 6. CPU utilization rate analysis
        self._plot_utilization_rate_analysis(axes[2, 1], df)
        
        plt.tight_layout()
        plt.close('all')  # Prevent duplicate plots in VS Code notebooks
        plt.show()
        
        return fig
    
    def _plot_time_series(self, ax, df):
        """Plot CPU usage time series for each node."""
        for node in df['node'].unique():
            node_data = df[df['node'] == node]
            node_label = self._generate_node_label(node)
            ax.plot(node_data['datetime'], node_data['cpu_cores_used'], 
                   label=node_label, marker='o', markersize=1, alpha=0.7)
        
        ax.set_title('CPU Usage Over Time by Node')
        ax.set_xlabel('Time')
        ax.set_ylabel('CPU Cores Used')
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis='x', rotation=45)
    
    def _plot_distribution_boxplot(self, ax, df):
        """Plot CPU usage distribution by node."""
        df.boxplot(column='cpu_cores_used', by='node', ax=ax)
        ax.set_title('CPU Usage Distribution by Node')
        ax.set_xlabel('Node')
        ax.set_ylabel('CPU Cores Used')
        plt.suptitle('')  # Remove auto-generated title
    
    def _plot_correlation_matrix(self, ax, df):
        """Plot CPU usage correlation matrix between nodes."""
        pivot_cpu = df.pivot_table(values='cpu_cores_used', 
                                  index='datetime', 
                                  columns='node', 
                                  aggfunc='mean')
        
        if len(pivot_cpu.columns) > 1:  # Only create correlation if we have multiple nodes
            cpu_corr = pivot_cpu.corr()
            # Create node labels for correlation matrix
            node_labels = [self._generate_node_label(node).split(' (')[0] for node in cpu_corr.columns]
            
            sns.heatmap(cpu_corr, ax=ax, annot=True, cmap='coolwarm', center=0,
                       xticklabels=node_labels, yticklabels=node_labels,
                       cbar_kws={'label': 'CPU Correlation'})
            ax.set_title('CPU Usage Correlation Between Nodes')
            plt.setp(ax.get_xticklabels(), rotation=45, ha='right', fontsize=8)
            plt.setp(ax.get_yticklabels(), rotation=0, fontsize=8)
        else:
            ax.text(0.5, 0.5, 'Single Node\nNo Correlation\nAnalysis', 
                   ha='center', va='center', transform=ax.transAxes, fontsize=12)
            ax.set_title('CPU Usage Correlation Between Nodes')
    
    def _plot_usage_heatmap(self, ax, df):
        """Plot CPU usage heatmap over time."""
        # Pivot data for heatmap
        pivot_data = df.pivot_table(values='cpu_cores_used', 
                                   index='node', 
                                   columns=df['datetime'].dt.strftime('%H:%M:%S'),
                                   aggfunc='mean')
        # Sample every nth column for readability
        sample_rate = max(1, len(pivot_data.columns) // 20)
        pivot_sample = pivot_data.iloc[:, ::sample_rate]
        
        # Create node labels for heatmap
        node_labels = [self._generate_node_label(node).split(' (')[0] for node in pivot_sample.index]
        
        sns.heatmap(pivot_sample, ax=ax, cmap='YlOrRd', 
                   yticklabels=node_labels,
                   cbar_kws={'label': 'CPU Cores Used'})
        ax.set_title('CPU Usage Heatmap (Time vs Node)')
        ax.set_xlabel('Time (sampled)')
        ax.set_ylabel('Node')
        plt.setp(ax.get_yticklabels(), rotation=0, fontsize=8)
    
    def _plot_summary_statistics(self, ax, df):
        """Plot summary statistics by node."""
        stats = df.groupby('node')['cpu_cores_used'].agg(['mean', 'std', 'min', 'max'])
        stats.plot(kind='bar', ax=ax)
        ax.set_title('CPU Usage Statistics by Node')
        ax.set_xlabel('Node')
        ax.set_ylabel('CPU Cores Used')
        ax.legend(['Mean', 'Std Dev', 'Min', 'Max'])
        ax.tick_params(axis='x', rotation=45)
    
    def _plot_utilization_rate_analysis(self, ax, df):
        """Plot CPU utilization rate analysis (change over time)."""
        # Calculate CPU utilization rate (change over time) for each node
        utilization_rates = []
        node_names = []
        
        for node in df['node'].unique():
            node_data = df[df['node'] == node].sort_values('datetime')
            if len(node_data) > 1:
                # Calculate rate of change (derivative)
                time_diff = (node_data['datetime'].diff().dt.total_seconds() / 60).fillna(1)  # minutes
                cpu_diff = node_data['cpu_cores_used'].diff().fillna(0)
                rate = (cpu_diff / time_diff).abs()  # absolute rate of change per minute
                
                utilization_rates.extend(rate.values)
                node_names.extend([self._generate_node_label(node).split(' (')[0]] * len(rate))
        
        if utilization_rates:
            # Create DataFrame for easier plotting
            rate_df = pd.DataFrame({
                'node': node_names,
                'utilization_rate': utilization_rates
            })
            
            # Remove extreme outliers for better visualization
            q95 = rate_df['utilization_rate'].quantile(0.95)
            rate_df_filtered = rate_df[rate_df['utilization_rate'] <= q95]
            
            # Box plot of utilization rates
            unique_nodes = rate_df_filtered['node'].unique()
            rate_data = [rate_df_filtered[rate_df_filtered['node'] == node]['utilization_rate'].values 
                        for node in unique_nodes]
            
            bp = ax.boxplot(rate_data, labels=unique_nodes, patch_artist=True)
            colors = plt.cm.Set3(np.linspace(0, 1, len(unique_nodes)))
            for patch, color in zip(bp['boxes'], colors):
                patch.set_facecolor(color)
            
            ax.set_title('CPU Utilization Rate Analysis\n(Cores/min change)')
            ax.set_xlabel('Node')
            ax.set_ylabel('Rate of Change (Cores/min)')
            ax.tick_params(axis='x', rotation=45)
            ax.grid(True, alpha=0.3)
        else:
            ax.text(0.5, 0.5, 'Insufficient data\nfor rate analysis', 
                   ha='center', va='center', transform=ax.transAxes, fontsize=12)
            ax.set_title('CPU Utilization Rate Analysis')
    
    def get_summary_stats(self):
        """Get CPU usage summary statistics."""
        if not self.data_loader.has_data('node_cpu'):
            return {}
        
        cpu_df = self.data_loader.get_data('node_cpu')
        
        stats = {
            'total_records': len(cpu_df),
            'nodes': cpu_df['node'].nunique(),
            'time_range': (cpu_df['datetime'].min(), cpu_df['datetime'].max()),
            'avg_usage': cpu_df['cpu_cores_used'].mean(),
            'peak_usage': cpu_df['cpu_cores_used'].max(),
            'per_node_stats': cpu_df.groupby('node')['cpu_cores_used'].agg(['mean', 'max', 'std']).to_dict()
        }
        
        return stats
    
    def print_summary(self):
        """Print detailed CPU usage summary."""
        if not self.data_loader.has_data('node_cpu'):
            print("❌ No node CPU data available")
            return
        
        cpu_df = self.data_loader.get_data('node_cpu')
        
        print(f"\n📊 NODE CPU USAGE:")
        print(f"   • Total data points: {len(cpu_df)}")
        print(f"   • Nodes monitored: {cpu_df['node'].nunique()}")
        print(f"   • Time range: {cpu_df['datetime'].min()} to {cpu_df['datetime'].max()}")
        print(f"   • Average CPU usage: {cpu_df['cpu_cores_used'].mean():.3f} cores")
        print(f"   • Peak CPU usage: {cpu_df['cpu_cores_used'].max():.3f} cores")
        
        # Per-node stats
        node_stats = cpu_df.groupby('node')['cpu_cores_used'].agg(['mean', 'max', 'std']).round(3)
        print(f"   • Per-node statistics:")
        for node, stats in node_stats.iterrows():
            node_label = self._generate_node_label(node)
            print(f"     - {node_label}: avg={stats['mean']}, max={stats['max']}, std={stats['std']}")


class PodCPUVisualizer(BaseVisualizer):
    """Handles pod-level CPU usage visualization and analysis."""
    
    def plot_analysis(self, figsize=(18, 14)):
        """Create and display pod CPU usage analysis plots."""
        if not self.data_loader.has_data('pod_cpu'):
            print("❌ No pod CPU data available for visualization")
            return None
        
        df = self.data_loader.get_data('pod_cpu').copy()
        
        if len(df) == 0:
            print("❌ Pod CPU data is empty")
            return None
        
        # Create subplots
        fig, axes = plt.subplots(2, 2, figsize=figsize)
        fig.suptitle('Pod CPU Usage Analysis', fontsize=16, fontweight='bold')
        
        # 1. Time series plot by namespace
        self._plot_namespace_time_series(axes[0, 0], df)
        
        # 2. Box plot by namespace
        self._plot_namespace_distribution(axes[0, 1], df)
        
        # 3. Top pods by average CPU usage
        self._plot_top_pods(axes[1, 0], df)
        
        # 4. CPU usage heatmap by pod over time
        self._plot_pod_heatmap(axes[1, 1], df)
        
        plt.tight_layout()
        plt.close('all')
        plt.show()
        
        return fig
    
    def _plot_namespace_time_series(self, ax, df):
        """Plot CPU usage time series by namespace."""
        namespaces = df['namespace'].unique()
        colors = plt.cm.Set3(np.linspace(0, 1, len(namespaces)))
        
        for i, namespace in enumerate(namespaces):
            ns_data = df[df['namespace'] == namespace]
            # Aggregate by namespace and time for cleaner visualization
            ns_agg = ns_data.groupby('datetime')['cpu_cores_used'].sum().reset_index()
            ax.plot(ns_agg['datetime'], ns_agg['cpu_cores_used'], 
                   label=f'Namespace: {namespace}', color=colors[i], linewidth=2, alpha=0.8)
        
        ax.set_title('CPU Usage Over Time by Namespace')
        ax.set_xlabel('Time')
        ax.set_ylabel('Total CPU Cores Used')
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis='x', rotation=45)
    
    def _plot_namespace_distribution(self, ax, df):
        """Plot CPU usage distribution by namespace."""
        namespaces = df['namespace'].unique()
        colors = plt.cm.Set3(np.linspace(0, 1, len(namespaces)))
        
        namespace_data = [df[df['namespace'] == ns]['cpu_cores_used'].values for ns in namespaces]
        bp = ax.boxplot(namespace_data, labels=namespaces, patch_artist=True)
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
        
        ax.set_title('CPU Usage Distribution by Namespace')
        ax.set_xlabel('Namespace')
        ax.set_ylabel('CPU Cores Used')
        ax.tick_params(axis='x', rotation=45)
        ax.grid(True, alpha=0.3)
    
    def _plot_top_pods(self, ax, df):
        """Plot top pods by average CPU usage."""
        pod_stats = df.groupby(['namespace', 'pod'])['cpu_cores_used'].agg(['mean', 'max']).reset_index()
        pod_stats['pod_label'] = pod_stats['namespace'] + '/' + pod_stats['pod']
        top_pods = pod_stats.nlargest(10, 'mean')
        
        bars = ax.barh(range(len(top_pods)), top_pods['mean'], color='skyblue', alpha=0.7)
        ax.set_yticks(range(len(top_pods)))
        ax.set_yticklabels(top_pods['pod_label'], fontsize=8)
        ax.set_xlabel('Average CPU Cores Used')
        ax.set_title('Top 10 Pods by Average CPU Usage')
        ax.grid(True, alpha=0.3, axis='x')
        
        # Add value labels on bars
        for i, (bar, value) in enumerate(zip(bars, top_pods['mean'])):
            ax.text(value + 0.001, bar.get_y() + bar.get_height()/2, 
                   f'{value:.3f}', va='center', fontsize=8)
    
    def _plot_pod_heatmap(self, ax, df):
        """Plot CPU usage heatmap by pod over time."""
        # Get top pods for heatmap
        pod_stats = df.groupby(['namespace', 'pod'])['cpu_cores_used'].agg(['mean']).reset_index()
        pod_stats['pod_label'] = pod_stats['namespace'] + '/' + pod_stats['pod']
        top_pods = pod_stats.nlargest(8, 'mean')  # Limit for readability
        
        if len(top_pods) > 0:
            top_pod_names = top_pods['pod_label'].tolist()
            heatmap_data = []
            
            # Sample time points
            unique_times = sorted(df['datetime'].unique())
            sample_rate = max(1, len(unique_times) // 15)  # Sample ~15 time points
            sampled_times = unique_times[::sample_rate]
            
            for pod_label in top_pod_names:
                namespace, pod = pod_label.split('/', 1)
                pod_data = df[(df['namespace'] == namespace) & (df['pod'] == pod)]
                pod_values = []
                
                for time_point in sampled_times:
                    time_data = pod_data[pod_data['datetime'] == time_point]
                    if len(time_data) > 0:
                        pod_values.append(time_data['cpu_cores_used'].iloc[0])
                    else:
                        pod_values.append(0)
                
                heatmap_data.append(pod_values)
            
            if heatmap_data:
                time_labels = [t.strftime('%H:%M') for t in sampled_times]
                sns.heatmap(heatmap_data, ax=ax, cmap='YlOrRd', 
                           xticklabels=time_labels, yticklabels=top_pod_names,
                           cbar_kws={'label': 'CPU Cores Used'})
                ax.set_title('CPU Usage Heatmap (Top Pods)')
                ax.set_xlabel('Time')
                ax.set_ylabel('Pod (Namespace/Name)')
                plt.setp(ax.get_yticklabels(), fontsize=8)
                plt.setp(ax.get_xticklabels(), rotation=45, fontsize=8)
        else:
            ax.text(0.5, 0.5, 'No pod data\navailable for heatmap', 
                   ha='center', va='center', transform=ax.transAxes, fontsize=12)
            ax.set_title('CPU Usage Heatmap (Top Pods)')
    
    def get_summary_stats(self):
        """Get pod CPU usage summary statistics."""
        if not self.data_loader.has_data('pod_cpu'):
            return {}
        
        pod_cpu_df = self.data_loader.get_data('pod_cpu')
        
        stats = {
            'total_records': len(pod_cpu_df),
            'namespaces': pod_cpu_df['namespace'].nunique(),
            'pods': pod_cpu_df['pod'].nunique(),
            'avg_usage': pod_cpu_df['cpu_cores_used'].mean(),
            'peak_usage': pod_cpu_df['cpu_cores_used'].max(),
            'per_namespace_stats': pod_cpu_df.groupby('namespace')['cpu_cores_used'].agg(['mean', 'max', 'count']).to_dict()
        }
        
        return stats
    
    def print_summary(self):
        """Print detailed pod CPU usage summary."""
        if not self.data_loader.has_data('pod_cpu'):
            print("❌ No pod CPU data available")
            return
        
        pod_cpu_df = self.data_loader.get_data('pod_cpu')
        
        print(f"\n📦 POD CPU USAGE:")
        print(f"   • Total data points: {len(pod_cpu_df)}")
        print(f"   • Namespaces monitored: {pod_cpu_df['namespace'].nunique()}")
        print(f"   • Pods monitored: {pod_cpu_df['pod'].nunique()}")
        print(f"   • Average CPU usage: {pod_cpu_df['cpu_cores_used'].mean():.3f} cores")
        print(f"   • Peak CPU usage: {pod_cpu_df['cpu_cores_used'].max():.3f} cores")
        
        # Per-namespace stats
        ns_stats = pod_cpu_df.groupby('namespace')['cpu_cores_used'].agg(['mean', 'max', 'count']).round(3)
        print(f"   • Per-namespace statistics:")
        for namespace, stats in ns_stats.iterrows():
            print(f"     - {namespace}: avg={stats['mean']}, max={stats['max']}, data_points={stats['count']}") 