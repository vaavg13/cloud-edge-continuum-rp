import os
import sys
import asyncio


# Add project root to path
project_root = os.path.abspath('..')
sys.path.append(project_root)

# Prevent hanging on imports (required for gevent)
from gevent import monkey
monkey.patch_all()

# Import experiment components
from mu_bench.metrics_exporter.prometheus_exporter import PrometheusExporter
from mu_bench.request_generator.edge_request_generator import EdgeRequestGenerator
from mu_bench.experiment_manager import EdgeExperimentManager

# Import drift monitor components (manual configuration only)
from nl_interface.drift_monitor.config_schema import (
    DriftMonitorConfig, 
    ThresholdConfig, 
    MetricType, 
    ComparisonOperator
)
from nl_interface.drift_monitor.monitor_manager import create_monitor_with_agent_actions


MONITOR_CONFIG = DriftMonitorConfig(
    loop_id="edge-experiment-monitor",
    namespace="app-edge-2",
    thresholds=[
        ThresholdConfig(
            metric_type=MetricType.POD_CPU,
            threshold_value=0.7,
            operator=ComparisonOperator.GREATER_THAN,
            unit="cores",
            description="Critical CPU usage"
        ),
        ThresholdConfig(
            metric_type=MetricType.POD_MEMORY,
            threshold_value=256,
            operator=ComparisonOperator.GREATER_THAN,
            unit="MB", 
            description="High memory usage"
        ),
        ThresholdConfig(
            metric_type=MetricType.ISTIO_LATENCY,
            threshold_value=200.0,
            operator=ComparisonOperator.GREATER_THAN,
            unit="ms",
            description="High latency detected"
        )
    ],
    check_interval_seconds=30
)

EXPERIMENT_CONFIG = {
    "base_host": "172.23.0.5",
    "apps": [
        # {
        #     "name": "app-edge",
        #     "port": 31115,
        #     "traffic_weight": 1,
        #     "wait_time": {"min": 0.7, "max": 1.5}
        # },
        {
            "name": "app-edge-2",
            "port": 31116,
            "traffic_weight": 0.9,
            "wait_time": {"min": 0.8, "max": 2.5}
        },
    ],
    "edge_sites": {
        "edge-site-1": {
            "pattern": "urban_peak",
            "description": "Urban site with business peaks",
            "traffic_weight": 1.0
        },
        "edge-site-2": {
            "pattern": "suburban_steady", 
            "description": "Suburban site with steady traffic",
            "traffic_weight": 0.8
        }
    }
}


async def experiment_with_manual_monitoring():
    """
    Simple demo: manual configuration + experiment from notebook.
    """
    # Custom intent template
    intent = "URGENT: Resource issue in {namespace} - {metric_type}: {metric_value} > {threshold_value}"
    
    # Create monitor
    monitor = create_monitor_with_agent_actions(MONITOR_CONFIG, intent)
    
    print(f"📊 Created monitor for: {MONITOR_CONFIG.namespace}")
    print(f"🔍 Monitoring {len(MONITOR_CONFIG.thresholds)} thresholds")
    
    # Setup experiment components (from notebook)
    prometheus_exporter = PrometheusExporter(
        prometheus_url="http://localhost:9090",
        target_namespaces=["app-edge-2"],
        collection_interval_minutes=5,
        metrics_step="30s",
        output_dir="metrics",
        verbose=True,
        create_output_dir=False
    )
    
    traffic_generator = EdgeRequestGenerator()
    
    experiment_manager = EdgeExperimentManager(
        prometheus_exporter=prometheus_exporter,
        traffic_generator=traffic_generator,
        experiment_name=None,
        output_base_dir="../DATA"
    )
    
    print("🧪 Experiment components ready")
    
    # 3. Run everything together
    print("\n🚀 Starting monitoring...")
    await monitor.start()
    
    try:
        # Quick check before experiment
        result = await monitor.check_once()
        print(f"✅ Initial check: {result.get('violations_found', 0)} violations")
        
        # Run experiment (shorter for demo - 3 minutes)
        print("\n🎯 Running experiment with monitoring...")
        success = experiment_manager.run_experiment(
            edge_config=EXPERIMENT_CONFIG,
            duration_hours=0.05,  # 3 minutes
            simulated_hours=24,
            max_users=40,
            spawn_rate=3
        )
        
        if success:
            print(f"🎉 Experiment completed!")
        else:
            print("💥 Experiment failed!")
            
        # Final check
        result = await monitor.check_once()
        print(f"🔍 Final check: {result.get('violations_found', 0)} violations")
        
    except KeyboardInterrupt:
        print("⛔ Interrupted by user")
    except Exception as e:
        print(f"💥 Error: {e}")
    finally:
        await monitor.stop()
        print("🛑 Monitoring stopped")


if __name__ == "__main__":
    asyncio.run(experiment_with_manual_monitoring()) 