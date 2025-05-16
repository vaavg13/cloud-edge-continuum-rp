import os

# Assuming experiment_runner.py is in the same directory or accessible in PYTHONPATH
from experiment_runner import setup_and_run_locust_test

# --- Configuration for the Actual Locust Experiment ---

# 1. Define Application and Target Site Configurations
# Each site for each app can have its own scaling and pattern references.
APP_DEFINITIONS = [
    {
        "name": "app-edge",
        "user_weight": 2, # This app will have roughly 2/3 of total users if another app has weight 1
        "port": 31115, # Optional: if this app runs on a specific port different from TARGET_HOST
        "targets": [
            {
                "path": "/s0-edge-site-1", 
                "site_base_scale": 1.2, 
                "site_random_factor_range": (0.8, 1.2),
                "pattern_config_refs": { 
                    "seasonality_refs": ["office_hours_peak"], # Defined in traffic_profiles.json
                    "burst_refs": ["moderate_occasional_spikes"]
                }
            },
            {
                "path": "/s0-edge-site-2", 
                "site_base_scale": 0.3, 
                "site_random_factor_range": (0.9, 1.1),
                "pattern_config_refs": { 
                    "seasonality_refs": ["evening_low_steady", "night_minimal"], 
                    "burst_refs": ["minor_frequent_glitches"]
                }
            }
        ]
    }
]

# 2. Define Locust Runtime Parameters
LOCUST_RUNTIME_PARAMS = {
    "max_total_users": 30,       # Max users controlled by the GlobalUserCountShape
    "spawn_rate": 4,             # Spawn rate for the GlobalUserCountShape
    "run_duration_seconds": 60*60, # Actual wall-clock time the test will run (e.g., 3 minutes)
    "simulated_period_seconds": 24 * 3600 # Traffic patterns will cycle through a simulated 24-hour period
}


TARGET_HOST = "http://172.23.0.5:31115" # Replace with your actual target service endpoint


if __name__ == "__main__":
    print("Starting Locust experiment...")
    print(f"Target Host: {TARGET_HOST}")
    print(f"App Definitions: {len(APP_DEFINITIONS)} apps configured.")
    print(f"Runtime Params: {LOCUST_RUNTIME_PARAMS}")

    # Ensure the script can find experiment_runner.py and traffic_profiles.json
    # If experiment_runner is not in PYTHONPATH or current dir, this might fail.
    # For simplicity, assuming they are co-located or experiment_runner is installed as a package.

    setup_and_run_locust_test(
        host_url=TARGET_HOST,
        locust_runtime_params=LOCUST_RUNTIME_PARAMS,
        app_definitions=APP_DEFINITIONS,
    )

    print("Locust experiment finished.") 