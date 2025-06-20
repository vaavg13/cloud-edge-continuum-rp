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


class CompactFormatter(logging.Formatter):
    """Ultra-compact formatter with no timestamps or log levels."""
    
    def format(self, record):
        return record.getMessage()


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for different log levels."""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        # Add color to the log level
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
        
        # Use a cleaner format
        formatter = logging.Formatter(
            '%(asctime)s %(levelname)s %(message)s',
            datefmt='%H:%M:%S'
        )
        return formatter.format(record)


class EdgeExperimentManager:
    def __init__(self, prometheus_exporter, traffic_generator, 
                 experiment_name=None, output_base_dir="DATA", quiet_mode=True):
        """
        Initialize the experiment manager.
        
        Args:
            prometheus_exporter: PrometheusExporter instance for metrics collection
            traffic_generator: EdgeRequestGenerator instance for load generation
            experiment_name (str): Name for this experiment (auto-generated if None)
            output_base_dir (str): Base directory for output files
            quiet_mode (bool): If True, use cleaner, less verbose logging
        """
        # Generate experiment name if not provided
        if experiment_name is None:
            timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M")
            experiment_name = f"edge_experiment_{timestamp}"
        
        self.experiment_name = experiment_name
        self.output_dir = Path(output_base_dir) / experiment_name
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.quiet_mode = quiet_mode
        
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
        
        # Clear any existing handlers to avoid duplicates
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Configure logging with ultra-compact format
        if self.quiet_mode:
            # Use compact formatter for console (no timestamps, no log levels)
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(CompactFormatter())
            
            # Use standard formatter for file
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            
            # Configure root logger
            root_logger.setLevel(logging.INFO)
            root_logger.addHandler(file_handler)
            root_logger.addHandler(console_handler)
        else:
            # Original verbose logging
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
                      max_users=15, spawn_rate=3, enable_request_logging=True):
        """
        Run the complete experiment with metrics collection.
        
        Args:
            edge_config (dict): Edge computing configuration
            duration_hours (int): Real duration of experiment in hours
            simulated_hours (int): Simulated time period in hours
            max_users (int): Maximum number of concurrent users
            spawn_rate (int): Rate of spawning users
            enable_request_logging (bool): Whether to log individual requests for visualization
            
        Returns:
            bool: True if experiment completed successfully
        """
        if self.is_running:
            self.logger.warning("Experiment is already running!")
            return False
        
        try:
            # Show overview
            self._show_experiment_overview(edge_config, duration_hours, simulated_hours)
            
            # Start metrics collection
            self.prometheus_exporter.start_collection()
            
            # Wait a moment for metrics collection to stabilize
            time.sleep(5)
            
            # Setup request logging file path
            request_log_file = None
            if enable_request_logging:
                request_log_file = str(self.output_dir / "edge_requests.csv")
            
            self.is_running = True
            
            success = self.traffic_generator.run_edge_experiment(
                edge_config=edge_config,
                max_users=max_users,
                spawn_rate=spawn_rate,
                run_duration_seconds=duration_hours * 60 * 60,
                simulated_period_seconds=simulated_hours * 60 * 60,
                log_level="INFO",
                enable_request_logging=enable_request_logging,
                request_log_file=request_log_file
            )
            
            self.is_running = False
            
            if success:
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
        self.prometheus_exporter.stop_collection()
        print("📊 Metrics collection completed")
        
    def _show_experiment_overview(self, edge_config, duration_hours, simulated_hours):
        """Display experiment configuration in a compact table format."""
        
        # Experiment header
        print(f"\n🚀 EXPERIMENT: {self.experiment_name}")
        print("=" * 60)
        
        # Configuration table
        print("📋 CONFIGURATION")
        print(f"{'Duration:':<15} {duration_hours}h real → {simulated_hours}h simulated")
        print(f"{'Host:':<15} {edge_config['base_host']}")
        print(f"{'Output:':<15} {self.output_dir.name}")
        print(f"{'Metrics:':<15} Every {self.prometheus_exporter.collection_interval_minutes}min")
        
        # Apps table
        print(f"\n🔌 APPLICATIONS ({len(edge_config['apps'])})")
        for app in edge_config['apps']:
            print(f"  {app['name']:<12} Port {app['port']:<6} Weight {app['traffic_weight']}")
        
        # Sites table  
        print(f"\n🌍 EDGE SITES ({len(edge_config['edge_sites'])})")
        for site_id, site_config in edge_config['edge_sites'].items():
            print(f"  {site_id:<15} {site_config['pattern']:<15} Weight {site_config['traffic_weight']}")
        
        # Endpoints count
        endpoint_count = len(edge_config['apps']) * len(edge_config['edge_sites'])
        print(f"\n📈 ENDPOINTS: {endpoint_count} total")
        
        print("=" * 60)
    
    def _show_final_results(self):
        """Show final experiment results in compact format."""
        print("\n" + "=" * 60)
        print("✅ EXPERIMENT COMPLETED")
        print("=" * 60)
        
        # Get load test stats
        stats = self.traffic_generator.get_stats()
        if stats:
            print("📊 RESULTS")
            print(f"{'Requests:':<15} {stats['total_requests']:,}")
            print(f"{'Rate:':<15} {stats['requests_per_second']:.1f} req/s")
            print(f"{'Avg Response:':<15} {stats['average_response_time']:.0f} ms")
            print(f"{'Failures:':<15} {stats['failure_rate']:.1%}")
        
        print(f"\n📁 OUTPUT: {self.output_dir}")
        print("=" * 60)

    @property
    def output_directory(self):
        """Get the output directory for this experiment."""
        return self.output_dir 