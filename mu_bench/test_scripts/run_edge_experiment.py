"""
Minimal Edge Experiment Runner

Simple script to run edge computing experiments with metrics collection.
Creates components and runs a 7-hour experiment simulating 24 hours.
"""

from mu_bench.metrics_exporter.prometheus_exporter import PrometheusExporter
from mu_bench.request_generator.edge_request_generator import EdgeRequestGenerator
from mu_bench.experiment_manager import EdgeExperimentManager


def get_edge_config():
    """Get the edge computing configuration."""
    return {
        "base_host": "172.23.0.5",
        "apps": [
            {
                "name": "app-1",
                "port": 31116,
                "traffic_weight": 1.0,
                "wait_time": {"min": 0.5, "max": 2.0}
            },
            {
                "name": "app-2", 
                "port": 31115,
                "traffic_weight": 0.8,
                "wait_time": {"min": 1.0, "max": 3.0}
            }
        ],
        "edge_sites": {
            "edge-site-1": {
                "pattern": "urban_peak",
                "description": "Primary urban edge site",
                "traffic_weight": 1.0
            },
            "edge-site-2": {
                "pattern": "suburban_steady",
                "description": "Secondary suburban edge site", 
                "traffic_weight": 0.7
            }
        }
    }


def main():
    """Run the edge experiment."""
    print("🌐 Edge Computing Experiment")
    
    # Create prometheus logger (every 15 minutes)
    # Note: output_dir will be set by EdgeExperimentManager to be inside the experiment directory
    prometheus_logger = PrometheusExporter(
        prometheus_url="http://localhost:9090",
        target_namespaces=["app-edge", "app-edge-2"],
        collection_interval_minutes=15,
        metrics_step="30s",
        output_dir="metrics",  # Will be overridden by EdgeExperimentManager
        verbose=True,
        create_output_dir=False  # Don't create directory yet - EdgeExperimentManager will handle it
    )
    
    # Create traffic generator
    traffic_generator = EdgeRequestGenerator()
    
    # Create experiment manager
    experiment_manager = EdgeExperimentManager(
        prometheus_exporter=prometheus_logger,
        traffic_generator=traffic_generator,
        experiment_name=None,  # Auto-generate
        output_base_dir="DATA"
    )
    
    # Get edge configuration
    edge_config = get_edge_config()
    
    # Ask for confirmation
    response = input("\n🤔 Start 1-hour experiment (simulating 24h)? (y/N): ")
    if response.lower() != 'y':
        print("💭 Experiment cancelled.")
        return
    
    # Run experiment
    success = experiment_manager.run_experiment(
        edge_config=edge_config,
        duration_hours=1,        # Real time: 7 hours
        simulated_hours=24,      # Simulated time: 24 hours
        max_users=40,
        spawn_rate=3
    )
    
    if success:
        print(f"\n🎉 Experiment completed! Results: {experiment_manager.output_directory}")
    else:
        print("\n💥 Experiment failed!")


if __name__ == "__main__":
    main() 