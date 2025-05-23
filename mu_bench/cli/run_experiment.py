import os
import argparse
import json
import sys
import logging

# Import the new RequestGenerator class
try:
    from ..request_generator import RequestGenerator, ConfigLoader
except ImportError:
    # Fallback if the above relative import fails
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from request_generator import RequestGenerator, ConfigLoader


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
    parser.add_argument("--log-level", default="INFO", help="Logging level (DEBUG, INFO, WARNING, ERROR)")
    args = parser.parse_args()

    config_folder_path = args.config_folder

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger("ExperimentCLI")

    logger.info(f"Loading configurations from: {config_folder_path}")

    # Load configurations using the new ConfigLoader
    app_definitions_path = os.path.join(config_folder_path, "app_definitions.json")
    runtime_params_path = os.path.join(config_folder_path, "locust_runtime_params.json")
    
    app_definitions = ConfigLoader.load_app_definitions(app_definitions_path)
    locust_runtime_params = ConfigLoader.load_runtime_params(runtime_params_path)

    if not app_definitions:
        logger.error("app_definitions.json is empty or could not be loaded.")
        sys.exit(1)
    
    if not locust_runtime_params:
        logger.error("locust_runtime_params.json is empty or could not be loaded.")
        sys.exit(1)

    target_host = locust_runtime_params.pop("target_host", None)
    if not target_host:
        logger.error("'target_host' not found in locust_runtime_params.json")
        sys.exit(1)

    logger.info("Starting Locust experiment...")
    logger.info(f"Target Host: {target_host}")
    logger.info(f"App Definitions: {len(app_definitions)} apps configured.")
    logger.info(f"Runtime Params: {locust_runtime_params}")

    try:
        # Initialize RequestGenerator
        generator = RequestGenerator(logger=logger)
        
        # Run the experiment
        success = generator.run_experiment(
            host_url=target_host,
            app_definitions=app_definitions,
            max_users=int(locust_runtime_params.get("max_total_users", 10)),
            spawn_rate=int(locust_runtime_params.get("spawn_rate", 2)),
            run_duration_seconds=float(locust_runtime_params.get("run_duration_seconds", 60)),
            simulated_period_seconds=float(locust_runtime_params.get("simulated_period_seconds", 86400)),
            log_level=args.log_level
        )
        
        if success:
            logger.info("Locust experiment finished successfully.")
            
            # Print final statistics
            stats = generator.get_stats()
            if stats:
                logger.info("Final Statistics:")
                logger.info(f"  Total Requests: {stats['total_requests']}")
                logger.info(f"  Total Failures: {stats['total_failures']}")
                logger.info(f"  Average Response Time: {stats['average_response_time']:.2f}ms")
                logger.info(f"  Requests per Second: {stats['requests_per_second']:.2f}")
                logger.info(f"  Failure Rate: {stats['failure_rate']:.2%}")
        else:
            logger.error("Experiment failed!")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Error running experiment: {e}")
        sys.exit(1) 