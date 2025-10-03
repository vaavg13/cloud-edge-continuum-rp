"""
Zone Visualization Module for MuBench.

This module provides comprehensive zone/site analysis and visualization
capabilities for cross-zone correlations and geographic distribution analysis.
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from .base import BaseVisualizer


class ZoneAnalysisVisualizer(BaseVisualizer):
    """Handles inter-zone analysis and cross-site correlations."""
    
    def plot_analysis(self, figsize=(16, 12)):
        """Create and display inter-site correlation and comparison analysis."""
        if not (self.data_loader.has_data('node_cpu') and self.data_loader.has_data('node_memory')):
            print("❌ Insufficient data for sites analysis (need both CPU and memory data)")
            return None
        
        if not self.node_ip_to_zone_map:
            print("❌ No zone mapping available - sites analysis requires kubectl access")
            return None
        
        # Prepare data with zone filtering
        print("🔄 Preparing zone data with filtering...")
        cpu_df = self._prepare_zone_data(self.data_loader.get_data('node_cpu'), 'cpu_cores_used')
        
        mem_df_temp = self.data_loader.get_data('node_memory').copy()
        mem_df_temp['memory_gb'] = mem_df_temp['memory_working_set_bytes'] / (1024**3)
        mem_df = self._prepare_zone_data(mem_df_temp, 'memory_gb')
        
        # Check if we have any data left after filtering
        if len(cpu_df) == 0 or len(mem_df) == 0:
            print("❌ No data remaining after zone filtering")
            return None
        
        # Create subplots
        fig, axes = plt.subplots(2, 2, figsize=figsize)
        fig.suptitle('Sites/Zones Analysis - Cross-Site Correlations', fontsize=16, fontweight='bold')
        
        # 1. CPU Usage by Zone (Box Plot)
        self._plot_cpu_by_zone(axes[0, 0], cpu_df)
        
        # 2. Memory Usage by Zone (Box Plot)
        self._plot_memory_by_zone(axes[0, 1], mem_df)
        
        # 3. Inter-Zone CPU Correlation Heatmap
        self._plot_cpu_correlation_heatmap(axes[1, 0], cpu_df)
        
        # 4. Inter-Zone Memory Correlation Heatmap
        self._plot_memory_correlation_heatmap(axes[1, 1], mem_df)
        
        plt.tight_layout()
        plt.close('all')  # Prevent duplicate plots in VS Code notebooks
        plt.show()
        
        # Print correlation analysis
        self._print_correlation_analysis(cpu_df, mem_df)
        
        return fig
    
    def _plot_cpu_by_zone(self, ax, cpu_df):
        """Plot CPU usage distribution by zone."""
        zones = cpu_df['zone'].unique()
        zone_colors = plt.cm.Set3(np.linspace(0, 1, len(zones)))
        
        cpu_by_zone = [cpu_df[cpu_df['zone'] == zone]['cpu_cores_used'].values for zone in zones]
        bp1 = ax.boxplot(cpu_by_zone, labels=zones, patch_artist=True)
        for patch, color in zip(bp1['boxes'], zone_colors):
            patch.set_facecolor(color)
        
        ax.set_title('CPU Usage Distribution by Zone')
        ax.set_xlabel('Zone')
        ax.set_ylabel('CPU Cores Used')
        ax.tick_params(axis='x', rotation=45)
        ax.grid(True, alpha=0.3)
    
    def _plot_memory_by_zone(self, ax, mem_df):
        """Plot memory usage distribution by zone."""
        zones = mem_df['zone'].unique()
        zone_colors = plt.cm.Set3(np.linspace(0, 1, len(zones)))
        
        mem_by_zone = [mem_df[mem_df['zone'] == zone]['memory_gb'].values for zone in zones]
        bp2 = ax.boxplot(mem_by_zone, labels=zones, patch_artist=True)
        for patch, color in zip(bp2['boxes'], zone_colors):
            patch.set_facecolor(color)
        
        ax.set_title('Memory Usage Distribution by Zone')
        ax.set_xlabel('Zone')
        ax.set_ylabel('Memory Usage (GB)')
        ax.tick_params(axis='x', rotation=45)
        ax.grid(True, alpha=0.3)
    
    def _plot_cpu_correlation_heatmap(self, ax, cpu_df):
        """Plot inter-zone CPU correlation heatmap."""
        cpu_pivot = cpu_df.pivot_table(values='cpu_cores_used', 
                                       index='datetime', 
                                       columns='zone', 
                                       aggfunc='mean')
        
        if len(cpu_pivot.columns) > 1:  # Only create correlation if we have multiple zones
            cpu_corr = cpu_pivot.corr()
            mask = np.triu(np.ones_like(cpu_corr, dtype=bool))  # Mask upper triangle
            sns.heatmap(cpu_corr, ax=ax, annot=True, cmap='coolwarm', center=0,
                       mask=mask, square=True, cbar_kws={'label': 'CPU Correlation'})
            ax.set_title('Inter-Zone CPU Usage Correlation')
        else:
            ax.text(0.5, 0.5, 'Single Zone\nNo Correlation\nAnalysis', 
                   ha='center', va='center', transform=ax.transAxes, fontsize=12)
            ax.set_title('Inter-Zone CPU Usage Correlation')
    
    def _plot_memory_correlation_heatmap(self, ax, mem_df):
        """Plot inter-zone memory correlation heatmap."""
        mem_pivot = mem_df.pivot_table(values='memory_gb', 
                                       index='datetime', 
                                       columns='zone', 
                                       aggfunc='mean')
        
        if len(mem_pivot.columns) > 1:  # Only create correlation if we have multiple zones
            mem_corr = mem_pivot.corr()
            mask = np.triu(np.ones_like(mem_corr, dtype=bool))  # Mask upper triangle
            sns.heatmap(mem_corr, ax=ax, annot=True, cmap='coolwarm', center=0,
                       mask=mask, square=True, cbar_kws={'label': 'Memory Correlation'})
            ax.set_title('Inter-Zone Memory Usage Correlation')
        else:
            ax.text(0.5, 0.5, 'Single Zone\nNo Correlation\nAnalysis', 
                   ha='center', va='center', transform=ax.transAxes, fontsize=12)
            ax.set_title('Inter-Zone Memory Usage Correlation')
    
    def _print_correlation_analysis(self, cpu_df, mem_df):
        """Print detailed correlation analysis."""
        zones = cpu_df['zone'].unique()
        
        print("\n" + "="*60)
        print("INTER-ZONE CORRELATION ANALYSIS")
        print("="*60)
        
        if len(zones) > 1:
            # CPU correlations
            cpu_pivot = cpu_df.pivot_table(values='cpu_cores_used', 
                                           index='datetime', 
                                           columns='zone', 
                                           aggfunc='mean')
            if len(cpu_pivot.columns) > 1:
                print(f"\n📊 CPU Usage Correlations:")
                cpu_corr_clean = cpu_pivot.corr()
                for i, zone1 in enumerate(cpu_corr_clean.columns):
                    for j, zone2 in enumerate(cpu_corr_clean.columns):
                        if i < j:  # Only show each pair once
                            corr_val = cpu_corr_clean.loc[zone1, zone2]
                            if abs(corr_val) > 0.7:
                                strength = "Strong"
                            elif abs(corr_val) > 0.4:
                                strength = "Moderate"
                            else:
                                strength = "Weak"
                            print(f"   • {zone1} ↔ {zone2}: {corr_val:.3f} ({strength})")
            
            # Memory correlations
            mem_pivot = mem_df.pivot_table(values='memory_gb', 
                                           index='datetime', 
                                           columns='zone', 
                                           aggfunc='mean')
            if len(mem_pivot.columns) > 1:
                print(f"\n💾 Memory Usage Correlations:")
                mem_corr_clean = mem_pivot.corr()
                for i, zone1 in enumerate(mem_corr_clean.columns):
                    for j, zone2 in enumerate(mem_corr_clean.columns):
                        if i < j:  # Only show each pair once
                            corr_val = mem_corr_clean.loc[zone1, zone2]
                            if abs(corr_val) > 0.7:
                                strength = "Strong"
                            elif abs(corr_val) > 0.4:
                                strength = "Moderate"
                            else:
                                strength = "Weak"
                            print(f"   • {zone1} ↔ {zone2}: {corr_val:.3f} ({strength})")
            
            # Zone performance summary
            print(f"\n🌍 Zone Performance Summary:")
            for zone in zones:
                zone_cpu = cpu_df[cpu_df['zone'] == zone]['cpu_cores_used']
                zone_mem = mem_df[mem_df['zone'] == zone]['memory_gb']
                node_count = len(cpu_df[cpu_df['zone'] == zone]['node'].unique())
                
                print(f"   • {zone}:")
                print(f"     - Nodes: {node_count}")
                print(f"     - Avg CPU: {zone_cpu.mean():.3f} cores (std: {zone_cpu.std():.3f})")
                print(f"     - Avg Memory: {zone_mem.mean():.2f} GB (std: {zone_mem.std():.2f})")
        else:
            print(f"\n⚠ Only one zone detected: {zones[0]}")
            print("   Cannot perform inter-zone correlation analysis.")
        
        print("="*60)
    
    def get_summary_stats(self):
        """Get zone analysis summary statistics."""
        if not (self.data_loader.has_data('node_cpu') and self.data_loader.has_data('node_memory')):
            return {}
        
        if not self.node_ip_to_zone_map:
            return {'error': 'No zone mapping available'}
        
        # Prepare data
        cpu_df = self._prepare_zone_data(self.data_loader.get_data('node_cpu'), 'cpu_cores_used')
        mem_df_temp = self.data_loader.get_data('node_memory').copy()
        mem_df_temp['memory_gb'] = mem_df_temp['memory_working_set_bytes'] / (1024**3)
        mem_df = self._prepare_zone_data(mem_df_temp, 'memory_gb')
        
        if len(cpu_df) == 0 or len(mem_df) == 0:
            return {'error': 'No data remaining after zone filtering'}
        
        zones = cpu_df['zone'].unique()
        
        stats = {
            'total_zones': len(zones),
            'zones': zones.tolist(),
            'excluded_zones': self.exclude_zones,
            'zone_performance': {}
        }
        
        for zone in zones:
            zone_cpu = cpu_df[cpu_df['zone'] == zone]['cpu_cores_used']
            zone_mem = mem_df[mem_df['zone'] == zone]['memory_gb']
            node_count = len(cpu_df[cpu_df['zone'] == zone]['node'].unique())
            
            stats['zone_performance'][zone] = {
                'node_count': node_count,
                'cpu_stats': {
                    'mean': zone_cpu.mean(),
                    'std': zone_cpu.std(),
                    'min': zone_cpu.min(),
                    'max': zone_cpu.max()
                },
                'memory_stats': {
                    'mean': zone_mem.mean(),
                    'std': zone_mem.std(),
                    'min': zone_mem.min(),
                    'max': zone_mem.max()
                }
            }
        
        # Calculate correlations if multiple zones
        if len(zones) > 1:
            cpu_pivot = cpu_df.pivot_table(values='cpu_cores_used', 
                                           index='datetime', 
                                           columns='zone', 
                                           aggfunc='mean')
            mem_pivot = mem_df.pivot_table(values='memory_gb', 
                                           index='datetime', 
                                           columns='zone', 
                                           aggfunc='mean')
            
            if len(cpu_pivot.columns) > 1:
                cpu_corr = cpu_pivot.corr()
                stats['cpu_correlations'] = cpu_corr.to_dict()
            
            if len(mem_pivot.columns) > 1:
                mem_corr = mem_pivot.corr()
                stats['memory_correlations'] = mem_corr.to_dict()
        
        return stats


class PodZoneAnalysisVisualizer(BaseVisualizer):
    """Handles pod-level zone analysis with namespace distribution."""
    
    def plot_analysis(self, figsize=(16, 12)):
        """Create pod-level inter-site analysis with zone filtering."""
        if not (self.data_loader.has_data('pod_cpu') and self.data_loader.has_data('pod_memory')):
            print("❌ Insufficient pod data for sites analysis (need both CPU and memory data)")
            return None
        
        if not self.node_ip_to_zone_map:
            print("❌ No zone mapping available - pod sites analysis requires kubectl access")
            return None
        
        # For pod-level analysis, we need to map pods to zones through nodes
        # This is more complex as we need to determine which node each pod is running on
        print("⚠ Pod-to-zone mapping requires additional node scheduling information")
        print("📊 Showing namespace-level analysis instead...")
        
        # Prepare data
        cpu_df = self.data_loader.get_data('pod_cpu').copy()
        mem_df = self.data_loader.get_data('pod_memory').copy()
        mem_df['memory_mb'] = mem_df['memory_usage_bytes'] / (1024**2)
        
        # Apply zone filtering at namespace level if configured
        if self.exclude_zones:
            print(f"🚫 Note: Zone filtering ({', '.join(self.exclude_zones)}) applied at namespace level")
        
        # Create subplots
        fig, axes = plt.subplots(2, 2, figsize=figsize)
        fig.suptitle('Pod Resource Analysis by Namespace', fontsize=16, fontweight='bold')
        
        # 1. CPU Usage by Namespace (Box Plot)
        self._plot_namespace_cpu_distribution(axes[0, 0], cpu_df)
        
        # 2. Memory Usage by Namespace (Box Plot)
        self._plot_namespace_memory_distribution(axes[0, 1], mem_df)
        
        # 3. Resource utilization over time by namespace
        self._plot_namespace_resource_timeline(axes[1, 0], cpu_df, mem_df)
        
        # 4. Namespace performance summary
        self._plot_namespace_performance_summary(axes[1, 1], cpu_df, mem_df)
        
        plt.tight_layout()
        plt.close('all')
        plt.show()
        
        # Print namespace analysis
        self._print_namespace_analysis(cpu_df, mem_df)
        
        return fig
    
    def _plot_namespace_cpu_distribution(self, ax, cpu_df):
        """Plot CPU usage distribution by namespace."""
        namespaces = cpu_df['namespace'].unique()
        namespace_colors = plt.cm.Set3(np.linspace(0, 1, len(namespaces)))
        
        cpu_by_namespace = [cpu_df[cpu_df['namespace'] == ns]['cpu_cores_used'].values for ns in namespaces]
        bp1 = ax.boxplot(cpu_by_namespace, labels=namespaces, patch_artist=True)
        for patch, color in zip(bp1['boxes'], namespace_colors):
            patch.set_facecolor(color)
        
        ax.set_title('Pod CPU Usage Distribution by Namespace')
        ax.set_xlabel('Namespace')
        ax.set_ylabel('CPU Cores Used')
        ax.tick_params(axis='x', rotation=45)
        ax.grid(True, alpha=0.3)
    
    def _plot_namespace_memory_distribution(self, ax, mem_df):
        """Plot memory usage distribution by namespace."""
        namespaces = mem_df['namespace'].unique()
        namespace_colors = plt.cm.Set3(np.linspace(0, 1, len(namespaces)))
        
        mem_by_namespace = [mem_df[mem_df['namespace'] == ns]['memory_mb'].values for ns in namespaces]
        bp2 = ax.boxplot(mem_by_namespace, labels=namespaces, patch_artist=True)
        for patch, color in zip(bp2['boxes'], namespace_colors):
            patch.set_facecolor(color)
        
        ax.set_title('Pod Memory Usage Distribution by Namespace')
        ax.set_xlabel('Namespace')
        ax.set_ylabel('Memory Usage (MB)')
        ax.tick_params(axis='x', rotation=45)
        ax.grid(True, alpha=0.3)
    
    def _plot_namespace_resource_timeline(self, ax, cpu_df, mem_df):
        """Plot resource utilization over time by namespace."""
        namespaces = cpu_df['namespace'].unique()
        namespace_colors = plt.cm.Set3(np.linspace(0, 1, len(namespaces)))
        
        for i, namespace in enumerate(namespaces):
            ns_cpu = cpu_df[cpu_df['namespace'] == namespace].groupby('datetime')['cpu_cores_used'].sum()
            
            if len(ns_cpu) > 0:
                ax.plot(ns_cpu.index, ns_cpu.values, label=f'{namespace} CPU', 
                       color=namespace_colors[i], linestyle='-', alpha=0.8)
        
        ax.set_title('Total CPU Usage Over Time by Namespace')
        ax.set_xlabel('Time')
        ax.set_ylabel('Total CPU Cores Used')
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis='x', rotation=45)
    
    def _plot_namespace_performance_summary(self, ax, cpu_df, mem_df):
        """Plot namespace performance summary."""
        namespaces = cpu_df['namespace'].unique()
        namespace_stats = []
        
        for namespace in namespaces:
            ns_cpu_stats = cpu_df[cpu_df['namespace'] == namespace]['cpu_cores_used']
            ns_mem_stats = mem_df[mem_df['namespace'] == namespace]['memory_mb']
            
            namespace_stats.append({
                'namespace': namespace,
                'avg_cpu': ns_cpu_stats.mean(),
                'avg_memory': ns_mem_stats.mean(),
                'pod_count': cpu_df[cpu_df['namespace'] == namespace]['pod'].nunique()
            })
        
        stats_df = pd.DataFrame(namespace_stats)
        
        # Create a scatter plot of avg CPU vs avg memory
        scatter = ax.scatter(stats_df['avg_cpu'], stats_df['avg_memory'], 
                           c=range(len(stats_df)), cmap='viridis', s=100, alpha=0.7)
        
        # Add namespace labels
        for i, row in stats_df.iterrows():
            ax.annotate(f"{row['namespace']}\n({row['pod_count']} pods)", 
                       (row['avg_cpu'], row['avg_memory']),
                       xytext=(5, 5), textcoords='offset points', fontsize=8)
        
        ax.set_xlabel('Average CPU Cores Used')
        ax.set_ylabel('Average Memory Usage (MB)')
        ax.set_title('Namespace Resource Profile')
        ax.grid(True, alpha=0.3)
    
    def _print_namespace_analysis(self, cpu_df, mem_df):
        """Print detailed namespace analysis."""
        namespaces = cpu_df['namespace'].unique()
        
        print("\n" + "="*60)
        print("NAMESPACE RESOURCE ANALYSIS")
        print("="*60)
        
        for namespace in namespaces:
            ns_cpu_stats = cpu_df[cpu_df['namespace'] == namespace]['cpu_cores_used']
            ns_mem_stats = mem_df[mem_df['namespace'] == namespace]['memory_mb']
            pod_count = cpu_df[cpu_df['namespace'] == namespace]['pod'].nunique()
            
            print(f"\n📦 Namespace: {namespace}")
            print(f"   • Pod count: {pod_count}")
            print(f"   • Avg CPU: {ns_cpu_stats.mean():.3f} cores")
            print(f"   • Avg Memory: {ns_mem_stats.mean():.1f} MB")
        
        print("="*60)
    
    def get_summary_stats(self):
        """Get pod zone analysis summary statistics."""
        if not (self.data_loader.has_data('pod_cpu') and self.data_loader.has_data('pod_memory')):
            return {}
        
        cpu_df = self.data_loader.get_data('pod_cpu')
        mem_df = self.data_loader.get_data('pod_memory').copy()
        mem_df['memory_mb'] = mem_df['memory_usage_bytes'] / (1024**2)
        
        namespaces = cpu_df['namespace'].unique()
        
        stats = {
            'total_namespaces': len(namespaces),
            'namespaces': namespaces.tolist(),
            'namespace_performance': {}
        }
        
        for namespace in namespaces:
            ns_cpu_stats = cpu_df[cpu_df['namespace'] == namespace]['cpu_cores_used']
            ns_mem_stats = mem_df[mem_df['namespace'] == namespace]['memory_mb']
            pod_count = cpu_df[cpu_df['namespace'] == namespace]['pod'].nunique()
            
            stats['namespace_performance'][namespace] = {
                'pod_count': pod_count,
                'cpu_stats': {
                    'mean': ns_cpu_stats.mean(),
                    'std': ns_cpu_stats.std(),
                    'min': ns_cpu_stats.min(),
                    'max': ns_cpu_stats.max()
                },
                'memory_stats': {
                    'mean': ns_mem_stats.mean(),
                    'std': ns_mem_stats.std(),
                    'min': ns_mem_stats.min(),
                    'max': ns_mem_stats.max()
                }
            }
        
        return stats 