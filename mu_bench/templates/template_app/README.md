# Template App Structure

This directory serves as a template for scaffolding new MuBench app projects.

## Structure

- `workmodel.json` — Example workmodel file (copy or generate as needed)
- `generators/` — Place generator config files here
- `yamls/` — Will be populated after deployment (initially empty)

## Usage

To create a new app:
1. Copy this directory to your desired app location (e.g., `APPS/my_new_app/`).
2. Edit `workmodel.json` and generator configs as needed.
3. Use the deployment manager to generate yamls and deploy.

You can create multiple template_app variants for different scenarios (e.g., parallel, serial, etc.). 