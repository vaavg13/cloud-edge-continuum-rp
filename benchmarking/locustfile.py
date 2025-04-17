from locust import LoadTestShape, events
from users import LightUser, MediumUser, HeavyUser
import random
import math
import time

# Simulate time of day (in seconds, 0 to 86400 for 24 hours)
current_time = 0

def get_traffic_multiplier():
    global current_time
    # Base daily pattern: sinusoidal with peak around midday
    base_pattern = 0.5 + 0.5 * math.sin(2 * math.pi * (current_time / 86400 - 0.25))
    
    # Random spikes: 10% chance of a spike, multiplier between 1.5 and 3
    spike = 1.0
    if random.random() < 0.1:
        spike = random.uniform(1.5, 3.0)
    
    # Time-based spikes: higher chance at 8 AM, 12 PM, 6 PM (in seconds)
    peak_times = [8*3600, 12*3600, 18*3600]
    for peak in peak_times:
        if abs(current_time - peak) < 1800:  # Within 30 minutes
            spike *= random.uniform(1.2, 2.0)
    
    current_time = (current_time + 60) % 86400  # Advance time by 1 minute
    return base_pattern * spike

class SeasonalLoadShape(LoadTestShape):
    def tick(self):
        # Calculate user count based on traffic multiplier
        base_users = 2  # Base number of users
        max_users = 10  # Maximum number of users
        multiplier = get_traffic_multiplier()
        user_count = int(base_users + (max_users - base_users) * multiplier)
        
        # Spawn rate: 10% of user count per second
        spawn_rate = max(1, user_count * 0.1)
        
        return (user_count, spawn_rate)

@events.test_start.add_listener
def on_test_start(**kwargs):
    global current_time
    current_time = 0  # Reset time at test start

@events.request.add_listener
def on_request(**kwargs):
    print(f"Traffic multiplier: {get_traffic_multiplier():.2f}")