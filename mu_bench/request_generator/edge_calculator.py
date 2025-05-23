import random
import math
from typing import Dict, Any

from .edge_profiles import get_edge_patterns, get_pattern


class EdgeTrafficCalculator:
    
    def __init__(self):
        """Initialize with edge patterns."""
        self.edge_patterns = get_edge_patterns()
    
    def calculate_site_traffic_multiplier(
        self, 
        pattern_name: str, 
        current_time_seconds: float
    ) -> float:
        """
        Calculate traffic multiplier for an edge site based on time of day.
        
        Args:
            pattern_name: Name of the edge pattern (e.g., "urban_peak", "rural_minimal")
            current_time_seconds: Current simulated time in seconds
            
        Returns:
            Traffic multiplier for this site at this time
        """
        pattern = get_pattern(pattern_name)
        if not pattern:
            return 1.0
        
        # Get current hour (0-23)
        current_hour = int((current_time_seconds % 86400) / 3600)
        
        # Determine base multiplier based on time of day
        if current_hour in pattern["peak_hours"]:
            base_multiplier = pattern["peak_multiplier"]
        elif 22 <= current_hour or current_hour <= 6:  # Night time (10pm - 6am)
            base_multiplier = pattern["night_multiplier"]
        else:
            base_multiplier = pattern["off_peak_multiplier"]
        
        # Apply base traffic weight for this site type
        weighted_multiplier = base_multiplier * pattern["base_traffic_weight"]
        
        # Add random bursts based on site characteristics
        if random.random() < pattern["burst_probability"]:
            burst_min, burst_max = pattern["burst_strength"]
            burst_multiplier = random.uniform(burst_min, burst_max)
            weighted_multiplier *= burst_multiplier
        
        return max(0.01, weighted_multiplier)  # Ensure positive value
    
    def get_site_base_weight(self, pattern_name: str) -> float:
        """Get the base traffic weight for a site pattern."""
        pattern = get_pattern(pattern_name)
        return pattern["base_traffic_weight"] if pattern else 1.0 