import argparse
import sys
import os
from mu_bench.app_scaffolder import list_templates, scaffold_app, validate_app_structure

def main():
    parser = argparse.ArgumentParser(description="Scaffold a new MuBench app from a template.")
    parser.add_argument('--list', action='store_true', help='List available templates')
    parser.add_argument('--template', type=str, help='Template name to use')
    parser.add_argument('--name', type=str, help='Name for the new app')
    parser.add_argument('--apps-dir', type=str, default=None, help='Directory to create the new app in (default: APPS)')
    args = parser.parse_args()

    if args.list:
        print("Available templates:")
        for t in list_templates():
            print(f"  - {t}")
        sys.exit(0)

    if not args.template or not args.name:
        parser.print_help()
        sys.exit(1)

    apps_dir = args.apps_dir if args.apps_dir else None
    try:
        app_dir = scaffold_app(args.template, args.name, apps_dir=apps_dir) if apps_dir else scaffold_app(args.template, args.name)
        validate_app_structure(app_dir)
        print(f"App '{args.name}' created successfully at {app_dir}.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 