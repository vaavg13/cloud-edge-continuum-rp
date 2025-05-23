#!/usr/bin/env python3
"""
Simple test script for PrometheusExporter.

This script tests the interval-based metrics collection by:
- Running collection for 20 minutes total
- Using 2-minute collection intervals
- Using 30-second metrics step for granular data
- Demonstrating verbose control
"""

import time
import os
import sys
from datetime import datetime
from pathlib import Path

# Use relative import since we're within the mu_bench package
from ..metrics_exporter.prometheus_exporter import PrometheusExporter

def main():
    print("=== PrometheusExporter Test ===")
    
    # Configuration
    collection_interval_minutes = 2   # Trigger collection every 2 minutes
    metrics_step = "30s"               # Get metrics every 30 seconds within each collection
    total_duration_minutes = 20        # Run test for 20 minutes (10 collections)
    output_dir = f"DATA/test_experiment_{datetime.now().strftime('%Y_%m_%d')}"
    prometheus_url = "http://localhost:9090"  # Adjust if needed
    verbose = False  # Set to False for quiet operation
    
    print(f"Collection: Every {collection_interval_minutes}min with {metrics_step} step intervals")
    print(f"Total duration: {total_duration_minutes}min")
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
    
    try:
        # Demonstrate verbose control
        if verbose:
            print("✓ Starting collection with verbose output...")
        else:
            print("✓ Starting collection in quiet mode...")
        
        exporter.start_collection()
        
        if not exporter.is_running():
            print("✗ Failed to start collection")
            return 1
        
        # Wait for the specified duration
        print(f"Running for {total_duration_minutes} minutes (Ctrl+C to stop early)")
        print(f"Expected {total_duration_minutes // collection_interval_minutes} collection cycles")
        
        # Demo: Switch verbosity during execution
        half_time = total_duration_minutes // 2
        start_time = time.time()
        
        try:
            # Run first half
            time.sleep(half_time * 60)
            
            # Switch verbosity for demonstration
            new_verbose = not verbose
            print(f"\n--- Switching to {'verbose' if new_verbose else 'quiet'} mode ---")
            exporter.set_verbose(new_verbose)
            
            # Run second half
            time.sleep(half_time * 60)
            
        except KeyboardInterrupt:
            print("\nStopped by user")
        
    finally:
        # Stop metrics collection
        exporter.stop_collection()
        print("✓ Collection stopped")
    
    # Show basic results
    csv_files = exporter.get_csv_files()
    created_files = [name for name, path in csv_files.items() if path.exists()]
    
    if created_files:
        print(f"✓ Created {len(created_files)} CSV files: {', '.join(created_files)}")
    else:
        print("✗ No CSV files created")
    
    print("Test completed")
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 