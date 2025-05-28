#!/usr/bin/env python3
"""
Edge Requests Analysis Script

This script demonstrates how to use the new EdgeRequestsVisualizer
to analyze request patterns from MuBench experiments.

Usage:
    python analyze_edge_requests.py [experiment_dir]
    
Example:
    python analyze_edge_requests.py DATA/edge_experiment_2025_05_28_14_11/
"""

import sys
import argparse
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from mu_bench.visualization import MetricsVisualizer, EdgeRequestsVisualizer
from mu_bench.visualization.base import DataLoader


def analyze_edge_requests(experiment_dir, output_dir=None):
    """Analyze edge requests from an experiment directory.
    
    Args:
        experiment_dir: Path to experiment directory
        output_dir: Optional output directory for analysis files
    """
    experiment_path = Path(experiment_dir)
    
    if not experiment_path.exists():
        print(f"❌ Experiment directory not found: {experiment_dir}")
        return
    
    print(f"🔍 Analyzing edge requests from: {experiment_path}")
    print("=" * 60)
    
    # Method 1: Using the integrated MetricsVisualizer
    print("\n📊 METHOD 1: Using Integrated MetricsVisualizer")
    print("-" * 40)
    
    try:
        # Look for metrics directory first
        metrics_dir = experiment_path / 'metrics'
        if not metrics_dir.exists():
            metrics_dir = experiment_path
        
        viz = MetricsVisualizer(str(metrics_dir))
        
        # Show comprehensive summary including edge requests
        viz.show_summary()
        
        # Generate edge requests analysis if available
        if viz.edge_requests_viz.requests_data is not None:
            print("\n🚀 Generating Edge Requests Analysis...")
            viz.plot_edge_requests_analysis()
            
            if output_dir:
                print(f"\n📁 Exporting analysis to: {output_dir}")
                viz.export_edge_requests_analysis(output_dir)
        else:
            print("\n⚠ No edge requests data found in experiment directory")
    
    except Exception as e:
        print(f"❌ Error with integrated analysis: {e}")
    
    # Method 2: Using standalone EdgeRequestsVisualizer
    print("\n\n📊 METHOD 2: Using Standalone EdgeRequestsVisualizer")
    print("-" * 40)
    
    try:
        # Create data loader
        metrics_dir = experiment_path / 'metrics'
        if not metrics_dir.exists():
            metrics_dir = experiment_path
            
        data_loader = DataLoader(str(metrics_dir))
        
        # Create edge requests visualizer
        edge_viz = EdgeRequestsVisualizer(data_loader)
        
        if edge_viz.requests_data is not None:
            # Print detailed summary
            edge_viz.print_summary()
            
            # Generate analysis plots
            print("\n📈 Generating detailed analysis plots...")
            edge_viz.plot_analysis()
            
            # Export analysis if output directory specified
            if output_dir:
                standalone_output = f"{output_dir}_standalone"
                print(f"\n📁 Exporting standalone analysis to: {standalone_output}")
                edge_viz.export_analysis(standalone_output)
        else:
            print("\n⚠ No edge requests data found for standalone analysis")
    
    except Exception as e:
        print(f"❌ Error with standalone analysis: {e}")


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Analyze edge requests from MuBench experiments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze specific experiment
  python analyze_edge_requests.py DATA/edge_experiment_2025_05_28_14_11/
  
  # Analyze with output export
  python analyze_edge_requests.py DATA/edge_experiment_2025_05_28_14_11/ --output analysis_results
  
  # Analyze latest experiment
  python analyze_edge_requests.py DATA/edge_experiment_2025_05_28_14_11/
        """
    )
    
    parser.add_argument(
        'experiment_dir',
        nargs='?',
        default='DATA/edge_experiment_2025_05_28_14_11/',
        help='Path to experiment directory (default: DATA/edge_experiment_2025_05_28_14_11/)'
    )
    
    parser.add_argument(
        '--output', '-o',
        help='Output directory for analysis files'
    )
    
    parser.add_argument(
        '--list-experiments', '-l',
        action='store_true',
        help='List available experiment directories'
    )
    
    args = parser.parse_args()
    
    # List experiments if requested
    if args.list_experiments:
        data_dir = Path('DATA')
        if data_dir.exists():
            print("📁 Available experiment directories:")
            for exp_dir in sorted(data_dir.glob('edge_experiment_*')):
                print(f"   • {exp_dir.name}")
                # Check if it has edge requests data
                edge_requests_file = exp_dir / 'edge_requests.csv'
                if edge_requests_file.exists():
                    print(f"     ✓ Has edge_requests.csv")
                else:
                    print(f"     ⚠ No edge_requests.csv found")
        else:
            print("❌ DATA directory not found")
        return
    
    # Analyze the specified experiment
    analyze_edge_requests(args.experiment_dir, args.output)


if __name__ == "__main__":
    main() 