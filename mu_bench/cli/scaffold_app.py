import argparse
import sys
import os
from mu_bench.app_scaffolder import scaffold_app, validate_app_structure, list_example_workmodels, copy_example_workmodel
from mu_bench.utils.pretty_print import print_status, print_error, print_info

def main():
    parser = argparse.ArgumentParser(description="Scaffold a new MuBench app from the default template.")
    subparsers = parser.add_subparsers(dest='command', required=True)

    # Create subcommand
    create_parser = subparsers.add_parser('create', help='Create a new app from the template')
    create_parser.add_argument('-n', '--name', type=str, required=True, help='Name for the new app')
    create_parser.add_argument('--apps-dir', type=str, default=None, help='Directory to create the new app in (default: APPS)')
    create_parser.add_argument('-e', '--example', type=str, help='Name of example workmodel JSON to use (from list)')

    # List subcommand
    list_parser = subparsers.add_parser('list', help='List available example workmodels')

    args = parser.parse_args()

    if args.command == 'list':
        print_info("Available example workmodels:")
        for f in list_example_workmodels():
            print(f"  - {f}")
        sys.exit(0)

    elif args.command == 'create':
        TEMPLATE_NAME = 'template_app'
        apps_dir = args.apps_dir if args.apps_dir else None
        try:
            app_dir = scaffold_app(TEMPLATE_NAME, args.name, apps_dir=apps_dir) if apps_dir else scaffold_app(TEMPLATE_NAME, args.name)
            if args.example:
                copy_example_workmodel(args.example, app_dir)
            validate_app_structure(app_dir)
            print_status(f"App '{args.name}' created successfully at {app_dir}.")
        except Exception as e:
            print_error(f"Error: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main() 