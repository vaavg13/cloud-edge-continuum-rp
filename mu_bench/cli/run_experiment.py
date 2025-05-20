import os
import argparse
import json
import sys

# Assuming experiment_runner.py is in the parent's request_generator directory
# Adjust path to import experiment_runner
# This assumes that the 'mu_bench' directory is in the Python path or that this script is run in a way that resolves this relative import.
try:
    from ..request_generator.experiment_runner import setup_and_run_locust_test
except ImportError:
    # Fallback if the above relative import fails (e.g. when script is run directly and 'cli' is not a package)
    # This requires 'mu_bench' to be in PYTHONPATH or for the script to be run from the 'mu_bench' directory's parent
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from request_generator.experiment_runner import setup_and_run_locust_test


def load_json_config(folder_path, filename):
    """Loads a JSON configuration file from the specified folder."""
    file_path = os.path.join(folder_path, filename)
    if not os.path.exists(file_path):
        print(f"Error: Configuration file not found: {file_path}")
        sys.exit(1)
    with open(file_path, 'r') as f:
        return json.load(f)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Locust experiment with configurations from JSON files.")
    parser.add_argument("config_folder", type=str, help="Path to the folder containing app_definitions.json and locust_runtime_params.json")
    args = parser.parse_args()

    config_folder_path = args.config_folder

    print(f"Loading configurations from: {config_folder_path}")

    app_definitions = load_json_config(config_folder_path, "app_definitions.json")
    locust_runtime_params = load_json_config(config_folder_path, "locust_runtime_params.json")

    if not app_definitions:
        print("Error: app_definitions.json is empty or could not be loaded.")
        sys.exit(1)
    
    if not locust_runtime_params:
        print("Error: locust_runtime_params.json is empty or could not be loaded.")
        sys.exit(1)

    target_host = locust_runtime_params.pop("target_host", None) # Remove target_host so it's not passed as a locust param
    if not target_host:
        print("Error: 'target_host' not found in locust_runtime_params.json")
        sys.exit(1)


    print("Starting Locust experiment...")
    print(f"Target Host: {target_host}")
    print(f"App Definitions: {len(app_definitions)} apps configured.")
    print(f"Runtime Params: {locust_runtime_params}")


    setup_and_run_locust_test(
        host_url=target_host,
        locust_runtime_params=locust_runtime_params,
        app_definitions=app_definitions,
    )

    print("Locust experiment finished.") 