import time
import logging
import gevent
import random
import requests
import math
import csv
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


class EdgeRequestGenerator:
    """
    Simplified request generator specifically designed for edge computing scenarios.
    
    Much simpler than the original RequestGenerator - focuses on realistic
    edge site patterns and port-based app differentiation.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize the EdgeRequestGenerator.
        
        Args:
            logger: Optional logger instance. If None, creates a default logger.
        """
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
        
        self.logger.info("EdgeRequestGenerator initialized successfully")
    
    def _setup_default_logger(self) -> logging.Logger:
        """Setup a default logger."""
        logger = logging.getLogger("EdgeRequestGenerator")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
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
        
        if not apps or not edge_sites:
            self.logger.warning("No apps or edge sites defined")
            return
        
        # Create one user class per app (port)
        for app_config in apps:
            app_name = app_config.get("name", "unknown")
            app_port = app_config.get("port")
            app_weight = app_config.get("traffic_weight", 1.0)
            wait_time_config = app_config.get("wait_time", {"min": 0.5, "max": 2.0})
            
            if not app_port:
                self.logger.warning(f"Skipping app '{app_name}' - no port specified")
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
                wait_time=between(wait_time_config["min"], wait_time_config["max"])
            )
            
            self.user_classes.append(user_class)
            self.logger.info(f"Generated edge user class: {class_name} for {base_host}:{app_port}")
    
    def _create_edge_user_class(
        self,
        class_name: str,
        app_name: str, 
        app_port: int,
        base_host: str,
        edge_sites: Dict[str, Any],
        app_weight: float,
        wait_time
    ):
        """Create a dynamic user class for edge computing scenarios."""
        
        # Capture variables for the class
        edge_calculator = self.edge_calculator
        logger = self.logger
        captured_wait_time = wait_time  # Capture wait_time for closure
        
        # Generate app-specific characteristics for more realistic behavior
        app_hash = hash(app_name)
        app_time_offset = (app_hash % (6 * 3600))  # 0-6 hour offset per app
        app_burst_base_prob = 0.008 + (app_hash % 100) / 10000  # 0.008-0.018% (reduced from 0.015-0.035%)
        app_burst_volume_factor = 0.6 + (app_hash % 1000) / 3333  # 0.6-0.9 (reduced from 0.5-1.0)
        app_traffic_phase = (app_hash % 100) / 100.0 * 2 * 3.14159  # Phase shift for traffic patterns
        
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
                
                # App-specific behavioral characteristics
                self.time_offset = app_time_offset
                self.burst_probability = app_burst_base_prob
                self.burst_volume_factor = app_burst_volume_factor
                self.traffic_phase = app_traffic_phase
                self.burst_cooldown = 0
                self.consecutive_requests = 0
                
                # Per-instance randomization for even more variation
                instance_hash = hash(f"{app_name}_{id(self)}")
                self.instance_time_jitter = (instance_hash % 1800)  # 0-30 min per instance
                self.instance_burst_modifier = 0.8 + (instance_hash % 400) / 1000  # 0.8-1.2 modifier
                
                # Reference to parent generator for logging
                self.generator = None
                if hasattr(environment, 'generator_instance'):
                    self.generator = environment.generator_instance
            
            @task(1)
            def hit_edge_site(self):
                """Make requests to edge sites based on traffic patterns."""
                if not hasattr(self.environment, 'shared_simulated_time'):
                    # Fallback to real time if no simulated time
                    base_time = time.time() % 86400  # Current time in day
                else:
                    base_time = self.environment.shared_simulated_time
                
                # Apply app-specific time offset and instance jitter
                current_time = (base_time + self.time_offset + self.instance_time_jitter) % 86400
                
                # Decrease burst cooldown
                if self.burst_cooldown > 0:
                    self.burst_cooldown -= 1
                
                # Calculate dynamic burst probability based on app activity
                self.consecutive_requests += 1
                activity_multiplier = min(2.0, 1.0 + self.consecutive_requests / 100)
                
                # Add temporal variation to burst probability
                time_factor = 1.0 + 0.2 * math.sin(current_time / 86400 * 2 * 3.14159 + self.traffic_phase)
                dynamic_burst_prob = self.burst_probability * activity_multiplier * time_factor * self.instance_burst_modifier
                
                # Check for independent app burst
                is_burst = False
                if self.burst_cooldown == 0 and random.random() < dynamic_burst_prob:
                    is_burst = True
                    # Variable burst volume and cooldown (reduced intensity)
                    burst_intensity = random.uniform(0.2, 0.6) * self.burst_volume_factor
                    burst_duration = max(1, int(random.uniform(3, 12) * burst_intensity))
                    self.burst_cooldown = random.randint(60, 180)
                    self.consecutive_requests = 0
                    
                    # For burst requests, select random sites with higher frequency
                    if random.random() < burst_intensity:
                        site_ids = list(self.edge_sites.keys())
                        chosen_site = random.choice(site_ids)
                        endpoint = f"/s0-{chosen_site}"
                        request_name = f"{self.app_port}:{endpoint}:BURST"
                        
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
                                        request_type="burst",
                                        response_time_ms=response_time_ms,
                                        status_code=response.status_code,
                                        success=success,
                                        simulated_time=current_time
                                    )
                                    
                        except Exception as e:
                            response_time_ms = (time.time() - start_time) * 1000
                            logger.warning(f"Burst request failed for {request_name}: {e}")
                            
                            # Log the failed request
                            if self.generator:
                                self.generator._log_request(
                                    app_name=self.app_name,
                                    app_port=self.app_port,
                                    edge_site=chosen_site,
                                    endpoint=endpoint,
                                    request_type="burst",
                                    response_time_ms=response_time_ms,
                                    status_code=0,  # Connection error
                                    success=False,
                                    simulated_time=current_time
                                )
                        return
                
                # Normal site selection with time-based patterns
                # Build weighted choices for edge sites
                weighted_sites = []
                for site_id, site_config in self.edge_sites.items():
                    pattern_name = site_config.get("pattern", "suburban_steady")
                    site_weight = site_config.get("traffic_weight", 1.0)
                    
                    # Calculate traffic multiplier for this site at this time
                    traffic_multiplier = self.edge_calculator.calculate_site_traffic_multiplier(
                        pattern_name, current_time
                    )
                    
                    # Apply app-specific phase shift to create different peak times
                    phase_shifted_multiplier = traffic_multiplier * (1.0 + 0.2 * math.sin(
                        current_time / 86400 * 2 * 3.14159 + self.traffic_phase
                    ))
                    
                    # Combine site weight with time-based multiplier and app characteristics
                    final_weight = site_weight * phase_shifted_multiplier * self.burst_volume_factor
                    
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
                
                # Make request to s0-{edge-site-id} endpoint
                endpoint = f"/s0-{chosen_site}"
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
        """Test connectivity to all endpoints before starting load test."""
        base_host = edge_config.get("base_host", "localhost")
        apps = edge_config.get("apps", [])
        edge_sites = edge_config.get("edge_sites", {})
        
        self.logger.info("Testing connectivity to edge endpoints...")
        
        all_working = True
        for app_config in apps:
            app_port = app_config.get("port")
            if not app_port:
                continue
                
            for site_id in edge_sites.keys():
                url = f"http://{base_host}:{app_port}/s0-{site_id}"
                try:
                    response = requests.get(url, timeout=5)
                    if response.status_code != 200:
                        self.logger.warning(f"Endpoint {url} returned HTTP {response.status_code}")
                        all_working = False
                except Exception as e:
                    self.logger.error(f"Failed to connect to {url}: {e}")
                    all_working = False
        
        return all_working

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
            # Setup logging
            setup_logging(log_level.upper(), None)
            
            # Setup request logging if enabled
            if enable_request_logging:
                if not request_log_file:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    request_log_file = f"edge_requests_{timestamp}.csv"
                self.enable_request_logging(request_log_file)
            
            # Test connectivity first
            if not self._test_connectivity(edge_config):
                self.logger.error("❌ Some endpoints are not reachable. Check your edge infrastructure.")
                return False
            
            # Generate user classes
            self._generate_edge_user_classes(edge_config)
            
            if not self.user_classes:
                self.logger.error("No user classes generated from edge config")
                return False
            
            # Configure load shape
            time_scale_factor = simulated_period_seconds / run_duration_seconds
            GlobalUserCountShape.configure(
                max_users=max_users,
                spawn_rate=spawn_rate, 
                time_scale_factor=time_scale_factor
            )
            
            # Create environment
            shape_instance = GlobalUserCountShape()
            self.environment = Environment(
                user_classes=self.user_classes,
                shape_class=shape_instance  # Pass the instance, not the class
            )
            
            # Set generator reference for request logging
            self.environment.generator_instance = self
            
            # Initialize shared simulated time - fix the 'bool' object is not callable error
            self.environment.shared_simulated_time = GlobalUserCountShape.current_simulated_time_seconds
            
            self.runner = self.environment.create_local_runner()
            
            # Start experiment
            self.logger.info("🚀 Starting edge computing experiment...")
            self.logger.info(f"📊 Config: {len(edge_config.get('apps', []))} apps, {len(edge_config.get('edge_sites', {}))} edge sites")
            self.logger.info(f"⚙️  Parameters: max_users={max_users}, spawn_rate={spawn_rate}, duration={run_duration_seconds}s")
            
            if self.request_logging_enabled:
                self.logger.info(f"📝 Request logging enabled: {self.request_log_file}")
            
            # Start stats printer
            self.stats_printer_greenlet = gevent.spawn(stats_printer(self.environment.stats))
            
            # Start load test
            self.runner.start_shape()
            
            # Setup auto-stop
            def stopper():
                time.sleep(run_duration_seconds)
                self.logger.info(f"⏰ Duration ({run_duration_seconds}s) reached. Stopping experiment.")
                if self.runner:
                    self.runner.quit()
            
            self.stop_greenlet = gevent.spawn(stopper)
            
            # Wait for completion
            self.runner.greenlet.join()
            
            self.logger.info("✅ Edge computing experiment completed successfully!")
            
            if self.request_logging_enabled:
                self.logger.info(f"📊 Request log saved to: {self.request_log_file}")
            
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
        """
        Enable request logging to CSV file for later visualization.
        
        Args:
            output_file: Path to CSV file where requests will be logged
        """
        try:
            self.request_log_file = Path(output_file)
            self.request_log_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Create CSV file with headers
            with open(self.request_log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp',
                    'simulated_time_seconds', 
                    'app_name',
                    'app_port',
                    'edge_site',
                    'endpoint',
                    'request_type',  # 'normal' or 'burst'
                    'response_time_ms',
                    'status_code',
                    'success'
                ])
            
            self.request_logging_enabled = True
            self.logger.info(f"✅ Request logging enabled: {self.request_log_file}")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to enable request logging: {e}")
            self.request_logging_enabled = False
    
    def _log_request(self, app_name: str, app_port: int, edge_site: str, endpoint: str, 
                    request_type: str, response_time_ms: float, status_code: int, 
                    success: bool, simulated_time: float):
        """Log a request to the CSV file."""
        if not self.request_logging_enabled or not self.request_log_file:
            return
            
        try:
            with open(self.request_log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(),
                    round(simulated_time, 2),
                    app_name,
                    app_port,
                    edge_site,
                    endpoint,
                    request_type,
                    round(response_time_ms, 2),
                    status_code,
                    success
                ])
        except Exception as e:
            self.logger.warning(f"Failed to log request: {e}")

    def get_request_log_file(self) -> Optional[Path]:
        """Get the path to the request log file."""
        return self.request_log_file if self.request_logging_enabled else None 