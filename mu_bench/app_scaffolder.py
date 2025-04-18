import os
import shutil

DEFAULT_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), 'templates')
DEFAULT_APPS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'APPS')

def list_templates(templates_dir=DEFAULT_TEMPLATES_DIR):
    """List available template app directories."""
    return [
        d for d in os.listdir(templates_dir)
        if os.path.isdir(os.path.join(templates_dir, d))
    ]

def scaffold_app(template_name, app_name, apps_dir=DEFAULT_APPS_DIR, templates_dir=DEFAULT_TEMPLATES_DIR):
    """Copy the template app directory to a new app directory under apps_dir with the given app_name."""
    src = os.path.join(templates_dir, template_name)
    dst = os.path.join(apps_dir, app_name)
    if not os.path.exists(src):
        raise FileNotFoundError(f"Template '{template_name}' not found in {templates_dir}")
    if os.path.exists(dst):
        raise FileExistsError(f"App directory '{dst}' already exists.")
    shutil.copytree(src, dst)
    print(f"Scaffolded new app at {dst}")
    return dst

def validate_app_structure(app_dir):
    """Check that the app directory has the expected structure."""
    required = ["workmodel.json", "generators", "yamls"]
    missing = [item for item in required if not os.path.exists(os.path.join(app_dir, item))]
    if missing:
        raise RuntimeError(f"Missing required items in app directory: {missing}")
    return True 