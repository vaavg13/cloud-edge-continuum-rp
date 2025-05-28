import time
import os
import sys
from datetime import datetime
from pathlib import Path

from ..metrics_exporter.prometheus_exporter import PrometheusExporter

def main():
    print("=== PrometheusExporter Test ===")
    
    # Configuration
    collection_interval_minutes = 2   # Trigger collection every 2 minutes
    metrics_step = "30s"               # Get metrics every 30 seconds within each collection
    output_dir = f"DATA/test_experiment_{datetime.now().strftime('%Y_%m_%d')}"
    prometheus_url = "http://localhost:9090"  # Adjust if needed
    verbose = False  # Set to False for quiet operation
    
    print(f"Collection: Every {collection_interval_minutes}min with {metrics_step} step intervals")
    print(f"Output: {output_dir}")
    print(f"Verbose mode: {'ON' if verbose else 'OFF'}")
    
    # Initialize the exporter
    try:
        exporter = PrometheusExporter(
            prometheus_url=prometheus_url,
            target_namespaces=["app-edge", "app-edge-2"],
            collection_interval_minutes=collection_interval_minutes,
            metrics_step=metrics_step,
            output_dir=output_dir,
            verbose=verbose
        )
        print("✓ Exporter initialized")
    except Exception as e:
        print(f"✗ Initialization failed: {e}")
        return 1
    finally:
        exporter.stop_collection()
    
    # Show basic results
    csv_files = exporter.get_csv_files()
    created_files = [name for name, path in csv_files.items() if path.exists()]
    
    print("Test completed")
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 