"""
Network Visualization Module for MuBench.

This module provides comprehensive network latency analysis and visualization
capabilities for Istio service mesh metrics.
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from .base import BaseVisualizer


class IstioLatencyVisualizer(BaseVisualizer):
    """Handles Istio service latency visualization and analysis."""
    
    def plot_analysis(self, figsize=(18, 14)):
        """Create and display Istio latency analysis plots."""
        if not self.data_loader.has_data('istio_latency'):
            print("❌ No Istio latency data available for visualization")
            return None
        
        df = self.data_loader.get_data('istio_latency').copy()
        
        if len(df) == 0:
            print("❌ Istio latency data is empty")
            return None
        
        # Create subplots
        fig, axes = plt.subplots(2, 2, figsize=figsize)
        fig.suptitle('Istio Service Latency Analysis (P95)', fontsize=16, fontweight='bold')
        
        # 1. Time series plot by namespace
        self._plot_namespace_time_series(axes[0, 0], df)
        
        # 2. Box plot by namespace
        self._plot_namespace_distribution(axes[0, 1], df)
        
        # 3. Top services by average latency
        self._plot_top_services(axes[1, 0], df)
        
        # 4. Latency distribution histogram
        self._plot_latency_distribution(axes[1, 1], df)
        
        plt.tight_layout()
        plt.close('all')
        plt.show()
        
        return fig
    
    def _plot_namespace_time_series(self, ax, df):
        """Plot latency time series by namespace."""
        namespaces = df['namespace'].unique()
        colors = plt.cm.Set3(np.linspace(0, 1, len(namespaces)))
        
        for i, namespace in enumerate(namespaces):
            ns_data = df[df['namespace'] == namespace]
            # Aggregate by namespace and time (average latency)
            ns_agg = ns_data.groupby('datetime')['p95_latency_ms'].mean().reset_index()
            ax.plot(ns_agg['datetime'], ns_agg['p95_latency_ms'], 
                   label=f'Namespace: {namespace}', color=colors[i], linewidth=2, alpha=0.8)
        
        ax.set_title('P95 Latency Over Time by Namespace')
        ax.set_xlabel('Time')
        ax.set_ylabel('P95 Latency (ms)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis='x', rotation=45)
    
    def _plot_namespace_distribution(self, ax, df):
        """Plot latency distribution by namespace."""
        namespaces = df['namespace'].unique()
        colors = plt.cm.Set3(np.linspace(0, 1, len(namespaces)))
        
        namespace_data = [df[df['namespace'] == ns]['p95_latency_ms'].values for ns in namespaces]
        bp = ax.boxplot(namespace_data, labels=namespaces, patch_artist=True)
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
        
        ax.set_title('P95 Latency Distribution by Namespace')
        ax.set_xlabel('Namespace')
        ax.set_ylabel('P95 Latency (ms)')
        ax.tick_params(axis='x', rotation=45)
        ax.grid(True, alpha=0.3)
    
    def _plot_top_services(self, ax, df):
        """Plot top services by average latency."""
        service_stats = df.groupby(['namespace', 'pod'])['p95_latency_ms'].agg(['mean', 'max', 'std']).reset_index()
        service_stats['service_label'] = service_stats['namespace'] + '/' + service_stats['pod']
        top_services = service_stats.nlargest(10, 'mean')
        
        bars = ax.barh(range(len(top_services)), top_services['mean'], color='orange', alpha=0.7)
        ax.set_yticks(range(len(top_services)))
        ax.set_yticklabels(top_services['service_label'], fontsize=8)
        ax.set_xlabel('Average P95 Latency (ms)')
        ax.set_title('Top 10 Services by Average P95 Latency')
        ax.grid(True, alpha=0.3, axis='x')
        
        # Add value labels on bars
        for i, (bar, value) in enumerate(zip(bars, top_services['mean'])):
            ax.text(value + max(top_services['mean']) * 0.01, bar.get_y() + bar.get_height()/2, 
                   f'{value:.1f}', va='center', fontsize=8)
    
    def _plot_latency_distribution(self, ax, df):
        """Plot latency distribution histogram."""
        # Filter out extreme outliers for better visualization
        q99 = df['p95_latency_ms'].quantile(0.99)
        filtered_latency = df[df['p95_latency_ms'] <= q99]['p95_latency_ms']
        
        ax.hist(filtered_latency, bins=30, alpha=0.7, color='green', edgecolor='black')
        ax.set_xlabel('P95 Latency (ms)')
        ax.set_ylabel('Frequency')
        ax.set_title('P95 Latency Distribution (99th percentile filtered)')
        ax.grid(True, alpha=0.3)
        
        # Add statistics
        mean_latency = filtered_latency.mean()
        median_latency = filtered_latency.median()
        ax.axvline(mean_latency, color='red', linestyle='--', linewidth=2, label=f'Mean: {mean_latency:.1f}ms')
        ax.axvline(median_latency, color='blue', linestyle='--', linewidth=2, label=f'Median: {median_latency:.1f}ms')
        ax.legend()
    
    def get_summary_stats(self):
        """Get Istio latency summary statistics."""
        if not self.data_loader.has_data('istio_latency'):
            return {}
        
        latency_df = self.data_loader.get_data('istio_latency')
        
        stats = {
            'total_records': len(latency_df),
            'namespaces': latency_df['namespace'].nunique(),
            'services': latency_df['pod'].nunique(),
            'avg_p95_latency_ms': latency_df['p95_latency_ms'].mean(),
            'peak_p95_latency_ms': latency_df['p95_latency_ms'].max(),
            'median_p95_latency_ms': latency_df['p95_latency_ms'].median(),
            'per_namespace_stats': latency_df.groupby('namespace')['p95_latency_ms'].agg(['mean', 'max', 'count']).to_dict()
        }
        
        return stats
    
    def print_summary(self):
        """Print detailed Istio latency summary."""
        if not self.data_loader.has_data('istio_latency'):
            print("❌ No Istio latency data available")
            return
        
        latency_df = self.data_loader.get_data('istio_latency')
        
        print(f"\n🌐 ISTIO LATENCY (P95):")
        print(f"   • Total data points: {len(latency_df)}")
        print(f"   • Namespaces monitored: {latency_df['namespace'].nunique()}")
        print(f"   • Services monitored: {latency_df['pod'].nunique()}")
        print(f"   • Average P95 latency: {latency_df['p95_latency_ms'].mean():.2f} ms")
        print(f"   • Peak P95 latency: {latency_df['p95_latency_ms'].max():.2f} ms")
        print(f"   • Median P95 latency: {latency_df['p95_latency_ms'].median():.2f} ms")
        
        # Per-namespace stats
        ns_stats = latency_df.groupby('namespace')['p95_latency_ms'].agg(['mean', 'max', 'count']).round(2)
        print(f"   • Per-namespace statistics:")
        for namespace, stats in ns_stats.iterrows():
            print(f"     - {namespace}: avg={stats['mean']} ms, max={stats['max']} ms, data_points={stats['count']}")


class NetworkAnalysisVisualizer(BaseVisualizer):
    """Handles comprehensive network analysis combining multiple metrics."""
    
    def plot_analysis(self, figsize=(18, 14)):
        """Create comprehensive network analysis plots."""
        if not self.data_loader.has_data('istio_latency'):
            print("❌ No network data available for comprehensive analysis")
            return None
        
        # For now, focus on Istio latency analysis
        # Could be extended to include other network metrics in the future
        latency_viz = IstioLatencyVisualizer(self.data_loader, self.exclude_zones)
        return latency_viz.plot_analysis(figsize)
    
    def get_summary_stats(self):
        """Get comprehensive network summary statistics."""
        stats = {}
        
        if self.data_loader.has_data('istio_latency'):
            latency_viz = IstioLatencyVisualizer(self.data_loader, self.exclude_zones)
            stats['istio_latency'] = latency_viz.get_summary_stats()
        
        return stats
    
    def print_summary(self):
        """Print comprehensive network summary."""
        if self.data_loader.has_data('istio_latency'):
            latency_viz = IstioLatencyVisualizer(self.data_loader, self.exclude_zones)
            latency_viz.print_summary()
        else:
            print("❌ No network data available for analysis")


class ServiceMeshAnalyzer(BaseVisualizer):
    """Advanced service mesh analysis combining latency with resource usage."""
    
    def plot_analysis(self, figsize=(20, 16)):
        """Create advanced service mesh analysis plots."""
        if not self.data_loader.has_data('istio_latency'):
            print("❌ No Istio latency data available for service mesh analysis")
            return None
        
        df = self.data_loader.get_data('istio_latency').copy()
        
        if len(df) == 0:
            print("❌ Istio latency data is empty")
            return None
        
        # Create subplots for advanced analysis
        fig, axes = plt.subplots(2, 3, figsize=figsize)
        fig.suptitle('Advanced Service Mesh Analysis', fontsize=16, fontweight='bold')
        
        # 1. Latency percentiles over time
        self._plot_latency_percentiles(axes[0, 0], df)
        
        # 2. Service latency vs request frequency (if data available)
        self._plot_latency_vs_frequency(axes[0, 1], df)
        
        # 3. Inter-namespace latency correlation
        self._plot_namespace_correlation(axes[0, 2], df)
        
        # 4. Latency degradation detection
        self._plot_latency_degradation(axes[1, 0], df)
        
        # 5. Service performance ranking
        self._plot_service_ranking(axes[1, 1], df)
        
        # 6. Latency anomaly detection
        self._plot_anomaly_detection(axes[1, 2], df)
        
        plt.tight_layout()
        plt.close('all')
        plt.show()
        
        return fig
    
    def _plot_latency_percentiles(self, ax, df):
        """Plot latency percentiles over time."""
        # Group by time and calculate percentiles
        time_stats = df.groupby('datetime')['p95_latency_ms'].agg([
            lambda x: np.percentile(x, 50),  # P50
            lambda x: np.percentile(x, 90),  # P90
            lambda x: np.percentile(x, 95),  # P95
            lambda x: np.percentile(x, 99)   # P99
        ])
        time_stats.columns = ['P50', 'P90', 'P95', 'P99']
        
        for percentile in ['P50', 'P90', 'P95', 'P99']:
            ax.plot(time_stats.index, time_stats[percentile], 
                   label=percentile, linewidth=2, alpha=0.8)
        
        ax.set_title('Latency Percentiles Over Time')
        ax.set_xlabel('Time')
        ax.set_ylabel('Latency (ms)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis='x', rotation=45)
    
    def _plot_latency_vs_frequency(self, ax, df):
        """Plot latency vs request frequency."""
        # Calculate request frequency (requests per time window)
        service_freq = df.groupby(['namespace', 'pod']).size().reset_index(name='request_count')
        service_latency = df.groupby(['namespace', 'pod'])['p95_latency_ms'].mean().reset_index()
        
        merged_stats = pd.merge(service_freq, service_latency, on=['namespace', 'pod'])
        
        scatter = ax.scatter(merged_stats['request_count'], merged_stats['p95_latency_ms'], 
                           alpha=0.6, s=50)
        ax.set_xlabel('Request Frequency (count)')
        ax.set_ylabel('Average P95 Latency (ms)')
        ax.set_title('Latency vs Request Frequency')
        ax.grid(True, alpha=0.3)
        
        # Add correlation coefficient
        if len(merged_stats) > 1:
            corr = merged_stats['request_count'].corr(merged_stats['p95_latency_ms'])
            ax.text(0.05, 0.95, f'Correlation: {corr:.3f}', 
                   transform=ax.transAxes, fontsize=10, 
                   bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    def _plot_namespace_correlation(self, ax, df):
        """Plot inter-namespace latency correlation."""
        pivot_latency = df.pivot_table(values='p95_latency_ms', 
                                      index='datetime', 
                                      columns='namespace', 
                                      aggfunc='mean')
        
        if len(pivot_latency.columns) > 1:
            latency_corr = pivot_latency.corr()
            mask = np.triu(np.ones_like(latency_corr, dtype=bool))  # Mask upper triangle
            sns.heatmap(latency_corr, ax=ax, annot=True, cmap='coolwarm', center=0,
                       mask=mask, square=True, cbar_kws={'label': 'Latency Correlation'})
            ax.set_title('Inter-Namespace Latency Correlation')
        else:
            ax.text(0.5, 0.5, 'Single Namespace\nNo Correlation\nAnalysis', 
                   ha='center', va='center', transform=ax.transAxes, fontsize=12)
            ax.set_title('Inter-Namespace Latency Correlation')
    
    def _plot_latency_degradation(self, ax, df):
        """Plot latency degradation detection."""
        # Calculate rolling average and detect trends
        time_series = df.groupby('datetime')['p95_latency_ms'].mean().sort_index()
        
        if len(time_series) > 5:
            rolling_avg = time_series.rolling(window=min(5, len(time_series)//2), center=True).mean()
            
            ax.plot(time_series.index, time_series.values, 
                   label='Actual Latency', alpha=0.6, color='blue')
            ax.plot(rolling_avg.index, rolling_avg.values, 
                   label='Rolling Average', linewidth=2, color='red')
            
            # Highlight degradation points (where current > rolling avg by threshold)
            threshold_multiplier = 1.2
            degradation_points = time_series > (rolling_avg * threshold_multiplier)
            if degradation_points.any():
                degradation_times = time_series[degradation_points]
                ax.scatter(degradation_times.index, degradation_times.values, 
                          color='red', s=50, alpha=0.8, label='Potential Degradation')
            
            ax.set_title('Latency Degradation Detection')
            ax.set_xlabel('Time')
            ax.set_ylabel('P95 Latency (ms)')
            ax.legend()
            ax.grid(True, alpha=0.3)
            ax.tick_params(axis='x', rotation=45)
        else:
            ax.text(0.5, 0.5, 'Insufficient data\nfor degradation analysis', 
                   ha='center', va='center', transform=ax.transAxes, fontsize=12)
            ax.set_title('Latency Degradation Detection')
    
    def _plot_service_ranking(self, ax, df):
        """Plot service performance ranking."""
        service_stats = df.groupby(['namespace', 'pod']).agg({
            'p95_latency_ms': ['mean', 'std']
        }).round(2)
        service_stats.columns = ['avg_latency', 'latency_std']
        service_stats = service_stats.reset_index()
        service_stats['service_label'] = service_stats['namespace'] + '/' + service_stats['pod']
        
        # Create composite score (lower is better)
        service_stats['performance_score'] = service_stats['avg_latency'] + (service_stats['latency_std'] * 0.5)
        best_services = service_stats.nsmallest(10, 'performance_score')
        
        bars = ax.barh(range(len(best_services)), best_services['performance_score'], 
                      color='lightgreen', alpha=0.7)
        ax.set_yticks(range(len(best_services)))
        ax.set_yticklabels(best_services['service_label'], fontsize=8)
        ax.set_xlabel('Performance Score (lower is better)')
        ax.set_title('Top 10 Best Performing Services')
        ax.grid(True, alpha=0.3, axis='x')
        
        # Add value labels on bars
        for i, (bar, value) in enumerate(zip(bars, best_services['performance_score'])):
            ax.text(value + max(best_services['performance_score']) * 0.01, 
                   bar.get_y() + bar.get_height()/2, 
                   f'{value:.1f}', va='center', fontsize=8)
    
    def _plot_anomaly_detection(self, ax, df):
        """Plot latency anomaly detection."""
        # Simple anomaly detection using IQR method
        Q1 = df['p95_latency_ms'].quantile(0.25)
        Q3 = df['p95_latency_ms'].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        
        # Identify anomalies
        anomalies = df[(df['p95_latency_ms'] < lower_bound) | (df['p95_latency_ms'] > upper_bound)]
        normal_data = df[(df['p95_latency_ms'] >= lower_bound) & (df['p95_latency_ms'] <= upper_bound)]
        
        # Plot normal data
        ax.scatter(normal_data['datetime'], normal_data['p95_latency_ms'], 
                  alpha=0.6, s=20, color='blue', label='Normal')
        
        # Plot anomalies
        if len(anomalies) > 0:
            ax.scatter(anomalies['datetime'], anomalies['p95_latency_ms'], 
                      alpha=0.8, s=50, color='red', label='Anomalies')
        
        # Add boundary lines
        ax.axhline(y=upper_bound, color='red', linestyle='--', alpha=0.7, label='Upper Bound')
        ax.axhline(y=lower_bound, color='red', linestyle='--', alpha=0.7, label='Lower Bound')
        
        ax.set_title(f'Latency Anomaly Detection ({len(anomalies)} anomalies found)')
        ax.set_xlabel('Time')
        ax.set_ylabel('P95 Latency (ms)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis='x', rotation=45)
    
    def get_summary_stats(self):
        """Get advanced service mesh analysis statistics."""
        if not self.data_loader.has_data('istio_latency'):
            return {}
        
        df = self.data_loader.get_data('istio_latency')
        
        # Anomaly detection
        Q1 = df['p95_latency_ms'].quantile(0.25)
        Q3 = df['p95_latency_ms'].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        anomalies = df[(df['p95_latency_ms'] < lower_bound) | (df['p95_latency_ms'] > upper_bound)]
        
        stats = {
            'total_services': df.groupby(['namespace', 'pod']).ngroups,
            'anomaly_count': len(anomalies),
            'anomaly_percentage': (len(anomalies) / len(df)) * 100 if len(df) > 0 else 0,
            'latency_bounds': {
                'lower': lower_bound,
                'upper': upper_bound,
                'iqr': IQR
            },
            'service_performance_spread': df.groupby(['namespace', 'pod'])['p95_latency_ms'].mean().std()
        }
        
        return stats 