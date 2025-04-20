import os
import shutil
import json

DEFAULT_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), 'templates')
DEFAULT_APPS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'APPS')

def list_templates(templates_dir=DEFAULT_TEMPLATES_DIR):
    """List available template app directories."""
    return [
        d for d in os.listdir(templates_dir)
        if os.path.isdir(os.path.join(templates_dir, d))
    ]

def scaffold_app(template_name, app_name, apps_dir=DEFAULT_APPS_DIR, templates_dir=DEFAULT_TEMPLATES_DIR):
    """Copy the template app directory to a new app directory under apps_dir with the given app_name. Also patch k8parameters.json with app-sensitive fields."""
    src = os.path.join(templates_dir, template_name)
    dst = os.path.join(apps_dir, app_name)
    if not os.path.exists(src):
        raise FileNotFoundError(f"Template '{template_name}' not found in {templates_dir}")
    if os.path.exists(dst):
        raise FileExistsError(f"App directory '{dst}' already exists.")
    shutil.copytree(src, dst)
    # Patch k8parameters.json if it exists
    k8params_path = os.path.join(dst, 'k8parameters.json')
    if os.path.exists(k8params_path):
        with open(k8params_path, 'r') as f:
            k8params = json.load(f)
        # Patch app-sensitive fields
        k8params['output_dir'] = f"APPS/{app_name}"
        k8params['namespace'] = app_name  # Set namespace to app_name
        with open(k8params_path, 'w') as f:
            json.dump(k8params, f, indent=2)
    return dst

def validate_app_structure(app_dir):
    """Check that the app directory has the expected structure."""
    required = ["workmodel.json", "generators", "yamls"]
    missing = [item for item in required if not os.path.exists(os.path.join(app_dir, item))]
    if missing:
        raise RuntimeError(f"Missing required items in app directory: {missing}")
    return True

def list_example_workmodels(example_dir=None):
    """List all JSON workmodel files in the example_workloads directory."""
    if example_dir is None:
        example_dir = os.path.join(DEFAULT_TEMPLATES_DIR, 'example_workloads')
    return [f for f in os.listdir(example_dir) if f.endswith('.json') and os.path.isfile(os.path.join(example_dir, f))]

def copy_example_workmodel(example_name, target_dir, example_dir=None):
    """Copy the selected example workmodel to the target directory as workmodel.json."""
    if example_dir is None:
        example_dir = os.path.join(DEFAULT_TEMPLATES_DIR, 'example_workloads')
    src = os.path.join(example_dir, example_name)
    dst = os.path.join(target_dir, 'workmodel.json')
    if not os.path.exists(src):
        raise FileNotFoundError(f"Example workmodel '{example_name}' not found in {example_dir}")
    shutil.copyfile(src, dst)