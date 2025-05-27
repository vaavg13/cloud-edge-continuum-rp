"""
Edge Computing Traffic Profiles - Simplified and Realistic

This module provides traffic patterns specifically designed for edge computing scenarios,
focusing on different types of edge sites (urban, suburban, rural, industrial, etc.)
with realistic traffic characteristics.
"""

# Simplified edge site traffic patterns
EDGE_SITE_PATTERNS = {
    "urban_peak": {
        "description": "High-density urban area with business hour peaks",
        "base_traffic_weight": 1.0,
        "peak_hours": [9, 10, 11, 14, 15, 16, 17],
        "peak_multiplier": 2.5,
        "off_peak_multiplier": 0.3,
        "night_multiplier": 0.1,
        "burst_probability": 0.18,  # Higher burst probability for urban
        "burst_strength": [1.2, 4.5]  # Wider range for more variation
    },
    "suburban_steady": {
        "description": "Suburban area with moderate, steady traffic",
        "base_traffic_weight": 0.6,
        "peak_hours": [8, 9, 17, 18, 19, 20],
        "peak_multiplier": 1.8,
        "off_peak_multiplier": 0.5,
        "night_multiplier": 0.2,
        "burst_probability": 0.12,  # Moderate burst probability
        "burst_strength": [1.1, 2.8]  # More realistic range
    },
    "rural_minimal": {
        "description": "Rural area with low, consistent traffic",
        "base_traffic_weight": 0.3,
        "peak_hours": [12, 18],  # Lunch and evening
        "peak_multiplier": 1.4,
        "off_peak_multiplier": 0.7,
        "night_multiplier": 0.4,
        "burst_probability": 0.04,  # Low but not too low
        "burst_strength": [1.05, 1.8]  # Smaller but varied bursts
    },
    "industrial_shift": {
        "description": "Industrial area with shift-based patterns",
        "base_traffic_weight": 0.8,
        "peak_hours": [6, 7, 8, 14, 15, 22, 23],  # Shift changes
        "peak_multiplier": 2.0,
        "off_peak_multiplier": 0.4,
        "night_multiplier": 0.6,  # Night shift activity
        "burst_probability": 0.08,  # Moderate bursts during shifts
        "burst_strength": [1.1, 3.2]  # Variable industrial loads
    },
    "residential_evening": {
        "description": "Residential area with evening and weekend peaks",
        "base_traffic_weight": 0.5,
        "peak_hours": [18, 19, 20, 21],  # Evening hours
        "peak_multiplier": 2.2,
        "off_peak_multiplier": 0.3,
        "night_multiplier": 0.1,
        "burst_probability": 0.09,  # Evening streaming/gaming bursts
        "burst_strength": [1.15, 2.4]  # Home usage patterns
    },
    "commercial_business": {
        "description": "Commercial district with strict business hours",
        "base_traffic_weight": 0.9,
        "peak_hours": [9, 10, 11, 13, 14, 15, 16],
        "peak_multiplier": 3.0,
        "off_peak_multiplier": 0.2,
        "night_multiplier": 0.05,
        "burst_probability": 0.15,  # Business events cause bursts
        "burst_strength": [1.3, 3.8]  # Large business-driven spikes
    }
}

def get_edge_patterns():
    """Get all available edge site patterns."""
    return EDGE_SITE_PATTERNS

def get_pattern(pattern_name: str):
    """Get a specific edge site pattern."""
    return EDGE_SITE_PATTERNS.get(pattern_name)

def list_available_patterns():
    """List all available edge site pattern names and descriptions."""
    return {
        name: config["description"] 
        for name, config in EDGE_SITE_PATTERNS.items()
    } 