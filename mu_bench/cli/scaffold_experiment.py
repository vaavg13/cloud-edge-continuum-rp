import os
import argparse
import shutil
import sys

# Define the root of the project or relevant base path if needed
# For simplicity, this script assumes it's run from a context where 'EXPERIMENTS' and 'mu_bench/templates' are accessible
# typically from the project root via ./mubench.sh scaffold-experiment <name>

# The path to the templates directory relative to this script or an absolute path
# Assuming this script is in mu_bench/cli/, templates are in mu_bench/templates/
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), '..', 'templates')
EXPERIMENTS_BASE_DIR = "EXPERIMENTS" # Assumes 'EXPERIMENTS' is at the project root

TEMPLATE_APP_DEFS_FILENAME = "template_app_definitions.json"
TEMPLATE_LOCUST_PARAMS_FILENAME = "template_locust_runtime_params.json"

TARGET_APP_DEFS_FILENAME = "app_definitions.json"
TARGET_LOCUST_PARAMS_FILENAME = "locust_runtime_params.json"

def scaffold_experiment(experiment_name):
    """Scaffolds a new experiment directory with template configuration files."""
    
    experiment_dir = os.path.join(EXPERIMENTS_BASE_DIR, experiment_name)

    if os.path.exists(experiment_dir):
        print(f"Error: Experiment directory '{experiment_dir}' already exists.")
        print("Please choose a different name or remove the existing directory.")
        sys.exit(1)

    try:
        os.makedirs(experiment_dir)
        print(f"Created experiment directory: {experiment_dir}")
    except OSError as e:
        print(f"Error creating directory {experiment_dir}: {e}")
        sys.exit(1)

    # Define source template paths
    template_app_defs_path = os.path.join(TEMPLATES_DIR, TEMPLATE_APP_DEFS_FILENAME)
    template_locust_params_path = os.path.join(TEMPLATES_DIR, TEMPLATE_LOCUST_PARAMS_FILENAME)

    # Define target file paths
    target_app_defs_path = os.path.join(experiment_dir, TARGET_APP_DEFS_FILENAME)
    target_locust_params_path = os.path.join(experiment_dir, TARGET_LOCUST_PARAMS_FILENAME)

    # Check if template files exist
    if not os.path.exists(template_app_defs_path):
        print(f"Error: Template file not found: {template_app_defs_path}")
        sys.exit(1)
    if not os.path.exists(template_locust_params_path):
        print(f"Error: Template file not found: {template_locust_params_path}")
        sys.exit(1)

    try:
        shutil.copyfile(template_app_defs_path, target_app_defs_path)
        print(f"Copied {TEMPLATE_APP_DEFS_FILENAME} to {target_app_defs_path}")
        shutil.copyfile(template_locust_params_path, target_locust_params_path)
        print(f"Copied {TEMPLATE_LOCUST_PARAMS_FILENAME} to {target_locust_params_path}")
    except IOError as e:
        print(f"Error copying template files: {e}")
        # Clean up created directory if copying fails
        shutil.rmtree(experiment_dir)
        print(f"Cleaned up partially created directory: {experiment_dir}")
        sys.exit(1)

    print(f"Successfully scaffolded experiment '{experiment_name}' in '{experiment_dir}'")
    print("You can now customize the app_definitions.json and locust_runtime_params.json files within this directory.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scaffold a new experiment directory with template configurations.")
    parser.add_argument("experiment_name", type=str, help="The name for the new experiment. A directory with this name will be created under EXPERIMENTS/")
    args = parser.parse_args()

    # Basic validation for experiment name (e.g., no slashes to prevent path traversal issues)
    if '/' in args.experiment_name or '\\' in args.experiment_name or '..' in args.experiment_name:
        print("Error: Experiment name cannot contain path separators (/, \\, ..).")
        sys.exit(1)
        
    scaffold_experiment(args.experiment_name) 