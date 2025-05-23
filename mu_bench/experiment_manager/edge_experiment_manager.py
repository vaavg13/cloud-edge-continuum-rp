"""
Edge Experiment Manager

Manages the execution of edge computing experiments with metrics collection.
"""
import logging
import time
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path


class EdgeExperimentManager:
    def __init__(self, prometheus_exporter, traffic_generator, 
                 experiment_name=None, output_base_dir="DATA"):
        """
        Initialize the experiment manager.
        
        Args:
            prometheus_exporter: PrometheusExporter instance for metrics collection
            traffic_generator: EdgeRequestGenerator instance for load generation
            experiment_name (str): Name for this experiment (auto-generated if None)
            output_base_dir (str): Base directory for output files
        """
        # Generate experiment name if not provided
        if experiment_name is None:
            timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M")
            experiment_name = f"edge_experiment_{timestamp}"
        
        self.experiment_name = experiment_name
        self.output_dir = Path(output_base_dir) / experiment_name
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Store components
        self.prometheus_exporter = prometheus_exporter
        self.traffic_generator = traffic_generator
        
        # Update prometheus exporter output directory to be inside experiment directory
        metrics_output_dir = self.output_dir / "metrics"
        self.prometheus_exporter.output_dir = metrics_output_dir
        self.prometheus_exporter.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Update CSV file paths to use the new directory
        self.prometheus_exporter.csv_files = {
            'node_cpu': metrics_output_dir / 'node_cpu_usage.csv',
            'node_memory': metrics_output_dir / 'node_memory_usage.csv', 
            'pod_cpu': metrics_output_dir / 'pod_cpu_usage.csv',
            'pod_memory': metrics_output_dir / 'pod_memory_usage.csv',
            'istio_latency': metrics_output_dir / 'istio_latency.csv'
        }
        
        # Initialize CSV files with headers in the correct location
        self.prometheus_exporter._initialize_csv_files()
        
        # Setup logging
        self.setup_logging()
        self.logger = logging.getLogger("EdgeExperiment")
        
        # Experiment control
        self.is_running = False
        self.setup_signal_handlers()
        
    def setup_logging(self):
        """Setup logging to both file and console."""
        log_file = self.output_dir / f"{self.experiment_name}.log"
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
            self.stop_experiment()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def run_experiment(self, edge_config, duration_hours=7, simulated_hours=24, 
                      max_users=15, spawn_rate=3):
        """
        Run the complete experiment with metrics collection.
        
        Args:
            edge_config (dict): Edge computing configuration
            duration_hours (int): Real duration of experiment in hours
            simulated_hours (int): Simulated time period in hours
            max_users (int): Maximum number of concurrent users
            spawn_rate (int): Rate of spawning users
            
        Returns:
            bool: True if experiment completed successfully
        """
        if self.is_running:
            self.logger.warning("Experiment is already running!")
            return False
        
        try:
            # Show overview
            self._show_experiment_overview(edge_config, duration_hours, simulated_hours)
            
            self.logger.info("\n" + "=" * 50)
            self.logger.info("🎯 STARTING EXPERIMENT")
            self.logger.info("=" * 50)
            
            # Start metrics collection
            self.logger.info("📊 Starting Prometheus metrics collection...")
            self.logger.info(f"📁 Metrics will be saved to: {self.output_dir / 'metrics'}")
            self.prometheus_exporter.start_collection()
            
            # Wait a moment for metrics collection to stabilize
            time.sleep(5)
            
            # Start the edge load test
            self.logger.info("🚀 Starting edge load test...")
            
            self.is_running = True
            
            success = self.traffic_generator.run_edge_experiment(
                edge_config=edge_config,
                max_users=max_users,
                spawn_rate=spawn_rate,
                run_duration_seconds=duration_hours * 60 * 60,
                simulated_period_seconds=simulated_hours * 60 * 60,
                log_level="INFO"
            )
            
            self.is_running = False
            
            if success:
                self.logger.info("✅ Edge load test completed successfully!")
                self._show_final_results()
                return True
            else:
                self.logger.error("❌ Edge load test failed!")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Experiment failed with error: {e}")
            self.is_running = False
            return False
        finally:
            # Always stop metrics collection
            self._stop_metrics_collection()
    
    def stop_experiment(self):
        """Stop the experiment gracefully."""
        self.logger.info("🛑 Stopping experiment...")
        self.is_running = False
        self._stop_metrics_collection()
    
    def _stop_metrics_collection(self):
        """Stop metrics collection."""
        self.logger.info("📊 Stopping metrics collection...")
        self.prometheus_exporter.stop_collection()
        
        # Show metrics file locations
        csv_files = self.prometheus_exporter.get_csv_files()
        self.logger.info("\n📁 Metrics files saved to:")
        for metric_type, filepath in csv_files.items():
            if filepath.exists():
                file_size = filepath.stat().st_size / 1024  # Size in KB
                self.logger.info(f"   • {metric_type}: {filepath} ({file_size:.1f} KB)")
    
    def _show_experiment_overview(self, edge_config, duration_hours, simulated_hours):
        """Display experiment configuration and overview."""
        self.logger.info("=" * 70)
        self.logger.info(f"🚀 EDGE COMPUTING EXPERIMENT: {self.experiment_name}")
        self.logger.info("=" * 70)
        self.logger.info(f"📁 Output Directory: {self.output_dir}")
        self.logger.info(f"🕐 Duration: {duration_hours} hours (simulating {simulated_hours} hours)")
        self.logger.info(f"📊 Metrics Collection: Every {self.prometheus_exporter.collection_interval_minutes} minutes")
        self.logger.info(f"🌐 Target Host: {edge_config['base_host']}")
        
        self.logger.info("\n🔌 Edge Applications:")
        for app in edge_config['apps']:
            self.logger.info(f"   • {app['name']} (Port {app['port']}) - Weight: {app['traffic_weight']}")
        
        self.logger.info("\n🌍 Edge Sites:")
        for site_id, site_config in edge_config['edge_sites'].items():
            self.logger.info(f"   • {site_id}: {site_config['description']}")
            self.logger.info(f"     Pattern: {site_config['pattern']}, Weight: {site_config['traffic_weight']}")
        
        self.logger.info("\n📈 Generated Endpoints:")
        for app in edge_config['apps']:
            for site_id in edge_config['edge_sites'].keys():
                url = f"http://{edge_config['base_host']}:{app['port']}/s0-{site_id}"
                self.logger.info(f"   • {url}")
        
        self.logger.info("\n📊 Metrics to be collected:")
        self.logger.info("   • Node CPU usage")
        self.logger.info("   • Node memory usage") 
        self.logger.info("   • Pod CPU usage")
        self.logger.info("   • Pod memory usage")
        self.logger.info("   • Istio service latency (P95)")
    
    def _show_final_results(self):
        """Show final experiment results."""
        self.logger.info("\n" + "=" * 50)
        self.logger.info("📊 EXPERIMENT RESULTS")
        self.logger.info("=" * 50)
        
        # Get load test stats
        stats = self.traffic_generator.get_stats()
        if stats:
            self.logger.info("🎯 Load Test Results:")
            self.logger.info(f"   Total Requests: {stats['total_requests']:,}")
            self.logger.info(f"   Requests/Second: {stats['requests_per_second']:.2f}")
            self.logger.info(f"   Average Response Time: {stats['average_response_time']:.2f} ms")
            self.logger.info(f"   Failure Rate: {stats['failure_rate']:.2%}")
        
        # Show output directory
        self.logger.info(f"\n📁 All experiment data saved to: {self.output_dir}")
        self.logger.info(f"📝 Experiment log: {self.output_dir / f'{self.experiment_name}.log'}")
        self.logger.info(f"📊 Metrics data: {self.output_dir / 'metrics'}")

    @property
    def output_directory(self):
        """Get the output directory for this experiment."""
        return self.output_dir 