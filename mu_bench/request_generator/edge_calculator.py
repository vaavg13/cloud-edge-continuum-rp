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
        
        # Enhanced burst generation with more realistic patterns
        burst_probability = pattern["burst_probability"]
        
        # Increase burst probability during peak hours
        if current_hour in pattern["peak_hours"]:
            burst_probability *= 1.5
        elif 22 <= current_hour or current_hour <= 6:
            burst_probability *= 0.3  # Fewer bursts at night
        
        # Add temporal clustering - bursts are more likely after recent bursts
        time_seed = int(current_time_seconds / 300)  # 5-minute windows
        random.seed(time_seed + hash(pattern_name))
        
        # Multiple burst opportunities with different intensities
        final_multiplier = weighted_multiplier
        
        # Primary burst check
        if random.random() < burst_probability:
            burst_min, burst_max = pattern["burst_strength"]
            
            # Use exponential distribution for more realistic burst volumes
            # Most bursts are small, few are very large
            lambda_param = 2.0  # Controls distribution shape
            exp_sample = random.expovariate(lambda_param)
            burst_intensity = min(exp_sample, 3.0)  # Cap at 3x
            
            # Map exponential sample to burst range
            normalized_intensity = burst_intensity / 3.0
            burst_multiplier = burst_min + normalized_intensity * (burst_max - burst_min)
            
            final_multiplier *= burst_multiplier
        
        # Secondary micro-burst check (smaller, more frequent)
        if random.random() < burst_probability * 0.8:
            micro_burst = random.uniform(1.05, 1.3)
            final_multiplier *= micro_burst
        
        # Add small random variations to prevent identical patterns
        noise_factor = random.uniform(0.95, 1.05)
        final_multiplier *= noise_factor
        
        # Reset random seed to avoid affecting other random operations
        random.seed()
        
        return max(0.01, final_multiplier)  # Ensure positive value
    
    def get_site_base_weight(self, pattern_name: str) -> float:
        """Get the base traffic weight for a site pattern."""
        pattern = get_pattern(pattern_name)
        return pattern["base_traffic_weight"] if pattern else 1.0 