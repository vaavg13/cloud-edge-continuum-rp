import time
import logging
import gevent
import random
import requests
import math
import csv
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse

from locust import HttpUser, task, between
from locust.env import Environment
from locust.stats import stats_printer
from locust.log import setup_logging

from .edge_calculator import EdgeTrafficCalculator
from .load_shape import GlobalUserCountShape


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


class EdgeRequestGenerator:
    """
    Simplified request generator specifically designed for edge computing scenarios.
    
    Much simpler than the original RequestGenerator - focuses on realistic
    edge site patterns and port-based app differentiation.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None, quiet_mode: bool = True):
        """
        Initialize the EdgeRequestGenerator.
        
        Args:
            logger: Optional logger instance. If None, creates a default logger.
            quiet_mode: If True, suppress verbose Locust output
        """
        self.quiet_mode = quiet_mode
        self.logger = logger or self._setup_default_logger()
        self.edge_calculator = EdgeTrafficCalculator()
        self.environment = None
        self.runner = None
        self.stats_printer_greenlet = None
        self.stop_greenlet = None
        self.user_classes = []
        
        # Request logging
        self.request_log_file = None
        self.request_log_writer = None
        self.request_logging_enabled = False
        
        # Suppress Locust's verbose logging if in quiet mode
        if self.quiet_mode:
            self._setup_quiet_logging()
    
    def _setup_default_logger(self) -> logging.Logger:
        """Setup a default logger with compact format."""
        logger = logging.getLogger("EdgeRequestGenerator")
        
        # Clear existing handlers to avoid duplicates
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            if self.quiet_mode:
                handler.setFormatter(CompactFormatter())
            else:
                handler.setFormatter(ColoredFormatter())
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            logger.propagate = False  # Prevent propagation to root logger
        return logger
    
    def _setup_quiet_logging(self):
        """Setup quiet logging to suppress Locust's verbose output but keep useful stats."""
        # Suppress only the most verbose Locust internal loggers
        # but keep the stats printer which shows the useful table
        verbose_loggers = [
            'locust.main',
            'locust.user',
            'locust.env'
        ]
        
        # Set these to WARNING to reduce noise but not completely silence
        moderate_loggers = [
            'locust.runners'
        ]
        
        for logger_name in verbose_loggers:
            logging.getLogger(logger_name).setLevel(logging.ERROR)
            
        for logger_name in moderate_loggers:
            logging.getLogger(logger_name).setLevel(logging.WARNING)
        
        # Keep locust.stats at INFO level so we see the table
        # Don't suppress stdout/stderr completely since we want to see the stats table
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
    
    def _suppress_output(self):
        """Temporarily suppress stdout/stderr only during environment creation."""
        if self.quiet_mode:
            # Only suppress during specific operations, not during stats display
            self._null_stdout = open(os.devnull, 'w')
            self._null_stderr = open(os.devnull, 'w')
            sys.stdout = self._null_stdout
            sys.stderr = self._null_stderr
    
    def _restore_output(self):
        """Restore stdout/stderr."""
        if self.quiet_mode and hasattr(self, '_null_stdout'):
            if hasattr(self._null_stdout, 'close'):
                self._null_stdout.close()
            if hasattr(self._null_stderr, 'close'):
                self._null_stderr.close()
            sys.stdout = self._original_stdout
            sys.stderr = self._original_stderr
    
    def _generate_edge_user_classes(self, edge_config: Dict[str, Any]):
        """
        Generate HttpUser classes for edge computing scenarios.
        
        Args:
            edge_config: Simplified edge configuration
        """
        self.user_classes.clear()
        
        base_host = edge_config.get("base_host", "localhost")
        apps = edge_config.get("apps", [])
        edge_sites = edge_config.get("edge_sites", {})
        endpoint = edge_config.get("endpoint", "s0")
        
        if not apps or not edge_sites:
            self.logger.warning("⚠️ No apps or edge sites defined")
            return
        
        # Create one user class per app (port)
        for app_config in apps:
            app_name = app_config.get("name", "unknown")
            app_port = app_config.get("port")
            app_weight = app_config.get("traffic_weight", 1.0)
            wait_time_config = app_config.get("wait_time", {"min": 0.5, "max": 2.0})
            
            if not app_port:
                self.logger.warning(f"⚠️ Skipping app '{app_name}' - no port specified")
                continue
            
            # Create dynamic user class for this app
            class_name = f"{app_name.replace('-', '').capitalize()}EdgeUser"
            
            user_class = self._create_edge_user_class(
                class_name=class_name,
                app_name=app_name,
                app_port=app_port,
                base_host=base_host,
                edge_sites=edge_sites,
                app_weight=app_weight,
                wait_time=between(wait_time_config["min"], wait_time_config["max"]),
                endpoint=endpoint
            )
            
            self.user_classes.append(user_class)
    
    def _create_edge_user_class(
        self,
        class_name: str,
        app_name: str, 
        app_port: int,
        base_host: str,
        edge_sites: Dict[str, Any],
        app_weight: float,
        endpoint: str,
        wait_time,
    ):
        """Create a dynamic user class for edge computing scenarios."""
        
        # Capture variables for the class
        edge_calculator = self.edge_calculator
        logger = self.logger
        captured_wait_time = wait_time  # Capture wait_time for closure
        
        class EdgeUser(HttpUser):
            weight = int(app_weight * 10)  # Scale for Locust weights
            wait_time = captured_wait_time
            host = f"http://{base_host}:{app_port}"  # Set host at class level
            def __init__(self, environment: Environment):
                super().__init__(environment)
                self.app_name = app_name
                self.app_port = app_port
                self.base_host = base_host
                self.edge_sites = edge_sites
                self.edge_calculator = edge_calculator
                self.endpoint = endpoint
                
                # Reference to parent generator for logging
                self.generator = None
                if hasattr(environment, 'generator_instance'):
                    self.generator = environment.generator_instance
            
            @task(1)
            def hit_edge_site(self):
                """Make requests to edge sites based on traffic patterns."""
                if not hasattr(self.environment, 'shared_simulated_time'):
                    # Fallback to real time if no simulated time
                    current_time = time.time() % 86400  # Current time in day
                else:
                    current_time = self.environment.shared_simulated_time
                
                # Build weighted choices for edge sites
                weighted_sites = []
                for site_id, site_config in self.edge_sites.items():
                    pattern_name = site_config.get("pattern", "suburban_steady")
                    site_weight = site_config.get("traffic_weight", 1.0)
                    
                    # Calculate traffic multiplier for this site at this time
                    traffic_multiplier = self.edge_calculator.calculate_site_traffic_multiplier(
                        pattern_name, current_time
                    )
                    
                    # Combine site weight with time-based multiplier
                    final_weight = site_weight * traffic_multiplier
                    
                    if final_weight > 0:
                        weighted_sites.append({
                            "site_id": site_id,
                            "weight": final_weight
                        })
                
                if not weighted_sites:
                    return
                
                # Select edge site based on weights
                sites = [site["site_id"] for site in weighted_sites]
                weights = [site["weight"] for site in weighted_sites]
                chosen_site = random.choices(population=sites, weights=weights, k=1)[0]
                
                # Make request to endpoint-{edge-site-id} format
                endpoint = f"/{self.endpoint}-{chosen_site}"
                request_name = f"{self.app_port}:{endpoint}"
                
                start_time = time.time()
                try:
                    with self.client.get(endpoint, name=request_name, catch_response=True) as response:
                        response_time_ms = (time.time() - start_time) * 1000
                        success = response.status_code == 200
                        
                        if success:
                            response.success()
                        else:
                            response.failure(f"HTTP {response.status_code}")
                        
                        # Log the request
                        if self.generator:
                            self.generator._log_request(
                                app_name=self.app_name,
                                app_port=self.app_port,
                                edge_site=chosen_site,
                                endpoint=endpoint,
                                request_type="normal",
                                response_time_ms=response_time_ms,
                                status_code=response.status_code,
                                success=success,
                                simulated_time=current_time
                            )
                            
                except Exception as e:
                    response_time_ms = (time.time() - start_time) * 1000
                    logger.warning(f"Request failed for {request_name}: {e}")
                    
                    # Log the failed request
                    if self.generator:
                        self.generator._log_request(
                            app_name=self.app_name,
                            app_port=self.app_port,
                            edge_site=chosen_site,
                            endpoint=endpoint,
                            request_type="normal",
                            response_time_ms=response_time_ms,
                            status_code=0,  # Connection error
                            success=False,
                            simulated_time=current_time
                        )
        
        # Set class name for debugging
        EdgeUser.__name__ = class_name
        EdgeUser.__qualname__ = class_name
        
        return EdgeUser
    
    def _test_connectivity(self, edge_config: Dict[str, Any]) -> bool:
        """Test connectivity to all edge endpoints."""
        base_host = edge_config.get("base_host", "localhost")
        apps = edge_config.get("apps", [])
        edge_sites = edge_config.get("edge_sites", {})
        endpoint_prefix = edge_config.get("endpoint", "s0")
        
        tested_count = 0
        failed_endpoints = []
        
        for app_config in apps:
            app_port = app_config.get("port")
            if not app_port:
                continue
                
            for site_id in edge_sites.keys():
                endpoint = f"http://{base_host}:{app_port}/{endpoint_prefix}-{site_id}"
                try:
                    response = requests.get(endpoint, timeout=5)
                    if response.status_code not in [200, 404]:  # 404 is OK for non-existent endpoints
                        failed_endpoints.append(f"{endpoint} (HTTP {response.status_code})")
                    tested_count += 1
                except requests.exceptions.RequestException as e:
                    failed_endpoints.append(f"{endpoint} ({str(e)})")
                    tested_count += 1
        
        if failed_endpoints:
            self.logger.error(f"❌ Failed endpoints: {', '.join(failed_endpoints)}")
            return False
        
        return True

    def run_edge_experiment(
        self,
        edge_config: Dict[str, Any],
        max_users: int = 20,
        spawn_rate: int = 5,
        run_duration_seconds: float = 300,
        simulated_period_seconds: float = 86400,
        log_level: str = "INFO",
        enable_request_logging: bool = False,
        request_log_file: Optional[str] = None
    ) -> bool:
        """
        Run a complete edge computing experiment.
        
        Args:
            edge_config: Simplified edge configuration
            max_users: Maximum concurrent users
            spawn_rate: User spawn rate
            run_duration_seconds: Experiment duration
            simulated_period_seconds: Simulated time period (for time scaling)
            log_level: Logging level
            enable_request_logging: Whether to log individual requests to CSV
            request_log_file: Path to request log file (auto-generated if None)
            
        Returns:
            True if experiment completed successfully
        """
        try:
            # Setup Locust logging (but we'll suppress most of it)
            if self.quiet_mode:
                setup_logging("WARNING", None)  # Only show warnings/errors from Locust
            else:
                setup_logging(log_level.upper(), None)
            
            # Test connectivity first
            if not self._test_connectivity(edge_config):
                return False
            
            # Generate user classes
            self._generate_edge_user_classes(edge_config)
            
            if not self.user_classes:
                self.logger.error("❌ No user classes generated")
                return False
            
            # Setup request logging if enabled
            if enable_request_logging and request_log_file:
                self.enable_request_logging(request_log_file)
            
            # Configure load shape
            time_scale_factor = simulated_period_seconds / run_duration_seconds
            GlobalUserCountShape.configure(
                max_users=max_users,
                spawn_rate=spawn_rate, 
                time_scale_factor=time_scale_factor
            )
            
            # Create Locust environment
            self._suppress_output()  # Suppress during environment creation
            try:
                # Create shape instance
                shape_instance = GlobalUserCountShape()
                
                self.environment = Environment(
                    user_classes=self.user_classes,
                    shape_class=shape_instance
                )
                
                # Set generator reference for request logging
                self.environment.generator_instance = self
                
                # Initialize shared simulated time
                self.environment.shared_simulated_time = GlobalUserCountShape.current_simulated_time_seconds
                
                # Create runner
                self.runner = self.environment.create_local_runner()
            finally:
                self._restore_output()
            
            # Start the test
            self.runner.start_shape()
            
            # Start stats printer
            gevent.spawn(stats_printer(self.environment.stats))
            
            # Setup stopper
            def stopper():
                gevent.sleep(run_duration_seconds)
                self.runner.stop()
            
            self.stop_greenlet = gevent.spawn(stopper)
            
            # Wait for completion
            self.runner.greenlet.join()
            
            return True
            
        except Exception as e:
            self.logger.error(f"💥 Edge experiment failed: {e}")
            return False
        finally:
            self._cleanup()
    
    def _cleanup(self):
        """Clean up resources."""
        if self.stop_greenlet and not self.stop_greenlet.dead:
            self.stop_greenlet.kill(block=False)
        if self.stats_printer_greenlet and not self.stats_printer_greenlet.dead:
            self.stats_printer_greenlet.kill(block=False)
        
        # Close CSV file if open
        if hasattr(self, 'request_log_file_handle') and self.request_log_file_handle:
            try:
                self.request_log_file_handle.close()
            except:
                pass
        
        # Restore output if it was suppressed
        self._restore_output()
    
    def get_stats(self) -> Optional[Dict[str, Any]]:
        """
        Get current experiment statistics.
        
        Returns:
            Dictionary containing current stats or None if no active experiment
        """
        if not self.environment or not self.environment.stats:
            return None
        
        stats = self.environment.stats
        return {
            'total_requests': stats.total.num_requests,
            'total_failures': stats.total.num_failures,
            'average_response_time': stats.total.avg_response_time,
            'min_response_time': stats.total.min_response_time,
            'max_response_time': stats.total.max_response_time,
            'requests_per_second': stats.total.current_rps,
            'failure_rate': stats.total.fail_ratio
        }
    
    def enable_request_logging(self, output_file: str):
        """Enable logging of individual requests to CSV file."""
        self.request_log_file = Path(output_file)
        self.request_log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Open CSV file for writing
        self.request_log_file_handle = open(self.request_log_file, 'w', newline='')
        self.request_log_writer = csv.writer(self.request_log_file_handle)
        
        # Write header
        self.request_log_writer.writerow([
            'timestamp', 'app_name', 'app_port', 'edge_site', 'endpoint', 
            'request_type', 'response_time_ms', 'status_code', 'success', 'simulated_time'
        ])
        
        self.request_logging_enabled = True
    
    def _log_request(self, app_name: str, app_port: int, edge_site: str, endpoint: str, 
                    request_type: str, response_time_ms: float, status_code: int, 
                    success: bool, simulated_time: float):
        """Log a request to the CSV file."""
        if not self.request_logging_enabled or not self.request_log_writer:
            return
            
        try:
            self.request_log_writer.writerow([
                datetime.now().isoformat(),
                app_name,
                app_port,
                edge_site,
                endpoint,
                request_type,
                round(response_time_ms, 2),
                status_code,
                success,
                round(simulated_time, 2)
            ])
        except Exception as e:
            self.logger.warning(f"Failed to log request: {e}")

    def get_request_log_file(self) -> Optional[Path]:
        """Get the path to the request log file."""
        return self.request_log_file if self.request_logging_enabled else None 