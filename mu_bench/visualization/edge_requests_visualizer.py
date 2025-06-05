"""
Edge Requests Visualizer

Analyzes and visualizes edge request patterns from experiment data.
Provides comprehensive analysis of request distribution, response times,
success rates, and edge site performance.
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from pathlib import Path
from datetime import datetime
from .base import BaseVisualizer


class EdgeRequestsVisualizer(BaseVisualizer):
    """Visualizer for edge request patterns and performance analysis."""
    
    def __init__(self, data_loader, exclude_zones=None):
        """Initialize the edge requests visualizer.
        
        Args:
            data_loader: DataLoader instance with edge requests data
            exclude_zones: List of zones to exclude from analysis
        """
        super().__init__(data_loader, exclude_zones)
        self.requests_data = None
        self.load_requests_data()
    
    def load_requests_data(self):
        """Load edge requests data from the data loader."""
        # Look for edge requests CSV file in the metrics directory
        requests_file = self.data_loader.metrics_dir / 'edge_requests.csv'
        
        if not requests_file.exists():
            # Try parent directory (common location for experiment data)
            requests_file = self.data_loader.metrics_dir.parent / 'edge_requests.csv'
        
        if requests_file.exists():
            try:
                self.requests_data = pd.read_csv(requests_file)
                
                # Convert timestamp to datetime
                try:
                    self.requests_data['timestamp'] = pd.to_datetime(self.requests_data['timestamp'])
                except ValueError as e:
                    print(f"Attempting flexible timestamp parsing for edge_requests due to: {e}")
                    self.requests_data['timestamp'] = pd.to_datetime(self.requests_data['timestamp'], format='ISO8601', errors='coerce')
                
                # Create time bins for temporal analysis (5-minute bins)
                self.requests_data['time_bin'] = self.requests_data['simulated_time_seconds'] // 300
                self.requests_data['time_hours'] = self.requests_data['simulated_time_seconds'] / 3600
                
                # Add zone information based on edge site
                self.requests_data['zone'] = self.requests_data['edge_site']
                
                # Apply zone filtering
                self.requests_data = self._filter_by_zones(self.requests_data, 'zone')
                
                print(f"✓ Loaded edge requests: {len(self.requests_data)} records")
                print(f"📊 Time range: {self.requests_data['time_hours'].min():.1f}h - {self.requests_data['time_hours'].max():.1f}h")
                print(f"🏢 Edge sites: {', '.join(sorted(self.requests_data['edge_site'].unique()))}")
                print(f"📱 Applications: {', '.join(sorted(self.requests_data['app_name'].unique()))}")
                
            except Exception as e:
                print(f"✗ Error loading edge requests data: {e}")
                self.requests_data = None
        else:
            print(f"⚠ Edge requests file not found at {requests_file}")
            self.requests_data = None
    
    def plot_analysis(self, figsize=(20, 16)):
        """Create comprehensive edge requests analysis plots.
        
        Args:
            figsize: Figure size (width, height)
            
        Returns:
            matplotlib.figure.Figure: The created figure
        """
        if self.requests_data is None or len(self.requests_data) == 0:
            print("❌ No edge requests data available for visualization")
            return None
        
        fig, axes = plt.subplots(3, 3, figsize=figsize)
        fig.suptitle('Edge Requests Analysis - Experiment Performance Overview', 
                    fontsize=16, fontweight='bold', y=0.98)
        
        # 1. Requests over time by application
        ax1 = axes[0, 0]
        temporal_data = self.requests_data.groupby(['time_bin', 'app_name']).size().unstack(fill_value=0)
        for app in temporal_data.columns:
            time_hours = temporal_data.index * 300 / 3600
            ax1.plot(time_hours, temporal_data[app], marker='o', linewidth=2, label=app, alpha=0.8)
        ax1.set_title('Request Volume Over Time', fontweight='bold')
        ax1.set_xlabel('Simulated Time (Hours)')
        ax1.set_ylabel('Requests per 5-min bin')
        ax1.legend(title='Applications', fontsize=9)
        ax1.grid(True, alpha=0.3)
        
        # 2. Request distribution by edge site
        ax2 = axes[0, 1]
        site_counts = self.requests_data['edge_site'].value_counts()
        colors = sns.color_palette("husl", len(site_counts))
        wedges, texts, autotexts = ax2.pie(site_counts.values, labels=site_counts.index, 
                                          autopct='%1.1f%%', colors=colors, startangle=90)
        ax2.set_title('Request Distribution by Edge Site', fontweight='bold')
        
        # 3. Success rate over time
        ax3 = axes[0, 2]
        success_over_time = self.requests_data.groupby(['time_bin', 'app_name'])['success'].mean().unstack(fill_value=0)
        for app in success_over_time.columns:
            time_hours = success_over_time.index * 300 / 3600
            ax3.plot(time_hours, success_over_time[app] * 100, marker='s', linewidth=2, label=app, alpha=0.8)
        ax3.set_title('Success Rate Over Time', fontweight='bold')
        ax3.set_xlabel('Simulated Time (Hours)')
        ax3.set_ylabel('Success Rate (%)')
        ax3.legend(title='Applications', fontsize=9)
        ax3.grid(True, alpha=0.3)
        ax3.set_ylim(0, 105)
        
        # 4. Response time distribution by application
        ax4 = axes[1, 0]
        apps = self.requests_data['app_name'].unique()
        response_times = [self.requests_data[self.requests_data['app_name'] == app]['response_time_ms'].values 
                         for app in apps]
        bp = ax4.boxplot(response_times, labels=apps, patch_artist=True)
        colors = sns.color_palette("husl", len(apps))
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
        ax4.set_title('Response Time Distribution', fontweight='bold')
        ax4.set_ylabel('Response Time (ms)')
        ax4.tick_params(axis='x', rotation=45)
        ax4.grid(True, alpha=0.3)
        
        # 5. Request type distribution
        ax5 = axes[1, 1]
        request_type_data = self.requests_data.groupby(['app_name', 'request_type']).size().unstack(fill_value=0)
        request_type_data.plot(kind='bar', stacked=True, ax=ax5, color=sns.color_palette("husl", 2))
        ax5.set_title('Request Type Distribution', fontweight='bold')
        ax5.set_xlabel('Application')
        ax5.set_ylabel('Number of Requests')
        ax5.legend(title='Request Type', fontsize=9)
        ax5.tick_params(axis='x', rotation=45)
        
        # 6. Response time vs success rate scatter
        ax6 = axes[1, 2]
        app_stats = self.requests_data.groupby('app_name').agg({
            'response_time_ms': 'mean',
            'success': 'mean'
        }).reset_index()
        
        colors = sns.color_palette("husl", len(app_stats))
        for i, (_, row) in enumerate(app_stats.iterrows()):
            ax6.scatter(row['response_time_ms'], row['success'] * 100, 
                       s=200, alpha=0.7, color=colors[i], label=row['app_name'])
        ax6.set_title('Response Time vs Success Rate', fontweight='bold')
        ax6.set_xlabel('Average Response Time (ms)')
        ax6.set_ylabel('Success Rate (%)')
        ax6.legend(fontsize=9)
        ax6.grid(True, alpha=0.3)
        
        # 7. Edge site performance comparison
        ax7 = axes[2, 0]
        site_performance = self.requests_data.groupby('edge_site').agg({
            'response_time_ms': 'mean',
            'success': 'mean'
        })
        
        x_pos = np.arange(len(site_performance))
        width = 0.35
        
        ax7_twin = ax7.twinx()
        bars1 = ax7.bar(x_pos - width/2, site_performance['response_time_ms'], width, 
                       label='Avg Response Time', alpha=0.8, color='skyblue')
        bars2 = ax7_twin.bar(x_pos + width/2, site_performance['success'] * 100, width, 
                            label='Success Rate', alpha=0.8, color='lightcoral')
        
        ax7.set_title('Edge Site Performance Comparison', fontweight='bold')
        ax7.set_xlabel('Edge Site')
        ax7.set_ylabel('Response Time (ms)', color='skyblue')
        ax7_twin.set_ylabel('Success Rate (%)', color='lightcoral')
        ax7.set_xticks(x_pos)
        ax7.set_xticklabels(site_performance.index, rotation=45)
        
        # Add legends
        lines1, labels1 = ax7.get_legend_handles_labels()
        lines2, labels2 = ax7_twin.get_legend_handles_labels()
        ax7.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=9)
        
        # 8. Hourly request pattern heatmap
        ax8 = axes[2, 1]
        hourly_data = self.requests_data.copy()
        hourly_data['hour'] = (hourly_data['simulated_time_seconds'] // 3600).astype(int)
        heatmap_data = hourly_data.groupby(['hour', 'app_name']).size().unstack(fill_value=0)
        
        if len(heatmap_data) > 0:
            sns.heatmap(heatmap_data.T, annot=True, fmt='d', cmap='YlOrRd', ax=ax8, cbar_kws={'label': 'Requests'})
            ax8.set_title('Hourly Request Pattern Heatmap', fontweight='bold')
            ax8.set_xlabel('Simulated Hour')
            ax8.set_ylabel('Application')
        
        # 9. Status code distribution
        ax9 = axes[2, 2]
        status_counts = self.requests_data['status_code'].value_counts()
        colors = ['green' if code == 200 else 'red' for code in status_counts.index]
        bars = ax9.bar(status_counts.index.astype(str), status_counts.values, color=colors, alpha=0.7)
        ax9.set_title('HTTP Status Code Distribution', fontweight='bold')
        ax9.set_xlabel('Status Code')
        ax9.set_ylabel('Number of Requests')
        
        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            ax9.text(bar.get_x() + bar.get_width()/2., height + height*0.01,
                    f'{int(height)}', ha='center', va='bottom', fontsize=10)
        
        plt.tight_layout()
        plt.close('all')
        plt.show()
        return fig
    
    def get_summary_stats(self):
        """Get comprehensive summary statistics for edge requests.
        
        Returns:
            dict: Summary statistics
        """
        if self.requests_data is None or len(self.requests_data) == 0:
            return {"error": "No edge requests data available"}
        
        stats = {
            "total_requests": len(self.requests_data),
            "time_range_hours": {
                "start": self.requests_data['time_hours'].min(),
                "end": self.requests_data['time_hours'].max(),
                "duration": self.requests_data['time_hours'].max() - self.requests_data['time_hours'].min()
            },
            "applications": {},
            "edge_sites": {},
            "overall_performance": {
                "success_rate": self.requests_data['success'].mean(),
                "avg_response_time_ms": self.requests_data['response_time_ms'].mean(),
                "median_response_time_ms": self.requests_data['response_time_ms'].median(),
                "p95_response_time_ms": self.requests_data['response_time_ms'].quantile(0.95),
                "p99_response_time_ms": self.requests_data['response_time_ms'].quantile(0.99)
            },
            "request_types": self.requests_data['request_type'].value_counts().to_dict(),
            "status_codes": self.requests_data['status_code'].value_counts().to_dict()
        }
        
        # Per-application statistics
        for app in self.requests_data['app_name'].unique():
            app_data = self.requests_data[self.requests_data['app_name'] == app]
            stats["applications"][app] = {
                "total_requests": len(app_data),
                "success_rate": app_data['success'].mean(),
                "avg_response_time_ms": app_data['response_time_ms'].mean(),
                "median_response_time_ms": app_data['response_time_ms'].median(),
                "request_types": app_data['request_type'].value_counts().to_dict(),
                "edge_sites": app_data['edge_site'].value_counts().to_dict()
            }
        
        # Per-edge-site statistics
        for site in self.requests_data['edge_site'].unique():
            site_data = self.requests_data[self.requests_data['edge_site'] == site]
            stats["edge_sites"][site] = {
                "total_requests": len(site_data),
                "success_rate": site_data['success'].mean(),
                "avg_response_time_ms": site_data['response_time_ms'].mean(),
                "median_response_time_ms": site_data['response_time_ms'].median(),
                "applications": site_data['app_name'].value_counts().to_dict()
            }
        
        return stats
    
    def print_summary(self):
        """Print a formatted summary of edge requests analysis."""
        stats = self.get_summary_stats()
        
        if "error" in stats:
            print(f"❌ {stats['error']}")
            return
        
        print("\n" + "="*60)
        print("🚀 EDGE REQUESTS ANALYSIS SUMMARY")
        print("="*60)
        
        print(f"\n📊 Overall Statistics:")
        print(f"   • Total Requests: {stats['total_requests']:,}")
        print(f"   • Time Range: {stats['time_range_hours']['start']:.1f}h - {stats['time_range_hours']['end']:.1f}h")
        print(f"   • Duration: {stats['time_range_hours']['duration']:.1f} hours")
        print(f"   • Success Rate: {stats['overall_performance']['success_rate']:.2%}")
        print(f"   • Avg Response Time: {stats['overall_performance']['avg_response_time_ms']:.1f}ms")
        print(f"   • P95 Response Time: {stats['overall_performance']['p95_response_time_ms']:.1f}ms")
        
        print(f"\n📱 Application Performance:")
        for app, app_stats in stats['applications'].items():
            print(f"   {app}:")
            print(f"     - Requests: {app_stats['total_requests']:,}")
            print(f"     - Success Rate: {app_stats['success_rate']:.2%}")
            print(f"     - Avg Response Time: {app_stats['avg_response_time_ms']:.1f}ms")
        
        print(f"\n🏢 Edge Site Performance:")
        for site, site_stats in stats['edge_sites'].items():
            print(f"   {site}:")
            print(f"     - Requests: {site_stats['total_requests']:,}")
            print(f"     - Success Rate: {site_stats['success_rate']:.2%}")
            print(f"     - Avg Response Time: {site_stats['avg_response_time_ms']:.1f}ms")
        
        print(f"\n🔄 Request Types:")
        for req_type, count in stats['request_types'].items():
            percentage = (count / stats['total_requests']) * 100
            print(f"   • {req_type}: {count:,} ({percentage:.1f}%)")
        
        print(f"\n📈 Status Codes:")
        for status, count in stats['status_codes'].items():
            percentage = (count / stats['total_requests']) * 100
            status_emoji = "✅" if status == 200 else "❌"
            print(f"   {status_emoji} {status}: {count:,} ({percentage:.1f}%)")
        
        print("="*60)
    
    def export_analysis(self, output_dir="edge_requests_analysis"):
        """Export comprehensive analysis to files.
        
        Args:
            output_dir: Directory to save analysis files
        """
        if self.requests_data is None or len(self.requests_data) == 0:
            print("❌ No edge requests data available for export")
            return
        
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # Generate and save plots
        fig = self.plot_analysis()
        if fig:
            plot_file = output_path / 'edge_requests_analysis.png'
            fig.savefig(plot_file, dpi=300, bbox_inches='tight')
            print(f"📊 Saved analysis plots: {plot_file}")
            plt.close(fig)
        
        # Save summary statistics as JSON
        import json
        stats = self.get_summary_stats()
        stats_file = output_path / 'edge_requests_stats.json'
        with open(stats_file, 'w') as f:
            json.dump(stats, f, indent=2, default=str)
        print(f"📈 Saved statistics: {stats_file}")
        
        # Generate detailed report
        report_file = output_path / 'edge_requests_report.txt'
        with open(report_file, 'w') as f:
            f.write("🚀 EDGE REQUESTS ANALYSIS REPORT\n")
            f.write("="*60 + "\n\n")
            f.write(f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"📁 Data Source: {self.data_loader.metrics_dir}\n\n")
            
            # Write summary statistics
            f.write("📊 SUMMARY STATISTICS\n")
            f.write("-"*30 + "\n")
            f.write(f"Total Requests: {stats['total_requests']:,}\n")
            f.write(f"Success Rate: {stats['overall_performance']['success_rate']:.2%}\n")
            f.write(f"Average Response Time: {stats['overall_performance']['avg_response_time_ms']:.1f}ms\n")
            f.write(f"P95 Response Time: {stats['overall_performance']['p95_response_time_ms']:.1f}ms\n")
            f.write(f"P99 Response Time: {stats['overall_performance']['p99_response_time_ms']:.1f}ms\n\n")
            
            # Application details
            f.write("📱 APPLICATION PERFORMANCE\n")
            f.write("-"*30 + "\n")
            for app, app_stats in stats['applications'].items():
                f.write(f"\n{app}:\n")
                f.write(f"  Requests: {app_stats['total_requests']:,}\n")
                f.write(f"  Success Rate: {app_stats['success_rate']:.2%}\n")
                f.write(f"  Avg Response Time: {app_stats['avg_response_time_ms']:.1f}ms\n")
                f.write(f"  Request Types: {app_stats['request_types']}\n")
            
            # Edge site details
            f.write(f"\n🏢 EDGE SITE PERFORMANCE\n")
            f.write("-"*30 + "\n")
            for site, site_stats in stats['edge_sites'].items():
                f.write(f"\n{site}:\n")
                f.write(f"  Requests: {site_stats['total_requests']:,}\n")
                f.write(f"  Success Rate: {site_stats['success_rate']:.2%}\n")
                f.write(f"  Avg Response Time: {site_stats['avg_response_time_ms']:.1f}ms\n")
        
        print(f"📄 Saved detailed report: {report_file}")
        print(f"✅ Analysis exported to: {output_path}") 