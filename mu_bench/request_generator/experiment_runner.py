import time
import os
import math
import random
import json
import gevent

from locust import LoadTestShape
from locust.env import Environment
from locust.stats import stats_printer
from locust.log import setup_logging
from .locustfile import configure_locust_users, USER_CLASSES

LOG_LEVEL = os.getenv("LOCUST_LOG_LEVEL", "INFO").upper()
setup_logging(LOG_LEVEL, None)

# --- Traffic Profile Loading ---
def load_traffic_profiles():
    """Loads seasonality and burst profile definitions from the local JSON data file."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    profiles_filepath = os.path.join(script_dir, "traffic_profiles.json")

    try:
        with open(profiles_filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Traffic profiles file not found at {profiles_filepath}")
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from {profiles_filepath}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred while loading {profiles_filepath}: {e}")
    return None

# --- Traffic Calculation Logic ---
def _calculate_single_seasonality_multiplier(
    profile_definition: dict, 
    current_simulated_time_seconds: float
) -> float:
    """Calculates a seasonal multiplier (0.0-1.0+) for a single profile definition."""
    pattern_type = profile_definition.get("pattern_type", "sinusoidal")
    baseline = float(profile_definition.get("baseline", 0.1))
    amplitude = float(profile_definition.get("amplitude", 0.9))
    peak_time_hour = float(profile_definition.get("peak_time_hour", 14))
    period_hours = float(profile_definition.get("period_hours", 24))

    if period_hours <= 0: return baseline # Avoid division by zero

    time_in_period_cycle = (current_simulated_time_seconds % (period_hours * 3600)) / (period_hours * 3600)
    peak_time_cycle = peak_time_hour / period_hours

    if pattern_type == "sinusoidal":
        phase_shift = peak_time_cycle - 0.25
        raw_sin_value = math.sin(2 * math.pi * (time_in_period_cycle - phase_shift))
        scaled_sin_value = (raw_sin_value + 1) / 2
        return max(0, baseline + amplitude * scaled_sin_value)
    
    elif pattern_type == "constant":
        return max(0, float(profile_definition.get("load_factor", baseline)))
    
    else:
        print(f"Warning: Unknown seasonality pattern type: {pattern_type}. Defaulting to baseline.")
        return baseline

def _calculate_single_burst_multiplier(
    profile_definition: dict, 
) -> float:
    """Calculates a burst multiplier (typically >= 1.0) for a single profile definition."""
    probability = float(profile_definition.get("probability", 0.0))
    min_strength = float(profile_definition.get("min_strength", 1.0))
    max_strength = float(profile_definition.get("max_strength", 1.0))

    if random.random() < probability:
        return random.uniform(min_strength, max_strength)
    return 1.0

def calculate_site_specific_dynamic_factor(
    site_pattern_refs: dict, 
    all_profiles_data: dict, 
    current_simulated_time_seconds: float
) -> float:
    """Calculates a dynamic factor for a single site based on its specific pattern refs."""
    if not all_profiles_data:
        print("Warning: all_profiles_data is empty in calculate_site_specific_dynamic_factor. Returning 1.0")
        return 1.0
    if not site_pattern_refs:
        return 1.0 # No patterns defined for this site, so it has a neutral dynamic factor.

    seasonal_refs = site_pattern_refs.get("seasonality_refs", [])
    burst_refs = site_pattern_refs.get("burst_refs", [])

    total_seasonal_multiplier = 0
    count_seasonal_profiles = 0
    if seasonal_refs:
        for ref in seasonal_refs:
            profile_def = all_profiles_data.get("seasonality_profiles", {}).get(ref)
            if profile_def:
                total_seasonal_multiplier += _calculate_single_seasonality_multiplier(profile_def, current_simulated_time_seconds)
                count_seasonal_profiles += 1
            else:
                print(f"Warning: Seasonality profile '{ref}' not found.")
    
    # If seasonal_refs is empty or none found, default_seasonal_factor is 1.0 (neutral)
    combined_seasonal_factor = (total_seasonal_multiplier / count_seasonal_profiles) if count_seasonal_profiles > 0 else 1.0

    max_burst_factor = 1.0
    if burst_refs:
        for ref in burst_refs:
            profile_def = all_profiles_data.get("burst_profiles", {}).get(ref)
            if profile_def:
                max_burst_factor = max(max_burst_factor, _calculate_single_burst_multiplier(profile_def))
            else:
                print(f"Warning: Burst profile '{ref}' not found.")
        
    final_factor = combined_seasonal_factor * max_burst_factor
    return max(0, final_factor)

def get_simple_global_trend(current_simulated_time_seconds: float) -> float:
    """A very simple global trend for total user count, e.g., slight daily curve."""
    return 0.7 + 0.3 * math.sin(2 * math.pi * (current_simulated_time_seconds / 86400 - 0.25))

class GlobalUserCountShape(LoadTestShape):
    min_users = 1
    max_total_users_config = 10 
    spawn_rate_config = 2      
    time_scale_factor = 1
    current_simulated_time_seconds = 0
    start_real_time = None

    def reset_time(self):
        self.current_simulated_time_seconds = 0
        self.start_real_time = time.time()
        if self.runner and hasattr(self.runner, 'environment'):
            self.runner.environment.shared_simulated_time = self.current_simulated_time_seconds
        print(f"GlobalUserCountShape: Simulated time reset to {self.current_simulated_time_seconds:.2f}s.")

    def tick(self):
        if self.start_real_time is None:
            self.reset_time()

        elapsed_real_time = time.time() - self.start_real_time
        self.current_simulated_time_seconds = (elapsed_real_time * self.time_scale_factor) % 86400 # Loop 24h cycle
        
        if self.runner and hasattr(self.runner, 'environment'):
            self.runner.environment.shared_simulated_time = self.current_simulated_time_seconds

        global_trend_multiplier = get_simple_global_trend(self.current_simulated_time_seconds)
        user_count = self.min_users + (self.max_total_users_config - self.min_users) * global_trend_multiplier
        user_count = int(round(max(self.min_users, min(user_count, self.max_total_users_config))))
        
        return (user_count, self.spawn_rate_config)

# --- Core Library Function to Run Locust Test ---
def setup_and_run_locust_test(
    host_url: str,
    locust_runtime_params: dict,
    app_definitions: list,
):
    """
    Sets up and runs a Locust test programmatically using dynamic configurations.

    Args:
        host_url (str): Base URL of the target system.
        locust_runtime_params (dict): Contains 'max_total_users', 'spawn_rate', 'run_duration_seconds', 'simulated_period_seconds'.
        app_definitions (list): Configuration for apps, their user weights, and target sites with base scales.
        traffic_profiles_filepath (str): Path to the JSON file defining traffic profiles.
    """
    all_traffic_profiles = load_traffic_profiles()
    if not all_traffic_profiles:
        print("Failed to load traffic profiles. Aborting Locust test.")
        return

    configure_locust_users(
        app_definitions=app_definitions,
        all_profiles_data=all_traffic_profiles,
        site_specific_dynamic_factor_calculator_func=calculate_site_specific_dynamic_factor
    )

    if not USER_CLASSES:
        print("No user classes were configured by locustfile.py. Aborting test.")
        return

    # Configure the GlobalUserCountShape
    GlobalUserCountShape.max_total_users_config = int(locust_runtime_params.get("max_total_users", 10))
    GlobalUserCountShape.spawn_rate_config = int(locust_runtime_params.get("spawn_rate", 2))
    run_duration_sec = float(locust_runtime_params.get("run_duration_seconds", 60))
    sim_period_sec = float(locust_runtime_params.get("simulated_period_seconds", 86400))
    
    if run_duration_sec > 0:
        GlobalUserCountShape.time_scale_factor = sim_period_sec / run_duration_sec
    else:
        GlobalUserCountShape.time_scale_factor = 1 # Avoid division by zero

    print(f"GlobalUserCountShape configured: max_users={GlobalUserCountShape.max_total_users_config}, "
          f"spawn_rate={GlobalUserCountShape.spawn_rate_config}, "
          f"time_scale_factor={GlobalUserCountShape.time_scale_factor:.2f} "
          f"(simulating {sim_period_sec/3600:.1f}h in {run_duration_sec}s)")

    shape_instance = GlobalUserCountShape()
    env = Environment(user_classes=USER_CLASSES, host=host_url, shape_class=shape_instance)
    
    # Initialize shared_simulated_time on the environment
    if not hasattr(env, 'shared_simulated_time'):
        env.shared_simulated_time = shape_instance.current_simulated_time_seconds 
        # reset_time() called by start_shape() will also set this.

    runner = env.create_local_runner()
    stats_printer_greenlet = gevent.spawn(stats_printer(env.stats))

    print(f"Starting Locust test on {host_url} with GlobalUserCountShape for {run_duration_sec}s.")
    print(f"User classes to be used: {[cls.__name__ for cls in USER_CLASSES]}")

    runner.start_shape() # This should call shape_instance.reset_time()

    # Stopper greenlet
    main_greenlet = gevent.getcurrent()
    def stopper():
        time.sleep(run_duration_sec)
        print(f"Run duration ({run_duration_sec}s) reached. Stopping test.")
        if runner: runner.quit()
        # main_greenlet.kill(exception=gevent.GreenletExit) # Force stop if runner.quit() is not enough
    stop_gevent = gevent.spawn(stopper)
    
    try:
        runner.greenlet.join() # Wait for the runner to complete (e.g., after quit() is called)
    except gevent.GreenletExit:
        print("Main greenlet for runner exited.")
    finally:
        if not stop_gevent.dead:
            stop_gevent.kill(block=False)
        if not stats_printer_greenlet.dead:
            stats_printer_greenlet.kill(block=False)
    
    print("Locust test run finished.")
