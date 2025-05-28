"""
Request Pattern Analyzer

Analyzes and visualizes traffic patterns from edge request logs.
Helps understand the improved desynchronized behavior.
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import argparse
from datetime import datetime
import numpy as np


class RequestPatternAnalyzer:
    """Analyzes request patterns from CSV logs."""
    
    def __init__(self, csv_file: str):
        """Initialize with CSV file path."""
        self.csv_file = Path(csv_file)
        self.df = None
        self.load_data()
    
    def load_data(self):
        """Load request data from CSV file."""
        if not self.csv_file.exists():
            raise FileNotFoundError(f"Request log file not found: {self.csv_file}")
        
        try:
            self.df = pd.read_csv(self.csv_file)
            print(f"✅ Loaded {len(self.df)} requests from {self.csv_file}")
            
            # Convert timestamp to datetime
            self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])
            
            # Create time bins for aggregation
            self.df['time_bin'] = self.df['simulated_time_seconds'] // 300  # 5-minute bins
            
        except Exception as e:
            raise Exception(f"Failed to load CSV data: {e}")
    
    def analyze_app_patterns(self):
        """Analyze traffic patterns per app."""
        print("\n📊 App Traffic Analysis")
        print("=" * 50)
        
        # Requests per app
        app_counts = self.df.groupby('app_name').size()
        print("\n🔢 Total Requests per App:")
        for app, count in app_counts.items():
            print(f"   {app}: {count:,}")
        
        # Success rates per app
        success_rates = self.df.groupby('app_name')['success'].mean()
        print("\n✅ Success Rates per App:")
        for app, rate in success_rates.items():
            print(f"   {app}: {rate:.2%}")
        
        # Burst vs normal requests
        burst_analysis = self.df.groupby(['app_name', 'request_type']).size().unstack(fill_value=0)
        print("\n⚡ Burst vs Normal Requests:")
        print(burst_analysis)
        
        return app_counts, success_rates, burst_analysis
    
    def analyze_temporal_patterns(self):
        """Analyze temporal traffic patterns."""
        print("\n⏰ Temporal Pattern Analysis")
        print("=" * 50)
        
        # Requests over time (5-minute bins)
        temporal_data = self.df.groupby(['time_bin', 'app_name']).size().unstack(fill_value=0)
        
        # Peak times per app
        print("\n🏔️ Peak Traffic Times (simulated hours):")
        for app in temporal_data.columns:
            peak_bin = temporal_data[app].idxmax()
            peak_hour = (peak_bin * 300) / 3600  # Convert to hours
            peak_requests = temporal_data[app].max()
            print(f"   {app}: Hour {peak_hour:.1f} ({peak_requests} requests)")
        
        return temporal_data
    
    def plot_traffic_patterns(self, output_dir: str = "plots"):
        """Create visualizations of traffic patterns."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # Set style
        plt.style.use('seaborn-v0_8')
        sns.set_palette("husl")
        
        # 1. Traffic over time per app
        plt.figure(figsize=(15, 8))
        temporal_data = self.df.groupby(['time_bin', 'app_name']).size().unstack(fill_value=0)
        
        for app in temporal_data.columns:
            time_hours = temporal_data.index * 300 / 3600  # Convert to hours
            plt.plot(time_hours, temporal_data[app], marker='o', linewidth=2, label=app)
        
        plt.title('Traffic Patterns Over Time (Desynchronized Apps)', fontsize=16, fontweight='bold')
        plt.xlabel('Simulated Time (Hours)', fontsize=12)
        plt.ylabel('Requests per 5-minute bin', fontsize=12)
        plt.legend(title='Applications', fontsize=10)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_path / 'traffic_over_time.png', dpi=300, bbox_inches='tight')
        print(f"📈 Saved: {output_path / 'traffic_over_time.png'}")
        
        # 2. Request type distribution
        plt.figure(figsize=(12, 6))
        request_type_data = self.df.groupby(['app_name', 'request_type']).size().unstack(fill_value=0)
        request_type_data.plot(kind='bar', stacked=True, ax=plt.gca())
        plt.title('Request Type Distribution by App', fontsize=16, fontweight='bold')
        plt.xlabel('Application', fontsize=12)
        plt.ylabel('Number of Requests', fontsize=12)
        plt.legend(title='Request Type')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(output_path / 'request_types.png', dpi=300, bbox_inches='tight')
        print(f"📊 Saved: {output_path / 'request_types.png'}")
        
        # 3. Response time distribution
        plt.figure(figsize=(12, 8))
        for i, app in enumerate(self.df['app_name'].unique()):
            app_data = self.df[self.df['app_name'] == app]
            plt.subplot(2, 2, i+1)
            plt.hist(app_data['response_time_ms'], bins=50, alpha=0.7, edgecolor='black')
            plt.title(f'{app} Response Times')
            plt.xlabel('Response Time (ms)')
            plt.ylabel('Frequency')
            plt.grid(True, alpha=0.3)
        
        plt.suptitle('Response Time Distributions', fontsize=16, fontweight='bold')
        plt.tight_layout()
        plt.savefig(output_path / 'response_times.png', dpi=300, bbox_inches='tight')
        print(f"⏱️ Saved: {output_path / 'response_times.png'}")
        
        # 4. Success rate over time
        plt.figure(figsize=(15, 6))
        success_over_time = self.df.groupby(['time_bin', 'app_name'])['success'].mean().unstack(fill_value=0)
        
        for app in success_over_time.columns:
            time_hours = success_over_time.index * 300 / 3600
            plt.plot(time_hours, success_over_time[app] * 100, marker='s', linewidth=2, label=app)
        
        plt.title('Success Rate Over Time', fontsize=16, fontweight='bold')
        plt.xlabel('Simulated Time (Hours)', fontsize=12)
        plt.ylabel('Success Rate (%)', fontsize=12)
        plt.legend(title='Applications')
        plt.grid(True, alpha=0.3)
        plt.ylim(0, 105)
        plt.tight_layout()
        plt.savefig(output_path / 'success_rates.png', dpi=300, bbox_inches='tight')
        print(f"✅ Saved: {output_path / 'success_rates.png'}")
        
        plt.show()
    
    def generate_report(self, output_file: str = "traffic_analysis_report.txt"):
        """Generate a text report of the analysis."""
        with open(output_file, 'w') as f:
            f.write("🚀 Edge Traffic Pattern Analysis Report\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"📁 Source: {self.csv_file}\n")
            f.write(f"📊 Total Requests: {len(self.df):,}\n\n")
            
            # App analysis
            app_counts, success_rates, burst_analysis = self.analyze_app_patterns()
            
            f.write("📱 Application Summary:\n")
            for app in self.df['app_name'].unique():
                app_data = self.df[self.df['app_name'] == app]
                f.write(f"\n{app}:\n")
                f.write(f"  • Total Requests: {len(app_data):,}\n")
                f.write(f"  • Success Rate: {app_data['success'].mean():.2%}\n")
                f.write(f"  • Avg Response Time: {app_data['response_time_ms'].mean():.1f}ms\n")
                f.write(f"  • Burst Requests: {len(app_data[app_data['request_type'] == 'burst']):,}\n")
            
            # Temporal analysis
            temporal_data = self.analyze_temporal_patterns()
            f.write(f"\n⏰ Peak Traffic Analysis:\n")
            for app in temporal_data.columns:
                peak_bin = temporal_data[app].idxmax()
                peak_hour = (peak_bin * 300) / 3600
                f.write(f"  • {app}: Peak at hour {peak_hour:.1f}\n")
            
            f.write(f"\n✅ Analysis complete! Check plots/ directory for visualizations.\n")
        
        print(f"📄 Report saved: {output_file}")


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description="Analyze edge request patterns")
    parser.add_argument("csv_file", help="Path to request log CSV file")
    parser.add_argument("--output-dir", default="plots", help="Output directory for plots")
    parser.add_argument("--report", default="traffic_analysis_report.txt", help="Report file name")
    
    args = parser.parse_args()
    
    try:
        analyzer = RequestPatternAnalyzer(args.csv_file)
        analyzer.analyze_app_patterns()
        analyzer.analyze_temporal_patterns()
        analyzer.plot_traffic_patterns(args.output_dir)
        analyzer.generate_report(args.report)
        
        print(f"\n🎉 Analysis complete!")
        print(f"📊 Plots saved to: {args.output_dir}/")
        print(f"📄 Report saved to: {args.report}")
        
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main() 