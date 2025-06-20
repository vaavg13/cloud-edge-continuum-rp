import time
import logging
import gevent
import random
import requests
from typing import Dict, Any

from locust import HttpUser, task, between
from locust.env import Environment

from .edge_calculator import EdgeTrafficCalculator
from .load_shape import GlobalUserCountShape
from locust.stats import stats_printer

class EdgeRequestGenerator:
    """
    Request generator specifically designed for edge computing scenarios.
    """
    
    def __init__(self):
        """
        Initialize the EdgeRequestGenerator.
        
        Args:
            logger: Optional logger instance. If None, creates a default logger.
        """
        self.edge_calculator = EdgeTrafficCalculator()
        self.environment = None
        self.runner = None
        self.stop_greenlet = None
        self.user_classes = []
     
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
            print("⚠️ No apps or edge sites defined")
            return
        
        # Create one user class per app (port)
        for app_config in apps:
            app_name = app_config.get("name", "unknown")
            app_port = app_config.get("port")
            app_weight = app_config.get("traffic_weight", 1.0)
            wait_time_config = app_config.get("wait_time", {"min": 0.5, "max": 2.0})
            
            if not app_port:
                print(f"⚠️ Skipping app '{app_name}' - no port specified")
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
    
    def _create_edge_user_class(
        self,
        class_name: str,
        app_name: str, 
        app_port: int,
        base_host: str,
        edge_sites: Dict[str, Any],
        app_weight: float,
        wait_time: float
    ):
        """Create a dynamic user class for edge computing scenarios."""
        
        # Capture variables for the class
        edge_calculator = self.edge_calculator
        captured_wait_time = wait_time
        
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
                
                start_time = time.time()
                try:
                    with self.client.get(endpoint, name=request_name, catch_response=True) as response:
                        response_time_ms = (time.time() - start_time) * 1000
                        success = response.status_code == 200
                        
                        if success:
                            response.success()
                        else:
                            response.failure(f"HTTP {response.status_code}")
                            
                except Exception as e:
                    print(f"Request failed for {request_name}: {e}")
        
        # Set class name for debugging
        EdgeUser.__name__ = class_name
        EdgeUser.__qualname__ = class_name
        
        return EdgeUser
    
    def _test_connectivity(self, edge_config: Dict[str, Any]) -> bool:
        """Test connectivity to all edge endpoints."""
        base_host = edge_config.get("base_host", "localhost")
        apps = edge_config.get("apps", [])
        edge_sites = edge_config.get("edge_sites", {})
        
        tested_count = 0
        failed_endpoints = []
        
        for app_config in apps:
            app_port = app_config.get("port")
            if not app_port:
                continue
                
            for site_id in edge_sites.keys():
                endpoint = f"http://{base_host}:{app_port}/s0-{site_id}"
                try:
                    response = requests.get(endpoint, timeout=5)
                    if response.status_code not in [200, 404]:  # 404 is OK for non-existent endpoints
                        failed_endpoints.append(f"{endpoint} (HTTP {response.status_code})")
                    tested_count += 1
                except requests.exceptions.RequestException as e:
                    failed_endpoints.append(f"{endpoint} ({str(e)})")
                    tested_count += 1
        
        if failed_endpoints:
            print(f"❌ Failed endpoints: {', '.join(failed_endpoints)}")
            return False
        
        print(f"✅ Tested {tested_count} endpoints")
        return True

    def run_edge_experiment(
        self,
        edge_config: Dict[str, Any],
        max_users: int = 20,
        spawn_rate: int = 5,
        run_duration_seconds: float = 300,
        simulated_period_seconds: float = 86400
    ) -> bool:
        """
        Run a complete edge computing experiment.
        
        Args:
            edge_config: Simplified edge configuration
            max_users: Maximum concurrent users
            spawn_rate: User spawn rate
            run_duration_seconds: Experiment duration
            simulated_period_seconds: Simulated time period (for time scaling)
            
        Returns:
            True if experiment completed successfully
        """
        try:
            print("🚀 Starting edge computing experiment")
            print(f"Configuration: {max_users} max users, {spawn_rate} spawn rate, {run_duration_seconds}s duration")
            
            # Test connectivity first
            if not self._test_connectivity(edge_config):
                return False
            
            # Generate user classes
            self._generate_edge_user_classes(edge_config)
            
            if not self.user_classes:
                print("❌ No user classes generated")
                return False
            
            print(f"✅ Generated {len(self.user_classes)} user classes")
            
            # Configure load shape
            time_scale_factor = simulated_period_seconds / run_duration_seconds
            GlobalUserCountShape.configure(
                max_users=max_users,
                spawn_rate=spawn_rate, 
                time_scale_factor=time_scale_factor
            )
            
            print(f"⏰ Time scale factor: {time_scale_factor:.2f} (simulating {simulated_period_seconds}s in {run_duration_seconds}s)")
            
            # Create Locust environment
            shape_instance = GlobalUserCountShape()
            
            self.environment = Environment(
                user_classes=self.user_classes,
                shape_class=shape_instance
            )
            
            # Initialize shared simulated time
            self.environment.shared_simulated_time = GlobalUserCountShape.current_simulated_time_seconds
            
            # Create runner
            self.runner = self.environment.create_local_runner()
            
            # Start the test and let Locust handle its own output
            self.runner.start_shape()
            print("🏃 Test started")
            
            # Setup stopper
            def stopper():
                gevent.sleep(run_duration_seconds)
                print("⏹️ Stopping test due to timeout")
                self.runner.stop()
            
            self.stop_greenlet = gevent.spawn(stopper)
            
            # Wait for completion
            self.runner.greenlet.join()
            
            print("✅ Edge experiment completed successfully")
            return True
            
        except Exception as e:
            print(f"💥 Edge experiment failed: {e}")
            return False
        finally:
            self._cleanup()
    
    def _cleanup(self):
        """Clean up resources."""
        if self.stop_greenlet and not self.stop_greenlet.dead:
            self.stop_greenlet.kill(block=False)