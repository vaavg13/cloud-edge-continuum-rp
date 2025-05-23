"""
Load test shape definitions for Locust test execution.

This module provides the GlobalUserCountShape class that controls
how user load varies over time during experiments.
"""
import time
import math
from locust import LoadTestShape


class GlobalUserCountShape(LoadTestShape):
    """Controls the user count over time based on global trends and configuration."""
    
    min_users = 1
    max_total_users_config = 10 
    spawn_rate_config = 2      
    time_scale_factor = 1
    current_simulated_time_seconds = 0
    start_real_time = None

    def reset_time(self):
        """Reset the simulated time to start a new experiment cycle."""
        self.current_simulated_time_seconds = 0
        self.start_real_time = time.time()
        if self.runner and hasattr(self.runner, 'environment'):
            self.runner.environment.shared_simulated_time = self.current_simulated_time_seconds
        print(f"GlobalUserCountShape: Simulated time reset to {self.current_simulated_time_seconds:.2f}s.")

    def tick(self):
        """Called by Locust to determine current user count and spawn rate."""
        if self.start_real_time is None:
            self.reset_time()

        elapsed_real_time = time.time() - self.start_real_time
        self.current_simulated_time_seconds = (elapsed_real_time * self.time_scale_factor) % 86400  # Loop 24h cycle
        
        if self.runner and hasattr(self.runner, 'environment'):
            self.runner.environment.shared_simulated_time = self.current_simulated_time_seconds

        global_trend_multiplier = self._get_global_trend(self.current_simulated_time_seconds)
        user_count = self.min_users + (self.max_total_users_config - self.min_users) * global_trend_multiplier
        user_count = int(round(max(self.min_users, min(user_count, self.max_total_users_config))))
        
        return (user_count, self.spawn_rate_config)
    
    @staticmethod
    def _get_global_trend(current_simulated_time_seconds: float) -> float:
        """Simple global trend for total user count with daily curve."""
        return 0.7 + 0.3 * math.sin(2 * math.pi * (current_simulated_time_seconds / 86400 - 0.25))
    
    @classmethod
    def configure(cls, max_users: int, spawn_rate: int, time_scale_factor: float = 1.0):
        """Configure the shape parameters before starting the test."""
        cls.max_total_users_config = max_users
        cls.spawn_rate_config = spawn_rate
        cls.time_scale_factor = time_scale_factor 