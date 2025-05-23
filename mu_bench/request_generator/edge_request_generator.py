"""
Simplified Edge Request Generator

A dramatically simplified approach for edge computing load testing that matches
real edge infrastructure patterns. Focuses on edge sites and port-based app differentiation.
"""
import time
import logging
import gevent
import random
import requests
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
                
                # Make request to s0-{edge-site-id} endpoint
                endpoint = f"/s0-{chosen_site}"
                request_name = f"{self.app_port}:{endpoint}"
                
                try:
                    with self.client.get(endpoint, name=request_name, catch_response=True) as response:
                        if response.status_code == 200:
                            response.success()
                        else:
                            response.failure(f"HTTP {response.status_code}")
                except Exception as e:
                    logger.warning(f"Request failed for {request_name}: {e}")
        
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
        log_level: str = "INFO"
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
            
        Returns:
            True if experiment completed successfully
        """
        try:
            # Setup logging
            setup_logging(log_level.upper(), None)
            
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
                shape_class=shape_instance
            )
            
            # Initialize shared simulated time
            self.environment.shared_simulated_time = shape_instance.current_simulated_time_seconds
            
            self.runner = self.environment.create_local_runner()
            
            # Start experiment
            self.logger.info("🚀 Starting edge computing experiment...")
            self.logger.info(f"📊 Config: {len(edge_config.get('apps', []))} apps, {len(edge_config.get('edge_sites', {}))} edge sites")
            self.logger.info(f"⚙️  Parameters: max_users={max_users}, spawn_rate={spawn_rate}, duration={run_duration_seconds}s")
            
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